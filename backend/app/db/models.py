from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text, JSON, CheckConstraint
# from sqlalchemy.orm import declarative_base

from backend.app.db.session import Base


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

    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)


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

    summary_comment = Column(Text, nullable=True)

    # 데이터 수집 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)


class Subscriber(Base):
    __tablename__ = "subscriber"

    chat_id = Column(String(50), primary_key=True, index=True)
    subscribed_alert = Column(Boolean, default=True)
    custom_time = Column(String(10), default="08:30")  # 알림 시간 (HH:MM 형식)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)

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
    recommend_time = Column(DateTime, default=datetime.utcnow)
    match_results = Column(Text, nullable=True)  # JSON string: 당첨 결과
