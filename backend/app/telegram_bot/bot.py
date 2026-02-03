import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, date, time as time_type, timedelta, timezone
import httpx

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from backend.app.config import settings
from backend.app.handlers.lotto.lotto_handler import (
    lotto_command,
    lotto_generate_callback,
    lotto_result_command,
    lotto_result_callback,
    lotto_performance_command
)

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "bot.log"

root_logger = logging.getLogger()
if not root_logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_PATH),
        ],
    )
else:
    root_logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(LOG_PATH)
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def _on_app_error(update, context):
    """에러 핸들러 - 네트워크 오류는 로그만"""
    try:
        from telegram.error import NetworkError
        if isinstance(context.error, NetworkError):
            logger.warning("Telegram NetworkError (transient): %s", context.error)
            return
    except Exception:
        pass
    logger.exception("Unhandled error", exc_info=context.error)


COINPAPRIKA_TICKER_URL = "https://api.coinpaprika.com/v1/tickers"

SUPPORTED_COINS: Dict[str, str] = {
    "BTC": "btc-bitcoin",
    "ETH": "eth-ethereum",
    "SOL": "sol-solana",
    "XRP": "xrp-xrp",
    "TRX": "trx-tron",
}

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🪙 BTC", "📊 시장 지수"],
        ["🪙 전체 암호화폐", "📰 전체 뉴스"],
        ["📈 오늘 요약", "💵 환율"],
        ["🥇 금속 조회하기"],
        ["🎰 로또 번호 생성"],
    ],
    resize_keyboard=True,
)


