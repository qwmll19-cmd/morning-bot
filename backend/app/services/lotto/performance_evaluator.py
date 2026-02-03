"""로또 ML 성능 평가 및 백테스팅"""
from datetime import datetime
from typing import Dict, List, Tuple
from backend.app.db.session import SessionLocal
from backend.app.db.models import LottoDraw, LottoMLPerformance, LottoUserPrediction
from backend.app.services.lotto.generator import generate_20_lines
from backend.app.services.lotto.stats_calculator import LottoStatsCalculator
from backend.app.services.lotto.ml_predictor import LottoMLPredictor
from backend.app.services.lotto.ml_trainer import LottoMLTrainer
import json


def evaluate_single_draw(draw_no: int, ai_weights: dict = None) -> Dict:
    """
    단일 회차에 대한 성능 평가

    Args:
        draw_no: 평가할 회차 번호
        ai_weights: AI 가중치 (None이면 현재 ML 모델 가중치 사용)

    Returns:
        평가 결과 딕셔너리
    """
    db = SessionLocal()

    try:
        # 1. 당첨 번호 조회
        draw = db.query(LottoDraw).filter(LottoDraw.draw_no == draw_no).first()
        if not draw:
            print(f"⚠️ {draw_no}회 데이터가 없습니다.")
            return None

        winning_numbers = {draw.n1, draw.n2, draw.n3, draw.n4, draw.n5, draw.n6}

        # 2. draw_no - 1까지의 데이터로 예측 생성
        draws = db.query(LottoDraw).filter(LottoDraw.draw_no < draw_no).order_by(LottoDraw.draw_no).all()

        if len(draws) < 10:
            print(f"⚠️ {draw_no}회 평가에 필요한 데이터가 부족합니다 (최소 10회 필요)")
            return None

        draws_dict = [
            {
                'draw_no': d.draw_no,
                'n1': d.n1, 'n2': d.n2, 'n3': d.n3,
                'n4': d.n4, 'n5': d.n5, 'n6': d.n6,
                'bonus': d.bonus
            }
            for d in draws
        ]

        # 3. 통계 데이터 준비
        most_common, least_common = LottoStatsCalculator.calculate_most_least(draws_dict, 15)
        scores_logic1 = LottoStatsCalculator.calculate_ai_scores_logic1(draws_dict)
        scores_logic2 = LottoStatsCalculator.calculate_ai_scores_logic2(draws_dict)
        scores_logic3 = LottoStatsCalculator.calculate_ai_scores_logic3(draws_dict)
        scores_logic4 = LottoStatsCalculator.calculate_ai_scores_logic4(draws_dict)

        patterns = LottoStatsCalculator.analyze_historical_patterns(draws_dict)
        best_patterns = LottoStatsCalculator.get_best_patterns(patterns)

        bonus_counts = {}
        for d in draws_dict:
            b = d.get('bonus')
            if b:
                bonus_counts[b] = bonus_counts.get(b, 0) + 1
        bonus_top = [num for num, _ in sorted(bonus_counts.items(), key=lambda x: x[1], reverse=True)]

        stats = {
            'most_common': most_common,
            'least_common': least_common,
            'scores_logic1': scores_logic1,
            'scores_logic2': scores_logic2,
            'scores_logic3': scores_logic3,
            'patterns': patterns,
            'best_patterns': best_patterns,
            'bonus_top': bonus_top
        }

        # 4. AI 가중치 로드 (또는 제공된 가중치 사용)
        if ai_weights is None:
            ai_weights = {'logic1': 0.25, 'logic2': 0.25, 'logic3': 0.25, 'logic4': 0.25}
            try:
                trainer = LottoMLTrainer()
                if trainer.load_model() and trainer.ai_weights:
                    ai_weights = trainer.ai_weights
            except Exception:
                pass

        # 5. 20줄 생성
        user_id = 99999  # 평가용 임시 ID
        result = generate_20_lines(user_id, stats, ai_weights)

        # 6. ML 5줄 생성
        ml_lines = []
        try:
            trainer = LottoMLTrainer()
            if trainer.load_model():
                predictor = LottoMLPredictor(trainer)

                existing_20_lines = []
                existing_20_lines.extend(result['basic'])
                existing_20_lines.extend(result['logic1'])
                existing_20_lines.extend(result['logic2'])
                existing_20_lines.extend(result['logic3'])
                existing_20_lines.extend(result['final'])
                existing_20_lines.extend(result['ai_core'])

                user_patterns = [
                    {'type': 'top_probability', 'params': {}},
                    {'type': 'balanced_zones', 'params': {'zones': (2, 2, 2)}},
                    {'type': 'odd_even_balanced', 'params': {'ratio': (3, 3)}},
                    {'type': 'consecutive_optimal', 'params': {}},
                    {'type': 'sum_range', 'params': {'min': 130, 'max': 140}}
                ]

                ml_lines = predictor.generate_ml_5_lines(draws_dict, user_patterns, existing_20_lines)
        except Exception as e:
            print(f"⚠️ ML 5줄 생성 실패: {e}")
            ml_lines = []

        # 7. 25줄 구성
        all_25_lines = {
            'basic': result['basic'],
            'logic1': result['logic1'],
            'logic2': result['logic2'],
            'logic3': result['logic3'],
            'final': result['final'],
            'ai_core': result['ai_core'],
            'ml': ml_lines
        }

        # 8. 당첨 분석
        match_3 = match_4 = match_5 = match_6 = 0
        total_matches = 0
        logic_matches = {
            'basic': 0, 'logic1': 0, 'logic2': 0, 'logic3': 0,
            'final': 0, 'ai_core': 0, 'ml': 0
        }
        logic_counts = {
            'basic': 0, 'logic1': 0, 'logic2': 0, 'logic3': 0,
            'final': 0, 'ai_core': 0, 'ml': 0
        }

        for logic_name, lines in all_25_lines.items():
            for line in lines:
                line_numbers = set(line)
                matches = len(line_numbers & winning_numbers)
                total_matches += matches
                logic_matches[logic_name] += matches
                logic_counts[logic_name] += 1

                if matches == 3:
                    match_3 += 1
                elif matches == 4:
                    match_4 += 1
                elif matches == 5:
                    match_5 += 1
                elif matches == 6:
                    match_6 += 1

        total_lines = sum(logic_counts.values())
        avg_matches_per_line = total_matches / total_lines if total_lines > 0 else 0

        # 로직별 평균 점수
        logic_scores = {}
        for logic_name, matches in logic_matches.items():
            count = logic_counts[logic_name]
            logic_scores[logic_name] = matches / count if count > 0 else 0

        # 9. 성능 점수 계산 (0-100)
        # 기준: 줄당 평균 2개 이상이면 50점, 3개이면 100점
        performance_score = min(100, (avg_matches_per_line / 3.0) * 100)

        return {
            'draw_no': draw_no,
            'total_lines': total_lines,
            'match_3': match_3,
            'match_4': match_4,
            'match_5': match_5,
            'match_6': match_6,
            'total_matches': total_matches,
            'avg_matches_per_line': avg_matches_per_line,
            'logic_scores': logic_scores,
            'ai_weights': ai_weights,
            'performance_score': performance_score
        }

    finally:
        db.close()


