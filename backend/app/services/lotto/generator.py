"""로또 번호 생성 (20줄) - 버그 수정 완료"""
import random
from typing import List, Dict, Tuple, Set
from itertools import combinations

def lucky_number(user_id: int, n: int = 6) -> List[int]:
    """유저ID 기반 행운 번호"""
    rng = random.Random(user_id)
    nums = sorted(rng.sample(range(1, 46), n))
    return nums

def get_top_candidates(ai_scores: Dict, n: int) -> List[int]:
    """AI 점수 상위 N개 후보"""
    sorted_items = sorted(ai_scores.items(), key=lambda x: float(x[1]), reverse=True)
    return [int(num) for num, _ in sorted_items[:n]]

def select_by_odd_even_balance(candidates: List[int], target: Tuple[int, int]) -> List[int]:
    """홀짝 밸런스에 맞춰 선택"""
    target_odd, target_even = target
    odds = [n for n in candidates if n % 2 == 1]
    evens = [n for n in candidates if n % 2 == 0]
    
    selected = set()
    selected.update(odds[:target_odd])
    selected.update(evens[:target_even])
    
    # 부족하면 추가
    while len(selected) < 6 and len(candidates) > len(selected):
        for c in candidates:
            if c not in selected:
                selected.add(c)
                if len(selected) >= 6:
                    break
    
    return sorted(list(selected))[:6]

def select_by_zone_balance(candidates: List[int], target: Tuple[int, int, int]) -> List[int]:
    """구간 밸런스에 맞춰 선택"""
    z1_cnt, z2_cnt, z3_cnt = target
    
    z1 = [n for n in candidates if 1 <= n <= 15]
    z2 = [n for n in candidates if 16 <= n <= 30]
    z3 = [n for n in candidates if 31 <= n <= 45]
    
    selected = set()
    selected.update(z1[:z1_cnt])
    selected.update(z2[:z2_cnt])
    selected.update(z3[:z3_cnt])
    
    # 부족하면 추가
    while len(selected) < 6 and len(candidates) > len(selected):
        for c in candidates:
            if c not in selected:
                selected.add(c)
                if len(selected) >= 6:
                    break
    
    return sorted(list(selected))[:6]

def has_consecutive(numbers: List[int]) -> bool:
    """연속 번호 쌍이 있는지 확인"""
    for i in range(len(numbers) - 1):
        if numbers[i+1] - numbers[i] == 1:
            return True
    return False

def calculate_sum(numbers: List[int]) -> int:
    """번호 합계"""
    return sum(numbers)

def is_duplicate(line1: List[int], line2: List[int], threshold: int = 5) -> bool:
    """두 조합이 중복인지 확인 (threshold개 이상 겹치면 중복)"""
    return len(set(line1) & set(line2)) >= threshold