def build_timeframe_keyboard(symbol: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("1H", callback_data=f"tf:{symbol}:1h"),
                InlineKeyboardButton("4H", callback_data=f"tf:{symbol}:4h"),
                InlineKeyboardButton("1D", callback_data=f"tf:{symbol}:1d"),
            ]
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import Subscriber

    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    is_new_user = False

    try:
        # 자동 구독 등록 (봇 추가 시 자동으로 구독자로 등록)
        subscriber = db.query(Subscriber).filter(Subscriber.chat_id == chat_id).first()
        if not subscriber:
            subscriber = Subscriber(
                chat_id=chat_id,
                subscribed_alert=True,
                custom_time="09:10"
            )
            db.add(subscriber)
            db.commit()
            is_new_user = True

            # 즉시 스케줄러에 등록
            try:
                from backend.app.scheduler.jobs import schedule_user_alerts
                schedule_user_alerts()
            except Exception as e:
                print(f"스케줄러 등록 오류: {e}")
    finally:
        db.close()

    if is_new_user:
        text = (
            "안녕하세요, 모닝 마켓 봇입니다 🌅\n\n"
            "✅ 자동으로 아침 알림이 구독되었습니다!\n"
            "📍 알림 시간: 매일 09:10\n"
            "⏰ /set_time 으로 시간 변경 가능\n\n"
            "━━━━━━━━━━━━━━\n"
            "아래 버튼을 눌러 바로 사용할 수 있어요.\n"
            "🪙 BTC - 비트코인 시세\n"
            "📊 시장 지수 - KOSPI/나스닥 지수 + Top5\n"
            "🪙 전체 암호화폐 - ETH/SOL/XRP/TRX 한 번에 보기\n"
            "📰 전체 뉴스 - 사회/경제/문화/연예 카테고리별 Top 5\n"
            "📈 오늘 요약 - 종합 뉴스, 지수, 환율, 금속\n"
            "💵 환율 - 주요 환율 확인\n"
            "🥇 금속 조회하기 - 금/은/구리/백금/팔라디움\n"
            "🎰 로또 번호 생성 - AI 로또 번호\n\n"
            "━━━━━━━━━━━━━━\n"
            "/unsubscribe - 알림 구독 취소\n"
            "/settings - 현재 설정 확인"
        )
    else:
        text = (
            "안녕하세요, 모닝 마켓 봇입니다 🌅\n\n"
            "아래 버튼을 눌러 바로 사용할 수 있어요.\n"
            "🪙 BTC - 비트코인 시세\n"
            "📊 시장 지수 - KOSPI/나스닥 지수 + Top5\n"
            "🪙 전체 암호화폐 - ETH/SOL/XRP/TRX 한 번에 보기\n"
            "📰 전체 뉴스 - 사회/경제/문화/연예 카테고리별 Top 5\n"
            "📈 오늘 요약 - 종합 뉴스, 지수, 환율, 금속\n"
            "💵 환율 - 주요 환율 확인\n"
            "🥇 금속 조회하기 - 금/은/구리/백금/팔라디움\n"
            "🎰 로또 번호 생성 - AI 로또 번호\n\n"
            "━━━━━━━━━━━━━━\n"
            "/set_time - 알림 시간 설정\n"
            "/settings - 현재 설정 확인\n"
            "/unsubscribe - 알림 구독 취소"
        )
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """오늘 요약 - DB에서 직접 가져오기 (09:05 기준)"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import MarketDaily, NewsDaily, KoreaMetalDaily
    from datetime import date, timedelta, timezone

    db = SessionLocal()

    try:
        # 한국 시간 (KST = UTC+9)
        KST = timezone(timedelta(hours=9))
        now = datetime.now(KST)
        cutoff_time = time_type(9, 5)  # 09:05 KST

        # 09:05 이전이면 어제 데이터, 이후면 오늘 데이터
        # KST 기준 날짜 (타임존 안전)
        if now.time() < cutoff_time:
            target_date = now.date() - timedelta(days=1)
            date_label = "어제"
        else:
            target_date = now.date()
            date_label = "오늘"
        
        # 시장 데이터 조회
        market = db.query(MarketDaily).filter(
            MarketDaily.date == target_date
        ).order_by(MarketDaily.id.desc()).first()
        
        # 뉴스 조회: 카테고리별 Top1 + 속보 1개 (중복 제거)
        from sqlalchemy import func
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

        news_list = news_list[:5]

        # 전일대비 값이 비어 있을 때 즉시 계산 (스케줄러 09:05 이전에도 표시되도록)
        market_yesterday = None
        if market:
            yesterday_date = target_date - timedelta(days=1)
            market_yesterday = db.query(MarketDaily).filter(
                MarketDaily.date == yesterday_date
            ).order_by(MarketDaily.id.desc()).first()

            def _calc_change(curr, prev):
                if curr is None or prev in (None, 0):
                    return None, None
                diff = curr - prev
                pct = (diff / prev) * 100
                return diff, pct

            # 환율 전일대비 보정
            if (
                market.usd_krw is not None
                and (market.usd_krw_change is None or market.usd_krw_change_pct is None)
                and market_yesterday
                and market_yesterday.usd_krw is not None
            ):
                market.usd_krw_change, market.usd_krw_change_pct = _calc_change(
                    market.usd_krw, market_yesterday.usd_krw
                )

            # KOSPI 전일대비 보정
            if (
                market.kospi_index is not None
                and (market.kospi_index_change is None or market.kospi_index_change_pct is None)
                and market_yesterday
                and market_yesterday.kospi_index is not None
            ):
                market.kospi_index_change, market.kospi_index_change_pct = _calc_change(
                    market.kospi_index, market_yesterday.kospi_index
                )

            # 나스닥 전일대비 보정
            if (
                market.nasdaq_index is not None
                and (market.nasdaq_index_change is None or market.nasdaq_index_change_pct is None)
                and market_yesterday
                and market_yesterday.nasdaq_index is not None
            ):
                market.nasdaq_index_change, market.nasdaq_index_change_pct = _calc_change(
                    market.nasdaq_index, market_yesterday.nasdaq_index
                )
        
        lines = []
        lines.append(f"☀️ 모닝 브리핑")
        lines.append(f"🗓️ {target_date} ({date_label})")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        if market:
            # 환율
            if market.usd_krw:
                lines.append("💱 글로벌 환율")
                lines.append("🇺🇸 USD → 🇰🇷 KRW")
                lines.append(f"💵 $1 = ₩{market.usd_krw:,.2f}")
                
                # 전일대비 (09:05 이후만)
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
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("")
            
            # 비트코인
            if market.btc_krw or market.btc_usdt:
                lines.append("₿ 비트코인 시세")
                if market.btc_krw:
                    lines.append(f"🇰🇷 ₩{market.btc_krw:,.0f}")
                if market.btc_usdt:
                    lines.append(f"🇺🇸 ${market.btc_usdt:,.2f}")
                if market.btc_change_24h is not None:
                    emoji = "🚀" if market.btc_change_24h > 0 else "📉" if market.btc_change_24h < 0 else "➡️"
                    color = "🟢" if market.btc_change_24h > 0 else "🔴" if market.btc_change_24h < 0 else "⚪"
                    lines.append(f"{emoji} 24h {market.btc_change_24h:+.2f}% {color}")
                lines.append("")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("")
            
            # 주요 지수
            if market.kospi_index or market.nasdaq_index:
                lines.append("📊 주요 지수")

                if market.kospi_index:
                    lines.append(f"KOSPI: {market.kospi_index:,.2f}")
                    if market.kospi_index_change is not None and market.kospi_index_change_pct is not None:
                        emoji = "🔺" if market.kospi_index_change > 0 else "🔻" if market.kospi_index_change < 0 else "➖"
                        sign = "+" if market.kospi_index_change > 0 else ""
                        lines.append(f"   {emoji} {sign}{market.kospi_index_change:.2f} ({sign}{market.kospi_index_change_pct:.2f}%)")

                # KOSDAQ 추가
                kosdaq_index = getattr(market, 'kosdaq_index', None)
                if kosdaq_index:
                    lines.append(f"KOSDAQ: {kosdaq_index:,.2f}")
                    kosdaq_change = getattr(market, 'kosdaq_index_change', None)
                    kosdaq_pct = getattr(market, 'kosdaq_index_change_pct', None)
                    if kosdaq_change is not None and kosdaq_pct is not None:
                        emoji = "🔺" if kosdaq_change > 0 else "🔻" if kosdaq_change < 0 else "➖"
                        sign = "+" if kosdaq_change > 0 else ""
                        lines.append(f"   {emoji} {sign}{kosdaq_change:.2f} ({sign}{kosdaq_pct:.2f}%)")

                if market.nasdaq_index:
                    lines.append(f"나스닥100: {market.nasdaq_index:,.2f}")
                    if market.nasdaq_index_change is not None and market.nasdaq_index_change_pct is not None:
                        emoji = "🔺" if market.nasdaq_index_change > 0 else "🔻" if market.nasdaq_index_change < 0 else "➖"
                        sign = "+" if market.nasdaq_index_change > 0 else ""
                        lines.append(f"   {emoji} {sign}{market.nasdaq_index_change:.2f} ({sign}{market.nasdaq_index_change_pct:.2f}%)")

                # S&P500 추가
                sp500_index = getattr(market, 'sp500_index', None)
                if sp500_index:
                    lines.append(f"S&P500: {sp500_index:,.2f}")
                    sp500_change = getattr(market, 'sp500_index_change', None)
                    sp500_pct = getattr(market, 'sp500_index_change_pct', None)
                    if sp500_change is not None and sp500_pct is not None:
                        emoji = "🔺" if sp500_change > 0 else "🔻" if sp500_change < 0 else "➖"
                        sign = "+" if sp500_change > 0 else ""
                        lines.append(f"   {emoji} {sign}{sp500_change:.2f} ({sign}{sp500_pct:.2f}%)")

                lines.append("")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("")
            
            # KOSPI Top5
            if market.kospi_top5 and isinstance(market.kospi_top5, list):
                lines.append("📈 KOSPI TOP 5")
                for idx, stock in enumerate(market.kospi_top5[:5], 1):
                    medal = ["🥇", "🥈", "🥉", "🏅", "🎖️"][idx-1]
                    name = stock.get("name", "")
                    price = stock.get("price", "")
                    change = stock.get("change", "")
                    change_rate = stock.get("change_rate", "")
                    emoji = "🔺" if "+" in str(change_rate) else "🔻" if "-" in str(change_rate) else "➖"
                    lines.append(f"{medal} {idx}위 {name}")
                    lines.append(f"   {price}")
                    if change or change_rate:
                        import re

                        change_text = str(change or "").strip()
                        rate_text = str(change_rate or "").strip()

                        sign = ""
                        if "-" in rate_text:
                            sign = "-"
                        elif "+" in rate_text:
                            sign = "+"
                        elif "하락" in change_text:
                            sign = "-"
                        elif "상승" in change_text:
                            sign = "+"

                        change_num = re.sub(r"[^0-9]", "", change_text)
                        if change_num:
                            change_num = f"{int(change_num):,}"
                            change_display = f"{sign}{change_num}" if sign else change_num
                        else:
                            change_display = change_text or "-"

                        rate_num = re.sub(r"[^0-9.]", "", rate_text)
                        if rate_num:
                            rate_display = f"{sign}{rate_num}%" if sign else f"{rate_num}%"
                        else:
                            rate_display = rate_text or "-"

                        emoji = "🔺" if sign == "+" else "🔻" if sign == "-" else "➖"
                        lines.append(f"   전일대비 {emoji} {change_display} ({rate_display})")
                lines.append("")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("")
            
            # 금속 시세
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

                # 어제 데이터 조회 (전일대비용)
                yesterday_date = target_date - timedelta(days=1)
                market_yesterday = db.query(MarketDaily).filter(
                    MarketDaily.date == yesterday_date
                ).order_by(MarketDaily.id.desc()).first()
                
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

                # 구리는 기존처럼 유지 (국내 시세와 무관하게 표시)
                if market.copper_usd:
                    copper_per_kg = market.copper_usd / 0.453592  # lb to kg
                    copper_krw = copper_per_kg * market.usd_krw
                    lines.append(f"🟤 구리 (1kg) ₩{copper_krw:,.0f}")
                    if market_yesterday and market_yesterday.copper_usd:
                        copper_change = market.copper_usd - market_yesterday.copper_usd
                        copper_change_pct = (copper_change / market_yesterday.copper_usd) * 100
                        emoji = "🔺" if copper_change > 0 else "🔻" if copper_change < 0 else "➖"
                        sign = "+" if copper_change > 0 else ""
                        lines.append(f"   전일대비 {emoji} {sign}${copper_change:.4f} ({sign}{copper_change_pct:.2f}%)")
                    
                
                lines.append("")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("")
        
        # 뉴스
        if news_list:
            lines.append("📰 주요 뉴스")
            lines.append("")
            for idx, news in enumerate(news_list[:5], 1):
                lines.append(f"{idx}️⃣ {news.title}")
                lines.append(f"🔗 {news.url}")
                lines.append("")
        
        if not market and not news_list:
            lines.append("📰 데이터가 아직 수집되지 않았습니다.")
            lines.append("")
            lines.append("잠시 후 다시 시도해 주세요.")
        
        await update.message.reply_text("\n".join(lines))
    
    finally:
        db.close()


async def fetch_coin_ticker(symbol: str) -> Optional[Dict[str, Any]]:
    coin_id = SUPPORTED_COINS.get(symbol.upper())
    if not coin_id:
        return None

    url = f"{COINPAPRIKA_TICKER_URL}/{coin_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Failed to fetch coin ticker: %s", e)
        return None


async def fetch_all_coins() -> Dict[str, Dict[str, Any]]:
    """모든 지원 코인의 시세를 한 번에 가져옵니다."""
    result = {}
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for symbol, coin_id in SUPPORTED_COINS.items():
            try:
                url = f"{COINPAPRIKA_TICKER_URL}/{coin_id}"
                resp = await client.get(url)
                resp.raise_for_status()
                result[symbol] = resp.json()
            except Exception as e:
                logger.exception(f"Failed to fetch {symbol}: %s", e)
                result[symbol] = None
    
    return result


def format_all_crypto_message(coins_data: Dict[str, Dict[str, Any]]) -> str:
    """모든 코인 시세를 한 번에 표시하는 메시지 포맷 (KRW 포함)"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import MarketDaily
    from datetime import date

    lines = []
    lines.append("🪙 전체 암호화폐")
    lines.append("")

    coin_symbols = {
        "BTC": "🪙 BTC",
        "ETH": "💎 ETH",
        "SOL": "⚡ SOL",
        "XRP": "💧 XRP",
        "TRX": "🔷 TRX"
    }

    # DB에서 환율 가져오기 (실패 시 실시간 API 조회)
    exchange_rate = None
    db = SessionLocal()
    try:
        market = db.query(MarketDaily).filter(
            MarketDaily.date == datetime.now(timezone(timedelta(hours=9))).date()
        ).order_by(MarketDaily.id.desc()).first()
        if market and market.usd_krw:
            exchange_rate = market.usd_krw
    except Exception as e:
        logger.warning(f"DB에서 환율 조회 실패: {e}")
    finally:
        db.close()

    # DB에 환율이 없으면 실시간 API 조회
    if not exchange_rate:
        from backend.app.collectors.market_collector import fetch_usd_krw_rate
        exchange_rate = fetch_usd_krw_rate()
        if exchange_rate:
            logger.info(f"실시간 환율 조회 성공: {exchange_rate}원")
        else:
            logger.error("환율 조회 실패 - 기본값(1430원) 사용")
            exchange_rate = 1430.0  # 최후의 폴백
    
    for symbol in ["BTC", "ETH", "SOL", "XRP", "TRX"]:
        coin = coins_data.get(symbol)
        if not coin:
            lines.append(coin_symbols.get(symbol, symbol))
            lines.append("데이터 없음")
            lines.append("")
            continue
        
        emoji = coin_symbols.get(symbol, symbol)
        quotes = coin.get("quotes", {})
        usd = quotes.get("USD", {})
        
        price = usd.get("price", 0)
        change_24h = usd.get("percent_change_24h", 0)
        
        if change_24h > 0:
            color = "🟢"
        elif change_24h < 0:
            color = "🔴"
        else:
            color = "⚪"
        
        lines.append(emoji)
        lines.append(f"🇺🇸 ${price:,.2f}")
        
        if price:
            krw_price = price * exchange_rate
            lines.append(f"🇰🇷 ₩{krw_price:,.0f}")
        
        lines.append(f"24h {change_24h:+.2f}% {color}")
        lines.append("")
    
    return "\n".join(lines)