def save_performance_to_db(evaluation_result: Dict) -> None:
    """
    성능 평가 결과를 DB에 저장

    Args:
        evaluation_result: evaluate_single_draw() 반환값
    """
    if not evaluation_result:
        return

    db = SessionLocal()

    try:
        draw_no = evaluation_result['draw_no']

        # 기존 레코드 확인
        perf = db.query(LottoMLPerformance).filter(LottoMLPerformance.draw_no == draw_no).first()

        if perf:
            # 업데이트
            perf.evaluated_at = datetime.now()
            perf.total_lines = evaluation_result['total_lines']
            perf.match_3 = evaluation_result['match_3']
            perf.match_4 = evaluation_result['match_4']
            perf.match_5 = evaluation_result['match_5']
            perf.match_6 = evaluation_result['match_6']
            perf.total_matches = evaluation_result['total_matches']
            perf.avg_matches_per_line = evaluation_result['avg_matches_per_line']
            perf.logic1_score = evaluation_result['logic_scores'].get('logic1', 0)
            perf.logic2_score = evaluation_result['logic_scores'].get('logic2', 0)
            perf.logic3_score = evaluation_result['logic_scores'].get('logic3', 0)
            perf.logic4_score = evaluation_result['logic_scores'].get('logic4', 0)
            perf.ml_score = evaluation_result['logic_scores'].get('ml', 0)
            perf.weights_logic1 = evaluation_result['ai_weights'].get('logic1')
            perf.weights_logic2 = evaluation_result['ai_weights'].get('logic2')
            perf.weights_logic3 = evaluation_result['ai_weights'].get('logic3')
            perf.weights_logic4 = evaluation_result['ai_weights'].get('logic4')
            perf.performance_score = evaluation_result['performance_score']
            perf.needs_retraining = evaluation_result['performance_score'] < 40  # 40점 이하면 재학습 필요
        else:
            # 신규 생성
            perf = LottoMLPerformance(
                draw_no=draw_no,
                evaluated_at=datetime.now(),
                total_lines=evaluation_result['total_lines'],
                match_3=evaluation_result['match_3'],
                match_4=evaluation_result['match_4'],
                match_5=evaluation_result['match_5'],
                match_6=evaluation_result['match_6'],
                total_matches=evaluation_result['total_matches'],
                avg_matches_per_line=evaluation_result['avg_matches_per_line'],
                logic1_score=evaluation_result['logic_scores'].get('logic1', 0),
                logic2_score=evaluation_result['logic_scores'].get('logic2', 0),
                logic3_score=evaluation_result['logic_scores'].get('logic3', 0),
                logic4_score=evaluation_result['logic_scores'].get('logic4', 0),
                ml_score=evaluation_result['logic_scores'].get('ml', 0),
                weights_logic1=evaluation_result['ai_weights'].get('logic1'),
                weights_logic2=evaluation_result['ai_weights'].get('logic2'),
                weights_logic3=evaluation_result['ai_weights'].get('logic3'),
                weights_logic4=evaluation_result['ai_weights'].get('logic4'),
                performance_score=evaluation_result['performance_score'],
                needs_retraining=evaluation_result['performance_score'] < 40
            )
            db.add(perf)

        db.commit()
        print(f"✅ {draw_no}회 성능 평가 결과 저장 완료 (점수: {evaluation_result['performance_score']:.1f})")

    except Exception as e:
        print(f"❌ 성능 평가 결과 저장 실패: {e}")
        db.rollback()
    finally:
        db.close()


