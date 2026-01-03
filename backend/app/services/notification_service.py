"""
알림/푸시 관련 서비스 모듈
"""

import httpx
import logging
from datetime import date as date_type
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.config import settings
from backend.app.db.models import Subscriber, MarketDaily, NewsDaily

logger = logging.getLogger(__name__)


def send_telegram_message_sync(chat_id: str, text: str) -> bool:
    """
    텔레그램 메시지 동기 전송
    (스케줄러에서 호출하기 위해 동기 방식)
    """
    token = settings.TELEGRAM_TOKEN
    if not token:
        logger.error("TELEGRAM_TOKEN is not set")
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
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
        logger.info(f"Message sent to {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")
        return False


def generate_morning_brief(db: Session, target_date: Optional[date_type] = None) -> str:
    """
    아침 브리핑 메시지 생성 (09:05 이후 - 전일대비 포함)
    """
    if target_date is None:
        target_date = date_type.today()
    
    # 시장 데이터 조회
    market: Optional[MarketDaily] = (
        db.query(MarketDaily)
        .filter(MarketDaily.date == target_date)
        .order_by(MarketDaily.id.desc())
        .first()
    )
    
    # 뉴스 Top5 조회
    news_list = (
        db.query(NewsDaily)
        .filter(NewsDaily.date == target_date, NewsDaily.is_top.is_(True))
        .order_by(NewsDaily.created_at.desc())
        .limit(10)
        .all()
    )
    
    lines = []
    lines.append(f"📊 오늘 아침 브리핑 ({target_date})")
    lines.append("")
    
    if market:
        # 환율
        if market.usd_krw:
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
        if market.kospi_index or market.nasdaq_index:
            lines.append("📊 주요 지수")
            
            if market.kospi_index:
                lines.append(f"KOSPI: {market.kospi_index:,.2f}")
                # 전일대비
                if market.kospi_index_change is not None and market.kospi_index_change_pct is not None:
                    emoji = "🔺" if market.kospi_index_change > 0 else "🔻" if market.kospi_index_change < 0 else "➖"
                    sign = "+" if market.kospi_index_change > 0 else ""
                    lines.append(f"   {emoji} {sign}{market.kospi_index_change:.2f} ({sign}{market.kospi_index_change_pct:.2f}%)")
            
            if market.nasdaq_index:
                lines.append(f"나스닥100: {market.nasdaq_index:,.2f}")
                # 전일대비
                if market.nasdaq_index_change is not None and market.nasdaq_index_change_pct is not None:
                    emoji = "🔺" if market.nasdaq_index_change > 0 else "🔻" if market.nasdaq_index_change < 0 else "➖"
                    sign = "+" if market.nasdaq_index_change > 0 else ""
                    lines.append(f"   {emoji} {sign}{market.nasdaq_index_change:.2f} ({sign}{market.nasdaq_index_change_pct:.2f}%)")
            
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
        
        # 금속 시세 (확장 버전)
        if market.gold_usd and market.usd_krw:
            lines.append("🥇 금속 시세")
            
            # 금
            gold_per_gram = market.gold_usd / 31.1035
            gold_per_don = gold_per_gram * 3.75 * market.usd_krw
            lines.append(f"💛 금: {gold_per_don:,.0f}원/돈")
            
            # 은
            if market.silver_usd:
                silver_per_gram = market.silver_usd / 31.1035
                silver_per_don = silver_per_gram * 3.75 * market.usd_krw
                lines.append(f"⚪ 은: {silver_per_don:,.0f}원/돈")
            
            # 구리
            if market.copper_usd:
                copper_per_kg = market.copper_usd / 0.453592  # lb to kg
                copper_krw = copper_per_kg * market.usd_krw
                lines.append(f"🟤 구리: {copper_krw:,.0f}원/kg")
            
            # 백금
            if market.platinum_usd:
                platinum_per_gram = market.platinum_usd / 31.1035
                platinum_per_don = platinum_per_gram * 3.75 * market.usd_krw
                lines.append(f"⚪ 백금: {platinum_per_don:,.0f}원/돈")
            
            # 팔라디움
            if market.palladium_usd:
                palladium_per_gram = market.palladium_usd / 31.1035
                palladium_per_don = palladium_per_gram * 3.75 * market.usd_krw
                lines.append(f"⚪ 팔라디움: {palladium_per_don:,.0f}원/돈")
            
            lines.append("")
    
    # 뉴스
    if news_list:
        lines.append("📰 주요 뉴스")
        for idx, news in enumerate(news_list[:5], 1):
            lines.append(f"{idx}) {news.title}")
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
    
    today = date.today()
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
    
    # 배치 메시지 생성
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
    
    # 모든 속보 전송 완료 플래그 설정
    for news in news_items:
        news.alert_sent = True
    db.commit()
    
    logger.info(f"Breaking batch sent: {len(news_items)} items to {sent_count} subscribers")
    
    return sent_count