async def all_crypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """전체 암호화폐 시세 표시"""
    coins_data = await fetch_all_coins()
    message = format_all_crypto_message(coins_data)
    await update.message.reply_text(message)


async def crypto_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """암호화폐 메뉴 표시"""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("BTC", callback_data="crypto_BTC"),
            InlineKeyboardButton("ETH", callback_data="crypto_ETH"),
        ],
        [
            InlineKeyboardButton("SOL", callback_data="crypto_SOL"),
            InlineKeyboardButton("XRP", callback_data="crypto_XRP"),
        ],
        [
            InlineKeyboardButton("TRX", callback_data="crypto_TRX"),
        ],
    ])
    
    await update.message.reply_text(
        "암호화폐를 선택하세요:",
        reply_markup=keyboard
    )


async def on_crypto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """암호화폐 콜백 처리"""
    query = update.callback_query
    await query.answer()
    
    symbol = query.data.replace("crypto_", "")
    
    # 새 메시지로 전송
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"🔄 {symbol} 시세를 가져오는 중..."
    )
    
    # 실제 시세 가져오기
    coin_data = await fetch_coin_ticker(symbol)
    
    if not coin_data:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"❌ {symbol} 시세를 가져오지 못했습니다."
        )
        return
    
    quotes = coin_data.get("quotes", {})
    usd = quotes.get("USD", {})
    
    price = usd.get("price", 0)
    change_1h = usd.get("percent_change_1h", 0)
    change_24h = usd.get("percent_change_24h", 0)
    change_7d = usd.get("percent_change_7d", 0)
    
    message = f"🪙 {symbol}\n\n"
    message += f"💵 ${price:,.2f}\n\n"
    message += f"1H: {change_1h:+.2f}%\n"
    message += f"24H: {change_24h:+.2f}%\n"
    message += f"7D: {change_7d:+.2f}%"
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=message
    )


async def btc_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await crypto_command(update, context, symbol="BTC")


async def crypto_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    symbol: str = "BTC"
) -> None:
    """특정 암호화폐 시세 조회"""
    if symbol not in SUPPORTED_COINS:
        await update.message.reply_text(
            f"❌ 지원하지 않는 코인입니다: {symbol}\n\n"
            f"지원 코인: {', '.join(SUPPORTED_COINS.keys())}"
        )
        return
    
    coin_data = await fetch_coin_ticker(symbol)
    
    if not coin_data:
        await update.message.reply_text(f"❌ {symbol} 시세를 가져오지 못했습니다.")
        return
    
    quotes = coin_data.get("quotes", {})
    usd = quotes.get("USD", {})
    
    price = usd.get("price", 0)
    change_1h = usd.get("percent_change_1h", 0)
    change_24h = usd.get("percent_change_24h", 0)
    change_7d = usd.get("percent_change_7d", 0)
    market_cap = usd.get("market_cap", 0)
    volume_24h = usd.get("volume_24h", 0)
    
    coin_symbols = {
        "BTC": "₿",
        "ETH": "Ξ",
        "SOL": "◎",
        "XRP": "✕",
        "TRX": "⬡"
    }
    emoji = coin_symbols.get(symbol, "🪙")
    
    message = f"{emoji} {symbol}\n\n"
    message += f"💵 ${price:,.2f}\n\n"
    message += f"📊 변동률\n"
    message += f"1H: {change_1h:+.2f}%\n"
    message += f"24H: {change_24h:+.2f}%\n"
    message += f"7D: {change_7d:+.2f}%\n\n"
    message += f"💰 시가총액: ${market_cap:,.0f}\n"
    message += f"📈 거래량(24H): ${volume_24h:,.0f}"
    
    # 타임프레임 버튼 추가
    keyboard = build_timeframe_keyboard(symbol)
    
    await update.message.reply_text(message, reply_markup=keyboard)