def evaluate_latest_draw() -> None:
    """
    가장 최근 회차에 대한 성능 평가 (스케줄러에서 호출)
    """
    db = SessionLocal()

    try:
        latest_draw = db.query(LottoDraw).order_by(LottoDraw.draw_no.desc()).first()

        if not latest_draw:
            print("⚠️ 로또 데이터가 없습니다.")
            return

        draw_no = latest_draw.draw_no

        print(f"🔍 {draw_no}회 성능 평가 시작...")

        evaluation_result = evaluate_single_draw(draw_no)

        if evaluation_result:
            save_performance_to_db(evaluation_result)

            # 결과 출력
            print(f"📊 평가 결과:")
            print(f"  • 전체 줄 수: {evaluation_result['total_lines']}줄")
            print(f"  • 3개 맞음: {evaluation_result['match_3']}줄")
            print(f"  • 4개 맞음: {evaluation_result['match_4']}줄")
            print(f"  • 5개 맞음: {evaluation_result['match_5']}줄")
            print(f"  • 6개 맞음: {evaluation_result['match_6']}줄")
            print(f"  • 줄당 평균: {evaluation_result['avg_matches_per_line']:.2f}개")
            print(f"  • 성능 점수: {evaluation_result['performance_score']:.1f}/100")

            if evaluation_result['performance_score'] < 40:
                print(f"⚠️ 성능이 낮습니다. 재학습이 필요합니다.")
            else:
                print(f"✅ 성능이 양호합니다.")

    finally:
        db.close()


def backtest_multiple_draws(start_draw: int, end_draw: int) -> List[Dict]:
    """
    여러 회차에 대한 백테스팅

    Args:
        start_draw: 시작 회차
        end_draw: 종료 회차 (포함)

    Returns:
        평가 결과 리스트
    """
    results = []

    for draw_no in range(start_draw, end_draw + 1):
        print(f"\n🔍 {draw_no}회 백테스팅...")
        evaluation_result = evaluate_single_draw(draw_no)

        if evaluation_result:
            save_performance_to_db(evaluation_result)
            results.append(evaluation_result)
            print(f"  ✅ 완료 - 점수: {evaluation_result['performance_score']:.1f}/100 "
                  f"(평균: {evaluation_result['avg_matches_per_line']:.2f}개/줄)")
        else:
            print(f"  ⚠️ 평가 실패")

    return results


def print_backtest_summary(results: List[Dict]) -> None:
    """백테스팅 결과 요약 출력"""
    if not results:
        print("⚠️ 백테스팅 결과가 없습니다.")
        return

    print("\n" + "=" * 80)
    print("📊 백테스팅 요약")
    print("=" * 80)
    print()

    total_draws = len(results)
    total_lines = sum(r['total_lines'] for r in results)
    total_match_3 = sum(r['match_3'] for r in results)
    total_match_4 = sum(r['match_4'] for r in results)
    total_match_5 = sum(r['match_5'] for r in results)
    total_match_6 = sum(r['match_6'] for r in results)
    avg_performance = sum(r['performance_score'] for r in results) / total_draws
    avg_matches = sum(r['avg_matches_per_line'] for r in results) / total_draws

    print(f"✅ 평가 회차 수: {total_draws}회")
    print(f"✅ 총 생성 줄 수: {total_lines}줄")
    print()
    print(f"📈 전체 당첨 통계:")
    print(f"  • 3개 맞음: {total_match_3}줄 ({total_match_3/total_lines*100:.2f}%)")
    print(f"  • 4개 맞음: {total_match_4}줄 ({total_match_4/total_lines*100:.2f}%)")
    print(f"  • 5개 맞음: {total_match_5}줄 ({total_match_5/total_lines*100:.2f}%)")
    print(f"  • 6개 맞음: {total_match_6}줄 ({total_match_6/total_lines*100:.2f}%)")
    print()
    print(f"📊 평균 성능:")
    print(f"  • 줄당 평균 맞은 개수: {avg_matches:.2f}개")
    print(f"  • 평균 성능 점수: {avg_performance:.1f}/100")
    print()

    if avg_performance < 40:
        print("⚠️ 전체 성능이 낮습니다. Grid Search 재학습을 권장합니다.")
    elif avg_performance < 60:
        print("📌 성능이 보통입니다. 지속적인 모니터링이 필요합니다.")
    else:
        print("✅ 성능이 양호합니다!")
