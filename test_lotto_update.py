#!/usr/bin/env python3
"""
로또 업데이트 기능 검증 스크립트
jobs.py의 job_lotto_weekly_update() 함수를 테스트합니다.
"""

import sys
from backend.app.db.session import SessionLocal
from backend.app.db.models import LottoDraw, LottoStatsCache

def test_lotto_update():
    """로또 업데이트 함수 직접 테스트"""
    print("=" * 60)
    print("  로또 업데이트 기능 검증")
    print("=" * 60)
    print()

    # 1. Import 테스트
    print("1️⃣  Import 테스트...")
    try:
        from backend.app.scheduler.jobs import job_lotto_weekly_update
        print("   ✅ job_lotto_weekly_update import 성공")
    except ImportError as e:
        print(f"   ❌ Import 실패: {e}")
        return False

    # 2. DB 연결 테스트
    print("\n2️⃣  데이터베이스 연결 테스트...")
    db = SessionLocal()
    try:
        # 현재 DB 상태 확인
        latest = db.query(LottoDraw).order_by(LottoDraw.draw_no.desc()).first()
        cache = db.query(LottoStatsCache).first()

        if latest:
            print(f"   ✅ DB 최신 회차: {latest.draw_no}회 ({latest.draw_date})")
        else:
            print("   ⚠️  DB에 로또 데이터 없음")

        if cache:
            print(f"   ✅ 통계 캐시: {cache.total_draws}회 (업데이트: {cache.updated_at})")
        else:
            print("   ⚠️  통계 캐시 없음")
    except Exception as e:
        print(f"   ❌ DB 조회 실패: {e}")
        return False
    finally:
        db.close()

    # 3. API Client 테스트
    print("\n3️⃣  로또 API 클라이언트 테스트...")
    try:
        from backend.app.collectors.lotto.api_client import LottoAPIClient

        api_client = LottoAPIClient(delay=0.5)
        latest_api = api_client.get_latest_draw_no()
        print(f"   ✅ API 최신 회차: {latest_api}회")

        # API 응답 구조 확인
        draw_info = api_client.get_lotto_draw(latest_api, retries=2)
        if draw_info:
            print(f"   ✅ API 응답 키: {list(draw_info.keys())}")
            print(f"   ✅ 회차 {latest_api}: {draw_info['n1']}, {draw_info['n2']}, {draw_info['n3']}, {draw_info['n4']}, {draw_info['n5']}, {draw_info['n6']} + {draw_info['bonus']}")
        else:
            print(f"   ⚠️  회차 {latest_api} 데이터 조회 실패")
    except Exception as e:
        print(f"   ❌ API 클라이언트 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. LottoStatsCalculator 테스트
    print("\n4️⃣  통계 계산기 테스트...")
    try:
        from backend.app.services.lotto.stats_calculator import LottoStatsCalculator

        # 테스트 데이터
        test_draws = [
            {'draw_no': 1, 'n1': 1, 'n2': 2, 'n3': 3, 'n4': 4, 'n5': 5, 'n6': 6, 'bonus': 7},
            {'draw_no': 2, 'n1': 8, 'n2': 9, 'n3': 10, 'n4': 11, 'n5': 12, 'n6': 13, 'bonus': 14},
        ]

        calculator = LottoStatsCalculator()
        most, least = calculator.calculate_most_least(test_draws)
        ai_scores = calculator.calculate_ai_scores(test_draws)

        print(f"   ✅ calculate_most_least: {len(most)}개, {len(least)}개")
        print(f"   ✅ calculate_ai_scores: {len(ai_scores)}개 번호 점수")
    except Exception as e:
        print(f"   ❌ 통계 계산기 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 5. 실제 업데이트 함수 테스트 (DRY RUN)
    print("\n5️⃣  업데이트 함수 호출 테스트...")
    print("   ⚠️  실제 DB 업데이트가 진행됩니다.")
    confirm = input("   계속하시겠습니까? (y/N): ")

    if confirm.lower() != 'y':
        print("   ⏭️  업데이트 함수 테스트 스킵")
    else:
        try:
            print("\n   🚀 job_lotto_weekly_update() 실행 중...")
            job_lotto_weekly_update()
            print("   ✅ 업데이트 함수 실행 완료")
        except Exception as e:
            print(f"   ❌ 업데이트 함수 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    print("\n" + "=" * 60)
    print("  ✅ 모든 검증 완료!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_lotto_update()
    sys.exit(0 if success else 1)