async def on_timeframe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """타임프레임 콜백 처리"""
    query = update.callback_query
    await query.answer()
    
    # callback_data 형식: "tf:BTC:1h"
    parts = query.data.split(":")
    if len(parts) != 3:
        return
    
    symbol = parts[1]
    timeframe = parts[2]
    
    await query.edit_message_text(
        f"📊 {symbol} {timeframe.upper()} 차트\n\n"
        f"차트 기능은 추후 추가 예정입니다."
    )


async def fx_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """환율 조회 (네이버 환율 API 기반 - 11개 통화 + 전일대비)"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import MarketDaily
    from datetime import date, timedelta

    db = SessionLocal()

    try:
        kst = timezone(timedelta(hours=9))
        today = datetime.now(kst).date()

        # 오늘 데이터 조회
        market = db.query(MarketDaily).filter(
            MarketDaily.date == today
        ).order_by(MarketDaily.id.desc()).first()

        # 오늘 데이터 없으면 최신 데이터 사용
        if not market or not market.usd_krw:
            market = db.query(MarketDaily).order_by(
                MarketDaily.date.desc(),
                MarketDaily.id.desc()
            ).first()
            if not market or not market.usd_krw:
                await update.message.reply_text("환율 데이터가 아직 수집되지 않았습니다.")
                return
            logger.warning("fx_command fallback to latest market date=%s", market.date)

        # exchange_rates JSON 데이터 확인
        exchange_rates = getattr(market, 'exchange_rates', None) or {}

        msg_lines = []
        msg_lines.append("글로벌 환율 (네이버 기준)")
        msg_lines.append("")

        if market.date != today:
            msg_lines.append(f"* 기준일: {market.date}")
            msg_lines.append("")

        msg_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # 주요 통화 (USD, EUR, JPY, CNY, GBP)
        msg_lines.append("")
        msg_lines.append("주요 통화")
        msg_lines.append("")

        major_currencies = ["USD", "EUR", "JPY", "CNY", "GBP"]
        for currency in major_currencies:
            line = _format_exchange_rate_line(currency, exchange_rates, market)
            if line:
                msg_lines.append(line)

        # 동남아 통화 (SGD, THB, VND, PHP, IDR, MYR)
        msg_lines.append("")
        msg_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        msg_lines.append("")
        msg_lines.append("동남아 통화")
        msg_lines.append("")

        sea_currencies = ["SGD", "THB", "VND", "PHP", "IDR", "MYR"]
        for currency in sea_currencies:
            line = _format_exchange_rate_line(currency, exchange_rates, market)
            if line:
                msg_lines.append(line)

        await update.message.reply_text("\n".join(msg_lines))
    except Exception:
        logger.exception("fx_command failed")
        await update.message.reply_text("환율 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
    finally:
        db.close()


def _format_exchange_rate_line(currency: str, exchange_rates: dict, market) -> str:
    """환율 한 줄 포맷팅 (전일대비 포함) - 한국어 통화명 표시"""
    data = exchange_rates.get(currency, {})

    rate = data.get("rate")
    change = data.get("change")
    change_pct = data.get("change_pct")
    unit = data.get("unit", 1)
    emoji = data.get("emoji", "")
    name = data.get("name", currency)

    # rate가 없으면 레거시 usd_krw 사용 (USD만)
    if rate is None and currency == "USD":
        rate = market.usd_krw
        change = getattr(market, 'usd_krw_change', None)
        change_pct = getattr(market, 'usd_krw_change_pct', None)
        emoji = "🇺🇸"
        name = "미국 달러"
        unit = 1

    if rate is None:
        return ""

    # 단위 표시 (100엔, 100동, 100루피아)
    unit_text = f"({unit})" if unit > 1 else ""

    # 전일대비 포맷
    if change is not None and change_pct is not None:
        arrow = "🔺" if change > 0 else "🔻" if change < 0 else "➖"
        sign = "+" if change_pct > 0 else ""
        change_text = f" {arrow}{sign}{change_pct:.2f}%"
    else:
        change_text = ""

    return f"{emoji} {name}{unit_text}: ₩{rate:,.2f}{change_text}"


async def collect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """관리자용 수동 데이터 수집 명령어"""
    import os
    from backend.app.db.session import SessionLocal
    from backend.app.collectors.market_collector import collect_market_daily, calculate_daily_changes

    # 관리자 체크 (LOTTO_ADMIN_CHAT_ID)
    admin_chat_id = os.getenv("LOTTO_ADMIN_CHAT_ID", "")
    user_chat_id = str(update.effective_chat.id)

    if user_chat_id != admin_chat_id:
        await update.message.reply_text("관리자 전용 명령어입니다.")
        return

    await update.message.reply_text("데이터 수집 시작...")

    db = SessionLocal()
    try:
        # 1. 시장 데이터 수집
        market = collect_market_daily(db)
        msg = f"시장 데이터 수집 완료\n"
        msg += f"- USD/KRW: {market.usd_krw:,.2f}\n" if market.usd_krw else "- USD/KRW: NULL\n"
        msg += f"- exchange_rates: {'OK' if market.exchange_rates else 'NULL'}\n"
        msg += f"- KOSPI: {market.kospi_index:,.2f}\n" if market.kospi_index else "- KOSPI: NULL\n"
        msg += f"- KOSDAQ: {market.kosdaq_index:,.2f}\n" if market.kosdaq_index else "- KOSDAQ: NULL\n"
        msg += f"- S&P500: {market.sp500_index:,.2f}\n" if market.sp500_index else "- S&P500: NULL\n"
        msg += f"- 나스닥100: {market.nasdaq_index:,.2f}\n" if market.nasdaq_index else "- 나스닥100: NULL\n"

        # 2. 전일대비 계산
        calculate_daily_changes(db)
        msg += "\n전일대비 계산 완료"

        await update.message.reply_text(msg)
    except Exception as e:
        logger.exception("collect_command failed")
        await update.message.reply_text(f"수집 실패: {e}")
    finally:
        db.close()


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """관리자용 통계 조회 명령어"""
    import os
    from sqlalchemy import func, distinct
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import Subscriber, MarketDaily, NewsDaily, NotificationLog

    # 관리자 체크
    admin_chat_id = os.getenv("LOTTO_ADMIN_CHAT_ID", "")
    user_chat_id = str(update.effective_chat.id)

    if user_chat_id != admin_chat_id:
        await update.message.reply_text("관리자 전용 명령어입니다.")
        return

    db = SessionLocal()
    try:
        # 구독자 통계
        total_subscribers = db.query(Subscriber).count()
        active_subscribers = db.query(Subscriber).filter(Subscriber.subscribed_alert.is_(True)).count()

        # 알림을 받은 적 있는 고유 사용자 수
        unique_notified_users = db.query(func.count(distinct(NotificationLog.chat_id))).scalar() or 0

        # 전체 알림 발송 횟수
        total_notifications = db.query(NotificationLog).count()

        # 오늘 날짜
        kst = timezone(timedelta(hours=9))
        today = datetime.now(kst).date()

        # 오늘 데이터 수집 여부
        market_today = db.query(MarketDaily).filter(MarketDaily.date == today).first()
        news_today_count = db.query(NewsDaily).filter(NewsDaily.date == today).count()

        # 오늘 알림 전송 현황
        notif_success = db.query(NotificationLog).filter(
            NotificationLog.scheduled_date == today,
            NotificationLog.status == "success"
        ).count()
        notif_failed = db.query(NotificationLog).filter(
            NotificationLog.scheduled_date == today,
            NotificationLog.status == "failed"
        ).count()
        notif_pending = db.query(NotificationLog).filter(
            NotificationLog.scheduled_date == today,
            NotificationLog.status == "pending_retry"
        ).count()

        # 구독자 목록 (chat_id, 알림시간, 활성여부)
        subscribers = db.query(Subscriber).all()

        msg = f"📊 시스템 통계 ({today})\n\n"
        msg += f"👥 구독자 (subscribers 테이블)\n"
        msg += f"   전체: {total_subscribers}명\n"
        msg += f"   활성: {active_subscribers}명\n\n"
        msg += f"📨 알림 기록 (notification_log)\n"
        msg += f"   고유 사용자: {unique_notified_users}명\n"
        msg += f"   총 발송 횟수: {total_notifications}건\n\n"
        msg += f"📈 오늘 데이터\n"
        msg += f"   시장: {'✅ 수집완료' if market_today else '❌ 미수집'}\n"
        msg += f"   뉴스: {news_today_count}건\n\n"
        msg += f"📬 오늘 알림 전송\n"
        msg += f"   성공: {notif_success}건\n"
        msg += f"   실패: {notif_failed}건\n"
        msg += f"   대기: {notif_pending}건\n\n"

        # 구독자 상세 목록
        if subscribers:
            msg += f"📋 구독자 목록:\n"
            for sub in subscribers:
                status = "✅" if sub.subscribed_alert else "❌"
                time_str = sub.custom_time or "09:05"
                msg += f"   {status} {sub.chat_id} ({time_str})\n"

        await update.message.reply_text(msg)
    except Exception as e:
        logger.exception("stats_command failed")
        await update.message.reply_text(f"통계 조회 실패: {e}")
    finally:
        db.close()


async def restore_subscribers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """관리자용 구독자 복원 명령어 - 로컬 DB에서 가져온 구독자 목록을 Render DB에 추가"""
    import os
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import Subscriber

    # 관리자 체크
    admin_chat_id = os.getenv("LOTTO_ADMIN_CHAT_ID", "")
    user_chat_id = str(update.effective_chat.id)

    if user_chat_id != admin_chat_id:
        await update.message.reply_text("관리자 전용 명령어입니다.")
        return

    # 로컬 SQLite에서 가져온 구독자 목록 (2026-02-03 기준)
    local_subscribers = [
        {"chat_id": "358553338", "custom_time": "09:10", "created_at": "2025-12-29"},
        {"chat_id": "1491178873", "custom_time": "09:10", "created_at": "2025-12-31"},
        {"chat_id": "5175083233", "custom_time": "09:10", "created_at": "2026-01-03"},
        {"chat_id": "1663252440", "custom_time": "09:10", "created_at": "2026-01-17"},
        {"chat_id": "8396696639", "custom_time": "09:10", "created_at": "2026-01-17"},
        {"chat_id": "273256976", "custom_time": "09:10", "created_at": "2026-01-21"},
        {"chat_id": "2039777089", "custom_time": "09:10", "created_at": "2026-01-21"},
        {"chat_id": "5142436956", "custom_time": "09:10", "created_at": "2026-01-21"},
        {"chat_id": "969601726", "custom_time": "09:10", "created_at": "2026-01-22"},
        {"chat_id": "8523886085", "custom_time": "09:10", "created_at": "2026-01-22"},
    ]

    db = SessionLocal()
    added_count = 0
    skipped_count = 0

    try:
        for sub_data in local_subscribers:
            chat_id = sub_data["chat_id"]

            # 이미 존재하는지 확인
            existing = db.query(Subscriber).filter(Subscriber.chat_id == chat_id).first()

            if existing:
                skipped_count += 1
            else:
                new_sub = Subscriber(
                    chat_id=chat_id,
                    subscribed_alert=True,
                    custom_time=sub_data["custom_time"]
                )
                db.add(new_sub)
                added_count += 1

        db.commit()

        # 스케줄러에 새 구독자 등록
        if added_count > 0:
            try:
                from backend.app.scheduler.jobs import schedule_user_alerts
                schedule_user_alerts()
            except Exception as e:
                logger.warning(f"스케줄러 등록 실패: {e}")

        msg = f"✅ 구독자 복원 완료\n\n"
        msg += f"➕ 추가됨: {added_count}명\n"
        msg += f"⏭️ 건너뜀 (이미 존재): {skipped_count}명\n"
        msg += f"📊 총 시도: {len(local_subscribers)}명"

        await update.message.reply_text(msg)
    except Exception as e:
        logger.exception("restore_subscribers_command failed")
        await update.message.reply_text(f"구독자 복원 실패: {e}")
    finally:
        db.close()


async def metal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """금속 시세 조회 (DB에서) - 전체 금속"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import MarketDaily, KoreaMetalDaily
    from datetime import date, timedelta
    
    db = SessionLocal()
    
    try:
        kst = timezone(timedelta(hours=9))
        today = datetime.now(kst).date()
        yesterday = today - timedelta(days=1)
        
        # 오늘자 MarketDaily 조회
        market_today = db.query(MarketDaily).filter(
            MarketDaily.date == today
        ).order_by(MarketDaily.id.desc()).first()
        
        # 어제 MarketDaily 조회
        market_yesterday = db.query(MarketDaily).filter(
            MarketDaily.date == yesterday
        ).order_by(MarketDaily.id.desc()).first()
        
        if not market_today:
            market_today = db.query(MarketDaily).order_by(
                MarketDaily.date.desc(),
                MarketDaily.id.desc()
            ).first()
            if not market_today:
                await update.message.reply_text(
                    "🥇 금속 시세 데이터가 아직 수집되지 않았습니다.\n\n"
                    "잠시 후 다시 시도해 주세요."
                )
                return
            logger.warning("metal_command fallback to latest market date=%s", market_today.date)
            yesterday = market_today.date - timedelta(days=1)
            market_yesterday = db.query(MarketDaily).filter(
                MarketDaily.date == yesterday
            ).order_by(MarketDaily.id.desc()).first()
        
        def format_metal(name, emoji, usd_price, usd_price_yesterday, unit_type, korea_row=None):
            """금속 시세 포맷팅
            unit_type: 0=oz(금/은/백금/팔라디움), 1=lb(구리/알루미늄/니켈/아연/납)
            """
            lines = []
            
            if not usd_price or not market_today.usd_krw:
                lines.append(f"{emoji} {name}")
                lines.append("데이터 없음")
                return lines
            
            # 환율 적용
            usd_krw = market_today.usd_krw
            
            if unit_type == 0:  # oz (금/은/백금/팔라디움)
                # 1oz = 31.1035g
                per_gram = usd_price / 31.1035
                per_don = per_gram * 3.75 * usd_krw  # 1돈 = 3.75g
                
                lines.append(f"{emoji} {name}")
                lines.append(f"1돈 (3.75g) = ₩{per_don:,.0f}")
                lines.append(f"1g = ₩{per_gram * usd_krw:,.0f}")
                lines.append(f"국제가격 = ${usd_price:,.2f}/oz")

                if korea_row and korea_row.buy_3_75g:
                    date_label = None
                    if korea_row.date_text:
                        date_label = korea_row.date_text
                    elif korea_row.date:
                        date_label = korea_row.date.isoformat()
                    label = f" (고시 {date_label})" if date_label else ""
                    lines.append(f"🇰🇷 국내{label}")
                    lines.append(f"   살때(순금) ₩{korea_row.buy_3_75g:,.0f}")
                    if korea_row.sell_3_75g:
                        lines.append(f"   팔때(순금) ₩{korea_row.sell_3_75g:,.0f}")
                    if korea_row.sell_18k:
                        lines.append(f"   팔때(18K) ₩{korea_row.sell_18k:,.0f}")
                    if korea_row.sell_14k:
                        lines.append(f"   팔때(14K) ₩{korea_row.sell_14k:,.0f}")
                    premium_pct = (korea_row.buy_3_75g - per_don) / per_don * 100
                    sign = "+" if premium_pct > 0 else ""
                    lines.append(f"   프리미엄 {sign}{premium_pct:.2f}% (국내 살때 vs 국제)")
            
            elif unit_type == 1:  # lb (구리/알루미늄/니켈/아연/납)
                # 1lb = 0.453592kg
                per_kg = usd_price / 0.453592
                krw_per_kg = per_kg * usd_krw
                
                lines.append(f"{emoji} {name}")
                lines.append(f"1kg = ₩{krw_per_kg:,.0f}")
                lines.append(f"국제가격 = ${usd_price:,.4f}/lb")
            
            # 전일대비
            if usd_price_yesterday:
                change = usd_price - usd_price_yesterday
                change_percent = (change / usd_price_yesterday) * 100
                
                if change > 0:
                    emoji_change = "🔺"
                    sign = "+"
                elif change < 0:
                    emoji_change = "🔻"
                    sign = ""
                else:
                    emoji_change = "➖"
                    sign = ""
                
                lines.append(f"{emoji_change} 전일대비 {sign}${abs(change):.2f} ({sign}{change_percent:.2f}%)")
            
            return lines
        
        lines = []
        lines.append("🥇 금속 시세")
        lines.append("⚡ LIVE")
        lines.append("")
        if market_today.date != today:
            lines.append(f"※ 최신 데이터 기준: {market_today.date}")
            lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")

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
        
        # 금 (oz)
        lines.extend(format_metal(
            "금 (Gold)", "💛",
            market_today.gold_usd,
            market_yesterday.gold_usd if market_yesterday else None,
            0,
            korea_gold,
        ))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 은 (oz)
        lines.extend(format_metal(
            "은 (Silver)", "⚪",
            market_today.silver_usd,
            market_yesterday.silver_usd if market_yesterday else None,
            0,
            korea_silver,
        ))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 백금 (oz)
        lines.extend(format_metal(
            "백금 (Platinum)", "⚪",
            market_today.platinum_usd,
            market_yesterday.platinum_usd if market_yesterday else None,
            0,
            korea_platinum,
        ))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 팔라디움 (oz)
        lines.extend(format_metal(
            "팔라디움 (Palladium)", "⚪",
            market_today.palladium_usd,
            market_yesterday.palladium_usd if market_yesterday else None,
            0
        ))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 구리 (lb)
        lines.extend(format_metal(
            "구리 (Copper)", "🟤",
            market_today.copper_usd,
            market_yesterday.copper_usd if market_yesterday else None,
            1
        ))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 알루미늄 (lb)
        lines.extend(format_metal(
            "알루미늄 (Aluminum)", "⚪",
            market_today.aluminum_usd,
            market_yesterday.aluminum_usd if market_yesterday else None,
            1
        ))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 니켈 (lb)
        lines.extend(format_metal(
            "니켈 (Nickel)", "⚪",
            market_today.nickel_usd,
            market_yesterday.nickel_usd if market_yesterday else None,
            1
        ))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 아연 (lb)
        lines.extend(format_metal(
            "아연 (Zinc)", "⚪",
            market_today.zinc_usd,
            market_yesterday.zinc_usd if market_yesterday else None,
            1
        ))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 납 (lb)
        lines.extend(format_metal(
            "납 (Lead)", "⚪",
            market_today.lead_usd,
            market_yesterday.lead_usd if market_yesterday else None,
            1
        ))
        
        await update.message.reply_text("\n".join(lines))
    except Exception:
        logger.exception("metal_command failed")
        await update.message.reply_text("🥇 금속 시세 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
    finally:
        db.close()


async def market_indices_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """시장 지수 조회 - 메뉴 표시"""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇸 미국지수", callback_data="mkt:us"),
            InlineKeyboardButton("🇯🇵🇨🇳 아시아지수", callback_data="mkt:asia"),
        ],
        [
            InlineKeyboardButton("🇪🇺 유럽지수", callback_data="mkt:europe"),
            InlineKeyboardButton("🇺🇸 미국주식", callback_data="mkt:us_stocks"),
        ],
        [
            InlineKeyboardButton("🇰🇷 KOSPI TOP5", callback_data="mkt:kospi"),
            InlineKeyboardButton("🇰🇷 KOSDAQ TOP5", callback_data="mkt:kosdaq"),
        ],
    ])

    await update.message.reply_text(
        "📊 시장지수 조회\n\n"
        "원하시는 항목을 선택해주세요.",
        reply_markup=keyboard
    )


