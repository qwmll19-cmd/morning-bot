"""DB 초기화 스크립트"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app.db.session import engine, Base
from backend.app.db.models import NewsDaily, MarketDaily, Subscriber, LottoStatsCache, LottoDraw, LottoRecommendLog

def init_database():
    """테이블 생성"""
    print("🔧 DB 초기화 시작...")
    
    # 모든 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    print("✅ 테이블 생성 완료!")
    print("\n생성된 테이블:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")
    
    print("\n📊 다음 단계:")
    print("1. 로또 데이터 수집: python backend/scripts/lotto/collect_lotto_history.py")
    print("2. 뉴스 수집: python backend/scripts/collect_news.py")
    print("3. 시장 데이터 수집: python backend/scripts/collect_market.py")

if __name__ == "__main__":
    init_database()
