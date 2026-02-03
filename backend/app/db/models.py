from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text, JSON, CheckConstraint, UniqueConstraint, Index
# from sqlalchemy.orm import declarative_base

from backend.app.db.session import Base


def utcnow():
    """타임존 aware UTC 시간 반환"""
    return datetime.now(timezone.utc)


class NewsDaily(Base):
    __tablename__ = "news_daily"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(Date, index=True)
    source = Column(String(100))
    title = Column(String(500))
    url = Column(String(500))
    category = Column(String(50), index=True)

    # 기사 메타 정보
    is_top = Column(Boolean, default=False)
    keywords = Column(Text, nullable=True)
    sentiment = Column(String(50), nullable=True)

    # 속보 관련
    is_breaking = Column(Boolean, default=False)
    alert_sent = Column(Boolean, default=False)

    # 중복 제거용 (날짜별 주제 키)
    topic_key = Column(String(100), index=True, nullable=True)

    # 핫 점수
    hot_score = Column(Integer, default=0, index=True)

    created_at = Column(DateTime, default=utcnow)
    published_at = Column(DateTime, nullable=True)

    __table_args__ = (
        # 같은 날짜의 같은 URL 중복 방지
        UniqueConstraint('date', 'url', name='uix_news_date_url'),
        # topic_key 중복 검색 최적화
        Index('ix_news_date_topic', 'date', 'topic_key'),
    )


class MarketDaily(Base):
    __tablename__ = "market_daily"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(Date, index=True)

    # 환율
    usd_krw = Column(Float, nullable=True)

    # 크립토 (주요 BTC 포커스, 나머지는 JSON으로 확장 가능)
    btc_usdt = Column(Float, nullable=True)
    btc_krw = Column(Float, nullable=True)
    btc_usd = Column(Float, nullable=True)
    btc_change_24h = Column(Float, nullable=True)

    # 추가 코인들 (ETH, XRP, SOL, TRX 등) - 심볼: 가격(USD) 형태
    crypto_usd = Column(JSON, nullable=True)

    # 금속/원자재 (USD 기준)
    gold_usd = Column(Float, nullable=True)       # 금 1oz USD
    silver_usd = Column(Float, nullable=True)     # 은 1oz USD
    platinum_usd = Column(Float, nullable=True)   # 백금 1oz USD
    copper_usd = Column(Float, nullable=True)     # 구리 1oz USD
    palladium_usd = Column(Float, nullable=True)  # 팔라디움 1oz USD
    aluminum_usd = Column(Float, nullable=True)   # 알루미늄 1oz USD
    nickel_usd = Column(Float, nullable=True)     # 니켈 1oz USD
    zinc_usd = Column(Float, nullable=True)       # 아연 1oz USD
    lead_usd = Column(Float, nullable=True)       # 납 1oz USD
    oil_usd = Column(Float, nullable=True)        # 원유(예: WTI) 배럴당 USD
    coffee_usd = Column(Float, nullable=True)     # 커피 원두 USD

    # KOSPI 및 지수 관련
    kospi_index = Column(Float, nullable=True)
    kospi_top5 = Column(JSON, nullable=True)  # [{name, price, change, change_rate}]

    # 나스닥
    nasdaq_index = Column(Float, nullable=True)
    nasdaq_top5 = Column(JSON, nullable=True)

    # KOSDAQ
    kosdaq_index = Column(Float, nullable=True)
    kosdaq_top5 = Column(JSON, nullable=True)

    # S&P500
    sp500_index = Column(Float, nullable=True)

    # 글로벌 지수 확장용 (현재는 수집 보류)
    # 예: {"sp500": {...}, "nasdaq100": {...}, "dow": {...}}
    indices = Column(JSON, nullable=True)

    # 전일대비 (09:05에 계산)
    usd_krw_change = Column(Float, nullable=True)
    usd_krw_change_pct = Column(Float, nullable=True)
    kospi_index_change = Column(Float, nullable=True)
    kospi_index_change_pct = Column(Float, nullable=True)
    nasdaq_index_change = Column(Float, nullable=True)
    nasdaq_index_change_pct = Column(Float, nullable=True)
    kosdaq_index_change = Column(Float, nullable=True)
    kosdaq_index_change_pct = Column(Float, nullable=True)
    sp500_index_change = Column(Float, nullable=True)
    sp500_index_change_pct = Column(Float, nullable=True)

    summary_comment = Column(Text, nullable=True)

    # 데이터 수집 타임스탬프
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        # 같은 날짜에 여러 레코드 허용 (시간대별 업데이트 가능)
        # 하지만 날짜 기준 조회 최적화
        Index('ix_market_date_created', 'date', 'created_at'),
    )


