"""
알림/푸시 관련 서비스 모듈
"""

import httpx
import os
import logging
import time
from datetime import date as date_type, datetime
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.config import settings
from backend.app.db.models import Subscriber, MarketDaily, NewsDaily, KoreaMetalDaily, NotificationLog

logger = logging.getLogger(__name__)


def send_telegram_message_sync(chat_id: str, text: str, max_retries: int = 3) -> bool:
    """
    텔레그램 메시지 동기 전송 (재시도 로직 포함)

    Args:
        chat_id: 텔레그램 chat ID
        text: 전송할 메시지
        max_retries: 최대 재시도 횟수 (기본값: 3)

    Returns:
        bool: 전송 성공 여부
    """
    # Telegram 메시지 길이 제한: 4096자
    MAX_MESSAGE_LENGTH = 4096
    if len(text) > MAX_MESSAGE_LENGTH:
        logger.warning(
            f"Message too long for {chat_id}: {len(text)} chars. Truncating to {MAX_MESSAGE_LENGTH}."
        )
        text = text[:MAX_MESSAGE_LENGTH - 50] + "\n\n... (메시지가 너무 길어 잘렸습니다)"
    if os.getenv("TELEGRAM_DRY_RUN") == "1":
        logger.info("TELEGRAM_DRY_RUN enabled: skip send to %s (len=%s)", chat_id, len(text))
        return False

    token = settings.TELEGRAM_TOKEN
    if not token:
        logger.error("TELEGRAM_TOKEN is not set")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for attempt in range(max_retries):
        try:
            response = httpx.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True
                },
                timeout=10.0
            )
            response.raise_for_status()

            if attempt > 0:
                logger.info(f"Message sent to {chat_id} (succeeded on attempt {attempt + 1})")
            else:
                logger.info(f"Message sent to {chat_id}")
            return True

        except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException, ConnectionResetError) as e:
            # 네트워크 관련 에러: 재시도 가능
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(
                    f"Network error sending to {chat_id} (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(
                    f"Failed to send message to {chat_id} after {max_retries} attempts: {e}"
                )
                return False

        except httpx.HTTPStatusError as e:
            # HTTP 에러 (400, 403, 404 등): 재시도해도 소용없음
            logger.error(
                f"HTTP error sending to {chat_id}: {e.response.status_code} - {e.response.text}"
            )
            return False

        except Exception as e:
            # 기타 예상치 못한 에러
            logger.error(f"Unexpected error sending to {chat_id}: {e}", exc_info=True)
            return False

    return False


