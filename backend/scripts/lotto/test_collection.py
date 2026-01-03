"""API 연결 테스트 (소규모 테스트)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.collectors.lotto.api_client import LottoAPIClient

def test_api():
    print("=" * 60)
    print("로또 API 테스트 시작")
    print("=" * 60)
    
    client = LottoAPIClient(delay=0.5)
    
    # 1. 최신 회차 확인
    print("\n[테스트 1] 최신 회차 조회")
    try:
        latest = client.get_latest_draw_no()
        print(f"✅ 최신 회차: {latest}회\n")
    except Exception as e:
        print(f"❌ 실패: {e}\n")
        return
    
    # 2. 특정 회차 조회 (1, 100, 최신)
    test_draws = [1, 100, latest]
    
    for draw_no in test_draws:
        print(f"[테스트 2] 회차 {draw_no} 조회")
        data = client.get_lotto_draw(draw_no, retries=2)
        if data:
            print(f"✅ 성공: {data}")
        else:
            print(f"❌ 데이터 없음")
        print()
    
    print("=" * 60)
    print("✅ API 테스트 완료!")
    print("=" * 60)

if __name__ == "__main__":
    test_api()
