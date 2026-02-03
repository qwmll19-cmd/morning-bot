# 로또 ML 성능 평가 및 자동 재학습 시스템

## 📋 개요

이 시스템은 ML 기반 로또 예측의 정확도를 자동으로 측정하고, 성능이 낮을 때 Grid Search를 통해 최적의 가중치를 찾아 모델을 자동으로 재학습합니다.

**중요**: 모든 성능 평가와 재학습은 **내부적으로만 실행**되며, **사용자에게는 아무런 알림이 가지 않습니다.**

---

## 🎯 주요 기능

### 1. 사용자 예측 자동 저장
- 사용자가 `/lotto` 명령으로 번호 생성 시 자동으로 DB에 저장
- `lotto_user_predictions` 테이블에 저장
- chat_id, 예측 회차, 생성한 줄 수, 번호 조합 저장

### 2. 개인 결과 자동 분석
- `/lotto_result [회차]` 명령 시 개인 예측 결과 자동 분석
- 3개, 4개, 5개, 6개 맞은 줄 수 표시
- 총 맞은 번호 개수 및 줄당 평균 표시
- **예측하지 않은 사용자에게는 당첨번호만 표시**

### 3. ML 성능 자동 평가 (내부)
- **매주 일요일 10시 자동 실행**
- 가장 최근 회차의 예측 정확도 측정
- 25줄 전체에 대한 당첨 통계 계산
- 로직별 성능 분석 (Logic1-4, ML)
- `lotto_ml_performance` 테이블에 결과 저장
- **사용자에게 알림 없음** (내부 평가만)

### 4. Grid Search 자동 재학습
- 성능 점수가 40점/100 미만일 때 자동으로 재학습 트리거
- 최근 10회차 데이터로 Grid Search 실행
- Logic1-4 가중치 조합 테스트 (10%-40% 범위, 5% 단위)
- 최적 가중치 자동 적용
- 재학습 정보 DB에 기록

---

## 📊 DB 테이블

### `lotto_user_predictions`
사용자 예측 저장 및 개인 결과 추적

| 컬럼 | 설명 |
|------|------|
| chat_id | 텔레그램 채팅 ID |
| target_draw_no | 예측 대상 회차 |
| lines | 예측한 번호 조합들 (JSON) |
| line_count | 생성한 줄 수 (5, 10, 15, 20, 25) |
| analyzed | 분석 완료 여부 |
| match_3 ~ match_6 | 각 등급별 맞은 줄 수 |
| total_matches | 총 맞은 번호 개수 |

### `lotto_ml_performance`
ML 모델 성능 추적

| 컬럼 | 설명 |
|------|------|
| draw_no | 평가 대상 회차 |
| total_lines | 평가한 총 줄 수 (25줄) |
| match_3 ~ match_6 | 각 등급별 맞은 줄 수 |
| avg_matches_per_line | 줄당 평균 맞은 개수 |
| logic1_score ~ logic4_score | 로직별 평균 점수 |
| ml_score | ML 5줄 평균 점수 |
| performance_score | 종합 성능 점수 (0-100) |
| needs_retraining | 재학습 필요 여부 |
| retrained | 재학습 완료 여부 |
| new_weights | 재학습 후 새 가중치 (JSON) |
| grid_search_results | Grid Search 결과 (JSON) |

---

## ⏰ 스케줄

### 토요일 21:00
- 로또 당첨번호 수집
- 통계 캐시 갱신
- ML 모델 기본 재학습

### 토요일 22:00 (NEW)
- **ML 성능 자동 평가** (내부 실행, 사용자 알림 없음)
- 최신 회차 정확도 측정
- 성능이 40점 미만이면 Grid Search 재학습 자동 실행
- 당첨번호 수집 1시간 후 실행 (데이터 안정화)

---

## 🧪 테스트 방법

### 1. DB 테이블 생성
```bash
python3 update_db_lotto_ml.py
```

### 2. ML 성능 평가 테스트
```bash
python3 test_ml_performance.py
```

메뉴:
1. **단일 회차 성능 평가**: 특정 회차의 예측 정확도 측정
2. **백테스팅**: 여러 회차에 대한 성능 평가 및 통계
3. **Grid Search 재학습**: 최적 가중치 찾기 (테스트 모드)
4. **자동 재학습 확인**: 성능이 낮은 회차 자동 재학습

### 3. 사용자 시나리오 테스트

#### 3-1. 번호 생성 및 저장
```
사용자: /lotto
봇: [5줄/10줄/15줄/20줄/25줄 버튼 표시]
사용자: [버튼 클릭]
봇: [선택한 줄 수만큼 번호 생성]
→ DB에 자동 저장됨 (lotto_user_predictions)
```

#### 3-2. 개인 결과 확인
```
사용자: /lotto_result 1206
봇:
🎰 1206회 당첨 결과
🎯 당첨번호: 01, 12, 23, 34, 42, 45
🎁 보너스: 15

━━━━━━━━━━━━━━━━━━━
🎉 회원님의 결과
━━━━━━━━━━━━━━━━━━━

📊 생성한 줄 수: 25줄

🎯 5등 당첨! (3개 맞음) - 3줄

📈 상세 통계:
  • 3개 맞은 줄: 3줄
  • 4개 맞은 줄: 0줄
  • 5개 맞은 줄: 0줄
  • 6개 맞은 줄: 0줄
  • 총 맞은 번호: 54개
  • 줄당 평균: 2.16개
```