def generate_morning_brief(db: Session, target_date: Optional[date_type] = None) -> str:
    """
    아침 브리핑 메시지 생성 (09:05 이후 - 전일대비 포함)
    """
    if target_date is None:
        # KST 기준 오늘 날짜 (타임존 안전)
        from datetime import timezone, timedelta
        kst = timezone(timedelta(hours=9))
        target_date = datetime.now(kst).date()
    
    # 시장 데이터 조회
    market: Optional[MarketDaily] = (
        db.query(MarketDaily)
        .filter(MarketDaily.date == target_date)
        .order_by(MarketDaily.id.desc())
        .first()
    )
    
    # 뉴스 Top5: 카테고리별 Top1 + 속보 1개 (중복 제거)
    from backend.app.utils.dedup import remove_duplicate_news
    news_list = []
    for category in ["society", "economy", "culture", "entertainment"]:
        top1 = (
            db.query(NewsDaily)
            .filter(NewsDaily.date == target_date, NewsDaily.category == category)
            .order_by(NewsDaily.hot_score.desc(), NewsDaily.created_at.desc())
            .first()
        )
        if top1:
            news_list.append(top1)

    breaking_top1 = (
        db.query(NewsDaily)
        .filter(NewsDaily.date == target_date, NewsDaily.is_breaking.is_(True))
        .order_by(NewsDaily.hot_score.desc(), NewsDaily.created_at.desc())
        .first()
    )
    if breaking_top1:
        news_list.append(breaking_top1)

    if news_list:
        news_list = remove_duplicate_news(news_list)


    # 전일 데이터 (전일대비 계산용)
    from datetime import timedelta
    yesterday = target_date - timedelta(days=1)
    market_yesterday: Optional[MarketDaily] = (
        db.query(MarketDaily)
        .filter(MarketDaily.date == yesterday)
        .order_by(MarketDaily.id.desc())
        .first()
    )
    
    lines = []
    lines.append(f"📊 오늘 아침 브리핑 ({target_date})")
    lines.append("")
    
    if market:
        # 환율 (네이버 API 기반 - exchange_rates JSON 우선)
        exchange_shown = False
        if market.exchange_rates and isinstance(market.exchange_rates, dict):
            # 주요 통화만 표시 (USD, EUR, JPY, CNY)
            main_currencies = [
                ("USD", "🇺🇸", "미국 달러", "$", 1),
                ("EUR", "🇪🇺", "유로", "€", 1),
                ("JPY", "🇯🇵", "일본 엔", "¥", 100),
                ("CNY", "🇨🇳", "중국 위안", "¥", 1),
            ]
            fx_lines = []
            for currency, flag, name, symbol, unit in main_currencies:
                rate_data = market.exchange_rates.get(currency, {})
                if rate_data and rate_data.get("rate"):
                    rate = rate_data["rate"]
                    change = rate_data.get("change")
                    change_pct = rate_data.get("change_pct")

                    unit_str = f"(100)" if unit != 1 else ""
                    line = f"{flag} {currency}{unit_str}: ₩{rate:,.2f}"

                    if change is not None and change_pct is not None:
                        emoji = "🔺" if change > 0 else "🔻" if change < 0 else "➖"
                        sign = "+" if change > 0 else ""
                        line += f" {emoji}{sign}{change_pct:.2f}%"

                    fx_lines.append(line)

            if fx_lines:
                lines.append("💱 환율 (네이버 기준)")
                lines.extend(fx_lines)
                lines.append("")
                exchange_shown = True

        # Fallback: 기존 usd_krw 컬럼
        if not exchange_shown and market.usd_krw:
            lines.append("💱 환율")
            lines.append(f"USD/KRW: {market.usd_krw:,.2f}원")

            # 전일대비
            if market.usd_krw_change is not None and market.usd_krw_change_pct is not None:
                if market.usd_krw_change > 0:
                    emoji = "🔺"
                    sign = "+"
                elif market.usd_krw_change < 0:
                    emoji = "🔻"
                    sign = ""
                else:
                    emoji = "➖"
                    sign = ""
                lines.append(f"{emoji} 전일대비 {sign}{market.usd_krw_change:.2f}원 ({sign}{market.usd_krw_change_pct:.2f}%)")

            lines.append("")

        # 비트코인
        lines.append("🪙 비트코인")
        if market.btc_krw:
            lines.append(f"BTC: {market.btc_krw:,.0f}원")
        if market.btc_usdt:
            lines.append(f"${market.btc_usdt:,.2f}")
        if market.btc_change_24h is not None:
            emoji = "🟢" if market.btc_change_24h > 0 else "🔴"
            lines.append(f"{emoji} {market.btc_change_24h:+.2f}%")
        lines.append("")
        
        # 주요 지수
        if market.kospi_index or market.kosdaq_index or market.nasdaq_index or market.sp500_index:
            lines.append("📊 주요 지수")

            if market.kospi_index:
                lines.append(f"KOSPI: {market.kospi_index:,.2f}")
                # 전일대비
                if market.kospi_index_change is not None and market.kospi_index_change_pct is not None:
                    emoji = "🔺" if market.kospi_index_change > 0 else "🔻" if market.kospi_index_change < 0 else "➖"
                    sign = "+" if market.kospi_index_change > 0 else ""
                    lines.append(f"   {emoji} {sign}{market.kospi_index_change:.2f} ({sign}{market.kospi_index_change_pct:.2f}%)")

            if market.kosdaq_index:
                lines.append(f"KOSDAQ: {market.kosdaq_index:,.2f}")
                # 전일대비
                if market.kosdaq_index_change is not None and market.kosdaq_index_change_pct is not None:
                    emoji = "🔺" if market.kosdaq_index_change > 0 else "🔻" if market.kosdaq_index_change < 0 else "➖"
                    sign = "+" if market.kosdaq_index_change > 0 else ""
                    lines.append(f"   {emoji} {sign}{market.kosdaq_index_change:.2f} ({sign}{market.kosdaq_index_change_pct:.2f}%)")

            if market.nasdaq_index:
                lines.append(f"나스닥100: {market.nasdaq_index:,.2f}")
                # 전일대비
                if market.nasdaq_index_change is not None and market.nasdaq_index_change_pct is not None:
                    emoji = "🔺" if market.nasdaq_index_change > 0 else "🔻" if market.nasdaq_index_change < 0 else "➖"
                    sign = "+" if market.nasdaq_index_change > 0 else ""
                    lines.append(f"   {emoji} {sign}{market.nasdaq_index_change:.2f} ({sign}{market.nasdaq_index_change_pct:.2f}%)")

            if market.sp500_index:
                lines.append(f"S&P500: {market.sp500_index:,.2f}")
                # 전일대비
                if market.sp500_index_change is not None and market.sp500_index_change_pct is not None:
                    emoji = "🔺" if market.sp500_index_change > 0 else "🔻" if market.sp500_index_change < 0 else "➖"
                    sign = "+" if market.sp500_index_change > 0 else ""
                    lines.append(f"   {emoji} {sign}{market.sp500_index_change:.2f} ({sign}{market.sp500_index_change_pct:.2f}%)")

            lines.append("")
        
        # KOSPI Top5
        if market.kospi_top5 and isinstance(market.kospi_top5, list):
            lines.append("📈 KOSPI Top5")
            for idx, stock in enumerate(market.kospi_top5[:5], 1):
                name = stock.get("name", "")
                price = stock.get("price", "")
                change_rate = stock.get("change_rate", "")

                if change_rate and "+" in str(change_rate):
                    emoji = "🟢"
                elif change_rate and "-" in str(change_rate):
                    emoji = "🔴"
                else:
                    emoji = "⚪"

                lines.append(f"{idx}. {name} {price} {emoji} {change_rate}")
            lines.append("")

        # KOSDAQ Top5
        if market.kosdaq_top5 and isinstance(market.kosdaq_top5, list):
            lines.append("📈 KOSDAQ Top5")
            for idx, stock in enumerate(market.kosdaq_top5[:5], 1):
                name = stock.get("name", "")
                price = stock.get("price", "")
                change_rate = stock.get("change_rate", "")

                if change_rate and "+" in str(change_rate):
                    emoji = "🟢"
                elif change_rate and "-" in str(change_rate):
                    emoji = "🔴"
                else:
                    emoji = "⚪"

                lines.append(f"{idx}. {name} {price} {emoji} {change_rate}")
            lines.append("")

        # 금속 시세 (확장 버전)
        if market.gold_usd and market.usd_krw:
            lines.append("🥇 금속 시세")

            korea_gold = (
                db.query(KoreaMetalDaily)
                .filter(KoreaMetalDaily.metal == "gold")
                .order_by(KoreaMetalDaily.date.desc(), KoreaMetalDaily.id.desc())
                .first()
            )
            korea_silver = (
                db.query(KoreaMetalDaily)
                .filter(KoreaMetalDaily.metal == "silver")
                .order_by(KoreaMetalDaily.date.desc(), KoreaMetalDaily.id.desc())
                .first()
            )
            korea_platinum = (
                db.query(KoreaMetalDaily)
                .filter(KoreaMetalDaily.metal == "platinum")
                .order_by(KoreaMetalDaily.date.desc(), KoreaMetalDaily.id.desc())
                .first()
            )

            def _format_korea_metal(name, emoji, usd_price, korea_row, usd_price_yesterday):
                if not usd_price or not korea_row or not korea_row.buy_3_75g:
                    return
                per_gram = usd_price / 31.1035
                per_don = per_gram * 3.75 * market.usd_krw
                lines.append(f"{emoji} {name} (1돈)")
                if korea_row.sell_3_75g:
                    lines.append(
                        f"   국내 살때 ₩{korea_row.buy_3_75g:,.0f} / 팔때 ₩{korea_row.sell_3_75g:,.0f}"
                    )
                else:
                    lines.append(f"   국내 살때 ₩{korea_row.buy_3_75g:,.0f}")
                premium_pct = (korea_row.buy_3_75g - per_don) / per_don * 100
                sign = "+" if premium_pct > 0 else ""
                lines.append(f"   프리미엄 {sign}{premium_pct:.2f}% (국내 살때 vs 국제)")
                # 전일대비 (2026-02-02 추가)
                if usd_price_yesterday:
                    change = usd_price - usd_price_yesterday
                    change_pct = (change / usd_price_yesterday) * 100
                    emoji_change = "🔺" if change > 0 else "🔻" if change < 0 else "➖"
                    sign_change = "+" if change > 0 else ""
                    lines.append(f"   전일대비 {emoji_change} {sign_change}${change:.2f} ({sign_change}{change_pct:.2f}%)")

            shown = False
            _format_korea_metal(
                "금", "💛", market.gold_usd, korea_gold,
                market_yesterday.gold_usd if market_yesterday else None
            )
            shown = shown or (korea_gold and korea_gold.buy_3_75g and market.gold_usd)
            if market.silver_usd:
                _format_korea_metal(
                    "은", "⚪", market.silver_usd, korea_silver,
                    market_yesterday.silver_usd if market_yesterday else None
                )
                shown = shown or (korea_silver and korea_silver.buy_3_75g and market.silver_usd)
            if market.platinum_usd:
                _format_korea_metal(
                    "백금", "⚪", market.platinum_usd, korea_platinum,
                    market_yesterday.platinum_usd if market_yesterday else None
                )
                shown = shown or (korea_platinum and korea_platinum.buy_3_75g and market.platinum_usd)

            if not shown:
                lines.append("국내 금/은/백금 시세 데이터가 없습니다.")

            lines.append("")
    
    # 뉴스
    if news_list:
        lines.append("📰 주요 뉴스")
        for idx, news in enumerate(news_list[:5], 1):
            lines.append(f"{idx}) {news.title}")
            if news.url:
                lines.append(f"🔗 {news.url}")
        lines.append("")
    
    if not market and not news_list:
        lines.append("오늘 데이터가 아직 수집되지 않았습니다.")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━")
    lines.append("📊 더 자세히 보려면 /today")
    
    return "\n".join(lines)


