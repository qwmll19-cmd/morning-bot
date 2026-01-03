"""로또 초기 데이터 수집 (1회차~최신) - SQLAlchemy"""
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.collectors.lotto.api_client import LottoAPIClient
from backend.app.collectors.lotto.db_manager import LottoDBManager
from backend.app.db.session import SessionLocal

def main():
    start_time = datetime.now()
    
    print("=" * 60)
    print("로또 초기 데이터 수집 시작")
    print("=" * 60)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [1/5] DB 연결
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n[1/5] DB 연결 중...")
    db = SessionLocal()
    db_manager = LottoDBManager(db)
    print("✅ DB 연결 완료")
    
    try:
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # [2/5] API 클라이언트 초기화
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n[2/5] API 클라이언트 초기화...")
        api_client = LottoAPIClient(delay=0.3)
        print("✅ 클라이언트 준비 완료")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # [3/5] 최신 회차 확인
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("\n[3/5] 최신 회차 확인 중...")
        try:
            latest = api_client.get_latest_draw_no()
        except Exception as e:
            print(f"❌ 최신 회차 조회 실패: {e}")
            return
        
        # DB 상태 확인
        db_max = db_manager.get_max_draw_no()
        db_count = db_manager.get_draw_count()
        print(f"   DB 저장된 최대 회차: {db_max if db_max else '없음'}")
        print(f"   DB 저장된 총 회차 수: {db_count}개")
        
        # 수집 범위 결정
        start_draw = 1 if db_max is None else db_max + 1
        
        if start_draw > latest:
            print(f"\n✅ 이미 최신 상태입니다. (DB: {db_max}회 / 최신: {latest}회)")
            return
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # [4/5] 데이터 수집
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        total_to_collect = latest - start_draw + 1
        estimated_time = total_to_collect * 0.3 / 60
        
        print(f"\n[4/5] 데이터 수집 중... ({start_draw}회 ~ {latest}회)")
        print(f"   총 {total_to_collect}개 회차")
        print(f"   예상 소요 시간: 약 {estimated_time:.1f}분\n")
        
        success_count = 0
        fail_count = 0
        
        for draw_no in range(start_draw, latest + 1):
            # API 호출
            draw_info = api_client.get_lotto_draw(draw_no, retries=3)
            
            if draw_info is None:
                fail_count += 1
                continue
            
            # DB 저장
            saved = db_manager.save_draw(draw_info)
            
            if saved:
                success_count += 1
            
            # 진행상황 표시 (100회차마다)
            if draw_no % 100 == 0:
                progress = (draw_no - start_draw + 1) / total_to_collect * 100
                print(f"   진행: {draw_no}회까지 완료... ({success_count}개 저장, {progress:.1f}%)")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # [5/5] 완료
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        final_count = db_manager.get_draw_count()
        elapsed_time = (datetime.now() - start_time).total_seconds() / 60
        
        print(f"\n[5/5] 수집 완료!")
        print(f"   • 성공: {success_count}개")
        print(f"   • 실패: {fail_count}개")
        print(f"   • 총 회차: {final_count}개")
        print(f"   • 소요 시간: {elapsed_time:.1f}분")
        
        print("\n✅ 모든 작업 완료!")
        print("=" * 60)
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