async def on_market_index_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """시장 지수 콜백 핸들러"""
    from backend.app.collectors.market_collector import (
        fetch_us_indices,
        fetch_asian_indices,
        fetch_european_indices,
        fetch_us_stocks,
        fetch_kospi_top5,
        fetch_kosdaq_top5,
    )

    query = update.callback_query
    await query.answer()

    # callback_data 형식: "mkt:us", "mkt:asia" 등
    category = query.data.split(":")[1]

    try:
        lines = []

        if category == "us":
            lines.append("🇺🇸 미국 주요 지수")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            indices = fetch_us_indices()
            for idx in indices:
                emoji = "🔺" if "+" in idx["change_rate"] else "🔻" if "-" in idx["change_rate"] else "➖"
                lines.append(f"{emoji} {idx['name']}: {idx['price']} ({idx['change_rate']})")

        elif category == "asia":
            lines.append("🇯🇵🇨🇳🇭🇰 아시아 주요 지수")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            indices = fetch_asian_indices()
            for idx in indices:
                emoji = "🔺" if "+" in idx["change_rate"] else "🔻" if "-" in idx["change_rate"] else "➖"
                lines.append(f"{emoji} {idx['name']}: {idx['price']} ({idx['change_rate']})")

        elif category == "europe":
            lines.append("🇪🇺 유럽 주요 지수")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            indices = fetch_european_indices()
            for idx in indices:
                emoji = "🔺" if "+" in idx["change_rate"] else "🔻" if "-" in idx["change_rate"] else "➖"
                lines.append(f"{emoji} {idx['name']}: {idx['price']} ({idx['change_rate']})")

        elif category == "us_stocks":
            lines.append("🇺🇸 미국 주요 개별주식")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            stocks = fetch_us_stocks()
            for stock in stocks:
                emoji = "🔺" if "+" in stock["change_rate"] else "🔻" if "-" in stock["change_rate"] else "➖"
                lines.append(f"{emoji} {stock['name']}: {stock['price']} ({stock['change_rate']})")

        elif category == "kospi":
            lines.append("🇰🇷 KOSPI 시가총액 TOP 5")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            stocks = fetch_kospi_top5()
            for idx, stock in enumerate(stocks[:5], 1):
                medal = ["🥇", "🥈", "🥉", "🏅", "🎖️"][idx - 1]
                emoji = "🔺" if "+" in str(stock.get("change_rate", "")) else "🔻" if "-" in str(stock.get("change_rate", "")) else "➖"
                lines.append(f"{medal} {stock['name']}")
                lines.append(f"   💵 {stock['price']} {emoji} {stock.get('change_rate', '')}")

        elif category == "kosdaq":
            lines.append("🇰🇷 KOSDAQ 시가총액 TOP 5")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            stocks = fetch_kosdaq_top5()
            for idx, stock in enumerate(stocks[:5], 1):
                medal = ["🥇", "🥈", "🥉", "🏅", "🎖️"][idx - 1]
                emoji = "🔺" if "+" in str(stock.get("change_rate", "")) else "🔻" if "-" in str(stock.get("change_rate", "")) else "➖"
                lines.append(f"{medal} {stock['name']}")
                lines.append(f"   💵 {stock['price']} {emoji} {stock.get('change_rate', '')}")

        if not lines:
            lines.append("데이터를 불러올 수 없습니다.")

        await query.edit_message_text("\n".join(lines))

    except Exception as e:
        logger.exception("on_market_index_callback failed")
        await query.edit_message_text("📊 시장 지수 조회 중 오류가 발생했습니다.")


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """뉴스 카테고리 선택 메뉴"""
    text = "📰 뉴스 카테고리를 선택하세요"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("사회", callback_data="news:society"),
            InlineKeyboardButton("경제", callback_data="news:economy"),
        ],
        [
            InlineKeyboardButton("문화", callback_data="news:culture"),
            InlineKeyboardButton("연예", callback_data="news:entertainment"),
        ],
    ])
    
    await update.message.reply_text(text, reply_markup=keyboard)


