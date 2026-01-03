# 🎯 로또봇 개발 완전 체크리스트

## ⚠️ 중요: 이 파일을 먼저 읽으세요!

이 체크리스트는 기존 morning-bot 프로젝트에 로또 기능을 추가하는 전체 과정입니다.

---

# Phase 0: 사전 확인 (10분) ⚠️ 필수

## ✅ 체크리스트 0-1: 프로젝트 백업

```bash
# Git 백업
git add .
git commit -m "로또 기능 추가 전 백업"
git branch backup-before-lotto-$(date +%Y%m%d)

# DB 백업
mkdir -p ~/backups
pg_dump -U your_user -d morning_bot > ~/backups/backup_$(date +%Y%m%d_%H%M%S).sql

# 백업 확인
ls -lh ~/backups/
```

**확인:**
- [ ] Git 백업 완료
- [ ] DB 덤프 완료

---

## ✅ 체크리스트 0-2: 기존 DB 연결 방식 확인

```bash
# DB 라이브러리 확인
cd ~/projects/morning-bot
grep -r "import.*psycopg\|import.*asyncpg" backend/
```

**확인:**
- [ ] asyncpg 사용 중 → OK
- [ ] psycopg2 사용 중 → 코드 수정 필요
- [ ] 없음 → asyncpg 새로 도입

---

## ✅ 체크리스트 0-3: DB 접속 테스트

```bash
psql -U your_user -d morning_bot -c "SELECT version();"
```

**확인:**
- [ ] DB 접속 성공

---

# Phase 1: 환경 설정 (10분)

## ✅ 체크리스트 1-1: 패키지 설치

```bash
cd ~/projects/morning-bot/backend

# requirements.txt 백업
cp requirements.txt requirements.txt.backup

# 로또 패키지 추가
cat >> requirements.txt <<'EOF'

# 로또 기능 패키지
beautifulsoup4==4.12.3
lxml==5.1.0
matplotlib==3.8.2
asyncpg==0.29.0
APScheduler==3.10.4
pytz==2024.1
EOF

# 설치
pip install -r requirements.txt
```

**확인:**
- [ ] 패키지 설치 완료
- [ ] 에러 없음

---

# Phase 2: DB 스키마 생성 (15분)

## ✅ 체크리스트 2-1: 스키마 적용

```bash
cd ~/projects/morning-bot

# 스키마 적용
psql -U your_user -d morning_bot -f db/lotto/schema.sql

# 확인
psql -U your_user -d morning_bot -c "\dt lotto_*"
```

**예상 결과:**
```
lotto_draws
lotto_recommend_logs
lotto_stats_cache
```

**확인:**
- [ ] 3개 테이블 생성 완료

---

# Phase 3: config.py 설정 (5분)

## ✅ 체크리스트 3-1: 필수 설정 추가

```bash
cd ~/projects/morning-bot/backend

# config.py 편집
vim config.py  # 또는 nano, code 등
```

**추가할 내용:**
```python
# Database
DATABASE_URL = "postgresql://your_user:your_password@localhost/morning_bot"

# Admin
ADMIN_CHAT_ID = 123456789  # 실제 텔레그램 chat ID
```

**확인:**
- [ ] DATABASE_URL 설정
- [ ] ADMIN_CHAT_ID 설정

---

# Phase 4: 초기 데이터 수집 (10분)

## ✅ 체크리스트 4-1: API 테스트

```bash
cd ~/projects/morning-bot/backend
python scripts/lotto/test_collection.py
```

**확인:**
- [ ] API 호출 성공
- [ ] 최신 회차 조회 성공

---

## ✅ 체크리스트 4-2: 전체 데이터 수집

```bash
cd ~/projects/morning-bot/backend
python scripts/lotto/init_data.py
```

**예상 소요 시간:** 6~10분

**확인:**
- [ ] 약 1148개 회차 수집 완료
- [ ] 에러 없음

---

## ✅ 체크리스트 4-3: 데이터 검증

```bash
psql -U your_user -d morning_bot <<EOF
SELECT COUNT(*) FROM lotto_draws;
SELECT MIN(draw_no), MAX(draw_no) FROM lotto_draws;
SELECT draw_no, draw_date, n1, n2, n3, n4, n5, n6, bonus 
FROM lotto_draws 
ORDER BY draw_no DESC 
LIMIT 5;
EOF
```

**확인:**
- [ ] 약 1148개 회차 저장
- [ ] 최신 데이터 정상

---

# Phase 5: 통계 캐시 생성 (5분)

## ✅ 체크리스트 5-1: 캐시 생성

```bash
cd ~/projects/morning-bot/backend
python scripts/lotto/init_stats_cache.py
```

**확인:**
- [ ] 캐시 생성 완료
- [ ] 에러 없음

---

## ✅ 체크리스트 5-2: 캐시 검증

```bash
psql -U your_user -d morning_bot -c "SELECT * FROM lotto_stats_cache WHERE id = 1;"
```

**확인:**
- [ ] 캐시 데이터 존재
- [ ] updated_at 시간 최신

---

# Phase 6: bot.py 통합 (30분)

## ✅ 체크리스트 6-1: bot.py 백업

