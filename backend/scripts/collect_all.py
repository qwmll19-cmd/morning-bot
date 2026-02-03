"""모든 데이터 한 번에 수집"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app.db.session import SessionLocal
from backend.app.collectors.market_collector import collect_market_daily, calculate_daily_changes
from backend.app.collectors.news_collector_v3 import build_daily_top5_v3, collect_breaking_news
from backend.app.collectors.koreagoldx_collector import collect_korea_metal_daily

def main():
    db = SessionLocal()

    try:
        print("="*60)
        print("데이터 수집 시작")
        print("="*60)

        # 1. 시장 데이터
        print("\n1️⃣ 시장 데이터 수집 중...")
        try:
            market = collect_market_daily(db)
            print(f"   ✅ 시장 데이터 수집 완료")
        except Exception as e:
            print(f"   ⚠️ 시장 수집 실패: {e}")

        # 2. 국내 금속 시세
        print("\n2️⃣ 국내 금속 시세 수집 중...")
        try:
            metals = collect_korea_metal_daily(db)
            print(f"   ✅ 국내 금속 {len(metals)}건 수집 완료")
        except Exception as e:
            print(f"   ⚠️ 금속 시세 수집 실패: {e}")

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

        # 5. 전일대비 계산
        print("\n5️⃣ 전일대비 계산 중...")
        try:
            calculate_daily_changes(db)
            print("   ✅ 전일대비 계산 완료")
        except Exception as e:
            print(f"   ⚠️ 전일대비 계산 실패: {e}")

        print("\n" + "="*60)
        print("✅ 모든 데이터 수집 완료!")
        print("="*60)

    finally:
        db.close()

if __name__ == "__main__":
    main()
