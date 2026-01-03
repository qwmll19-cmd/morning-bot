#!/usr/bin/env python3
"""
수동 데이터 수집 스크립트
즉시 뉴스 + 시장 데이터를 수집합니다.
"""

from backend.app.db.session import SessionLocal
from backend.app.collectors.news_collector_v3 import build_daily_top5_v3
from backend.app.collectors.market_collector import collect_market_daily

if __name__ == "__main__":
    print("=" * 60)
    print("  Morning Bot - 수동 데이터 수집")
    print("=" * 60)
    print()

    db = SessionLocal()

    try:
        print("1/2 뉴스 Top5 생성 중...")
        build_daily_top5_v3(db)
        print("  ✓ 완료")

        print("2/2 시장 데이터 수집 중...")
        collect_market_daily(db)
        print("  ✓ 완료")

        # 전일대비 계산까지 수행 (수동 실행 시에도 표시되도록)
        from backend.app.collectors.market_collector import calculate_daily_changes
        calculate_daily_changes(db)
        print("  ✓ 전일대비 계산 완료")

        print()
        print("=" * 60)
        print("  ✅ 수집 완료! 텔레그램 봇에서 /today 명령으로 확인하세요.")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
