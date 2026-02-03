from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import time
from typing import Any, Dict, List, Optional, Tuple
import logging

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.models import MarketDaily

logger = logging.getLogger(__name__)

COINPAPRIKA_TICKER_URL = "https://api.coinpaprika.com/v1/tickers"
UNIRATE_BASE_URL = "https://api.unirateapi.com/api"
METALPRICE_BASE_URL = "https://api.metalpriceapi.com/v1/latest"
NAVER_KOSPI_MARKET_SUM_URL = (
    "https://finance.naver.com/sise/sise_market_sum.nhn?sosok=0&page=1"
)

# Metals.Dev API (전체 금속 시세)
METALSDEV_BASE_URL = "https://api.metals.dev/v1/latest"


def _get_with_retry(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 10.0,
    retries: int = 3,
    backoff: float = 1.5,
) -> Optional[httpx.Response]:
    """httpx GET 래퍼: 커넥션 리셋 등 일시 오류를 재시도."""
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                return resp
        except Exception as e:
            if attempt >= retries:
                logger.error(
                    "HTTP GET 실패 (종료) %s attempt %s/%s: %s",
                    url,
                    attempt,
                    retries,
                    e,
                    exc_info=True,
                )
                return None
            wait = backoff * attempt
            logger.warning(
                "HTTP GET 실패 (재시도) %s attempt %s/%s: %s -> %.1fs 후 재시도",
                url,
                attempt,
                retries,
                e,
                wait,
            )
            time.sleep(wait)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(str(value).replace(",", ""))
    except Exception:
        return None


def fetch_usd_krw_rate() -> Optional[float]:
    """UniRate API 를 사용해 USD/KRW 환율을 가져옵니다."""
    if not settings.UNIRATE_API_KEY:
        logger.warning("UNIRATE_API_KEY가 설정되지 않았습니다")
        return None
    
    resp = _get_with_retry(
        f"{UNIRATE_BASE_URL}/rates",
        params={"api_key": settings.UNIRATE_API_KEY, "from": "USD"},
        timeout=15.0,
        retries=3,
    )
    if resp is None:
        return None

    try:
        data = resp.json()
    except Exception as e:
        logger.error(f"USD/KRW 환율 응답 파싱 실패: {e}", exc_info=True)
        return None

    # 공식 문서 기준: { "rates": { "KRW": 1320.12, ... } } 구조를 가정
    rates = data.get("rates") or data.get("data") or {}
    krw = rates.get("KRW")

    if krw is None:
        logger.error(f"USD/KRW 환율을 응답에서 찾을 수 없습니다. 응답 구조: {list(data.keys())}")

    return _safe_float(krw)


def fetch_btc_from_coinpaprika() -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """CoinPaprika 에서 BTC 시세(USD)와 24h 변동률을 가져옵니다.
    KRW는 USD * usd_krw 환율로 계산합니다."""
    resp = _get_with_retry(
        f"{COINPAPRIKA_TICKER_URL}/btc-bitcoin",
        timeout=15.0,
        retries=3,
    )
    if resp is None:
        return None, None, None, None

    try:
        data = resp.json()
    except Exception as e:
        logger.error(f"BTC 시세 응답 파싱 실패 (CoinPaprika): {e}", exc_info=True)
        return None, None, None, None

    quotes = data.get("quotes", {})
    usd_quote = quotes.get("USD") or {}

    btc_usd = _safe_float(usd_quote.get("price"))
    btc_change_24h = _safe_float(usd_quote.get("percent_change_24h"))

    # USDT는 USD와 거의 동일하므로 같은 값 사용
    btc_usdt = btc_usd

    # KRW는 collect_market_daily에서 환율 곱해서 계산
    btc_krw = None

    return btc_usdt, btc_krw, btc_usd, btc_change_24h