```bash
cd ~/projects/morning-bot/backend/app
cp bot.py bot.py.backup
```

**확인:**
- [ ] bot.py 백업 완료

---

## ✅ 체크리스트 6-2: bot.py 수정

**BOT_INTEGRATION.md 파일 참고하여 수정**

**추가할 내용:**
1. import 추가
2. post_init 함수 추가 (DB 풀)
3. post_shutdown 함수 추가
4. setup_schedulers 함수 추가
5. 핸들러 등록

**확인:**
- [ ] import 추가 완료
- [ ] DB 풀 초기화 추가
- [ ] 스케줄러 추가
- [ ] /lotto 핸들러 등록
- [ ] 종료 핸들러 추가

---

# Phase 7: 테스트 실행 (20분)

## ✅ 체크리스트 7-1: 봇 실행

```bash
cd ~/projects/morning-bot/backend
python app/bot.py
```

**확인:**
- [ ] 봇 정상 실행
- [ ] DB 풀 생성 메시지 표시
- [ ] 스케줄러 시작 메시지 표시
- [ ] 에러 없음

---

## ✅ 체크리스트 7-2: 텔레그램 테스트

**텔레그램에서:**
1. `/lotto` 명령어 전송
2. 6줄 번호 응답 확인
3. 기존 뉴스 명령어 정상 동작 확인

**확인:**
- [ ] /lotto 명령어 응답 정상
- [ ] 6줄 생성 확인
- [ ] 각 줄마다 6개 번호 (1~45 범위)
- [ ] 기존 뉴스 명령어 정상

---

## ✅ 체크리스트 7-3: 추천 로그 확인

```bash
psql -U your_user -d morning_bot -c "SELECT COUNT(*) FROM lotto_recommend_logs;"
```

**확인:**
- [ ] 로그 저장 확인 (테스트한 횟수만큼)

---

# Phase 8: 스케줄러 테스트 (10분)

## ✅ 체크리스트 8-1: 시간 변경 테스트

**bot.py에서 임시로 시간 변경:**
```python
# hour=21 → hour=현재시각+1분
```

**봇 재시작 후 1분 대기**

**확인:**
- [ ] 1분 후 스케줄러 실행
- [ ] 관리자 텔레그램 메시지 수신
- [ ] 에러 없음

**원복:**
```python
# hour=현재시각+1분 → hour=21
```

---

# Phase 9: 최종 확인 (10분)

## ✅ 체크리스트 9-1: 전체 기능 확인

```bash
# DB 상태
psql -U your_user -d morning_bot <<EOF
SELECT 
  (SELECT COUNT(*) FROM lotto_draws) as draws,
  (SELECT COUNT(*) FROM lotto_stats_cache) as cache,
  (SELECT COUNT(*) FROM lotto_recommend_logs) as logs;
EOF

# 봇 프로세스
ps aux | grep "python.*bot.py"
```

**확인:**
- [ ] lotto_draws: 약 1148개
- [ ] lotto_stats_cache: 1개
- [ ] lotto_recommend_logs: 테스트 횟수
- [ ] 봇 정상 실행 중

---

## ✅ 체크리스트 9-2: 롤백 방법 숙지

**문제 발생 시:**

```bash
# 1. 코드 롤백
cd ~/projects/morning-bot
git checkout backup-before-lotto-YYYYMMDD

# 2. DB 롤백
psql -U your_user -d morning_bot <<EOF
DROP TABLE IF EXISTS lotto_draws CASCADE;
DROP TABLE IF EXISTS lotto_stats_cache CASCADE;
DROP TABLE IF EXISTS lotto_recommend_logs CASCADE;
EOF

# 3. DB 복구
psql -U your_user -d morning_bot < ~/backups/backup_YYYYMMDD_HHMMSS.sql
```

**확인:**
- [ ] 롤백 방법 숙지

---

# ✅ 최종 체크리스트

## Phase 0: 사전 확인
- [ ] Git 백업
- [ ] DB 백업
- [ ] DB 연결 방식 확인

## Phase 1: 환경 설정
- [ ] 패키지 설치

## Phase 2: DB 스키마
- [ ] 3개 테이블 생성

## Phase 3: config.py
- [ ] DATABASE_URL 설정
- [ ] ADMIN_CHAT_ID 설정

## Phase 4: 초기 데이터
- [ ] API 테스트
- [ ] 1148개 회차 수집
- [ ] 데이터 검증

## Phase 5: 통계 캐시
- [ ] 캐시 생성
- [ ] 캐시 검증

## Phase 6: bot.py 통합
- [ ] bot.py 백업
- [ ] bot.py 수정

## Phase 7: 테스트
- [ ] 봇 실행
- [ ] /lotto 명령어 테스트
- [ ] 기존 기능 정상 확인

## Phase 8: 스케줄러
- [ ] 스케줄러 테스트

## Phase 9: 최종 확인
- [ ] 전체 기능 확인
- [ ] 롤백 방법 숙지

---

# 🎉 완료!

모든 체크리스트를 통과했으면 로또봇 개발 완료입니다!

**문제 발생 시:**
1. 어느 Phase인지 확인
2. 해당 Phase 체크리스트 재확인
3. 에러 메시지 전체 복사
4. 롤백 후 재시도
