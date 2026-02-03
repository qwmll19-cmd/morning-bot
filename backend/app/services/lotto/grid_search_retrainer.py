"""Grid Search 기반 ML 재학습"""
from datetime import datetime
from itertools import product
from typing import Dict, List, Tuple
from backend.app.db.session import SessionLocal
from backend.app.db.models import LottoDraw, LottoMLPerformance
from backend.app.services.lotto.performance_evaluator import evaluate_single_draw, save_performance_to_db
from backend.app.services.lotto.ml_trainer import LottoMLTrainer
import json


def grid_search_weights(
    test_draws: List[int],
    weight_candidates: List[List[float]] = None
) -> Tuple[Dict, float, List[Dict]]:
    """
    Grid Search로 최적 가중치 찾기

    Args:
        test_draws: 테스트할 회차 리스트
        weight_candidates: 각 로직별 가중치 후보 리스트
                          기본값: [[0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4]]

    Returns:
        (최적_가중치, 최고_점수, 전체_결과)
    """
    if weight_candidates is None:
        # 기본 후보: 10%에서 40%까지 5% 단위
        weight_candidates = [[0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40] for _ in range(4)]

    print("=" * 80)
    print("🔍 Grid Search 시작")
    print("=" * 80)
    print()
    print(f"📊 테스트 회차: {len(test_draws)}회")
    print(f"📊 가중치 후보: {len(weight_candidates[0])}개 (각 로직별)")
    print()

    # 모든 가중치 조합 생성 (합이 1.0인 것만)
    all_combinations = []
    for combo in product(*weight_candidates):
        # 합이 1.0 ± 0.01 범위인 것만 허용
        if 0.99 <= sum(combo) <= 1.01:
            normalized = [w / sum(combo) for w in combo]  # 정규화
            all_combinations.append({
                'logic1': normalized[0],
                'logic2': normalized[1],
                'logic3': normalized[2],
                'logic4': normalized[3]
            })

    print(f"✅ 유효한 가중치 조합: {len(all_combinations)}개")
    print()

    if len(all_combinations) == 0:
        print("⚠️ 유효한 가중치 조합이 없습니다.")
        return None, 0, []

    # 각 조합 테스트
    results = []

    for idx, weights in enumerate(all_combinations, 1):
        print(f"[{idx}/{len(all_combinations)}] 테스트 중... ", end="")
        print(f"L1:{weights['logic1']:.2f} L2:{weights['logic2']:.2f} "
              f"L3:{weights['logic3']:.2f} L4:{weights['logic4']:.2f}")

        # 각 회차에 대해 평가
        draw_scores = []
        for draw_no in test_draws:
            evaluation_result = evaluate_single_draw(draw_no, ai_weights=weights)
            if evaluation_result:
                draw_scores.append(evaluation_result['performance_score'])

        if draw_scores:
            avg_score = sum(draw_scores) / len(draw_scores)
            results.append({
                'weights': weights,
                'avg_score': avg_score,
                'draw_scores': draw_scores
            })
            print(f"  → 평균 점수: {avg_score:.2f}")
        else:
            print(f"  → 평가 실패")

    # 최고 점수 찾기
    if not results:
        print("⚠️ Grid Search 결과가 없습니다.")
        return None, 0, []

    best_result = max(results, key=lambda x: x['avg_score'])
    best_weights = best_result['weights']
    best_score = best_result['avg_score']

    print()
    print("=" * 80)
    print("🏆 Grid Search 완료")
    print("=" * 80)
    print()
    print(f"✅ 최적 가중치:")
    print(f"  • Logic1: {best_weights['logic1']*100:.1f}%")
    print(f"  • Logic2: {best_weights['logic2']*100:.1f}%")
    print(f"  • Logic3: {best_weights['logic3']*100:.1f}%")
    print(f"  • Logic4: {best_weights['logic4']*100:.1f}%")
    print()
    print(f"✅ 최고 평균 점수: {best_score:.2f}/100")
    print()

    return best_weights, best_score, results


