from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.models import MarketDaily

COINPAPRIKA_TICKER_URL = "https://api.coinpaprika.com/v1/tickers"
UNIRATE_BASE_URL = "https://api.unirateapi.com/api"
METALPRICE_BASE_URL = "https://api.metalpriceapi.com/v1/latest"
NAVER_KOSPI_MARKET_SUM_URL = (
    "https://finance.naver.com/sise/sise_market_sum.nhn?sosok=0&page=1"
)

# Metals.Dev API (전체 금속 시세)
METALSDEV_API_KEY = "AGMKHJ71JN8LPPER7C7M290ER7C7M"
METALSDEV_BASE_URL = "https://api.metals.dev/v1/latest"


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
        return None

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{UNIRATE_BASE_URL}/rates",
                params={"api_key": settings.UNIRATE_API_KEY, "from": "USD"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None

    # 공식 문서 기준: { "rates": { "KRW": 1320.12, ... } } 구조를 가정
    rates = data.get("rates") or data.get("data") or {}
    krw = rates.get("KRW")
    return _safe_float(krw)


def fetch_btc_from_coinpaprika() -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """CoinPaprika 에서 BTC 시세(USD)와 24h 변동률을 가져옵니다.
    KRW는 USD * usd_krw 환율로 계산합니다."""
    try:
        with httpx.Client(timeout=10) as client:
            # 파라미터 없이 기본 USD만 가져오기
            resp = client.get(f"{COINPAPRIKA_TICKER_URL}/btc-bitcoin")
            resp.raise_for_status()
            data = resp.json()
    except Exception:
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
    
    if not METALSDEV_API_KEY:
        return result
    
    try:
        url = f"{METALSDEV_BASE_URL}?api_key={METALSDEV_API_KEY}&currency=USD&unit=toz"
        
        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        
        if data.get('status') != 'success':
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
        
    except Exception:
        pass
    
    return result


def fetch_kospi_top5() -> List[Dict[str, Any]]:
    """네이버 금융 시가총액 상위 페이지에서 KOSPI TOP5 종목을 파싱합니다."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(NAVER_KOSPI_MARKET_SUM_URL)
            resp.raise_for_status()
            html = resp.text
    except Exception:
        return []

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
        change_rate = cols[9].get_text(strip=True)

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
    try:
        url = "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"
        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            resp.raise_for_status()
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
        print(f"KOSPI 지수 수집 실패: {e}")
        return {}


def fetch_nasdaq100_index() -> Dict[str, Any]:
    """네이버에서 나스닥 100 지수 크롤링"""
    try:
        url = "https://finance.naver.com/world/sise.naver?symbol=NAS@NDX"
        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            resp.raise_for_status()
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
        print(f"나스닥100 지수 수집 실패: {e}")
        return {}


def collect_market_daily(db: Session) -> MarketDaily:
    """오늘자 시세를 수집하여 MarketDaily 에 저장하고 반환합니다."""
    today = date.today()

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
    
    today = date.today()
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
