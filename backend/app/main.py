from datetime import date as date_type
from pathlib import Path
import logging
import threading
from typing import List, Optional

from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from backend.app.db.session import Base, engine, get_db
from backend.app.db.models import NewsDaily, MarketDaily
from backend.app.collectors.market_collector import collect_market_daily
from backend.app.scheduler.jobs import start_scheduler


# ---- Logging ----
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "server.log"

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
    root_logger.addHandler(logging.FileHandler(LOG_PATH))

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
def _run_telegram_bot():
    """텔레그램 봇을 백그라운드 스레드에서 실행 (새 이벤트 루프 생성)"""
    import asyncio
    try:
        # 새 스레드에서는 새 이벤트 루프 필요
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from backend.app.telegram_bot.bot import main as bot_main
        bot_main()
    except Exception as e:
        logging.error(f"텔레그램 봇 실행 실패: {e}", exc_info=True)


@app.on_event("startup")
def on_startup() -> None:
    """FastAPI 시작 시 스케줄러 및 텔레그램 봇 실행"""
    start_scheduler()

    # 텔레그램 봇을 백그라운드 스레드에서 실행
    bot_thread = threading.Thread(target=_run_telegram_bot, daemon=True)
    bot_thread.start()
    logging.info("✅ 텔레그램 봇 백그라운드 스레드 시작")


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


# ---- Cron API 엔드포인트 (cron-job.org용) ----
from fastapi import Header, HTTPException
import os

CRON_SECRET = os.getenv("CRON_SECRET", "")


def verify_cron_secret(x_cron_secret: str = Header(default="")) -> None:
    """Cron 요청 인증 (선택적)"""
    if CRON_SECRET and x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Invalid cron secret")


@app.get("/api/cron/keep-alive")
def cron_keep_alive() -> dict:
    """10분마다 - Render 슬립 방지 (인증 불필요)"""
    return {"status": "ok", "message": "Server is alive"}


