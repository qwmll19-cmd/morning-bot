"""로또 통계 캐시 초기화 (15줄용 - 패턴 분석 포함)"""
import sys
import json
from datetime import datetime
from backend.app.db.session import SessionLocal
from backend.app.db.models import LottoDraw, LottoStatsCache
from backend.app.services.lotto.stats_calculator import LottoStatsCalculator

def main():
    print("=" * 60)
    print("로또 통계 캐시 생성 (15줄용 - 패턴 분석)")
    print("=" * 60)
    
    print("[1/5] DB 연결 중...")
    db = SessionLocal()
    
    try:
        print("✅ DB 연결 완료")
        
        print("[2/5] 전체 데이터 조회 중...")
        draws = db.query(LottoDraw).order_by(LottoDraw.draw_no).all()
        
        if not draws:
            print("❌ 회차 데이터가 없습니다.")
            return
        
        print(f"✅ {len(draws)}개 회차 조회 완료")
        
        draws_dict = [
            {
                'draw_no': d.draw_no,
                'draw_date': d.draw_date,
                'n1': d.n1, 'n2': d.n2, 'n3': d.n3,
                'n4': d.n4, 'n5': d.n5, 'n6': d.n6,
                'bonus': d.bonus
            }
            for d in draws
        ]
        
        print("[3/5] 통계 계산 중...")
        most_common, least_common = LottoStatsCalculator.calculate_most_least(draws_dict, top_n=15)
        print(f"   최다 출현: {most_common[:5]}...")
        print(f"   최소 출현: {least_common[:5]}...")
        
        ai_scores = LottoStatsCalculator.calculate_ai_scores(draws_dict)
        print(f"   AI 점수 계산 완료 (45개 번호)")
        
        print("[4/5] 패턴 분석 중...")
        patterns = LottoStatsCalculator.analyze_historical_patterns(draws_dict)
        
        print(f"   홀짝 패턴: {len(patterns['odd_even_patterns'])}가지")
        print(f"   구간 패턴: {len(patterns['zone_patterns'])}가지")
        print(f"   연속 패턴: {len(patterns['consecutive_patterns'])}가지")
        print(f"   합계 범위: {len(patterns['sum_ranges'])}가지")
        
        best_patterns = LottoStatsCalculator.get_best_patterns(patterns)
        print(f"   최적 홀짝: {best_patterns['best_odd_even']}")
        print(f"   최적 구간: {best_patterns['best_zone']}")
        print(f"   최적 연속: {best_patterns['best_consecutive']}쌍")
        print(f"   최적 합계: {best_patterns['best_sum_range']}")
        
        print("[5/5] 캐시 저장 중...")
        db.query(LottoStatsCache).delete()
        
        # 튜플을 리스트/문자열로 변환 (JSON 직렬화)
        patterns_serializable = {
            'odd_even_patterns': {str(k): v for k, v in patterns['odd_even_patterns'].items()},
            'zone_patterns': {str(k): v for k, v in patterns['zone_patterns'].items()},
            'consecutive_patterns': patterns['consecutive_patterns'],
            'sum_ranges': {str(k): v for k, v in patterns['sum_ranges'].items()}
        }
        
        best_patterns_serializable = {
            'best_odd_even': list(best_patterns['best_odd_even']),
            'best_zone': list(best_patterns['best_zone']),
            'best_consecutive': best_patterns['best_consecutive'],
            'best_sum_range': list(best_patterns['best_sum_range'])
        }
        
        # ai_scores를 확장해서 패턴 정보도 함께 저장
        ai_scores_extended = {
            'scores': ai_scores,
            'patterns': patterns_serializable,
            'best_patterns': best_patterns_serializable
        }
        
        cache = LottoStatsCache(
            id=1,
            updated_at=datetime.now(),
            total_draws=len(draws),
            most_common=json.dumps(most_common),
            least_common=json.dumps(least_common),
            ai_scores=json.dumps(ai_scores_extended, ensure_ascii=False)
        )
        
        db.add(cache)
        db.commit()
        
        print("✅ 캐시 저장 완료")
        print(f"\n캐시 정보:")
        print(f"   • 총 회차: {len(draws)}")
        print(f"   • 최다 출현: {most_common[:5]}...")
        print(f"   • 최소 출현: {least_common[:5]}...")
        print(f"   • 최적 패턴:")
        print(f"      - 홀짝: {best_patterns['best_odd_even']}")
        print(f"      - 구간: {best_patterns['best_zone']}")
        print(f"      - 연속: {best_patterns['best_consecutive']}쌍")
        print(f"      - 합계: {best_patterns['best_sum_range']}")
        print("\n✅ 모든 작업 완료!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == '__main__':
    main()
