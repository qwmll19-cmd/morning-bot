"""모든 데이터 한 번에 수집"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app.db.session import SessionLocal
from backend.app.collectors.market_collector import collect_market_daily
from backend.app.collectors.news_collector_v3 import build_daily_top5_v3, collect_breaking_news
from backend.app.collectors.lotto.history_collector import collect_lotto_history

def main():
    db = SessionLocal()
    
    try:
        print("="*60)
        print("데이터 수집 시작")
        print("="*60)
        
        # 1. 로또 히스토리
        print("\n1️⃣ 로또 데이터 수집 중...")
        try:
            collect_lotto_history(db)
            print("   ✅ 로또 데이터 수집 완료")
        except Exception as e:
            print(f"   ⚠️ 로또 수집 실패: {e}")
        
        # 2. 시장 데이터
        print("\n2️⃣ 시장 데이터 수집 중...")
        try:
            market = collect_market_daily(db)
            print(f"   ✅ 시장 데이터 수집 완료")
        except Exception as e:
            print(f"   ⚠️ 시장 수집 실패: {e}")
        
        # 3. 뉴스 Top5
        print("\n3️⃣ 뉴스 Top5 생성 중...")
        try:
            build_daily_top5_v3(db)
            print("   ✅ 뉴스 Top5 생성 완료")
        except Exception as e:
            print(f"   ⚠️ 뉴스 수집 실패: {e}")
        
        # 4. 속보
        print("\n4️⃣ 속보 수집 중...")
        try:
            breaking = collect_breaking_news(db)
            print(f"   ✅ 속보 {len(breaking)}건 수집 완료")
        except Exception as e:
            print(f"   ⚠️ 속보 수집 실패: {e}")
        
        print("\n" + "="*60)
        print("✅ 모든 데이터 수집 완료!")
        print("="*60)
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