async def on_news_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """뉴스 카테고리 콜백 처리"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import NewsDaily
    from datetime import date, datetime, timedelta
    from sqlalchemy import func
    
    query = update.callback_query
    await query.answer()
    
    data = query.data  # 예: "news:society"
    parts = data.split(":")
    if len(parts) != 2:
        return
    
    category = parts[1]
    
    category_names = {
        "society": "사회",
        "economy": "경제",
        "culture": "문화",
        "entertainment": "연예"
    }
    
    db = SessionLocal()

    try:
        # 오늘자 데이터만 사용
        candidate_limit = 50
        news_list = db.query(NewsDaily).filter(
            NewsDaily.category == category,
            NewsDaily.date == datetime.now(timezone(timedelta(hours=9))).date()
        ).order_by(
            NewsDaily.hot_score.desc(),
            NewsDaily.created_at.desc()
        ).limit(candidate_limit).all()

        if news_list:
            from backend.app.utils.dedup import remove_duplicate_news
            news_list = remove_duplicate_news(news_list)[:5]
        
        if not news_list:
            await query.edit_message_text(
                f"📰 {category_names.get(category, category)} 뉴스가 아직 수집되지 않았습니다.\n\n"
                "잠시 후 다시 시도해 주세요."
            )
            return
        
        lines = []
        lines.append(f"📰 {category_names.get(category, category)} Top 5")
        lines.append("")
        
        for idx, news in enumerate(news_list, 1):
            lines.append(f"{idx}. {news.title}")
            lines.append(f"🔗 {news.url}")
            lines.append("")
        
        await query.edit_message_text("\n".join(lines))
    
    finally:
        db.close()


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """알림 구독"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import Subscriber
    
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    
    try:
        subscriber = db.query(Subscriber).filter(Subscriber.chat_id == chat_id).first()
        
        if not subscriber:
            subscriber = Subscriber(
                chat_id=chat_id,
                subscribed_alert=True,
                custom_time="09:10"  # 기본 알림 시간 설정
            )
            db.add(subscriber)
            db.commit()

            # 즉시 스케줄러에 등록
            try:
                from backend.app.scheduler.jobs import schedule_user_alerts
                schedule_user_alerts()
            except Exception as e:
                print(f"스케줄러 등록 오류: {e}")

            await update.message.reply_text(
                "✅ 아침 알림 구독이 완료되었습니다!\n\n"
                "📍 알림 시간: 매일 09:10 (전일대비 포함)\n"
                "📍 내용: 뉴스, 환율, 코인, KOSPI/나스닥 지수, KOSPI Top5, 금속\n\n"
                "⏰ /set_time 으로 시간을 변경할 수 있습니다.\n"
                "⚙️ /settings 로 설정을 확인하세요."
            )
        else:
            if subscriber.subscribed_alert:
                await update.message.reply_text(
                    "ℹ️ 이미 알림을 구독 중입니다.\n\n"
                    f"📍 알림 시간: 매일 {subscriber.custom_time or '09:05'}\n"
                    "⚙️ /settings 로 설정을 확인하세요."
                )
            else:
                subscriber.subscribed_alert = True
                if not subscriber.custom_time:
                    subscriber.custom_time = "09:10"
                db.commit()

                # 즉시 스케줄러에 등록
                try:
                    from backend.app.scheduler.jobs import schedule_user_alerts
                    schedule_user_alerts()
                except Exception as e:
                    print(f"스케줄러 등록 오류: {e}")

                await update.message.reply_text(
                    "✅ 알림 구독이 다시 활성화되었습니다!\n\n"
                    f"📍 알림 시간: 매일 {subscriber.custom_time}\n"
                    "⚙️ /settings 로 설정을 확인하세요."
                )
    finally:
        db.close()


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """알림 구독 취소"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import Subscriber
    
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    
    try:
        subscriber = db.query(Subscriber).filter(Subscriber.chat_id == chat_id).first()
        
        if subscriber:
            subscriber.subscribed_alert = False
            db.commit()
            
            await update.message.reply_text(
                "✅ 아침 알림 구독이 취소되었습니다.\n\n"
                "자동 알림을 받지 않습니다.\n"
                "📈 '오늘 요약' 버튼으로 언제든 확인 가능합니다.\n\n"
                "다시 구독하려면 /subscribe 를 입력하세요."
            )
        else:
            await update.message.reply_text(
                "ℹ️ 구독 정보가 없습니다.\n\n"
                "/subscribe 로 알림을 구독할 수 있습니다."
            )
    finally:
        db.close()


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """현재 설정 확인"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import Subscriber
    
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    
    try:
        subscriber = db.query(Subscriber).filter(Subscriber.chat_id == chat_id).first()
        
        if subscriber:
            status = "✅ 활성화" if subscriber.subscribed_alert else "❌ 비활성화"
            alarm_time = subscriber.custom_time or "09:05"
            
            await update.message.reply_text(
                f"⚙️ 현재 설정\n\n"
                f"📍 알림 상태: {status}\n"
                f"⏰ 알림 시간: 매일 {alarm_time}\n"
                f"📱 Chat ID: {chat_id}\n\n"
                "━━━━━━━━━━━━━━\n"
                "명령어:\n"
                "/subscribe - 알림 구독\n"
                "/unsubscribe - 알림 구독 취소\n"
                "/set_time - 알림 시간 변경\n"
                "/today - 오늘 요약 보기"
            )
        else:
            await update.message.reply_text(
                "⚙️ 설정 정보가 없습니다.\n\n"
                "/subscribe 로 알림을 구독하세요."
            )
    finally:
        db.close()


