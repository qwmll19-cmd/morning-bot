#!/usr/bin/env python3
"""
DB 초기화 스크립트
morning_bot.db 새로 생성
"""

import os
import sys

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app.db.session import engine, Base
from backend.app.db.models import (
    NewsDaily, MarketDaily, KoreaMetalDaily, Subscriber,
    LottoDraw, LottoStatsCache, LottoRecommendLog, NotificationLog,
    LottoUserPrediction, LottoMLPerformance
)

def init_db():
    print("🔧 DB 초기화 시작...")

    # 모든 테이블 생성
    Base.metadata.create_all(bind=engine)

    print("✅ DB 초기화 완료!")
    print("📍 생성된 테이블:")
    print("  - news_daily")
    print("  - market_daily")
    print("  - korea_metal_daily")
    print("  - subscriber (custom_time 컬럼 포함)")
    print("  - lotto_draws")
    print("  - lotto_stats_cache")
    print("  - lotto_recommend_logs")
    print("  - lotto_user_predictions (NEW)")
    print("  - lotto_ml_performance (NEW)")
    print("  - notification_log")

if __name__ == "__main__":
    init_db()