class KoreaMetalDaily(Base):
    __tablename__ = "korea_metal_daily"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    metal = Column(String(20), index=True)
    date = Column(Date, index=True, nullable=True)
    date_text = Column(String(20), nullable=True)

    buy_3_75g = Column(Integer, nullable=True)   # 내가 살 때(순금)
    sell_3_75g = Column(Integer, nullable=True)  # 내가 팔 때(순금)
    sell_18k = Column(Integer, nullable=True)    # 내가 팔 때(18K)
    sell_14k = Column(Integer, nullable=True)    # 내가 팔 때(14K)

    source_url = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        # 같은 날짜, 같은 금속 중복 방지
        UniqueConstraint('metal', 'date', name='uix_korea_metal_metal_date'),
    )


class Subscriber(Base):
    __tablename__ = "subscriber"

    chat_id = Column(String(50), primary_key=True, index=True)
    subscribed_alert = Column(Boolean, default=True, index=True)  # 구독 상태로 자주 필터링
    custom_time = Column(String(10), default="09:10")  # 알림 시간 (HH:MM 형식)
    created_at = Column(DateTime, default=utcnow)


class LottoStatsCache(Base):
    """로또 통계 캐시 (싱글톤)"""
    __tablename__ = "lotto_stats_cache"

    id = Column(Integer, primary_key=True, default=1)
    updated_at = Column(DateTime, nullable=False)
    total_draws = Column(Integer, nullable=False)
    most_common = Column(JSON, nullable=False)   # 가장 많이 나온 번호들
    least_common = Column(JSON, nullable=False)  # 가장 적게 나온 번호들
    ai_scores = Column(JSON, nullable=False)     # AI 스코어

    __table_args__ = (
        CheckConstraint('id = 1', name='singleton_check'),
    )


class LottoDraw(Base):
    """로또 당첨 번호 이력"""
    __tablename__ = "lotto_draws"

    draw_no = Column(Integer, primary_key=True)  # 회차
    draw_date = Column(String, nullable=False, index=True)  # 추첨일
    n1 = Column(Integer, nullable=False)
    n2 = Column(Integer, nullable=False)
    n3 = Column(Integer, nullable=False)
    n4 = Column(Integer, nullable=False)
    n5 = Column(Integer, nullable=False)
    n6 = Column(Integer, nullable=False)
    bonus = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint('n1 BETWEEN 1 AND 45', name='n1_range'),
        CheckConstraint('n2 BETWEEN 1 AND 45', name='n2_range'),
        CheckConstraint('n3 BETWEEN 1 AND 45', name='n3_range'),
        CheckConstraint('n4 BETWEEN 1 AND 45', name='n4_range'),
        CheckConstraint('n5 BETWEEN 1 AND 45', name='n5_range'),
        CheckConstraint('n6 BETWEEN 1 AND 45', name='n6_range'),
        CheckConstraint('bonus BETWEEN 1 AND 45', name='bonus_range'),
    )


class LottoRecommendLog(Base):
    """로또 번호 추천 로그"""
    __tablename__ = "lotto_recommend_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    target_draw_no = Column(Integer, nullable=False, index=True)
    lines = Column(Text, nullable=False)  # JSON string: 추천한 번호 조합들
    recommend_time = Column(DateTime, default=utcnow)
    match_results = Column(Text, nullable=True)  # JSON string: 당첨 결과


