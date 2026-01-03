"""AI 핵심번호 학습 스크립트 (500~1024회)"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from backend.app.db.session import SessionLocal
from backend.app.db.models import LottoDraw
from backend.app.services.lotto.stats_calculator import LottoStatsCalculator
from collections import defaultdict

def train_ai_core():
    """500~1024회 학습"""
    db = SessionLocal()
    
    print("="*60)
    print("AI 핵심번호 학습 시작 (500~1024회)")
    print("="*60)
    
    # 500~1024회 데이터 조회
    draws = db.query(LottoDraw).filter(
        LottoDraw.draw_no >= 500,
        LottoDraw.draw_no <= 1024
    ).order_by(LottoDraw.draw_no).all()
    
    print(f"\n학습 데이터: {len(draws)}회")
    
    if len(draws) < 100:
        print("⚠️ 학습 데이터 부족 (최소 100회 필요)")
        db.close()
        return
    
    # 회차별 테스트
    logic1_matches = []
    logic2_matches = []
    logic3_matches = []
    
    print("\n학습 진행 중...")
    
    for test_idx in range(100, len(draws)):  # 최소 100회 이후부터 테스트
        # 학습 데이터
        train_draws = draws[:test_idx]
        train_dict = [
            {
                'draw_no': d.draw_no,
                'n1': d.n1, 'n2': d.n2, 'n3': d.n3,
                'n4': d.n4, 'n5': d.n5, 'n6': d.n6,
                'bonus': d.bonus
            }
            for d in train_draws
        ]
        
        # 테스트 회차
        test_draw = draws[test_idx]
        actual_nums = {test_draw.n1, test_draw.n2, test_draw.n3, 
                      test_draw.n4, test_draw.n5, test_draw.n6}
        
        # 3가지 로직 점수 계산
        scores1 = LottoStatsCalculator.calculate_ai_scores_logic1(train_dict)
        scores2 = LottoStatsCalculator.calculate_ai_scores_logic2(train_dict)
        scores3 = LottoStatsCalculator.calculate_ai_scores_logic3(train_dict)
        
        # 각 로직 상위 10개 선정
        top1 = sorted(scores1.items(), key=lambda x: x[1], reverse=True)[:10]
        top2 = sorted(scores2.items(), key=lambda x: x[1], reverse=True)[:10]
        top3 = sorted(scores3.items(), key=lambda x: x[1], reverse=True)[:10]
        
        pred1 = {int(n) for n, _ in top1}
        pred2 = {int(n) for n, _ in top2}
        pred3 = {int(n) for n, _ in top3}
        
        # 일치 개수 계산
        match1 = len(pred1 & actual_nums)
        match2 = len(pred2 & actual_nums)
        match3 = len(pred3 & actual_nums)
        
        logic1_matches.append(match1)
        logic2_matches.append(match2)
        logic3_matches.append(match3)
        
        if test_idx % 100 == 0:
            print(f"  진행: {test_idx}/{len(draws)} 회차...")
    
    # 결과 분석
    avg1 = sum(logic1_matches) / len(logic1_matches)
    avg2 = sum(logic2_matches) / len(logic2_matches)
    avg3 = sum(logic3_matches) / len(logic3_matches)
    
    win1 = sum(1 for m in logic1_matches if m >= 3)
    win2 = sum(1 for m in logic2_matches if m >= 3)
    win3 = sum(1 for m in logic3_matches if m >= 3)
    
    print("\n" + "="*60)
    print("학습 결과")
    print("="*60)
    print(f"\n로직1 (현재):")
    print(f"  평균 일치: {avg1:.2f}개")
    print(f"  3개 이상: {win1}회 ({win1/len(logic1_matches)*100:.1f}%)")
    
    print(f"\n로직2 (최근30회 강화):")
    print(f"  평균 일치: {avg2:.2f}개")
    print(f"  3개 이상: {win2}회 ({win2/len(logic2_matches)*100:.1f}%)")
    
    print(f"\n로직3 (최근100회):")
    print(f"  평균 일치: {avg3:.2f}개")
    print(f"  3개 이상: {win3}회 ({win3/len(logic3_matches)*100:.1f}%)")
    
    # 최적 가중치 계산
    total_score = avg1 + avg2 + avg3
    weight1 = avg1 / total_score
    weight2 = avg2 / total_score
    weight3 = avg3 / total_score
    
    print("\n" + "="*60)
    print("최적 가중치")
    print("="*60)
    print(f"로직1: {weight1:.3f}")
    print(f"로직2: {weight2:.3f}")
    print(f"로직3: {weight3:.3f}")
    
    print("\n✅ 학습 완료!")
    print("\n💡 이 가중치를 lotto_handler.py의 ai_weights에 적용하세요:")
    print(f"   'logic1': {weight1:.2f},")
    print(f"   'logic2': {weight2:.2f},")
    print(f"   'logic3': {weight3:.2f}")
    
    db.close()

if __name__ == "__main__":
    train_ai_core()
