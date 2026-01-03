#!/usr/bin/env python3
"""
로또 업데이트 수동 실행 스크립트
토요일 21시 스케줄을 놓친 경우 수동으로 실행
"""

from backend.app.scheduler.jobs import job_lotto_weekly_update

if __name__ == "__main__":
    print("=" * 60)
    print("  로또 업데이트 수동 실행")
    print("=" * 60)
    print()

    try:
        job_lotto_weekly_update()
        print()
        print("=" * 60)
        print("  ✅ 로또 업데이트 완료!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