async def set_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """알림 시간 설정 - 버튼으로 간편하게!"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import Subscriber
    import re
    
    chat_id = str(update.effective_chat.id)
    args = context.args or []
    
    # args가 없으면 → 버튼 표시!
    if not args:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("07:00", callback_data="settime:07:00"),
                InlineKeyboardButton("07:30", callback_data="settime:07:30"),
                InlineKeyboardButton("08:00", callback_data="settime:08:00"),
            ],
            [
                InlineKeyboardButton("08:30", callback_data="settime:08:30"),
                InlineKeyboardButton("09:00", callback_data="settime:09:00"),
                InlineKeyboardButton("09:05", callback_data="settime:09:05"),
            ],
            [
                InlineKeyboardButton("09:30", callback_data="settime:09:30"),
                InlineKeyboardButton("10:00", callback_data="settime:10:00"),
            ],
        ])
        
        await update.message.reply_text(
            "⏰ 알림 시간을 선택하세요!\n\n"
            "버튼을 클릭하면 바로 설정됩니다.\n\n"
            "💡 09:05 이후 시간은 전일대비가 포함됩니다.\n"
            "💡 다른 시간을 원하시면:\n"
            "/set_time 07:45 처럼 직접 입력하세요.",
            reply_markup=keyboard
        )
        return
    
    time_str = args[0]
    
    # 시간 형식 검증 (HH:MM)
    if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time_str):
        await update.message.reply_text(
            "❌ 잘못된 시간 형식입니다.\n\n"
            "올바른 형식: HH:MM (예: 08:30)\n"
            "시간: 00-23\n"
            "분: 00-59"
        )
        return
    
    db = SessionLocal()
    
    try:
        subscriber = db.query(Subscriber).filter(Subscriber.chat_id == chat_id).first()
        
        if not subscriber:
            # 구독자가 아니면 생성
            subscriber = Subscriber(
                chat_id=chat_id,
                subscribed_alert=True,
                custom_time=time_str
            )
            db.add(subscriber)
            db.commit()
            
            await update.message.reply_text(
                f"✅ 알림 시간이 설정되었습니다!\n\n"
                f"⏰ 매일 {time_str}에 알림을 받습니다.\n\n"
                "알림이 자동으로 구독되었습니다.\n"
                "구독 취소: /unsubscribe"
            )
        else:
            subscriber.custom_time = time_str
            if not subscriber.subscribed_alert:
                subscriber.subscribed_alert = True
            db.commit()
            
            await update.message.reply_text(
                f"✅ 알림 시간이 변경되었습니다!\n\n"
                f"⏰ 매일 {time_str}에 알림을 받습니다.\n\n"
                "현재 설정: /settings"
            )
    finally:
        db.close()


async def on_set_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """시간 설정 콜백 처리"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import Subscriber
    
    query = update.callback_query
    await query.answer()
    
    # callback_data 형식: "settime:08:30"
    time_str = query.data.replace("settime:", "")
    chat_id = str(query.message.chat_id)
    
    db = SessionLocal()
    
    try:
        subscriber = db.query(Subscriber).filter(Subscriber.chat_id == chat_id).first()
        
        if not subscriber:
            subscriber = Subscriber(
                chat_id=chat_id,
                subscribed_alert=True,
                custom_time=time_str
            )
            db.add(subscriber)
            db.commit()
            
            await query.edit_message_text(
                f"✅ 알림 시간이 설정되었습니다!\n\n"
                f"⏰ 매일 {time_str}에 알림을 받습니다.\n\n"
                "알림이 자동으로 구독되었습니다.\n"
                "구독 취소: /unsubscribe"
            )
        else:
            subscriber.custom_time = time_str
            if not subscriber.subscribed_alert:
                subscriber.subscribed_alert = True
            db.commit()
            
            await query.edit_message_text(
                f"✅ 알림 시간이 변경되었습니다!\n\n"
                f"⏰ 매일 {time_str}에 알림을 받습니다.\n\n"
                "현재 설정: /settings"
            )
    finally:
        db.close()