@app.get("/api/cron/morning-collect")
def cron_morning_collect(db: Session = Depends(get_db), _: None = Depends(verify_cron_secret)) -> dict:
    """09:01 - 모든 데이터 수집"""
    from backend.app.scheduler.jobs import job_morning_all
    try:
        job_morning_all()
        return {"status": "success", "job": "morning_collect"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/cron/morning-send")
def cron_morning_send(db: Session = Depends(get_db), _: None = Depends(verify_cron_secret)) -> dict:
    """09:10 - 모닝 브리핑 전송"""
    from backend.app.scheduler.jobs import job_calculate_changes_and_send
    try:
        job_calculate_changes_and_send()
        return {"status": "success", "job": "morning_send"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/cron/breaking-collect")
def cron_breaking_collect(_: None = Depends(verify_cron_secret)) -> dict:
    """매시 55분 - 속보 수집"""
    from backend.app.scheduler.jobs import job_collect_breaking_news
    try:
        job_collect_breaking_news()
        return {"status": "success", "job": "breaking_collect"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/cron/breaking-send")
def cron_breaking_send(_: None = Depends(verify_cron_secret)) -> dict:
    """12시, 18시, 22시 - 속보 배치 전송"""
    from backend.app.scheduler.jobs import job_send_breaking_batch
    try:
        job_send_breaking_batch()
        return {"status": "success", "job": "breaking_send"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/cron/lotto-update")
def cron_lotto_update(_: None = Depends(verify_cron_secret)) -> dict:
    """토요일 21:00 - 로또 당첨번호 업데이트"""
    from backend.app.scheduler.jobs import job_lotto_weekly_update
    try:
        job_lotto_weekly_update()
        return {"status": "success", "job": "lotto_update"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/cron/lotto-ml-eval")
def cron_lotto_ml_eval(_: None = Depends(verify_cron_secret)) -> dict:
    """토요일 22:00 - 로또 ML 성능 평가"""
    from backend.app.scheduler.jobs import job_lotto_performance_evaluation
    try:
        job_lotto_performance_evaluation()
        return {"status": "success", "job": "lotto_ml_eval"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/admin/lotto-init")
def admin_lotto_init(
    start: int = Query(default=1, description="시작 회차"),
    end: int = Query(default=None, description="종료 회차 (미지정 시 최신까지)"),
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret)
) -> dict:
    """
    로또 초기 데이터 로드 (Render PostgreSQL 초기화용)

    사용법: GET /api/admin/lotto-init?start=1&end=1209
    헤더: X-Cron-Secret: {your_secret}

    주의: 전체 1200+회 수집 시 약 10-20분 소요
    """
    from backend.app.collectors.lotto.api_client import LottoAPIClient
    from backend.app.db.models import LottoDraw, LottoStatsCache
    from backend.app.services.lotto.stats_calculator import LottoStatsCalculator
    import json
    from datetime import datetime
    import logging

    logger = logging.getLogger(__name__)

    try:
        # 1. 현재 DB 상태 확인
        latest_db_row = db.query(LottoDraw).order_by(LottoDraw.draw_no.desc()).first()
        current_latest = latest_db_row.draw_no if latest_db_row else 0
        total_in_db = db.query(LottoDraw).count()

        # 2. API 클라이언트 초기화
        api_client = LottoAPIClient(delay=0.3)

        # 3. 최신 회차 확인
        if end is None:
            end = api_client.get_latest_draw_no()
            if end == 0:
                return {
                    "status": "error",
                    "message": "최신 회차 확인 실패 (API 차단 가능)",
                    "current_db_latest": current_latest,
                    "total_in_db": total_in_db
                }

        # 4. 수집 대상 회차 결정
        missing_draws = []
        for draw_no in range(start, end + 1):
            exists = db.query(LottoDraw).filter(LottoDraw.draw_no == draw_no).first()
            if not exists:
                missing_draws.append(draw_no)

        if not missing_draws:
            return {
                "status": "success",
                "message": "이미 모든 데이터가 존재합니다",
                "current_db_latest": current_latest,
                "total_in_db": total_in_db,
                "requested_range": f"{start}~{end}"
            }

        # 5. 데이터 수집
        collected = 0
        failed = []

        for draw_no in missing_draws:
            draw_info = api_client.get_lotto_draw(draw_no, retries=2)

            if draw_info is None:
                failed.append(draw_no)
                continue

            new_draw = LottoDraw(
                draw_no=draw_no,
                draw_date=draw_info['date'],
                n1=draw_info['n1'],
                n2=draw_info['n2'],
                n3=draw_info['n3'],
                n4=draw_info['n4'],
                n5=draw_info['n5'],
                n6=draw_info['n6'],
                bonus=draw_info['bonus']
            )
            db.add(new_draw)
            collected += 1

            # 100개마다 커밋 (메모리 관리)
            if collected % 100 == 0:
                db.commit()
                logger.info(f"로또 초기화 진행 중: {collected}개 저장됨")

        db.commit()

        # 6. 통계 캐시 갱신
        draws = db.query(LottoDraw).order_by(LottoDraw.draw_no).all()
        draws_dict = [
            {
                'draw_no': d.draw_no,
                'n1': d.n1, 'n2': d.n2, 'n3': d.n3,
                'n4': d.n4, 'n5': d.n5, 'n6': d.n6,
                'bonus': d.bonus
            }
            for d in draws
        ]

        calculator = LottoStatsCalculator()
        most_common, least_common = calculator.calculate_most_least(draws_dict)
        ai_scores = calculator.calculate_ai_scores(draws_dict)

        cache = db.query(LottoStatsCache).first()
        if cache:
            cache.updated_at = datetime.now()
            cache.total_draws = len(draws_dict)
            cache.most_common = json.dumps(most_common)
            cache.least_common = json.dumps(least_common)
            cache.ai_scores = json.dumps(ai_scores)
        else:
            cache = LottoStatsCache(
                updated_at=datetime.now(),
                total_draws=len(draws_dict),
                most_common=json.dumps(most_common),
                least_common=json.dumps(least_common),
                ai_scores=json.dumps(ai_scores)
            )
            db.add(cache)

        db.commit()

        # 7. ML 모델 학습 (데이터가 100개 이상일 때)
        ml_result = None
        if len(draws_dict) >= 100:
            try:
                from backend.app.services.lotto.ml_trainer import LottoMLTrainer
                trainer = LottoMLTrainer()
                ml_result = trainer.train(draws_dict, test_size=0.2)
                logger.info(f"ML 모델 학습 완료: Acc={ml_result['test_accuracy']:.4f}")
            except Exception as e:
                logger.warning(f"ML 모델 학습 실패: {e}")

        return {
            "status": "success",
            "message": f"{collected}개 회차 수집 완료",
            "collected": collected,
            "failed_draws": failed[:20] if failed else [],  # 처음 20개만
            "failed_count": len(failed),
            "total_in_db_after": len(draws_dict),
            "stats_cache_updated": True,
            "ml_trained": ml_result is not None,
            "ml_accuracy": ml_result['test_accuracy'] if ml_result else None
        }

    except Exception as e:
        db.rollback()
        logger.error(f"로또 초기화 실패: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/api/admin/lotto-status")
def admin_lotto_status(db: Session = Depends(get_db)) -> dict:
    """로또 DB 상태 확인 (인증 불필요)"""
    from backend.app.db.models import LottoDraw, LottoStatsCache

    total = db.query(LottoDraw).count()
    latest = db.query(LottoDraw).order_by(LottoDraw.draw_no.desc()).first()
    cache = db.query(LottoStatsCache).first()

    return {
        "total_draws": total,
        "latest_draw_no": latest.draw_no if latest else None,
        "latest_draw_date": latest.draw_date if latest else None,
        "stats_cache_exists": cache is not None,
        "stats_cache_updated_at": cache.updated_at.isoformat() if cache else None
    }


@app.get("/api/admin/lotto-export")
def admin_lotto_export(db: Session = Depends(get_db)) -> dict:
    """로컬 SQLite에서 로또 데이터 JSON 추출 (마이그레이션용)"""
    from backend.app.db.models import LottoDraw

    draws = db.query(LottoDraw).order_by(LottoDraw.draw_no).all()
    data = [
        {
            "draw_no": d.draw_no,
            "draw_date": d.draw_date,
            "n1": d.n1, "n2": d.n2, "n3": d.n3,
            "n4": d.n4, "n5": d.n5, "n6": d.n6,
            "bonus": d.bonus
        }
        for d in draws
    ]

    return {
        "status": "success",
        "total": len(data),
        "draws": data
    }


from pydantic import BaseModel as PydanticBaseModel
from typing import List


class LottoDrawImport(PydanticBaseModel):
    draw_no: int
    draw_date: str
    n1: int
    n2: int
    n3: int
    n4: int
    n5: int
    n6: int
    bonus: int


class LottoImportRequest(PydanticBaseModel):
    draws: List[LottoDrawImport]


@app.post("/api/admin/lotto-import")
def admin_lotto_import(
    request: LottoImportRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret)
) -> dict:
    """
    로또 데이터 일괄 import (Render PostgreSQL 마이그레이션용)

    사용법:
    1. 로컬에서 /api/admin/lotto-export 호출하여 JSON 추출
    2. Render에서 /api/admin/lotto-import에 POST로 전송

    curl -X POST -H "Content-Type: application/json" \\
         -H "X-Cron-Secret: YOUR_SECRET" \\
         -d @lotto_data.json \\
         https://YOUR_APP.onrender.com/api/admin/lotto-import
    """
    from backend.app.db.models import LottoDraw, LottoStatsCache
    from backend.app.services.lotto.stats_calculator import LottoStatsCalculator
    import json
    from datetime import datetime
    import logging

    logger = logging.getLogger(__name__)

    try:
        imported = 0
        skipped = 0

        for draw in request.draws:
            exists = db.query(LottoDraw).filter(LottoDraw.draw_no == draw.draw_no).first()
            if exists:
                skipped += 1
                continue

            new_draw = LottoDraw(
                draw_no=draw.draw_no,
                draw_date=draw.draw_date,
                n1=draw.n1, n2=draw.n2, n3=draw.n3,
                n4=draw.n4, n5=draw.n5, n6=draw.n6,
                bonus=draw.bonus
            )
            db.add(new_draw)
            imported += 1

            if imported % 100 == 0:
                db.commit()
                logger.info(f"로또 import 진행 중: {imported}개")

        db.commit()

        # 통계 캐시 갱신
        draws = db.query(LottoDraw).order_by(LottoDraw.draw_no).all()
        draws_dict = [
            {
                'draw_no': d.draw_no,
                'n1': d.n1, 'n2': d.n2, 'n3': d.n3,
                'n4': d.n4, 'n5': d.n5, 'n6': d.n6,
                'bonus': d.bonus
            }
            for d in draws
        ]

        calculator = LottoStatsCalculator()
        most_common, least_common = calculator.calculate_most_least(draws_dict)
        ai_scores = calculator.calculate_ai_scores(draws_dict)

        cache = db.query(LottoStatsCache).first()
        if cache:
            cache.updated_at = datetime.now()
            cache.total_draws = len(draws_dict)
            cache.most_common = json.dumps(most_common)
            cache.least_common = json.dumps(least_common)
            cache.ai_scores = json.dumps(ai_scores)
        else:
            cache = LottoStatsCache(
                updated_at=datetime.now(),
                total_draws=len(draws_dict),
                most_common=json.dumps(most_common),
                least_common=json.dumps(least_common),
                ai_scores=json.dumps(ai_scores)
            )
            db.add(cache)

        db.commit()

        # ML 모델 학습
        ml_result = None
        if len(draws_dict) >= 100:
            try:
                from backend.app.services.lotto.ml_trainer import LottoMLTrainer
                trainer = LottoMLTrainer()
                ml_result = trainer.train(draws_dict, test_size=0.2)
                logger.info(f"ML 모델 학습 완료: Acc={ml_result['test_accuracy']:.4f}")
            except Exception as e:
                logger.warning(f"ML 모델 학습 실패: {e}")

        return {
            "status": "success",
            "imported": imported,
            "skipped": skipped,
            "total_in_db": len(draws_dict),
            "stats_cache_updated": True,
            "ml_trained": ml_result is not None,
            "ml_accuracy": ml_result['test_accuracy'] if ml_result else None
        }

    except Exception as e:
        db.rollback()
        logger.error(f"로또 import 실패: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/api/admin/lotto-ml-train")
def admin_lotto_ml_train(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret)
) -> dict:
    """
    로또 ML 모델 강제 재학습 (수동 트리거용)

    신규 회차 없이도 현재 DB 데이터로 ML 모델을 재학습합니다.
    """
    from backend.app.db.models import LottoDraw
    import logging

    logger = logging.getLogger(__name__)

    try:
        draws = db.query(LottoDraw).order_by(LottoDraw.draw_no).all()
        if len(draws) < 100:
            return {
                "status": "error",
                "message": f"데이터 부족: {len(draws)}개 (최소 100개 필요)"
            }

        draws_dict = [
            {
                'draw_no': d.draw_no,
                'n1': d.n1, 'n2': d.n2, 'n3': d.n3,
                'n4': d.n4, 'n5': d.n5, 'n6': d.n6,
                'bonus': d.bonus
            }
            for d in draws
        ]

        from backend.app.services.lotto.ml_trainer import LottoMLTrainer
        trainer = LottoMLTrainer()
        result = trainer.train(draws_dict, test_size=0.2)

        logger.info(f"ML 모델 강제 재학습 완료: Acc={result['test_accuracy']:.4f}")

        return {
            "status": "success",
            "message": "ML 모델 재학습 완료",
            "total_draws": len(draws_dict),
            "train_accuracy": result['train_accuracy'],
            "test_accuracy": result['test_accuracy'],
            "ai_weights": result['ai_weights']
        }

    except Exception as e:
        logger.error(f"ML 재학습 실패: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }
