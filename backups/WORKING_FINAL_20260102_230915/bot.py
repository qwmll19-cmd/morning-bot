import logging
from typing import Optional, Dict, Any
from datetime import datetime, time as time_type
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
from backend.app.handlers.lotto.lotto_handler import lotto_command, lotto_result_callback, lotto_result_message

logging.basicConfig(level=logging.INFO)
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
UNIRATE_BASE_URL = "https://api.unirateapi.com/api"

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
    text = (
        "안녕하세요, 모닝 마켓 봇입니다 🌅\n\n"
        "아래 버튼을 눌러 바로 사용할 수 있어요.\n"
        "🪙 BTC - 비트코인 시세\n"
        "📊 시장 지수 - KOSPI/나스닥 지수 + Top5\n"
        "🪙 전체 암호화폐 - ETH/SOL/XRP/TRX 한 번에 보기\n"
        "📰 전체 뉴스 - 사회/경제/문화/연예 카테고리별 Top 5\n"
        "📈 오늘 요약 - 종합 뉴스, 지수, 환율, 금속 (09:05 이후 전일대비 포함)\n"
        "💵 환율 - 주요 환율 확인\n"
        "🥇 금속 조회하기 - 금/은/구리/백금/팔라디움 가격 조회\n\n"
        "━━━━━━━━━━━━━━\n"
        "🔔 자동 알림 받기\n\n"
        "/subscribe - 매일 아침 자동 알림 구독\n"
        "/set_time - 알림 시간 설정 (버튼 클릭)\n"
        "/settings - 현재 설정 확인\n"
        "/unsubscribe - 알림 구독 취소\n\n"
        "자동 알림은 원하는 시간에 받을 수 있습니다!"
    )
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """오늘 요약 - DB에서 직접 가져오기 (09:05 기준)"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import MarketDaily, NewsDaily
    from datetime import date, timedelta
    
    db = SessionLocal()
    
    try:
        # 현재 시간 확인
        now = datetime.now()
        cutoff_time = time_type(9, 5)  # 09:05
        
        # 09:05 이전이면 어제 데이터, 이후면 오늘 데이터
        if now.time() < cutoff_time:
            target_date = date.today() - timedelta(days=1)
            date_label = "어제"
        else:
            target_date = date.today()
            date_label = "오늘"
        
        # 시장 데이터 조회
        market = db.query(MarketDaily).filter(
            MarketDaily.date == target_date
        ).order_by(MarketDaily.id.desc()).first()
        
        # 뉴스 조회
        news_list = db.query(NewsDaily).filter(
            NewsDaily.date == target_date,
            NewsDaily.is_top.is_(True)
        ).order_by(NewsDaily.created_at.desc()).limit(10).all()
        
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
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("")
            
            # KOSPI Top5
            if market.kospi_top5 and isinstance(market.kospi_top5, list):
                lines.append("📈 KOSPI TOP 5")
                for idx, stock in enumerate(market.kospi_top5[:5], 1):
                    medal = ["🥇", "🥈", "🥉", "🏅", "🎖️"][idx-1]
                    name = stock.get("name", "")
                    price = stock.get("price", "")
                    change_rate = stock.get("change_rate", "")
                    emoji = "🔺" if "+" in str(change_rate) else "🔻" if "-" in str(change_rate) else "➖"
                    lines.append(f"{medal} {idx}위 {name}")
                    lines.append(f"   {price} {emoji} {change_rate}")
                lines.append("")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("")
            
            # 금속 시세
            if market.gold_usd and market.usd_krw:
                lines.append("🥇 금속 시세")
                
                # 어제 데이터 조회 (전일대비용)
                yesterday_date = target_date - timedelta(days=1)
                market_yesterday = db.query(MarketDaily).filter(
                    MarketDaily.date == yesterday_date
                ).order_by(MarketDaily.id.desc()).first()
                
                # 금
                gold_per_gram = market.gold_usd / 31.1035
                gold_per_don = gold_per_gram * 3.75 * market.usd_krw
                lines.append(f"💛 금 (1돈) ₩{gold_per_don:,.0f}")
                if market_yesterday and market_yesterday.gold_usd:
                    gold_change = market.gold_usd - market_yesterday.gold_usd
                    gold_change_pct = (gold_change / market_yesterday.gold_usd) * 100
                    emoji = "��" if gold_change > 0 else "🔻" if gold_change < 0 else "➖"
                    sign = "+" if gold_change > 0 else ""
                    lines.append(f"   {emoji} {sign}${gold_change:.2f} ({sign}{gold_change_pct:.2f}%)")
                
                
                # 은
                if market.silver_usd:
                    silver_per_gram = market.silver_usd / 31.1035
                    silver_per_don = silver_per_gram * 3.75 * market.usd_krw
                    lines.append(f"⚪ 은 (1돈) ₩{silver_per_don:,.0f}")
                    if market_yesterday and market_yesterday.silver_usd:
                        silver_change = market.silver_usd - market_yesterday.silver_usd
                        silver_change_pct = (silver_change / market_yesterday.silver_usd) * 100
                        emoji = "🔺" if silver_change > 0 else "🔻" if silver_change < 0 else "➖"
                        sign = "+" if silver_change > 0 else ""
                        lines.append(f"   {emoji} {sign}${silver_change:.2f} ({sign}{silver_change_pct:.2f}%)")
                    
                
                # 구리
                if market.copper_usd:
                    copper_per_kg = market.copper_usd / 0.453592  # lb to kg
                    copper_krw = copper_per_kg * market.usd_krw
                    lines.append(f"🟤 구리 (1kg) ₩{copper_krw:,.0f}")
                    if market_yesterday and market_yesterday.copper_usd:
                        copper_change = market.copper_usd - market_yesterday.copper_usd
                        copper_change_pct = (copper_change / market_yesterday.copper_usd) * 100
                        emoji = "🔺" if copper_change > 0 else "🔻" if copper_change < 0 else "➖"
                        sign = "+" if copper_change > 0 else ""
                        lines.append(f"   {emoji} {sign}${copper_change:.4f} ({sign}{copper_change_pct:.2f}%)")
                    
                
                # 백금
                if market.platinum_usd:
                    platinum_per_gram = market.platinum_usd / 31.1035
                    platinum_per_don = platinum_per_gram * 3.75 * market.usd_krw
                    lines.append(f"⚪ 백금 (1돈) ₩{platinum_per_don:,.0f}")
                    if market_yesterday and market_yesterday.platinum_usd:
                        platinum_change = market.platinum_usd - market_yesterday.platinum_usd
                        platinum_change_pct = (platinum_change / market_yesterday.platinum_usd) * 100
                        emoji = "🔺" if platinum_change > 0 else "🔻" if platinum_change < 0 else "➖"
                        sign = "+" if platinum_change > 0 else ""
                        lines.append(f"   {emoji} {sign}${platinum_change:.2f} ({sign}{platinum_change_pct:.2f}%)")
                    
                
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
    
    # DB에서 환율 가져오기
    exchange_rate = 1430.0
    db = SessionLocal()
    try:
        market = db.query(MarketDaily).filter(
            MarketDaily.date == date.today()
        ).order_by(MarketDaily.id.desc()).first()
        if market and market.usd_krw:
            exchange_rate = market.usd_krw
    except:
        pass
    finally:
        db.close()
    
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
    """환율 조회 (DB에서 + 교차환율)"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import MarketDaily
    from datetime import date, timedelta
    
    db = SessionLocal()
    
    try:
        market = db.query(MarketDaily).filter(
            MarketDaily.date == date.today()
        ).order_by(MarketDaily.id.desc()).first()
        
        yesterday = date.today() - timedelta(days=1)
        market_yesterday = db.query(MarketDaily).filter(
            MarketDaily.date == yesterday
        ).order_by(MarketDaily.id.desc()).first()
        
        if not market or not market.usd_krw:
            await update.message.reply_text("💱 환율 데이터가 아직 수집되지 않았습니다.")
            return
        
        usd_krw = market.usd_krw
        yesterday_usd_krw = market_yesterday.usd_krw if market_yesterday else None
        
        # 고정 환율
        usd_eur = 0.92
        usd_jpy = 149.0
        usd_cny = 7.24
        usd_thb = 34.5
        usd_php = 56.5
        
        msg_lines = []
        msg_lines.append("💱 글로벌 환율")
        msg_lines.append("🌍 LIVE EXCHANGE RATES")
        msg_lines.append("")
        msg_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        msg_lines.append("")
        msg_lines.append("🇺🇸 USD → 🇰🇷 KRW")
        msg_lines.append(f"💵 $1 = ₩{usd_krw:,.2f}")
        
        if yesterday_usd_krw:
            change = usd_krw - yesterday_usd_krw
            change_percent = (change / yesterday_usd_krw) * 100
            emoji = "🔺" if change > 0 else "🔻" if change < 0 else "➖"
            sign = "+" if change > 0 else ""
            msg_lines.append(f"{emoji} 전일대비 {sign}{change:.2f} ({sign}{change_percent:.2f}%)")
        
        msg_lines.append("")
        msg_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        msg_lines.append("")
        msg_lines.append("기타 환율")
        msg_lines.append("")
        
        eur_krw = usd_krw / usd_eur
        msg_lines.append(f"🇪🇺 €1 = ₩{eur_krw:,.2f}")
        
        jpy_krw_100 = 100 * (usd_krw / usd_jpy)
        msg_lines.append(f"🇯🇵 ¥100 = ₩{jpy_krw_100:,.2f}")
        
        cny_krw = usd_krw / usd_cny
        msg_lines.append(f"🇨🇳 ¥1 = ₩{cny_krw:,.2f}")
        
        thb_krw = usd_krw / usd_thb
        msg_lines.append(f"🇹🇭 ฿1 = ₩{thb_krw:,.2f}")
        
        php_krw = usd_krw / usd_php
        msg_lines.append(f"🇵🇭 ₱1 = ₩{php_krw:,.2f}")
        
        await update.message.reply_text("\n".join(msg_lines))
    
    finally:
        db.close()