def generate_20_lines(user_id: int, stats: Dict, ai_weights: Dict = None) -> Dict:
    """20줄 생성 (버그 수정)"""
    most = stats['most_common']
    least = stats['least_common']
    scores1 = stats['scores_logic1']
    scores2 = stats['scores_logic2']
    scores3 = stats['scores_logic3']
    bonus_top = stats.get('bonus_top', [])
    
    if ai_weights is None:
        ai_weights = {'logic1': 0.33, 'logic2': 0.33, 'logic3': 0.34}
    
    result = {
        'basic': [],
        'logic1': [],
        'logic2': [],
        'logic3': [],
        'final': [],
        'ai_core': []
    }
    
    all_generated = []  # 중복 체크용

    def _is_exact_duplicate(candidate: List[int]) -> bool:
        cset = set(candidate)
        return any(cset == set(existing) for existing in all_generated)

    def _unique_line(make_line, attempts: int = 8) -> List[int]:
        last = None
        for _ in range(attempts):
            line = make_line()
            last = line
            if not _is_exact_duplicate(line):
                return line
        return last if last is not None else []

    def _line_with_bonus(candidates: List[int]) -> List[int]:
        """보너스 번호를 포함한 조합 생성 (중복 대체용)."""
        for bonus in bonus_top:
            if bonus in candidates:
                pool = [n for n in candidates if n != bonus]
            else:
                pool = candidates[:]
            if len(pool) < 5:
                continue
            line = sorted([bonus] + random.sample(pool, 5))
            if not _is_exact_duplicate(line):
                return line
        return []

    def _ensure_unique(line: List[int], candidates: List[int]) -> List[int]:
        """전역 중복이면 보너스 기반으로 대체."""
        if not _is_exact_duplicate(line):
            return line
        bonus_line = _line_with_bonus(candidates)
        return bonus_line if bonus_line else line
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 기본 4줄
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    # ① 믹스
    line1 = set()
    line1.add(random.choice(most))
    line1.add(random.choice(least))
    while len(line1) < 6:
        line1.add(random.randint(1, 45))
    line1 = sorted(list(line1))
    result['basic'].append(line1)
    all_generated.append(line1)
    
    # ② 최다
    line2 = sorted(most[:6])
    result['basic'].append(line2)
    all_generated.append(line2)
    
    # ③ 최소
    line3 = sorted(least[:6])
    result['basic'].append(line3)
    all_generated.append(line3)
    
    # ④ 최다믹스
    line4 = set(most[:3])
    line4.update(random.sample(range(1, 46), 2))
    line4.add(lucky_number(user_id, 1)[0])
    line4 = sorted(list(line4))[:6]
    result['basic'].append(line4)
    all_generated.append(line4)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 로직1 3줄
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    top1_10 = get_top_candidates(scores1, 10)
    
    line5 = _unique_line(lambda: select_by_odd_even_balance(random.sample(top1_10, len(top1_10)), (3, 3)))
    line5 = _ensure_unique(line5, top1_10)
    result['logic1'].append(line5)
    all_generated.append(line5)
    
    line6 = _unique_line(lambda: select_by_zone_balance(random.sample(top1_10, len(top1_10)), (2, 2, 2)))
    line6 = _ensure_unique(line6, top1_10)
    result['logic1'].append(line6)
    all_generated.append(line6)
    
    line7 = _unique_line(lambda: sorted(random.sample(top1_10, 6)))
    line7 = _ensure_unique(line7, top1_10)
    result['logic1'].append(line7)
    all_generated.append(line7)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 로직2 3줄
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    top2_15 = get_top_candidates(scores2, 15)
    
    line8 = _unique_line(lambda: select_by_odd_even_balance(random.sample(top2_15, len(top2_15)), (3, 3)))
    line8 = _ensure_unique(line8, top2_15)
    result['logic2'].append(line8)
    all_generated.append(line8)
    
    line9 = _unique_line(lambda: select_by_zone_balance(random.sample(top2_15, len(top2_15)), (2, 2, 2)))
    line9 = _ensure_unique(line9, top2_15)
    result['logic2'].append(line9)
    all_generated.append(line9)
    
    # ⑩ 합계 최적화
    combos = list(combinations(top2_15[:12], 6))
    best_combo = None
    best_score = -999
    for combo in combos:
        s = calculate_sum(combo)
        if 130 <= s <= 140:
            combo_score = sum(scores2.get(n, 0) for n in combo)
            if combo_score > best_score and not _is_exact_duplicate(list(combo)):
                best_score = combo_score
                best_combo = combo
    
    if best_combo:
        line10 = sorted(list(best_combo))
    else:
        line10 = _unique_line(lambda: sorted(random.sample(top2_15, 6)))
    line10 = _ensure_unique(line10, top2_15)
    
    result['logic2'].append(line10)
    all_generated.append(line10)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 로직3 3줄
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    top3_15 = get_top_candidates(scores3, 15)
    
    line11 = _unique_line(lambda: select_by_odd_even_balance(random.sample(top3_15, len(top3_15)), (3, 3)))
    line11 = _ensure_unique(line11, top3_15)
    result['logic3'].append(line11)
    all_generated.append(line11)
    
    line12 = _unique_line(lambda: select_by_zone_balance(random.sample(top3_15, len(top3_15)), (2, 2, 2)))
    line12 = _ensure_unique(line12, top3_15)
    result['logic3'].append(line12)
    all_generated.append(line12)
    
    # ⑬ 연속 최적화
    combos = list(combinations(top3_15[:10], 6))
    best_combo = None
    best_score = -999
    for combo in combos:
        sorted_combo = sorted(combo)
        if has_consecutive(sorted_combo):
            combo_score = sum(scores3.get(n, 0) for n in combo)
            if combo_score > best_score and not _is_exact_duplicate(sorted_combo):
                best_score = combo_score
                best_combo = sorted_combo
    
    if best_combo:
        line13 = best_combo
    else:
        line13 = _unique_line(lambda: sorted(random.sample(top3_15, 6)))
    line13 = _ensure_unique(line13, top3_15)
    
    result['logic3'].append(line13)
    all_generated.append(line13)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 종합 2줄
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    scores_final = {}
    for n in range(1, 46):
        scores_final[n] = (
            scores1.get(n, 0) * ai_weights['logic1'] +
            scores2.get(n, 0) * ai_weights['logic2'] +
            scores3.get(n, 0) * ai_weights['logic3']
        )
    
    top_final_12 = get_top_candidates(scores_final, 12)
    
    line14 = select_by_zone_balance(top_final_12, (2, 2, 2))
    line14 = _ensure_unique(line14, top_final_12)
    result['final'].append(line14)
    all_generated.append(line14)
    
    line15 = sorted(top_final_12[:6])
    line15 = _ensure_unique(line15, top_final_12)
    result['final'].append(line15)
    all_generated.append(line15)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # AI 핵심 5줄 (다양성 보장)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    ai_core_10 = get_top_candidates(scores_final, 10)
    core_combos = list(combinations(ai_core_10, 6))
    
    # 각 조합 평가
    scored_combos = []
    for combo in core_combos:
        combo_list = sorted(list(combo))
        
        # 기존 15줄과 중복 체크
        is_dup = False
        for existing in all_generated:
            if is_duplicate(combo_list, existing, 6):  # 6개 모두 같으면
                is_dup = True
                break
        
        if is_dup:
            continue
        
        # 점수 계산
        score = sum(scores_final.get(n, 0) for n in combo)
        
        # 패턴 보너스
        odd_cnt = sum(1 for n in combo if n % 2 == 1)
        if odd_cnt == 3:
            score += 10
        
        z1 = sum(1 for n in combo if 1 <= n <= 15)
        z2 = sum(1 for n in combo if 16 <= n <= 30)
        z3 = sum(1 for n in combo if 31 <= n <= 45)
        if (z1, z2, z3) == (2, 2, 2):
            score += 10
        
        if has_consecutive(combo_list):
            score += 5
        
        s = calculate_sum(combo)
        if 130 <= s <= 140:
            score += 10
        
        scored_combos.append((combo_list, score))
    
    # 점수 높은 5줄 선택 (다양성 체크)
    scored_combos.sort(key=lambda x: x[1], reverse=True)
    
    for combo, score in scored_combos:
        # 이미 선택된 AI 핵심 번호와도 체크
        is_dup = False
        for existing in result['ai_core']:
            if is_duplicate(combo, existing, 5):  # 5개 이상 겹치면
                is_dup = True
                break
        
        if not is_dup:
            combo = _ensure_unique(combo, ai_core_10)
            result['ai_core'].append(combo)
        
        if len(result['ai_core']) >= 5:
            break
    
    # 부족하면 채우기
    while len(result['ai_core']) < 5:
        # 랜덤 조합
        random_combo = sorted(random.sample(ai_core_10, 6))
        result['ai_core'].append(random_combo)
    
    return result


# 하위 호환성
def generate_15_lines(user_id: int, stats: Dict) -> Dict[str, List[List[int]]]:
    """15줄 생성 (하위 호환용)"""
    result_20 = generate_20_lines(user_id, stats)
    
    result_15 = {
        'basic': result_20['basic'] + [result_20['logic1'][0]],
        'plan1': result_20['logic1'][1:] + result_20['logic2'][:2],
        'plan2': result_20['logic2'][2:] + result_20['logic3'][:2] + result_20['final']
    }
    
    return result_15
