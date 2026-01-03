from datetime import date as date_type
from typing import List, Optional

from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from backend.app.db.session import Base, engine, get_db
from backend.app.db.models import NewsDaily, MarketDaily
from backend.app.collectors.market_collector import collect_market_daily
from backend.app.scheduler.jobs import start_scheduler


# ---- DB 초기화 ----
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Morning Bot Backend")


# ---- Pydantic 응답 모델 ----
class NewsItemResponse(BaseModel):
    id: int
    date: date_type
    source: Optional[str] = None
    title: str
    url: str
    category: Optional[str] = None
    is_top: bool
    keywords: Optional[str] = None  # DB TEXT 타입
    sentiment: Optional[str] = None

    # SQLAlchemy 모델에서 값 읽기
    model_config = ConfigDict(from_attributes=True)


class MarketDailyResponse(BaseModel):
    date: date_type
    usd_krw: Optional[float] = None
    usd_krw_change: Optional[float] = None  # 전일 대비 (절대값)
    usd_krw_change_pct: Optional[float] = None  # 전일 대비 (%)

    # BTC (CoinPaprika 기반)
    btc_usdt: Optional[float] = None
    btc_krw: Optional[float] = None
    btc_usd: Optional[float] = None
    btc_change_24h: Optional[float] = None

    # Metals (Metals.Dev API, USD 기준)
    gold_usd: Optional[float] = None
    gold_usd_change: Optional[float] = None  # 전일 대비 (절대값)
    gold_usd_change_pct: Optional[float] = None  # 전일 대비 (%)
    
    silver_usd: Optional[float] = None
    silver_usd_change: Optional[float] = None  # 전일 대비
    silver_usd_change_pct: Optional[float] = None  # 전일 대비 (%)
    
    platinum_usd: Optional[float] = None
    platinum_usd_change: Optional[float] = None  # 전일 대비
    platinum_usd_change_pct: Optional[float] = None  # 전일 대비 (%)
    
    copper_usd: Optional[float] = None
    copper_usd_change: Optional[float] = None  # 전일 대비
    copper_usd_change_pct: Optional[float] = None  # 전일 대비 (%)
    
    palladium_usd: Optional[float] = None
    palladium_usd_change: Optional[float] = None  # 전일 대비
    palladium_usd_change_pct: Optional[float] = None  # 전일 대비 (%)
    
    aluminum_usd: Optional[float] = None
    aluminum_usd_change: Optional[float] = None  # 전일 대비
    aluminum_usd_change_pct: Optional[float] = None  # 전일 대비 (%)
    
    nickel_usd: Optional[float] = None
    nickel_usd_change: Optional[float] = None  # 전일 대비
    nickel_usd_change_pct: Optional[float] = None  # 전일 대비 (%)
    
    zinc_usd: Optional[float] = None
    zinc_usd_change: Optional[float] = None  # 전일 대비
    zinc_usd_change_pct: Optional[float] = None  # 전일 대비 (%)
    
    lead_usd: Optional[float] = None
    lead_usd_change: Optional[float] = None  # 전일 대비
    lead_usd_change_pct: Optional[float] = None  # 전일 대비 (%)

    # KOSPI / 지수
    kospi_index: Optional[float] = None
    kospi_top5: Optional[list[dict]] = None
    nasdaq_index: Optional[float] = None  # 현재는 수집하지 않음, 필드만 유지
    indices: Optional[dict] = None        # 향후 S&P500, 나스닥100 등 확장용 JSON

    summary_comment: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TodaySummaryResponse(BaseModel):
    date: date_type
    markets: Optional[MarketDailyResponse] = None
    top_news: List[NewsItemResponse] = []
    summary_comment: Optional[str] = None


# ---- 이벤트 & 헬스체크 ----
@app.on_event("startup")
def on_startup() -> None:
    """FastAPI 시작 시 스케줄러 실행"""
    start_scheduler()