def send_morning_brief_to_all(db: Session) -> dict:
    """
    모든 구독자에게 아침 브리핑 전송
    """
    # 구독자 조회
    subscribers = (
        db.query(Subscriber)
        .filter(Subscriber.subscribed_alert.is_(True))
        .all()
    )
    
    if not subscribers:
        logger.info("No active subscribers")
        return {"sent": 0, "failed": 0, "message": "No active subscribers"}
    
    # 메시지 생성
    message = generate_morning_brief(db)
    
    sent_count = 0
    failed_count = 0
    
    for subscriber in subscribers:
        if send_telegram_message_sync(subscriber.chat_id, message):
            sent_count += 1
        else:
            failed_count += 1
    
    logger.info(f"Morning brief sent: {sent_count} success, {failed_count} failed")
    
    return {
        "sent": sent_count,
        "failed": failed_count,
        "total": len(subscribers),
        "message": f"Sent to {sent_count}/{len(subscribers)} subscribers"
    }


def send_morning_brief_to_chat(db: Session, chat_id: str) -> bool:
    """특정 사용자에게 아침 브리핑 전송 (로그 기록 포함)"""
    from datetime import timezone, timedelta

    message = generate_morning_brief(db)
    # KST 기준 오늘 날짜 (타임존 안전)
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).date()

    # 로그 생성 또는 조회
    log = db.query(NotificationLog).filter(
        NotificationLog.chat_id == chat_id,
        NotificationLog.notification_type == "morning_brief",
        NotificationLog.scheduled_date == today
    ).first()

    if not log:
        log = NotificationLog(
            chat_id=chat_id,
            notification_type="morning_brief",
            status="pending_retry",
            scheduled_date=today,
            message_preview=message[:100] if message else None,
            retry_count=0
        )
        db.add(log)
        db.commit()

    # 전송 시도
    from backend.app.db.models import utcnow
    log.last_attempt_at = utcnow()
    log.retry_count += 1

    success = send_telegram_message_sync(chat_id, message)

    if success:
        log.status = "success"
        log.succeeded_at = utcnow()
        log.error_message = None
    else:
        if log.retry_count >= log.max_retries:
            log.status = "failed"
            log.error_message = f"Failed after {log.retry_count} attempts"
        else:
            log.status = "pending_retry"

    db.commit()
    return success


