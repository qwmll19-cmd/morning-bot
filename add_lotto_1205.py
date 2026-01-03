#!/usr/bin/env python3
"""
1205회 로또 당첨번호 수동 추가 스크립트
API가 작동하지 않을 때 사용
"""

from backend.app.db.session import SessionLocal
from backend.app.db.models import LottoDraw, LottoStatsCache
from backend.app.services.lotto.stats_calculator import LottoStatsCalculator
import json
from datetime import datetime

# 1205회 당첨번호 (실제 당첨번호로 교체 필요)
# https://www.dhlottery.co.kr/gameResult.do?method=byWin 에서 확인
DRAW_1205 = {
    'draw_no': 1205,
    'draw_date': '2026-01-03',
    'n1': 1,
    'n2': 4,
    'n3': 16,
    'n4': 23,
    'n5': 31,
    'n6': 41,
    'bonus': 2
}

if __name__ == "__main__":
    print("=" * 60)
    print("  1205회 로또 당첨번호 수동 추가")
    print("=" * 60)
    print()

    # 당첨번호 확인
    print("추가할 당첨번호:")
    print(f"  회차: {DRAW_1205['draw_no']}회")
    print(f"  날짜: {DRAW_1205['draw_date']}")
    print(f"  번호: {DRAW_1205['n1']}, {DRAW_1205['n2']}, {DRAW_1205['n3']}, {DRAW_1205['n4']}, {DRAW_1205['n5']}, {DRAW_1205['n6']}")
    print(f"  보너스: {DRAW_1205['bonus']}")
    print()

    # 0이 있으면 경고
    if 0 in [DRAW_1205['n1'], DRAW_1205['n2'], DRAW_1205['n3'],
             DRAW_1205['n4'], DRAW_1205['n5'], DRAW_1205['n6'], DRAW_1205['bonus']]:
        print("⚠️  경고: 번호에 0이 포함되어 있습니다!")
        print("   스크립트 상단의 DRAW_1205를 실제 당첨번호로 수정하세요.")
        print()
        confirm = input("그래도 계속하시겠습니까? (y/N): ")
        if confirm.lower() != 'y':
            print("취소되었습니다.")
            exit(0)

    db = SessionLocal()

    try:
        # 1. 기존 회차 확인
        existing = db.query(LottoDraw).filter(LottoDraw.draw_no == 1205).first()
        if existing:
            print("⚠️  1205회가 이미 DB에 있습니다.")
            print(f"   기존: {existing.n1}, {existing.n2}, {existing.n3}, {existing.n4}, {existing.n5}, {existing.n6} + {existing.bonus}")
            print()
            confirm = input("덮어쓰시겠습니까? (y/N): ")
            if confirm.lower() != 'y':
                print("취소되었습니다.")
                exit(0)

            # 업데이트
            existing.draw_date = DRAW_1205['draw_date']
            existing.n1 = DRAW_1205['n1']
            existing.n2 = DRAW_1205['n2']
            existing.n3 = DRAW_1205['n3']
            existing.n4 = DRAW_1205['n4']
            existing.n5 = DRAW_1205['n5']
            existing.n6 = DRAW_1205['n6']
            existing.bonus = DRAW_1205['bonus']
            print("   ✅ 기존 데이터 업데이트")
        else:
            # 신규 추가
            new_draw = LottoDraw(
                draw_no=DRAW_1205['draw_no'],
                draw_date=DRAW_1205['draw_date'],
                n1=DRAW_1205['n1'],
                n2=DRAW_1205['n2'],
                n3=DRAW_1205['n3'],
                n4=DRAW_1205['n4'],
                n5=DRAW_1205['n5'],
                n6=DRAW_1205['n6'],
                bonus=DRAW_1205['bonus']
            )
            db.add(new_draw)
            print("   ✅ 신규 데이터 추가")

        db.commit()

        # 2. 통계 캐시 갱신
        print("\n통계 캐시 갱신 중...")
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
        print("   ✅ 통계 캐시 갱신 완료")

        print()
        print("=" * 60)
        print(f"  ✅ 완료! 전체 {len(draws_dict)}회")
        print("=" * 60)

        # DB 확인
        latest = db.query(LottoDraw).order_by(LottoDraw.draw_no.desc()).first()
        print(f"\nDB 최신 회차: {latest.draw_no}회 ({latest.draw_date})")
        print(f"번호: {latest.n1}, {latest.n2}, {latest.n3}, {latest.n4}, {latest.n5}, {latest.n6} + {latest.bonus}")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