def fetch_metals_from_metalprice() -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """MetalpriceAPI 에서 금/은 시세(USD 기준)를 가져옵니다.
    
    구리(XCU)는 유료 플랜만 가능하므로 제외합니다.

    MetalpriceAPI 의 latest 응답은 보통 '1 USD 로 살 수 있는 금속의 양' 이라서
    금 1oz 의 USD 가격을 얻으려면 1 / rate 형태로 변환해야 합니다.
    (정확한 스펙은 MetalpriceAPI 문서를 참고해서 필요시 조정)
    """
    if not settings.METALPRICE_API_KEY:
        return None, None, None

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                METALPRICE_BASE_URL,
                params={
                    "api_key": settings.METALPRICE_API_KEY,
                    "base": "USD",
                    "currencies": "XAU,XAG",  # 금, 은만 (구리는 유료)
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None, None, None

    rates = data.get("rates", {})

    gold_rate = _safe_float(rates.get("XAU"))
    silver_rate = _safe_float(rates.get("XAG"))

    def invert(v: Optional[float]) -> Optional[float]:
        try:
            if v is None or v == 0:
                return None
            return 1.0 / v
        except Exception:
            return None

    gold_usd = invert(gold_rate)
    silver_usd = invert(silver_rate)
    copper_usd = None  # 구리는 유료 플랜만 가능

    return gold_usd, silver_usd, copper_usd


def fetch_all_metals_from_metalsdev() -> Dict[str, Optional[float]]:
    """
    Metals.Dev API에서 전체 금속 시세 수집

    Returns:
        {
            'gold': float,
            'silver': float,
            'platinum': float,
            'copper': float,
            'palladium': float,
            'aluminum': float,
            'nickel': float,
            'zinc': float,
            'lead': float
        }
    """
    result = {
        'gold': None,
        'silver': None,
        'platinum': None,
        'copper': None,
        'palladium': None,
        'aluminum': None,
        'nickel': None,
        'zinc': None,
        'lead': None
    }

    # .env에서 API 키 가져오기
    api_key = settings.METALSDEV_API_KEY

    if not api_key:
        logger.warning("METALSDEV_API_KEY가 설정되지 않았습니다")
        return result

    url = f"{METALSDEV_BASE_URL}?api_key={api_key}&currency=USD&unit=toz"
    resp = _get_with_retry(url, timeout=20.0, retries=3)
    if resp is None:
        return result

    try:
        data = resp.json()
    except Exception as e:
        logger.error(f"금속 시세 응답 파싱 실패 (Metals.Dev): {e}", exc_info=True)
        return result

    if data.get('status') != 'success':
        logger.error(f"Metals.Dev API 응답 상태 오류: {data.get('status')}")
        return result

    metals = data.get('metals', {})

    # 금속별 추출 ($/toz)
    result['gold'] = _safe_float(metals.get('gold'))
    result['silver'] = _safe_float(metals.get('silver'))
    result['platinum'] = _safe_float(metals.get('platinum'))
    result['copper'] = _safe_float(metals.get('copper'))
    result['palladium'] = _safe_float(metals.get('palladium'))
    result['aluminum'] = _safe_float(metals.get('aluminum'))
    result['nickel'] = _safe_float(metals.get('nickel'))
    result['zinc'] = _safe_float(metals.get('zinc'))
    result['lead'] = _safe_float(metals.get('lead'))

    logger.info(f"금속 시세 수집 완료: 금=${result['gold']}, 은=${result['silver']}, 구리=${result['copper']}")

    return result


def fetch_kospi_top5() -> List[Dict[str, Any]]:
    """네이버 모바일 API에서 KOSPI 시가총액 상위 5종목을 가져옵니다.

    해외 IP에서도 접근 가능한 모바일 API 사용 (기존 웹 크롤링 대체)
    """
    url = "https://m.stock.naver.com/api/stocks/marketValue/KOSPI?page=1&pageSize=5"

    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"KOSPI TOP5 모바일 API 실패: {e}")
        return _fetch_kospi_top5_fallback()

    stocks = data.get("stocks", [])
    top5: List[Dict[str, Any]] = []

    for stock in stocks[:5]:
        name = stock.get("stockName", "")
        price = stock.get("closePrice", "")

        # 전일비 (예: "9,200" 또는 "-5,100")
        compare_price = stock.get("compareToPreviousClosePrice", "0")
        price_info = stock.get("compareToPreviousPrice", {})
        price_text = price_info.get("text", "")  # "상승" 또는 "하락"

        # 등락률 (예: "6.12")
        fluctuation = stock.get("fluctuationsRatio", "0")

        # change 포맷: "상승9,200" 또는 "하락5,100"
        if price_text == "상승":
            change = f"상승{compare_price}"
            change_rate = f"+{fluctuation}%"
        elif price_text == "하락":
            change = f"하락{compare_price}"
            change_rate = f"-{fluctuation}%"
        else:
            change = f"보합{compare_price}"
            change_rate = f"{fluctuation}%"

        top5.append({
            "name": name,
            "price": price,
            "change": change,
            "change_rate": change_rate,
        })

    return top5