def send_breaking_alert(db: Session, news_item) -> dict:
    """
    속보 알림 전송
    """
    # 구독자 조회
    subscribers = (
        db.query(Subscriber)
        .filter(Subscriber.subscribed_alert.is_(True))
        .all()
    )
    
    if not subscribers:
        return {"sent": 0, "message": "No active subscribers"}
    
    # 속보 메시지
    message = f"⚡ 긴급 속보 · BREAKING\n\n{news_item.title}\n\n🔗 {news_item.url}"
    
    sent_count = 0
    failed_count = 0
    
    for subscriber in subscribers:
        if send_telegram_message_sync(subscriber.chat_id, message):
            sent_count += 1
        else:
            failed_count += 1
    
    logger.info(f"Breaking alert sent: {sent_count} success, {failed_count} failed")
    
    return {
        "sent": sent_count,
        "failed": failed_count,
        "total": len(subscribers)
    }


def send_urgent_alert(db: Session, news_item) -> dict:
    """긴급 속보 즉시 전송"""
    from backend.app.utils.urgent_keywords import extract_urgent_keywords
    
    subscribers = db.query(Subscriber).filter(Subscriber.subscribed_alert.is_(True)).all()
    if not subscribers:
        return {"sent": 0}
    
    keywords = extract_urgent_keywords(news_item.title)
    keywords_str = ", ".join(keywords[:3]) if keywords else "긴급"
    message = f"🚨 긴급속보 [{keywords_str}]\n\n{news_item.title}\n\n🔗 {news_item.url}"
    
    sent_count = 0
    for subscriber in subscribers:
        if send_telegram_message_sync(subscriber.chat_id, message):
            sent_count += 1
    
    logger.info(f"Urgent alert sent: {sent_count}")
    return {"sent": sent_count}