class LottoUserPrediction(Base):
    """사용자 로또 예측 저장"""
    __tablename__ = "lotto_user_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(50), nullable=False, index=True)
    target_draw_no = Column(Integer, nullable=False, index=True)  # 예측 대상 회차
    lines = Column(JSON, nullable=False)  # 예측한 번호 조합들 [{name, numbers, logic}]
    line_count = Column(Integer, nullable=False)  # 5, 10, 15, 20, 25
    created_at = Column(DateTime, default=utcnow)

    # 결과 분석 (당첨번호 발표 후 계산)
    analyzed = Column(Boolean, default=False)
    match_3 = Column(Integer, default=0)  # 3개 맞은 줄 수
    match_4 = Column(Integer, default=0)  # 4개 맞은 줄 수
    match_5 = Column(Integer, default=0)  # 5개 맞은 줄 수
    match_6 = Column(Integer, default=0)  # 6개 맞은 줄 수
    total_matches = Column(Integer, default=0)  # 전체 맞은 번호 개수
    analyzed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        # 같은 사용자, 같은 회차는 하나만 (최신 예측으로 덮어쓰기)
        UniqueConstraint('chat_id', 'target_draw_no', name='uix_lotto_user_prediction'),
        Index('ix_lotto_user_pred_draw_analyzed', 'target_draw_no', 'analyzed'),
    )


class LottoMLPerformance(Base):
    """ML 모델 성능 추적"""
    __tablename__ = "lotto_ml_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    draw_no = Column(Integer, nullable=False, index=True, unique=True)  # 평가 대상 회차
    evaluated_at = Column(DateTime, default=utcnow)

    # 전체 시스템 성능 (25줄 기준)
    total_lines = Column(Integer, default=25)
    match_3 = Column(Integer, default=0)
    match_4 = Column(Integer, default=0)
    match_5 = Column(Integer, default=0)
    match_6 = Column(Integer, default=0)
    total_matches = Column(Integer, default=0)  # 전체 맞은 번호 개수
    avg_matches_per_line = Column(Float, default=0.0)  # 줄당 평균 맞은 개수

    # 로직별 성능 (각 로직 기여도 분석)
    logic1_score = Column(Float, default=0.0)  # Logic1 줄들의 평균 맞은 개수
    logic2_score = Column(Float, default=0.0)
    logic3_score = Column(Float, default=0.0)
    logic4_score = Column(Float, default=0.0)
    ml_score = Column(Float, default=0.0)  # ML 5줄 평균 점수

    # 현재 AI 가중치 (이 회차에 사용된 가중치)
    weights_logic1 = Column(Float, nullable=True)
    weights_logic2 = Column(Float, nullable=True)
    weights_logic3 = Column(Float, nullable=True)
    weights_logic4 = Column(Float, nullable=True)

    # 성능 평가
    performance_score = Column(Float, default=0.0)  # 종합 성능 점수 (0-100)
    needs_retraining = Column(Boolean, default=False)  # 재학습 필요 여부

    # 재학습 기록
    retrained = Column(Boolean, default=False)
    retrained_at = Column(DateTime, nullable=True)
    new_weights = Column(JSON, nullable=True)  # 재학습 후 새 가중치
    grid_search_results = Column(JSON, nullable=True)  # Grid Search 결과

    __table_args__ = (
        Index('ix_lotto_ml_perf_needs_retrain', 'needs_retraining', 'retrained'),
    )


class NotificationLog(Base):
    """알림 전송 로그"""
    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chat_id = Column(String(50), index=True, nullable=False)
    notification_type = Column(String(50), index=True, nullable=False)  # 'morning_brief', 'breaking_news', etc.
    status = Column(String(20), index=True, nullable=False)  # 'success', 'failed', 'pending_retry'
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    scheduled_date = Column(Date, index=True, nullable=False)  # 전송 예정 날짜
    message_preview = Column(Text, nullable=True)  # 메시지 미리보기 (처음 100자)
    created_at = Column(DateTime, default=utcnow, index=True)
    last_attempt_at = Column(DateTime, nullable=True)
    succeeded_at = Column(DateTime, nullable=True)

    __table_args__ = (
        # 같은 날짜, 같은 사용자, 같은 타입의 알림은 하나만
        UniqueConstraint('chat_id', 'notification_type', 'scheduled_date', name='uix_notif_chat_type_date'),
        # 재시도 대상 조회 최적화
        Index('ix_notif_status_date', 'status', 'scheduled_date', 'retry_count'),
    )