#### 3-3. 예측하지 않은 회차 조회
```
사용자: /lotto_result 1200
봇:
🎰 1200회 당첨 결과
🎯 당첨번호: 05, 11, 22, 33, 41, 44
🎁 보너스: 18

━━━━━━━━━━━━━━━━━━━
⚠️ 이 회차에 추천 번호가 없습니다.

💡 /lotto 명령어로 번호를 받으면
   다음 회차부터 자동으로 당첨 확인됩니다!
```

---

## 📈 성능 평가 방법

### 성능 점수 계산
```
성능 점수 = (줄당 평균 맞은 개수 / 3.0) × 100

예시:
- 줄당 평균 1.5개 → 50점
- 줄당 평균 2.0개 → 66.7점
- 줄당 평균 3.0개 → 100점
```

### 재학습 기준
- **40점 미만**: 재학습 필요 (needs_retraining = True)
- **40-60점**: 보통 (모니터링)
- **60점 이상**: 양호

---

## 🔧 Grid Search 설정

### 가중치 후보
- Logic1: 10%, 15%, 20%, 25%, 30%, 35%, 40%
- Logic2: 10%, 15%, 20%, 25%, 30%, 35%, 40%
- Logic3: 10%, 15%, 20%, 25%, 30%, 35%, 40%
- Logic4: 10%, 15%, 20%, 25%, 30%, 35%, 40%

### 조합 생성
- 합이 1.0인 조합만 테스트
- 유효한 조합 수: 약 200-300개

### 평가 방법
- 최근 N회차 (기본 10회) 백테스팅
- 각 조합의 평균 성능 점수 계산
- 최고 점수 조합 선택

---

## 🚀 수동 실행 방법

### 단일 회차 평가
```python
from backend.app.services.lotto.performance_evaluator import evaluate_single_draw, save_performance_to_db

result = evaluate_single_draw(1206)
save_performance_to_db(result)
```

### 백테스팅
```python
from backend.app.services.lotto.performance_evaluator import backtest_multiple_draws, print_backtest_summary

results = backtest_multiple_draws(1200, 1206)  # 1200~1206회 평가
print_backtest_summary(results)
```

### Grid Search 재학습
```python
from backend.app.services.lotto.grid_search_retrainer import retrain_with_grid_search

result = retrain_with_grid_search(test_draw_count=10, save_to_model=True)
```

### 자동 재학습 확인
```python
from backend.app.services.lotto.grid_search_retrainer import check_and_retrain_if_needed

check_and_retrain_if_needed()
```

---

## 📝 주요 파일

| 파일 | 설명 |
|------|------|
| `backend/app/db/models.py` | LottoUserPrediction, LottoMLPerformance 모델 |
| `backend/app/handlers/lotto/lotto_handler.py` | 사용자 예측 저장 및 결과 표시 |
| `backend/app/services/lotto/performance_evaluator.py` | 성능 평가 및 백테스팅 |
| `backend/app/services/lotto/grid_search_retrainer.py` | Grid Search 재학습 |
| `backend/app/scheduler/jobs.py` | 스케줄러 (일요일 10시 평가) |
| `update_db_lotto_ml.py` | DB 마이그레이션 스크립트 |
| `test_ml_performance.py` | 테스트 스크립트 |

---

## ✅ 체크리스트

- [x] DB 테이블 생성 (LottoUserPrediction, LottoMLPerformance)
- [x] 사용자 예측 자동 저장 구현
- [x] /lotto_result 개인 결과 표시 구현
- [x] 성능 평가 함수 구현 (evaluate_single_draw)
- [x] 백테스팅 함수 구현 (backtest_multiple_draws)
- [x] Grid Search 재학습 구현 (grid_search_weights)
- [x] 자동 재학습 트리거 구현 (check_and_retrain_if_needed)
- [x] 스케줄러 작업 추가 (일요일 10시)
- [x] 테스트 스크립트 작성
- [x] 문서화

---

## 🎯 사용자 경험

### 일반 사용자가 보는 것
1. `/lotto` 명령으로 번호 생성 (버튼 선택)
2. `/lotto_result [회차]` 명령으로 개인 결과 확인

### 관리자가 보는 것 (NEW)
3. `/lotto_performance [회차수]` 명령으로 ML 성능 평가 결과 조회
   - 최근 N회(기본 5회, 최대 20회) 성능 평가 결과 확인
   - 전체 성능 통계 (3개, 4개, 5개, 6개 맞은 줄 수)
   - 성능 점수 (0-100점)
   - 로직별 평균 성능
   - 사용된 가중치 정보
   - 재학습 여부 및 시각

### 사용자가 보지 못하는 것 (백그라운드 내부 처리)
1. 매주 토요일 22시 성능 평가 (자동 실행)
2. Grid Search 자동 재학습
3. DB에 성능 기록 저장

**→ 일반 사용자에게는 아무런 알림이나 메시지가 가지 않습니다!**
**→ 관리자는 `/lotto_performance` 명령으로 언제든지 성능을 확인할 수 있습니다!**

---

## 🔒 개인정보 보호

- 사용자 예측은 chat_id로만 저장 (개인정보 없음)
- 성능 평가는 시스템 전체 정확도만 측정 (개인별 데이터 수집 안 함)
- 사용자가 `/lotto_result` 조회 시에만 개인 결과 분석 및 표시