def send_breaking_top5(db: Session) -> dict:
    """속보 TOP 5 전송 (하루 3번)"""
    from datetime import date
    
    subscribers = db.query(Subscriber).filter(Subscriber.subscribed_alert.is_(True)).all()
    if not subscribers:
        return {"sent": 0}

    # KST 기준 오늘 날짜 (타임존 안전)
    from datetime import timezone, timedelta
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).date()
    breaking_news = db.query(NewsDaily).filter(
        NewsDaily.date == today,
        NewsDaily.is_breaking.is_(True),
        NewsDaily.alert_sent.is_(False)
    ).order_by(NewsDaily.hot_score.desc()).limit(5).all()
    
    if not breaking_news:
        return {"sent": 0}
    
    lines = ["📰 속보 TOP 5", ""]
    for idx, news in enumerate(breaking_news, 1):
        lines.append(f"{idx}️⃣ {news.title}")
        lines.append(f"🔗 {news.url}")
        lines.append("")
    
    message = "\n".join(lines)
    sent_count = 0
    for subscriber in subscribers:
        if send_telegram_message_sync(subscriber.chat_id, message):
            sent_count += 1
    
    if sent_count > 0:
        for news in breaking_news:
            news.alert_sent = True
        db.commit()
    
    return {"sent": sent_count}


def send_breaking_batch(db: Session, news_items: list) -> int:
    """
    속보 배치 전송 (하루 3번)
    여러 개를 모아서 한 번에 전송
    """
    if not news_items:
        return 0
    
    # 구독자 조회
    subscribers = (
        db.query(Subscriber)
        .filter(Subscriber.subscribed_alert.is_(True))
        .all()
    )
    
    if not subscribers:
        return 0
    
    # 중복 제거 후 배치 메시지 생성
    from backend.app.utils.dedup import remove_duplicate_news
    if news_items:
        news_items = remove_duplicate_news(news_items)

    lines = ["⚡ 긴급 속보 모음 · BREAKING NEWS"]
    lines.append("")
    lines.append(f"📰 총 {len(news_items)}건")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    
    for i, news in enumerate(news_items[:20], 1):  # 최대 20개
        lines.append(f"{i}. {news.title}")
        lines.append(f"   🔗 {news.url}")
        lines.append("")
    
    if len(news_items) > 20:
        lines.append(f"외 {len(news_items) - 20}건...")
    
    message = "\n".join(lines)
    
    # 전송
    sent_count = 0
    for subscriber in subscribers:
        if send_telegram_message_sync(subscriber.chat_id, message):
            sent_count += 1
    
    failed_count = len(subscribers) - sent_count
    logger.info(
        "Breaking batch send result: items=%s subscribers=%s sent=%s failed=%s",
        len(news_items),
        len(subscribers),
        sent_count,
        failed_count,
    )

    # 전송이 0건이면 alert_sent 갱신하지 않음 (재시도 가능하도록 보존)
    if sent_count > 0:
        for news in news_items:
            news.alert_sent = True
        db.commit()
        logger.info("Breaking batch marked sent (items=%s)", len(news_items))
    else:
        logger.warning("Breaking batch skipped alert_sent update (sent=0)")
    
    return sent_count