@app.get("/api/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    return {"status": "ok"}


# ---- 오늘 요약 ----
@app.get("/api/today/summary", response_model=TodaySummaryResponse)
def get_today_summary(
    date: Optional[date_type] = Query(
        default=None,
        description="조회할 기준 날짜 (YYYY-MM-DD). 미지정 시 오늘 날짜 기준.",
    ),
    db: Session = Depends(get_db),
) -> TodaySummaryResponse:
    target_date = date or date_type.today()

    # 최신 MarketDaily 1건
    market: Optional[MarketDaily] = (
        db.query(MarketDaily)
        .filter(MarketDaily.date == target_date)
        .order_by(MarketDaily.id.desc())
        .first()
    )
    
    # 전일 데이터 조회 (전일 대비 계산용)
    from datetime import timedelta
    yesterday = target_date - timedelta(days=1)
    yesterday_market: Optional[MarketDaily] = (
        db.query(MarketDaily)
        .filter(MarketDaily.date == yesterday)
        .order_by(MarketDaily.id.desc())
        .first()
    )

    # 오늘자 Top 뉴스 - 각 카테고리 1개 + 속보 1개 = 총 5개
    from backend.app.utils.dedup import remove_duplicate_news
    
    news_list: List[NewsDaily] = []
    
    # 1. 각 카테고리에서 hot_score 최고 1개씩 (4개)
    for category in ["society", "economy", "culture", "entertainment"]:
        top1 = (
            db.query(NewsDaily)
            .filter(NewsDaily.date == target_date, NewsDaily.category == category)
            .order_by(NewsDaily.hot_score.desc(), NewsDaily.created_at.desc())
            .first()
        )
        if top1:
            news_list.append(top1)
    
    # 2. 속보 1개 추가 (hot_score 최고)
    breaking_top1 = (
        db.query(NewsDaily)
        .filter(NewsDaily.date == target_date, NewsDaily.is_breaking.is_(True))
        .order_by(NewsDaily.hot_score.desc(), NewsDaily.created_at.desc())
        .first()
    )
    if breaking_top1:
        news_list.append(breaking_top1)
    
    # 3. 추가 중복 제거 (혹시 모를 경우 대비)
    news_list = remove_duplicate_news(news_list)

    summary_comment: Optional[str] = market.summary_comment if market else None

    # MarketDailyResponse 생성 + 전일 대비 계산
    markets_response: Optional[MarketDailyResponse] = None
    if market:
        # 기본 데이터
        market_dict = {
            "date": market.date,
            "usd_krw": market.usd_krw,
            "btc_usdt": market.btc_usdt,
            "btc_krw": market.btc_krw,
            "btc_usd": market.btc_usd,
            "btc_change_24h": market.btc_change_24h,
            "gold_usd": market.gold_usd,
            "silver_usd": market.silver_usd,
            "platinum_usd": market.platinum_usd,
            "copper_usd": market.copper_usd,
            "palladium_usd": market.palladium_usd,
            "aluminum_usd": market.aluminum_usd,
            "nickel_usd": market.nickel_usd,
            "zinc_usd": market.zinc_usd,
            "lead_usd": market.lead_usd,
            "kospi_index": market.kospi_index,
            "kospi_top5": market.kospi_top5,
            "nasdaq_index": market.nasdaq_index,
            "indices": market.indices,
            "summary_comment": market.summary_comment,
        }
        
        # 전일 대비 계산
        if yesterday_market:
            # 환율
            if market.usd_krw and yesterday_market.usd_krw:
                market_dict["usd_krw_change"] = market.usd_krw - yesterday_market.usd_krw
                market_dict["usd_krw_change_pct"] = (market_dict["usd_krw_change"] / yesterday_market.usd_krw) * 100
            
            # 금
            if market.gold_usd and yesterday_market.gold_usd:
                market_dict["gold_usd_change"] = market.gold_usd - yesterday_market.gold_usd
                market_dict["gold_usd_change_pct"] = (market_dict["gold_usd_change"] / yesterday_market.gold_usd) * 100
            
            # 은
            if market.silver_usd and yesterday_market.silver_usd:
                market_dict["silver_usd_change"] = market.silver_usd - yesterday_market.silver_usd
                market_dict["silver_usd_change_pct"] = (market_dict["silver_usd_change"] / yesterday_market.silver_usd) * 100
            
            # 백금
            if market.platinum_usd and yesterday_market.platinum_usd:
                market_dict["platinum_usd_change"] = market.platinum_usd - yesterday_market.platinum_usd
                market_dict["platinum_usd_change_pct"] = (market_dict["platinum_usd_change"] / yesterday_market.platinum_usd) * 100
            
            # 구리
            if market.copper_usd and yesterday_market.copper_usd:
                market_dict["copper_usd_change"] = market.copper_usd - yesterday_market.copper_usd
                market_dict["copper_usd_change_pct"] = (market_dict["copper_usd_change"] / yesterday_market.copper_usd) * 100
            
            # 팔라디움
            if market.palladium_usd and yesterday_market.palladium_usd:
                market_dict["palladium_usd_change"] = market.palladium_usd - yesterday_market.palladium_usd
                market_dict["palladium_usd_change_pct"] = (market_dict["palladium_usd_change"] / yesterday_market.palladium_usd) * 100
            
            # 알루미늄
            if market.aluminum_usd and yesterday_market.aluminum_usd:
                market_dict["aluminum_usd_change"] = market.aluminum_usd - yesterday_market.aluminum_usd
                market_dict["aluminum_usd_change_pct"] = (market_dict["aluminum_usd_change"] / yesterday_market.aluminum_usd) * 100
            
            # 니켈
            if market.nickel_usd and yesterday_market.nickel_usd:
                market_dict["nickel_usd_change"] = market.nickel_usd - yesterday_market.nickel_usd
                market_dict["nickel_usd_change_pct"] = (market_dict["nickel_usd_change"] / yesterday_market.nickel_usd) * 100
            
            # 아연
            if market.zinc_usd and yesterday_market.zinc_usd:
                market_dict["zinc_usd_change"] = market.zinc_usd - yesterday_market.zinc_usd
                market_dict["zinc_usd_change_pct"] = (market_dict["zinc_usd_change"] / yesterday_market.zinc_usd) * 100
            
            # 납
            if market.lead_usd and yesterday_market.lead_usd:
                market_dict["lead_usd_change"] = market.lead_usd - yesterday_market.lead_usd
                market_dict["lead_usd_change_pct"] = (market_dict["lead_usd_change"] / yesterday_market.lead_usd) * 100
        
        markets_response = MarketDailyResponse(**market_dict)

    top_news_response: List[NewsItemResponse] = [
        NewsItemResponse.model_validate(n, from_attributes=True) for n in news_list
    ]

    return TodaySummaryResponse(
        date=target_date,
        markets=markets_response,
        top_news=top_news_response,
        summary_comment=summary_comment,
    )


# ---- 수동 수집용 DEV 엔드포인트 ----
@app.post("/api/dev/collect-markets-today", response_model=MarketDailyResponse)
def dev_collect_markets_today(
    db: Session = Depends(get_db),
) -> MarketDailyResponse:
    """수동 테스트용 엔드포인트.

    오늘 날짜 기준 시세를 한 번 수집하고, 저장된 MarketDaily를 반환합니다.
    """
    market = collect_market_daily(db)

    return MarketDailyResponse.model_validate(market, from_attributes=True)


# ---- 데이터 수집 API (중요!) ----
@app.get("/api/collect/market")
def collect_market_data(db: Session = Depends(get_db)) -> dict:
    """
    시장 데이터 수집 (환율, BTC, 금/은/구리, KOSPI Top5)
    수동으로 데이터 수집할 때 사용
    """
    try:
        market = collect_market_daily(db)
        return {
            "status": "success",
            "message": "Market data collected",
            "data": {
                "date": str(market.date),
                "usd_krw": market.usd_krw,
                "btc_krw": market.btc_krw,
                "gold_usd": market.gold_usd,
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/api/collect/news")
def collect_news_data(db: Session = Depends(get_db)) -> dict:
    """
    뉴스 데이터 수집 (Top5)
    수동으로 데이터 수집할 때 사용
    """
    try:
        from backend.app.collectors.news_collector import build_daily_top5
        
        result = build_daily_top5(db)
        
        return {
            "status": "success",
            "message": f"News collected: {len(result)} items",
            "count": len(result)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# ---- 시장 데이터 범위 조회 ----
@app.get("/api/markets", response_model=list[MarketDailyResponse])
def get_markets(
    from_date: Optional[date_type] = Query(default=None, alias="from", description="조회 시작 날짜"),
    to_date: Optional[date_type] = Query(default=None, alias="to", description="종료 날짜"),
    db: Session = Depends(get_db),
) -> list[MarketDailyResponse]:
    """시장 데이터 목록 조회"""
    query = db.query(MarketDaily)

    if from_date:
        query = query.filter(MarketDaily.date >= from_date)

    if to_date:
        query = query.filter(MarketDaily.date <= to_date)

    markets: List[MarketDaily] = query.order_by(MarketDaily.date.desc()).all()

    return [
        MarketDailyResponse.model_validate(m, from_attributes=True)
        for m in markets
    ]


# ---- 뉴스 조회 ----
@app.get("/api/news", response_model=List[NewsItemResponse])
def get_news(
    date: Optional[date_type] = Query(default=None, description="조회할 날짜 (YYYY-MM-DD)"),
    category: Optional[str] = Query(default=None, description="카테고리 필터 (general/economy/breaking)"),
    db: Session = Depends(get_db),
) -> List[NewsItemResponse]:
    """뉴스 목록 조회"""
    query = db.query(NewsDaily)

    if date:
        query = query.filter(NewsDaily.date == date)

    if category:
        query = query.filter(NewsDaily.category == category)

    news: List[NewsDaily] = query.order_by(NewsDaily.hot_score.desc(), NewsDaily.created_at.desc()).all()
    
    # 중복 제거 (1+2+3 조합)
    from backend.app.utils.dedup import remove_duplicate_news
    news = remove_duplicate_news(news)
    
    # TOP 10만 반환
    news = news[:10]

    return [
        NewsItemResponse.model_validate(n, from_attributes=True)
        for n in news
    ]
