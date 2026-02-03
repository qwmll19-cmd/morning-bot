# ML 스케줄 및 재학습 검증 가이드

## 🎯 목적
ML 모델이 정확히 스케줄에 따라 재학습되고, 성능이 실제로 개선되는지 확인합니다.

---

## 📋 검증 단계

### 1단계: 수동 워크플로우 테스트

가장 먼저 수동으로 전체 워크플로우를 테스트합니다.

```bash
python3 test_ml_schedule_verification.py
```

**옵션 1 선택** - 전체 워크플로우 테스트

#### 확인 사항:
- ✅ 현재 ML 모델이 정상적으로 로드되는가?
- ✅ 가중치가 올바르게 표시되는가?
- ✅ 성능 평가가 정상적으로 실행되는가?
- ✅ Grid Search가 최적의 가중치를 찾는가?
- ✅ 새로운 가중치가 이전 가중치와 비교되는가?
- ✅ 성능 점수가 개선되는가? (또는 양호한 수준을 유지하는가?)
- ✅ 모델에 새 가중치를 저장할 수 있는가?

#### 예상 출력:
```
📊 현재 가중치:
  • logic1: 25.00%
  • logic2: 25.00%
  • logic3: 25.00%
  • logic4: 25.00%

📊 평가 결과:
  • 3개 맞음: X줄
  • 4개 맞음: X줄
  • 5개 맞음: X줄
  • 6개 맞음: X줄
  • 줄당 평균: X.XX개
  • 성능 점수: XX.X/100

📊 새로운 최적 가중치:
  • logic1: XX.XX%
  • logic2: XX.XX%
  • logic3: XX.XX%
  • logic4: XX.XX%

📊 최고 평균 점수: XX.XX/100

🟢 성능 개선: XX.X → XX.X (+X.X점)
```

---

### 2단계: 스케줄러 설정 확인

```bash
python3 test_ml_schedule_verification.py
```

**옵션 2 선택** - 스케줄 확인

#### 확인 사항:
- ✅ 스케줄러 모듈이 정상 로드되는가?
- ✅ 작업이 올바른 시간에 등록되어 있는가?
  - 로또 당첨번호 수집: 매주 토요일 21:00
  - ML 성능 평가: 매주 토요일 22:00

---

### 3단계: 실제 스케줄러 실행 확인

애플리케이션을 실행하여 스케줄러가 정상 작동하는지 확인합니다.

```bash
./run.sh
```

#### 로그에서 확인할 내용:

**시작 시 로그:**
```
Scheduler started - ...
  • News 수집: 매일 06:00, 09:00, ...
  • Lotto 수집: 토요일 21:00
  • Lotto ML 평가: 토요일 22:00
```

**토요일 22:00 실행 로그 (자동):**
```
=== 로또 ML 성능 평가 시작 ===
[INFO] 최신 회차 XXXX회 성능 평가 중...
[INFO] 성능 점수: XX.X/100
[INFO] ✅ 성능 평가 완료

[INFO] 재학습 필요 여부 확인 중...
[INFO] 성능 점수가 XX.X점 (기준: 40.0점)
[INFO] ✅ 재학습 확인 완료
```

**재학습이 필요한 경우 (성능 < 40점):**
```
[WARNING] 성능이 기준 미달! Grid Search 시작...
[INFO] Grid Search 진행 중...
[INFO] 테스트 조합: XXX개
[INFO] 최적 가중치 발견: logic1=X.XX, logic2=X.XX, logic3=X.XX, logic4=X.XX
[INFO] 최고 점수: XX.XX
[INFO] ✅ 새로운 가중치 저장 완료
[INFO] ✅ 재학습 완료
```

---

### 4단계: DB에서 성능 기록 확인

```bash
sqlite3 backend/database.db
```

```sql
-- 최근 성능 평가 기록 확인
SELECT
    draw_no,
    datetime(evaluated_at, 'localtime') as eval_time,
    performance_score,
    needs_retraining,
    retrained,
    datetime(retrained_at, 'localtime') as retrain_time
FROM lotto_ml_performance
ORDER BY draw_no DESC
LIMIT 10;

-- 재학습 기록 확인
SELECT
    draw_no,
    performance_score,
    new_weights,
    grid_search_results
FROM lotto_ml_performance
WHERE retrained = 1
ORDER BY draw_no DESC;
```

#### 확인 사항:
- ✅ 매주 토요일 22:00 이후 새로운 레코드가 생성되는가?
- ✅ `performance_score`가 정확히 계산되어 있는가?
- ✅ 성능이 40점 미만일 때 `needs_retraining = 1`로 설정되는가?
- ✅ 재학습 후 `retrained = 1`로 업데이트되는가?
- ✅ `new_weights`와 `grid_search_results`가 저장되는가?

---

### 5단계: 텔레그램에서 성능 확인

관리자 계정에서 텔레그램 봇 명령어를 실행합니다.