def retrain_with_grid_search(
    test_draw_count: int = 10,
    save_to_model: bool = True
) -> Dict:
    """
    Grid Search로 재학습하고 모델 업데이트

    Args:
        test_draw_count: 테스트에 사용할 최근 회차 수
        save_to_model: True면 최적 가중치를 모델에 저장

    Returns:
        재학습 결과 딕셔너리
    """
    db = SessionLocal()

    try:
        # 1. 최근 N회차 조회
        latest_draws = db.query(LottoDraw).order_by(
            LottoDraw.draw_no.desc()
        ).limit(test_draw_count).all()

        if len(latest_draws) < test_draw_count:
            print(f"⚠️ 데이터가 부족합니다. (필요: {test_draw_count}회, 현재: {len(latest_draws)}회)")
            return None

        test_draw_nos = [d.draw_no for d in reversed(latest_draws)]

        print(f"🔍 재학습 대상 회차: {test_draw_nos[0]}회 ~ {test_draw_nos[-1]}회 ({len(test_draw_nos)}회)")
        print()

        # 2. Grid Search 실행
        best_weights, best_score, all_results = grid_search_weights(test_draw_nos)

        if not best_weights:
            print("⚠️ Grid Search 실패")
            return None

        # 3. 모델에 저장
        if save_to_model:
            trainer = LottoMLTrainer()
            trainer.ai_weights = best_weights

            if trainer.save_model():
                print(f"✅ 최적 가중치를 모델에 저장했습니다.")
            else:
                print(f"⚠️ 모델 저장 실패")

        # 4. 성능 기록 업데이트 (가장 최근 회차)
        latest_draw_no = test_draw_nos[-1]
        perf = db.query(LottoMLPerformance).filter(
            LottoMLPerformance.draw_no == latest_draw_no
        ).first()

        if perf:
            perf.retrained = True
            perf.retrained_at = datetime.now()
            perf.new_weights = best_weights
            perf.grid_search_results = {
                'test_draws': test_draw_nos,
                'best_score': best_score,
                'total_combinations': len(all_results)
            }
            perf.needs_retraining = False
            db.commit()
            print(f"✅ {latest_draw_no}회 성능 기록에 재학습 정보 업데이트")

        return {
            'best_weights': best_weights,
            'best_score': best_score,
            'test_draws': test_draw_nos,
            'total_combinations': len(all_results)
        }

    finally:
        db.close()


def check_and_retrain_if_needed() -> None:
    """
    성능이 낮은 경우 자동 재학습 (스케줄러에서 호출)
    """
    db = SessionLocal()

    try:
        # 재학습이 필요한 최신 회차 확인
        perf = db.query(LottoMLPerformance).filter(
            LottoMLPerformance.needs_retraining == True,
            LottoMLPerformance.retrained == False
        ).order_by(LottoMLPerformance.draw_no.desc()).first()

        if not perf:
            print("✅ 재학습이 필요한 회차가 없습니다.")
            return

        print(f"⚠️ {perf.draw_no}회 성능이 낮습니다 (점수: {perf.performance_score:.1f}/100)")
        print(f"🔄 자동 재학습을 시작합니다...")
        print()

        result = retrain_with_grid_search(test_draw_count=10, save_to_model=True)

        if result:
            print()
            print("=" * 80)
            print("✅ 자동 재학습 완료")
            print("=" * 80)
            print()
            print(f"📊 새로운 가중치:")
            print(f"  • Logic1: {result['best_weights']['logic1']*100:.1f}%")
            print(f"  • Logic2: {result['best_weights']['logic2']*100:.1f}%")
            print(f"  • Logic3: {result['best_weights']['logic3']*100:.1f}%")
            print(f"  • Logic4: {result['best_weights']['logic4']*100:.1f}%")
            print()
            print(f"📊 개선된 점수: {result['best_score']:.2f}/100")
        else:
            print("❌ 자동 재학습 실패")

    finally:
        db.close()


def manual_retrain(test_draw_count: int = 20) -> None:
    """
    수동 재학습 (관리자가 직접 실행)

    Args:
        test_draw_count: 테스트에 사용할 최근 회차 수
    """
    print("=" * 80)
    print("🔧 수동 재학습 시작")
    print("=" * 80)
    print()

    result = retrain_with_grid_search(test_draw_count=test_draw_count, save_to_model=True)

    if result:
        print()
        print("=" * 80)
        print("✅ 수동 재학습 완료")
        print("=" * 80)
        print()
        print(f"📊 테스트 회차: {len(result['test_draws'])}회")
        print(f"📊 테스트한 조합: {result['total_combinations']}개")
        print()
        print(f"🏆 최적 가중치:")
        print(f"  • Logic1: {result['best_weights']['logic1']*100:.1f}%")
        print(f"  • Logic2: {result['best_weights']['logic2']*100:.1f}%")
        print(f"  • Logic3: {result['best_weights']['logic3']*100:.1f}%")
        print(f"  • Logic4: {result['best_weights']['logic4']*100:.1f}%")
        print()
        print(f"🏆 최고 점수: {result['best_score']:.2f}/100")
        print()
    else:
        print("❌ 수동 재학습 실패")