async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """메인 키보드 버튼 텍스트 처리."""
    text = (update.message.text or "").strip()

    if text == "🪙 BTC":
        await crypto_command(update, context, symbol="BTC")
    elif text == "📊 시장 지수":
        await market_indices_command(update, context)
    elif text == "🪙 전체 암호화폐":
        await all_crypto_command(update, context)
    elif text == "📰 전체 뉴스":
        await news_command(update, context)
    elif text == "📈 오늘 요약":
        await today_command(update, context)
    elif text == "💵 환율":
        await fx_command(update, context)
    elif text == "🥇 금속 조회하기":
        await metal_command(update, context)
    elif text in ("🎰 로또 번호 생성", "🎰 로또 번호"):
        await lotto_command(update, context)
    elif text.isdigit() and 1 <= len(text) <= 4:
        try:
            from backend.app.handlers.lotto.lotto_handler import show_lotto_result
            draw_no = int(text)
            if 1 <= draw_no <= 1300:
                await show_lotto_result(update.message, draw_no)
                return
        except Exception as e:
            print(f"로또 조회 오류: {e}")
            pass
    else:
        await update.message.reply_text("아래 버튼을 이용해보세요 😊")


def _build_application(token: str):
    application = ApplicationBuilder().token(token).build()
    application.add_error_handler(_on_app_error)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("btc", btc_command))
    application.add_handler(CommandHandler("crypto", crypto_command))
    application.add_handler(CommandHandler("fx", fx_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("lotto", lotto_command))
    application.add_handler(CommandHandler("lotto_result", lotto_result_command))
    application.add_handler(CommandHandler("lotto_performance", lotto_performance_command))
    application.add_handler(CommandHandler("set_time", set_time_command))
    application.add_handler(CommandHandler("collect", collect_command))  # 관리자용 수동 수집
    application.add_handler(CommandHandler("stats", stats_command))  # 관리자용 통계 조회
    application.add_handler(CommandHandler("restore_subscribers", restore_subscribers_command))  # 관리자용 구독자 복원
    application.add_handler(CallbackQueryHandler(on_timeframe_callback, pattern="^tf:"))
    application.add_handler(CallbackQueryHandler(on_crypto_callback, pattern="^crypto_"))
    application.add_handler(CallbackQueryHandler(on_set_time_callback, pattern="^settime:"))
    application.add_handler(CallbackQueryHandler(on_news_category_callback, pattern="^news:"))
    application.add_handler(CallbackQueryHandler(on_market_index_callback, pattern="^mkt:"))
    application.add_handler(CallbackQueryHandler(lotto_generate_callback, pattern="^lotto_gen:"))
    application.add_handler(CallbackQueryHandler(lotto_result_callback, pattern="^lotto_result:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    return application


def main() -> None:
    token = settings.TELEGRAM_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN is not set in environment variables")

    # 봇 시작 시 오래된 속보만 "전송됨"으로 표시 (중복 알림 방지)
    # 최근 1시간 이내 속보는 보존하여 재시작 후에도 전송 가능하도록 함
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import NewsDaily
    from datetime import datetime, timedelta, timezone as dt_timezone

    db = SessionLocal()
    try:
        kst = dt_timezone(timedelta(hours=9))
        cutoff_time = datetime.now(kst) - timedelta(hours=1)

        # 1시간 이전 미전송 속보만 전송됨으로 표시
        updated_count = db.query(NewsDaily).filter(
            NewsDaily.is_breaking.is_(True),
            NewsDaily.alert_sent.is_(False),
            NewsDaily.created_at < cutoff_time
        ).update({NewsDaily.alert_sent: True})
        db.commit()
        print(f"✅ 오래된 속보 초기화 완료 ({updated_count}건, 1시간 이전 뉴스)")
    except Exception as e:
        print(f"⚠️ 속보 초기화 실패: {e}")
        db.rollback()
    finally:
        db.close()

    retry_delay = 30
    while True:
        application = _build_application(token)
        try:
            application.run_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"],
                poll_interval=1.0,
                timeout=30
            )
            break
        except Exception as e:
            logger.exception("Telegram polling crashed: %s. Retry in %ss", e, retry_delay)
            time.sleep(retry_delay)


if __name__ == "__main__":
    main()