def _fetch_kospi_top5_fallback() -> List[Dict[str, Any]]:
    """모바일 API 실패 시 기존 웹 크롤링으로 폴백"""
    resp = _get_with_retry(NAVER_KOSPI_MARKET_SUM_URL, timeout=12.0, retries=3)
    if resp is None:
        return []
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table.type_2 tr")

    top5: List[Dict[str, Any]] = []
    for row in rows:
        cols = row.select("td")
        if len(cols) < 10:
            continue

        name = cols[1].get_text(strip=True)
        price = cols[2].get_text(strip=True)
        change = cols[3].get_text(strip=True)
        change_rate = cols[4].get_text(strip=True)

        if not name:
            continue

        top5.append(
            {
                "name": name,
                "price": price,
                "change": change,
                "change_rate": change_rate,
            }
        )

        if len(top5) >= 5:
            break

    return top5


def fetch_kospi_index() -> Dict[str, Any]:
    """네이버에서 KOSPI 지수 크롤링"""
    url = "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"
    resp = _get_with_retry(url, timeout=12.0, retries=3)
    if resp is None:
        return {}

    try:
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        
        # 현재가
        now_val = soup.select_one("#now_value")
        if not now_val:
            return {}
        
        current = float(now_val.get_text(strip=True).replace(",", ""))
        
        # 등락
        change_val = soup.select_one("#change_value_and_rate span.num")
        change = 0.0
        if change_val:
            change_text = change_val.get_text(strip=True).replace(",", "")
            change = float(change_text)
        
        return {
            "index": current,
            "change": change
        }
    except Exception as e:
        logger.error(f"KOSPI 지수 수집 실패: {e}", exc_info=True)
        return {}


def fetch_nasdaq100_index() -> Dict[str, Any]:
    """네이버에서 나스닥 100 지수 크롤링"""
    url = "https://finance.naver.com/world/sise.naver?symbol=NAS@NDX"
    resp = _get_with_retry(url, timeout=12.0, retries=3)
    if resp is None:
        return {}

    try:
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        
        # em 태그 사용
        em_tags = soup.select("em.no_down, em.no_up")
        if len(em_tags) < 2:
            return {}
        
        current = float(em_tags[0].get_text().strip().replace(",", ""))
        change = float(em_tags[1].get_text().strip().replace(",", ""))
        
        return {
            "index": current,
            "change": change
        }
    except Exception as e:
        logger.error(f"나스닥100 지수 수집 실패: {e}", exc_info=True)
        return {}