async def metal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """금속 시세 조회 (DB에서) - 전체 금속"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import MarketDaily
    from datetime import date, timedelta
    
    db = SessionLocal()
    
    try:
        today = date.today()
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
            await update.message.reply_text(
                "🥇 금속 시세 데이터가 아직 수집되지 않았습니다.\n\n"
                "잠시 후 다시 시도해 주세요."
            )
            return
        
        def format_metal(name, emoji, usd_price, usd_price_yesterday, unit_type):
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
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 금 (oz)
        lines.extend(format_metal(
            "금 (Gold)", "💛",
            market_today.gold_usd,
            market_yesterday.gold_usd if market_yesterday else None,
            0
        ))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 은 (oz)
        lines.extend(format_metal(
            "은 (Silver)", "⚪",
            market_today.silver_usd,
            market_yesterday.silver_usd if market_yesterday else None,
            0
        ))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 백금 (oz)
        lines.extend(format_metal(
            "백금 (Platinum)", "⚪",
            market_today.platinum_usd,
            market_yesterday.platinum_usd if market_yesterday else None,
            0
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
    finally:
        db.close()


async def market_indices_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """시장 지수 조회 - KOSPI/나스닥 + Top5"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import MarketDaily
    from datetime import date
    
    db = SessionLocal()
    
    try:
        # 오늘자 MarketDaily 조회
        market = db.query(MarketDaily).filter(
            MarketDaily.date == date.today()
        ).order_by(MarketDaily.id.desc()).first()
        
        if not market:
            await update.message.reply_text(
                "📊 시장 지수 데이터가 아직 수집되지 않았습니다.\n\n"
                "잠시 후 다시 시도해 주세요."
            )
            return
        
        lines = []
        lines.append("📊 시장 지수")
        lines.append("⚡ LIVE")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # KOSPI 지수
        if market.kospi_index:
            lines.append("🇰🇷 KOSPI")
            lines.append(f"   {market.kospi_index:,.2f}")
            
            if market.kospi_index_change is not None and market.kospi_index_change_pct is not None:
                emoji = "🔺" if market.kospi_index_change > 0 else "🔻" if market.kospi_index_change < 0 else "➖"
                sign = "+" if market.kospi_index_change > 0 else ""
                lines.append(f"   {emoji} {sign}{market.kospi_index_change:.2f} ({sign}{market.kospi_index_change_pct:.2f}%)")
            
            lines.append("")
        
        # 나스닥 지수
        if market.nasdaq_index:
            lines.append("🇺🇸 나스닥 100")
            lines.append(f"   {market.nasdaq_index:,.2f}")
            
            if market.nasdaq_index_change is not None and market.nasdaq_index_change_pct is not None:
                emoji = "🔺" if market.nasdaq_index_change > 0 else "🔻" if market.nasdaq_index_change < 0 else "➖"
                sign = "+" if market.nasdaq_index_change > 0 else ""
                lines.append(f"   {emoji} {sign}{market.nasdaq_index_change:.2f} ({sign}{market.nasdaq_index_change_pct:.2f}%)")
            
            lines.append("")
        
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # KOSPI Top5
        if market.kospi_top5 and isinstance(market.kospi_top5, list):
            lines.append("📈 KOSPI TOP 5")
            lines.append("")
            for idx, stock in enumerate(market.kospi_top5[:5], 1):
                name = stock.get("name", "")
                price = stock.get("price", "")
                change = stock.get("change", "")
                change_rate = stock.get("change_rate", "")
                
                # 메달 이모지
                medal = ["🥇", "🥈", "🥉", "🏅", "🎖️"][idx-1]
                
                # 등락 이모지
                emoji = "🔺" if "+" in str(change_rate) else "🔻" if "-" in str(change_rate) else "➖"
                
                lines.append(f"{medal} {idx}위 {name}")
                lines.append(f"   💵 {price}")
                lines.append(f"   {emoji} {change} ({change_rate})")
                lines.append("")
        
        await update.message.reply_text("\n".join(lines))
    finally:
        db.close()


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
    from datetime import date
    
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
        # 오늘자 해당 카테고리 뉴스 조회
        news_list = db.query(NewsDaily).filter(
            NewsDaily.date == date.today(),
            NewsDaily.category == category
        ).order_by(NewsDaily.hot_score.desc()).limit(5).all()
        
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
                subscribed_alert=True
            )
            db.add(subscriber)
            db.commit()
            
            await update.message.reply_text(
                "✅ 아침 알림 구독이 완료되었습니다!\n\n"
                "📍 알림 시간: 매일 09:05 (전일대비 포함)\n"
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
                db.commit()
                
                await update.message.reply_text(
                    "✅ 알림 구독이 다시 활성화되었습니다!\n\n"
                    f"📍 알림 시간: 매일 {subscriber.custom_time or '09:05'}\n"
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
    elif text == "🎰 로또 번호 생성":
        await lotto_command(update, context)
    else:
        await update.message.reply_text("아래 버튼을 이용해보세요 😊")


def main() -> None:
    token = settings.TELEGRAM_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN is not set in environment variables")

    # 봇 시작 시 기존 속보 모두 "전송됨"으로 표시 (중복 알림 방지)
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import NewsDaily
    db = SessionLocal()
    try:
        db.query(NewsDaily).filter(
            NewsDaily.is_breaking.is_(True),
            NewsDaily.alert_sent.is_(False)
        ).update({NewsDaily.alert_sent: True})
        db.commit()
        print("✅ 기존 속보 초기화 완료")
    except Exception as e:
        print(f"⚠️ 속보 초기화 실패: {e}")
    finally:
        db.close()

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
    application.add_handler(CommandHandler("set_time", set_time_command))
    application.add_handler(CallbackQueryHandler(on_timeframe_callback, pattern="^tf:"))
    application.add_handler(CallbackQueryHandler(on_crypto_callback, pattern="^crypto_"))
    application.add_handler(CallbackQueryHandler(on_set_time_callback, pattern="^settime:"))
    application.add_handler(CallbackQueryHandler(on_news_category_callback, pattern="^news:"))
    application.add_handler(CallbackQueryHandler(lotto_result_callback, pattern="^lotto_result_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))

    application.run_polling()


if __name__ == "__main__":
    main()
