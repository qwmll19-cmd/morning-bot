"""XGBoost 기반 로또 번호 예측 및 5줄 생성"""
import random
from typing import List, Dict, Tuple
from itertools import combinations
from backend.app.services.lotto.ml_trainer import LottoMLTrainer


class LottoMLPredictor:
    """ML 기반 로또 번호 예측"""

    def __init__(self, trainer: LottoMLTrainer = None):
        self.trainer = trainer or LottoMLTrainer()

    def generate_ml_5_lines(
        self,
        draws: List[Dict],
        user_patterns: List[Dict] = None,
        existing_20_lines: List[List[int]] = None
    ) -> List[List[int]]:
        """
        ML 기반 5줄 생성 (기존 20줄과 중복 방지)

        Args:
            draws: 전체 회차 데이터
            user_patterns: 사용자 정의 패턴 (5개)
                예: [
                    {'type': 'top_probability', 'params': {}},
                    {'type': 'balanced_zones', 'params': {'zones': (2, 2, 2)}},
                    {'type': 'odd_even_balanced', 'params': {'ratio': (3, 3)}},
                    {'type': 'consecutive_optimal', 'params': {}},
                    {'type': 'sum_range', 'params': {'min': 130, 'max': 140}}
                ]
            existing_20_lines: 기존 20줄 (중복 방지용)

        Returns:
            5줄 리스트
        """
        # 다음 회차 예측
        next_draw_no = max(d['draw_no'] for d in draws) + 1

        # 각 번호의 출현 확률 예측
        probabilities = self.trainer.predict_proba(draws, next_draw_no)

        # 확률 상위 번호들
        sorted_numbers = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
        top_15 = [num for num, _ in sorted_numbers[:15]]
        top_20 = [num for num, _ in sorted_numbers[:20]]

        # 기본 패턴 (사용자 정의가 없을 경우)
        if user_patterns is None:
            user_patterns = [
                {'type': 'top_probability', 'params': {}},
                {'type': 'balanced_zones', 'params': {'zones': (2, 2, 2)}},
                {'type': 'odd_even_balanced', 'params': {'ratio': (3, 3)}},
                {'type': 'consecutive_optimal', 'params': {}},
                {'type': 'sum_range', 'params': {'min': 130, 'max': 140}}
            ]

        result = []
        # 중복 방지: 기존 20줄 + ML 내부 생성 줄
        all_generated = existing_20_lines.copy() if existing_20_lines else []

        for pattern in user_patterns[:5]:
            line = self._generate_line_by_pattern(
                pattern,
                probabilities,
                top_15,
                top_20,
                all_generated
            )
            result.append(line)
            all_generated.append(line)

        return result

    def _generate_line_by_pattern(
        self,
        pattern: Dict,
        probabilities: Dict[int, float],
        top_15: List[int],
        top_20: List[int],
        existing_lines: List[List[int]]
    ) -> List[int]:
        """패턴에 따라 1줄 생성"""
        pattern_type = pattern['type']
        params = pattern.get('params', {})

        if pattern_type == 'top_probability':
            # 확률 상위 6개
            return self._select_top_probability(probabilities, existing_lines)

        elif pattern_type == 'balanced_zones':
            # 구간 밸런스
            zones = params.get('zones', (2, 2, 2))
            return self._select_balanced_zones(top_15, zones, existing_lines)

        elif pattern_type == 'odd_even_balanced':
            # 홀짝 밸런스
            ratio = params.get('ratio', (3, 3))
            return self._select_odd_even_balanced(top_15, ratio, existing_lines)

        elif pattern_type == 'consecutive_optimal':
            # 연속 번호 최적화
            return self._select_consecutive_optimal(top_15, probabilities, existing_lines)

        elif pattern_type == 'sum_range':
            # 합계 범위
            min_sum = params.get('min', 130)
            max_sum = params.get('max', 140)
            return self._select_sum_range(top_20, probabilities, min_sum, max_sum, existing_lines)

        else:
            # 기본값: 확률 상위
            return self._select_top_probability(probabilities, existing_lines)

    def _select_top_probability(self, probabilities: Dict[int, float], existing: List[List[int]]) -> List[int]:
        """확률 상위 6개 선택"""
        sorted_numbers = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)

        for i in range(6, len(sorted_numbers)):
            candidates = [num for num, _ in sorted_numbers[:i]]
            line = sorted(candidates[:6])

            if not self._is_duplicate(line, existing):
                return line

        # 최악의 경우 상위 6개
        return sorted([num for num, _ in sorted_numbers[:6]])

    def _select_balanced_zones(self, candidates: List[int], zones: Tuple[int, int, int], existing: List[List[int]]) -> List[int]:
        """구간 밸런스 선택"""
        z1_cnt, z2_cnt, z3_cnt = zones

        z1 = [n for n in candidates if 1 <= n <= 15]
        z2 = [n for n in candidates if 16 <= n <= 30]
        z3 = [n for n in candidates if 31 <= n <= 45]

        for _ in range(10):  # 10번 시도
            selected = []
            selected.extend(random.sample(z1, min(z1_cnt, len(z1))))
            selected.extend(random.sample(z2, min(z2_cnt, len(z2))))
            selected.extend(random.sample(z3, min(z3_cnt, len(z3))))

            # 부족하면 채우기
            while len(selected) < 6:
                selected.append(random.choice(candidates))

            line = sorted(list(set(selected)))[:6]

            if not self._is_duplicate(line, existing):
                return line

        return sorted(candidates[:6])

    def _select_odd_even_balanced(self, candidates: List[int], ratio: Tuple[int, int], existing: List[List[int]]) -> List[int]:
        """홀짝 밸런스 선택"""
        odd_cnt, even_cnt = ratio

        odds = [n for n in candidates if n % 2 == 1]
        evens = [n for n in candidates if n % 2 == 0]

        for _ in range(10):
            selected = []
            selected.extend(random.sample(odds, min(odd_cnt, len(odds))))
            selected.extend(random.sample(evens, min(even_cnt, len(evens))))

            while len(selected) < 6:
                selected.append(random.choice(candidates))

            line = sorted(list(set(selected)))[:6]

            if not self._is_duplicate(line, existing):
                return line

        return sorted(candidates[:6])

    def _select_consecutive_optimal(self, candidates: List[int], probabilities: Dict[int, float], existing: List[List[int]]) -> List[int]:
        """연속 번호 최적화"""
        combos = list(combinations(candidates[:12], 6))

        best_combo = None
        best_score = -1

        for combo in combos:
            sorted_combo = sorted(combo)

            # 연속 번호가 있는지 확인
            has_consecutive = any(
                sorted_combo[i+1] - sorted_combo[i] == 1
                for i in range(len(sorted_combo) - 1)
            )

            if not has_consecutive:
                continue

            # 확률 점수 계산
            score = sum(probabilities.get(n, 0) for n in combo)

            if score > best_score and not self._is_duplicate(sorted_combo, existing):
                best_score = score
                best_combo = sorted_combo

        return best_combo if best_combo else sorted(candidates[:6])

    def _select_sum_range(self, candidates: List[int], probabilities: Dict[int, float], min_sum: int, max_sum: int, existing: List[List[int]]) -> List[int]:
        """합계 범위 선택"""
        combos = list(combinations(candidates[:15], 6))

        best_combo = None
        best_score = -1

        for combo in combos:
            total = sum(combo)

            if not (min_sum <= total <= max_sum):
                continue

            score = sum(probabilities.get(n, 0) for n in combo)
            sorted_combo = sorted(combo)

            if score > best_score and not self._is_duplicate(sorted_combo, existing):
                best_score = score
                best_combo = sorted_combo

        return best_combo if best_combo else sorted(candidates[:6])

    def _is_duplicate(self, line: List[int], existing_lines: List[List[int]], threshold: int = 5) -> bool:
        """중복 확인 (threshold개 이상 겹치면 중복)"""
        line_set = set(line)
        return any(len(line_set & set(existing)) >= threshold for existing in existing_lines)

    def get_ml_scores_for_display(self, draws: List[Dict]) -> Dict:
        """
        텔레그램 표시용 ML 정보 반환

        Returns:
            {
                'next_draw_no': 다음 회차,
                'top_10_numbers': 확률 상위 10개 번호,
                'probabilities': {번호: 확률},
                'ai_weights': {logic1: 가중치, ...}
            }
        """
        next_draw_no = max(d['draw_no'] for d in draws) + 1
        probabilities = self.trainer.predict_proba(draws, next_draw_no)

        sorted_numbers = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
        top_10 = [num for num, _ in sorted_numbers[:10]]

        return {
            'next_draw_no': next_draw_no,
            'top_10_numbers': top_10,
            'probabilities': probabilities,
            'ai_weights': self.trainer.get_ai_weights()
        }