```
/lotto_performance
```

또는 특정 회차 수 지정:

```
/lotto_performance 10
```

#### 확인 사항:
- ✅ 최근 N회차의 성능 평가 결과가 표시되는가?
- ✅ 각 회차별로 다음 정보가 나타나는가?
  - 평가 시각
  - 3개, 4개, 5개, 6개 맞은 줄 수
  - 줄당 평균 맞은 개수
  - 성능 점수 (0-100)
  - 로직별 평균 성능
  - 사용된 가중치
  - 재학습 여부 및 시각

---

## 🧪 추가 테스트 시나리오

### 시나리오 1: 성능이 낮을 때 자동 재학습
1. `test_ml_performance.py` 실행
2. 옵션 4 선택 (자동 재학습 확인)
3. 성능이 40점 미만인 회차가 있으면 자동으로 Grid Search 실행됨
4. 최적 가중치가 자동으로 모델에 저장됨

### 시나리오 2: Grid Search 수동 실행
1. `test_ml_performance.py` 실행
2. 옵션 3 선택 (Grid Search 재학습)
3. 테스트 회차 수 입력 (권장: 10회)
4. 약 200-300개 조합 테스트
5. 최적 가중치 확인
6. 저장 여부 선택

### 시나리오 3: 백테스팅
1. `test_ml_performance.py` 실행
2. 옵션 2 선택 (백테스팅)
3. 테스트 회차 수 입력
4. 여러 회차에 걸친 성능 추이 확인

---

## 📊 성능 개선 판단 기준

### 성능 점수 해석
- **60점 이상**: 🟢 양호 - 재학습 불필요
- **40-60점**: 🟡 보통 - 모니터링 필요
- **40점 미만**: 🔴 낮음 - 재학습 필요

### 개선 확인 방법
1. **재학습 전 점수 기록**
2. **Grid Search 실행**
3. **재학습 후 점수 비교**
4. **최소 2-3회차 이상에서 일관된 개선 확인**

---

## ⚠️ 주의사항

### 1. 데이터 충분성
- Grid Search는 최소 10회차 이상의 데이터가 필요합니다
- DB에 충분한 로또 데이터가 있는지 확인하세요

### 2. 실행 시간
- Grid Search는 약 200-300개 조합을 테스트하므로 시간이 걸립니다
- 테스트 회차가 많을수록 더 오래 걸립니다
- 10회차 기준 약 2-5분 소요

### 3. 과적합 주의
- 너무 적은 회차로 테스트하면 과적합 위험
- 최소 10회차 이상 권장

### 4. 스케줄러 시간
- 로또 당첨번호 수집: 토요일 21:00
- ML 성능 평가 및 재학습: 토요일 22:00 (수집 1시간 후)
- 1시간 간격은 데이터 안정화를 위함

---

## ✅ 검증 체크리스트

### 수동 테스트
- [ ] `test_ml_schedule_verification.py` 전체 워크플로우 테스트 완료
- [ ] 현재 모델 상태 정상 확인
- [ ] 성능 평가 정상 실행 확인
- [ ] Grid Search 정상 실행 확인
- [ ] 가중치 변화 확인
- [ ] 성능 개선 또는 유지 확인
- [ ] 모델 저장 정상 작동 확인

### 스케줄러 테스트
- [ ] `test_ml_schedule_verification.py` 스케줄 확인 완료
- [ ] 스케줄러 모듈 정상 로드 확인
- [ ] 작업 등록 시간 확인 (토요일 22:00)

### 실제 운영 확인
- [ ] 애플리케이션 시작 로그에서 스케줄러 확인
- [ ] 토요일 22:00 자동 실행 로그 확인
- [ ] DB에 성능 기록 저장 확인
- [ ] 텔레그램 `/lotto_performance` 명령 정상 작동 확인

### DB 검증
- [ ] `lotto_ml_performance` 테이블에 레코드 생성 확인
- [ ] 성능 점수 정확히 계산 확인
- [ ] 재학습 필요 여부 플래그 정확히 설정 확인
- [ ] 재학습 후 업데이트 확인

---

## 🚀 다음 단계

모든 검증이 완료되면:
1. ✅ 시스템이 정상 작동함을 확인
2. 📊 매주 토요일 자동으로 성능 평가 및 재학습 실행됨
3. 🔍 `/lotto_performance` 명령으로 언제든 결과 확인 가능
4. 📈 성능이 지속적으로 모니터링되고 개선됨

---

## 📞 문제 발생 시

### 로그 확인
```bash
tail -f backend/logs/app.log | grep -i "lotto\|ml\|grid"
```

### DB 직접 확인
```bash
sqlite3 backend/database.db "SELECT * FROM lotto_ml_performance ORDER BY draw_no DESC LIMIT 5;"
```

### 스케줄러 재시작
```bash
pkill -f "python.*main.py"
./run.sh
```