def collect_market_daily(db: Session) -> MarketDaily:
    """오늘자 시세를 수집하여 MarketDaily 에 저장하고 반환합니다."""
    # KST 기준 오늘 날짜 (타임존 안전)
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).date()

    usd_krw = fetch_usd_krw_rate()
    btc_usdt, btc_krw, btc_usd, btc_change_24h = fetch_btc_from_coinpaprika()
    
    # Metals.Dev로 전체 금속 시세 수집
    metals = fetch_all_metals_from_metalsdev()
    
    kospi_top5 = fetch_kospi_top5()
    
    # KOSPI/나스닥 지수 수집
    kospi_data = fetch_kospi_index()
    nasdaq_data = fetch_nasdaq100_index()
    
    # BTC KRW 계산 (USD * 환율)
    if btc_usd and usd_krw and not btc_krw:
        btc_krw = btc_usd * usd_krw

    # 직전 데이터로 누락값 보정 (API 실패 대비)
    previous = (
        db.query(MarketDaily)
        .filter(MarketDaily.date < today)
        .order_by(MarketDaily.date.desc(), MarketDaily.id.desc())
        .first()
    )
    if previous:
        missing_fields = []
        def _fallback(value, prev_value, field_name):
            if value is None and prev_value is not None:
                missing_fields.append(field_name)
                return prev_value
            return value

        usd_krw = _fallback(usd_krw, previous.usd_krw, "usd_krw")
        btc_usdt = _fallback(btc_usdt, previous.btc_usdt, "btc_usdt")
        btc_usd = _fallback(btc_usd, previous.btc_usd, "btc_usd")
        btc_change_24h = _fallback(btc_change_24h, previous.btc_change_24h, "btc_change_24h")
        kospi_top5 = _fallback(kospi_top5, previous.kospi_top5, "kospi_top5")

        if btc_usd and usd_krw and not btc_krw:
            btc_krw = btc_usd * usd_krw
        btc_krw = _fallback(btc_krw, previous.btc_krw, "btc_krw")

        metals = {
            "gold": _fallback(metals.get("gold"), previous.gold_usd, "gold_usd"),
            "silver": _fallback(metals.get("silver"), previous.silver_usd, "silver_usd"),
            "platinum": _fallback(metals.get("platinum"), previous.platinum_usd, "platinum_usd"),
            "copper": _fallback(metals.get("copper"), previous.copper_usd, "copper_usd"),
            "palladium": _fallback(metals.get("palladium"), previous.palladium_usd, "palladium_usd"),
            "aluminum": _fallback(metals.get("aluminum"), previous.aluminum_usd, "aluminum_usd"),
            "nickel": _fallback(metals.get("nickel"), previous.nickel_usd, "nickel_usd"),
            "zinc": _fallback(metals.get("zinc"), previous.zinc_usd, "zinc_usd"),
            "lead": _fallback(metals.get("lead"), previous.lead_usd, "lead_usd"),
        }

        kospi_index = _fallback(kospi_data.get("index"), previous.kospi_index, "kospi_index")
        nasdaq_index = _fallback(nasdaq_data.get("index"), previous.nasdaq_index, "nasdaq_index")
        kospi_data = {"index": kospi_index}
        nasdaq_data = {"index": nasdaq_index}

        if missing_fields:
            logger.warning("시장 데이터 누락 보정 적용: %s", ", ".join(sorted(set(missing_fields))))

    market = MarketDaily(
        date=today,
        usd_krw=usd_krw,
        btc_usdt=btc_usdt,
        btc_krw=btc_krw,
        btc_usd=btc_usd,
        btc_change_24h=btc_change_24h,
        
        # Metals.Dev에서 수집한 금속 시세
        gold_usd=metals['gold'],
        silver_usd=metals['silver'],
        platinum_usd=metals['platinum'],
        copper_usd=metals['copper'],
        palladium_usd=metals['palladium'],
        aluminum_usd=metals['aluminum'],
        nickel_usd=metals['nickel'],
        zinc_usd=metals['zinc'],
        lead_usd=metals['lead'],
        
        kospi_index=kospi_data.get("index"),
        kospi_top5=kospi_top5,
        nasdaq_index=nasdaq_data.get("index"),
        crypto_usd=None,
        oil_usd=None,
        coffee_usd=None,
        indices=None,
        summary_comment=None,
    )

    db.add(market)
    db.commit()
    db.refresh(market)

    return market


def calculate_daily_changes(db: Session) -> None:
    """09:05에 실행 - 오늘/어제 데이터를 비교하여 전일대비 계산"""
    import logging
    logger = logging.getLogger(__name__)

    # KST 기준 날짜 (타임존 안전)
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).date()
    yesterday = today - timedelta(days=1)
    
    # 오늘 데이터 조회
    market_today = db.query(MarketDaily).filter(
        MarketDaily.date == today
    ).order_by(MarketDaily.id.desc()).first()
    
    if not market_today:
        logger.warning("오늘 데이터가 없습니다. 전일대비 계산 불가")
        return
    
    # 어제 데이터 조회
    market_yesterday = db.query(MarketDaily).filter(
        MarketDaily.date == yesterday
    ).order_by(MarketDaily.id.desc()).first()
    
    if not market_yesterday:
        logger.warning("어제 데이터가 없습니다. 전일대비 계산 불가")
        return
    
    # USD/KRW 전일대비
    if market_today.usd_krw and market_yesterday.usd_krw:
        market_today.usd_krw_change = market_today.usd_krw - market_yesterday.usd_krw
        market_today.usd_krw_change_pct = (market_today.usd_krw_change / market_yesterday.usd_krw) * 100
    
    # KOSPI 전일대비
    if market_today.kospi_index and market_yesterday.kospi_index:
        market_today.kospi_index_change = market_today.kospi_index - market_yesterday.kospi_index
        market_today.kospi_index_change_pct = (market_today.kospi_index_change / market_yesterday.kospi_index) * 100
    
    # 나스닥100 전일대비
    if market_today.nasdaq_index and market_yesterday.nasdaq_index:
        market_today.nasdaq_index_change = market_today.nasdaq_index - market_yesterday.nasdaq_index
        market_today.nasdaq_index_change_pct = (market_today.nasdaq_index_change / market_yesterday.nasdaq_index) * 100
    
    db.commit()
    
    logger.info(f"전일대비 계산 완료: USD/KRW {market_today.usd_krw_change:+.2f}, KOSPI {market_today.kospi_index_change:+.2f}, 나스닥 {market_today.nasdaq_index_change:+.2f}")
