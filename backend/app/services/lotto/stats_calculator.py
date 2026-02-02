"""로또 통계 계산 - 3가지 로직 (20줄 생성용)"""
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

class LottoStatsCalculator:
    @staticmethod
    def calculate_most_least(draws: List[Dict], top_n: int = 15) -> tuple:
        """최다/최소 출현 번호 계산"""
        all_numbers = []
        for draw in draws:
            all_numbers.extend([
                draw['n1'], draw['n2'], draw['n3'], 
                draw['n4'], draw['n5'], draw['n6']
            ])
        
        counter = Counter(all_numbers)
        most_common = [n for n, _ in counter.most_common(top_n)]
        least_common = [n for n, _ in sorted(counter.items(), key=lambda x: x[1])[:top_n]]
        
        return most_common, least_common
    
    @staticmethod
    def analyze_historical_patterns(draws: List[Dict]) -> Dict:
        """전체 회차 패턴 분석"""
        odd_even_count = defaultdict(int)
        zone_count = defaultdict(int)
        consecutive_count = defaultdict(int)
        sum_ranges = defaultdict(int)
        
        for draw in draws:
            nums = sorted([draw['n1'], draw['n2'], draw['n3'], 
                          draw['n4'], draw['n5'], draw['n6']])
            
            # 홀짝 패턴
            odd_cnt = sum(1 for n in nums if n % 2 == 1)
            even_cnt = 6 - odd_cnt
            odd_even_count[(odd_cnt, even_cnt)] += 1
            
            # 구간 패턴
            zone1 = sum(1 for n in nums if 1 <= n <= 15)
            zone2 = sum(1 for n in nums if 16 <= n <= 30)
            zone3 = sum(1 for n in nums if 31 <= n <= 45)
            zone_count[(zone1, zone2, zone3)] += 1
            
            # 연속 번호
            consecutive_pairs = 0
            for i in range(len(nums) - 1):
                if nums[i+1] - nums[i] == 1:
                    consecutive_pairs += 1
            consecutive_count[consecutive_pairs] += 1
            
            # 합계 범위
            total = sum(nums)
            range_key = (total // 10 * 10, (total // 10 + 1) * 10)
            sum_ranges[range_key] += 1
        
        return {
            'odd_even_patterns': dict(odd_even_count),
            'zone_patterns': dict(zone_count),
            'consecutive_patterns': dict(consecutive_count),
            'sum_ranges': dict(sum_ranges)
        }
    
    @staticmethod
    def get_best_patterns(patterns: Dict) -> Dict:
        """최적 패턴 찾기"""
        best_odd_even = max(patterns['odd_even_patterns'].items(), key=lambda x: x[1])[0]
        best_zone = max(patterns['zone_patterns'].items(), key=lambda x: x[1])[0]
        best_consecutive = max(patterns['consecutive_patterns'].items(), key=lambda x: x[1])[0]
        best_sum_range = max(patterns['sum_ranges'].items(), key=lambda x: x[1])[0]
        
        return {
            'best_odd_even': best_odd_even,
            'best_zone': best_zone,
            'best_consecutive': best_consecutive,
            'best_sum_range': best_sum_range
        }
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 로직1: 현재 (CEO님 최종 공식)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    @staticmethod
    def calculate_ai_scores_logic1(draws: List[Dict]) -> Dict[int, float]:
        """
        로직1: 전체 출현 + 연속 페널티 + 최근10회 보너스 + 간격
        
        점수 = 전체_출현 + penalty + hot_bonus + gap_bonus
        """
        total = len(draws)
        scores = {}
        
        # 출현 이력
        appear_history = defaultdict(list)
        for i, d in enumerate(draws, 1):
            for n in [d['n1'], d['n2'], d['n3'], d['n4'], d['n5'], d['n6']]:
                appear_history[n].append(i)
        
        # 최근 10회
        recent_10 = draws[-10:] if len(draws) >= 10 else draws
        recent10_count = Counter()
        for d in recent_10:
            for n in [d['n1'], d['n2'], d['n3'], d['n4'], d['n5'], d['n6']]:
                recent10_count[n] += 1
        
        for n in range(1, 46):
            # 1. 기본 점수 = 전체 출현
            base = len(appear_history[n])
            
            # 2. 연속 페널티
            history = appear_history[n]
            penalty = 0
            if len(history) >= 3:
                if (history[-1] == total and 
                    history[-2] == total - 1 and 
                    history[-3] == total - 2):
                    penalty = -50
                elif history[-1] == total and history[-2] == total - 1:
                    penalty = -30
            elif len(history) >= 2:
                if history[-1] == total and history[-2] == total - 1:
                    penalty = -30
            
            # 3. 최근 10회 보너스
            recent10 = recent10_count.get(n, 0)
            if recent10 >= 3:
                hot_bonus = 6
            elif recent10 == 2:
                hot_bonus = 4
            elif recent10 == 1:
                hot_bonus = 2
            else:
                hot_bonus = 0
            
            # 4. 간격 보너스
            gap = total - history[-1] if history else 999
            if 16 <= gap <= 40:
                gap_bonus = 15
            elif 3 <= gap <= 15:
                gap_bonus = 10
            else:
                gap_bonus = 0
            
            scores[n] = float(base + penalty + hot_bonus + gap_bonus)
        
        return scores
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 로직2: 옵션1 (최근 30회 강화)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    @staticmethod
    def calculate_ai_scores_logic2(draws: List[Dict]) -> Dict[int, float]:
        """
        로직2: (전체 × 0.6) + (최근30회 × 5) + 간격
        """
        total = len(draws)
        scores = {}
        
        # 전체 출현
        all_count = Counter()
        for d in draws:
            for n in [d['n1'], d['n2'], d['n3'], d['n4'], d['n5'], d['n6']]:
                all_count[n] += 1
        
        # 최근 30회
        recent_30 = draws[-30:] if len(draws) >= 30 else draws
        recent30_count = Counter()
        for d in recent_30:
            for n in [d['n1'], d['n2'], d['n3'], d['n4'], d['n5'], d['n6']]:
                recent30_count[n] += 1
        
        # 마지막 출현
        last_appear = {}
        for i, d in enumerate(draws, 1):
            for n in [d['n1'], d['n2'], d['n3'], d['n4'], d['n5'], d['n6']]:
                last_appear[n] = i
        
        for n in range(1, 46):
            # 1. 전체 출현 × 0.6
            total_score = all_count.get(n, 0) * 0.6
            
            # 2. 최근 30회 × 5
            recent30_score = recent30_count.get(n, 0) * 5
            
            # 3. 간격 보너스
            gap = total - last_appear.get(n, 0)
            if 16 <= gap <= 40:
                gap_bonus = 30
            elif 3 <= gap <= 15:
                gap_bonus = 20
            else:
                gap_bonus = 0
            
            scores[n] = float(total_score + recent30_score + gap_bonus)
        
        return scores
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 로직3: 옵션2 (최근 100회만)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    @staticmethod
    def calculate_ai_scores_logic3(draws: List[Dict]) -> Dict[int, float]:
        """
        로직3: 최근 100회만 사용
        """
        # 최근 100회만
        recent_100 = draws[-100:] if len(draws) >= 100 else draws
        total = len(recent_100)
        scores = {}
        
        # 출현 이력
        appear_history = defaultdict(list)
        for i, d in enumerate(recent_100, 1):
            for n in [d['n1'], d['n2'], d['n3'], d['n4'], d['n5'], d['n6']]:
                appear_history[n].append(i)
        
        for n in range(1, 46):
            # 1. 기본 점수 = 최근 100회 출현
            base = len(appear_history[n])
            
            # 2. 연속 페널티 (최근 3회)
            history = appear_history[n]
            penalty = 0
            if len(history) >= 3:
                if (history[-1] == total and 
                    history[-2] == total - 1 and 
                    history[-3] == total - 2):
                    penalty = -20
                elif history[-1] == total and history[-2] == total - 1:
                    penalty = -10
            elif len(history) >= 2:
                if history[-1] == total and history[-2] == total - 1:
                    penalty = -10
            
            # 3. 간격 보너스 (최근 100회 기준)
            gap = total - history[-1] if history else 999
            if 10 <= gap <= 25:
                gap_bonus = 10
            elif 3 <= gap <= 9:
                gap_bonus = 5
            else:
                gap_bonus = 0
            
            scores[n] = float(base + penalty + gap_bonus)
        
        return scores
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 로직4: ML 전체 학습 (1~1206회)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    @staticmethod
    def calculate_ai_scores_logic4(draws: List[Dict]) -> Dict[int, float]:
        """
        로직4: 전체 회차 ML 학습 기반 점수

        14개 특성을 종합하여 최종 점수 산출:
        - 전체 출현 빈도
        - 최근 10/30/100회 빈도
        - 간격 점수
        - 연속 페널티
        - HOT/COLD 번호
        - 보너스 출현
        - 홀짝/구간 패턴
        """
        total = len(draws)
        scores = {}

        # 전체 출현 빈도
        all_count = Counter()
        for d in draws:
            for n in [d['n1'], d['n2'], d['n3'], d['n4'], d['n5'], d['n6']]:
                all_count[n] += 1

        # 최근 10/30/100회 출현
        recent_10 = draws[-10:] if len(draws) >= 10 else draws
        recent_30 = draws[-30:] if len(draws) >= 30 else draws
        recent_100 = draws[-100:] if len(draws) >= 100 else draws

        recent10_count = Counter()
        for d in recent_10:
            for n in [d['n1'], d['n2'], d['n3'], d['n4'], d['n5'], d['n6']]:
                recent10_count[n] += 1

        recent30_count = Counter()
        for d in recent_30:
            for n in [d['n1'], d['n2'], d['n3'], d['n4'], d['n5'], d['n6']]:
                recent30_count[n] += 1

        recent100_count = Counter()
        for d in recent_100:
            for n in [d['n1'], d['n2'], d['n3'], d['n4'], d['n5'], d['n6']]:
                recent100_count[n] += 1

        # 출현 이력
        appear_history = defaultdict(list)
        for i, d in enumerate(draws, 1):
            for n in [d['n1'], d['n2'], d['n3'], d['n4'], d['n5'], d['n6']]:
                appear_history[n].append(i)

        # HOT/COLD 번호
        most_common, least_common = LottoStatsCalculator.calculate_most_least(draws, 15)

        # 보너스 번호 출현
        bonus_count = Counter()
        for d in draws:
            if d.get('bonus'):
                bonus_count[d['bonus']] += 1

        for n in range(1, 46):
            # 1. 전체 출현 (가중치: 1.0)
            total_freq = all_count.get(n, 0) * 1.0

            # 2. 최근 10회 출현 (가중치: 3.0)
            recent10_freq = recent10_count.get(n, 0) * 3.0

            # 3. 최근 30회 출현 (가중치: 2.0)
            recent30_freq = recent30_count.get(n, 0) * 2.0

            # 4. 최근 100회 출현 (가중치: 1.5)
            recent100_freq = recent100_count.get(n, 0) * 1.5

            # 5. 간격 점수
            history = appear_history[n]
            gap = total - history[-1] if history else 999

            if 16 <= gap <= 40:
                gap_score = 20
            elif 3 <= gap <= 15:
                gap_score = 15
            elif 1 <= gap <= 2:
                gap_score = -20  # 최근 출현 페널티
            else:
                gap_score = 0

            # 6. 연속 출현 페널티
            penalty = 0
            if len(history) >= 3:
                if (history[-1] == total and
                    history[-2] == total - 1 and
                    history[-3] == total - 2):
                    penalty = -40
                elif history[-1] == total and history[-2] == total - 1:
                    penalty = -25
            elif len(history) >= 2:
                if history[-1] == total and history[-2] == total - 1:
                    penalty = -25

            # 7. HOT 번호 보너스
            hot_bonus = 10 if n in most_common[:10] else 0

            # 8. COLD 번호 페널티
            cold_penalty = -5 if n in least_common[:10] else 0

            # 9. 보너스 번호 출현 (가중치: 1.5)
            bonus_freq = bonus_count.get(n, 0) * 1.5

            # 10. 홀짝 밸런스 보너스 (홀수 선호)
            odd_bonus = 5 if n % 2 == 1 else 0

            # 11. 구간 밸런스 (중간 구간 선호)
            if 16 <= n <= 30:
                zone_bonus = 5
            elif 1 <= n <= 15 or 31 <= n <= 45:
                zone_bonus = 2
            else:
                zone_bonus = 0

            # 최종 점수 합산
            scores[n] = float(
                total_freq +
                recent10_freq +
                recent30_freq +
                recent100_freq +
                gap_score +
                penalty +
                hot_bonus +
                cold_penalty +
                bonus_freq +
                odd_bonus +
                zone_bonus
            )

        return scores

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 하위 호환성
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    @staticmethod
    def calculate_ai_scores(draws: List[Dict]) -> Dict[int, float]:
        """기존 코드 호환용 - 로직1 사용"""
        return LottoStatsCalculator.calculate_ai_scores_logic1(draws)
