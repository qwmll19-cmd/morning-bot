# DB 마이그레이션 가이드

## 📋 개요

이 마이그레이션은 `NewsDaily` 테이블에 `topic_key` 필드를 추가합니다.

**변경 내용:**
- `topic_key` 컬럼 추가 (VARCHAR(100), nullable, indexed)
- 기존 뉴스 데이터에 topic_key 자동 생성

**목적:**
- 뉴스 중복 방지
- 동일한 뉴스 제목 필터링
- 데이터 품질 향상

---

## 🚀 실행 방법

### 방법 1: 통합 스크립트 실행 (권장)

```bash
# 프로젝트 루트에서 실행
python scripts/migrate_db.py
```

**실행 순서:**
1. 자동 DB 백업 (morning_bot.db.backup_YYYYMMDD_HHMMSS)
2. topic_key 필드 추가
3. 기존 뉴스 데이터에 topic_key 생성
4. 검증

**예상 출력:**
```
============================================================
  Morning Bot DB 마이그레이션
  - NewsDaily 테이블에 topic_key 필드 추가
============================================================
✅ DB 백업 완료: morning_bot.db.backup_20251229_131733

🔧 Step 1: topic_key 필드 추가
  ✅ topic_key 컬럼 추가 완료
  ✅ 인덱스 생성 완료

🔧 Step 2: 기존 뉴스 데이터에 topic_key 생성
  → 150개의 뉴스 항목 처리 중...
    진행 중: 100/150
  ✅ 150개 뉴스 topic_key 생성 완료
  ✅ 검증 완료: 모든 뉴스에 topic_key가 생성되었습니다.

🔍 Step 3: 마이그레이션 검증
  → 전체 뉴스: 150개
  → topic_key 있음: 150개
  ✅ 모든 뉴스에 topic_key가 있습니다.

============================================================
  ✅ DB 마이그레이션 완료!
============================================================
```

---

### 방법 2: 단계별 실행

#### Step 1: 필드 추가
```bash
python scripts/add_topic_key_field.py
```

#### Step 2: 데이터 마이그레이션
```bash
python scripts/migrate_topic_keys.py
```

---

## 🧪 테스트 방법

### 1. 마이그레이션 확인

```bash
# Python 인터프리터 실행
python

# 코드 실행
from backend.app.db.session import SessionLocal
from backend.app.db.models import NewsDaily

db = SessionLocal()

# 전체 뉴스 수
total = db.query(NewsDaily).count()
print(f"전체 뉴스: {total}개")

# topic_key 있는 뉴스 수
with_key = db.query(NewsDaily).filter(NewsDaily.topic_key.isnot(None)).count()
print(f"topic_key 있음: {with_key}개")

# 샘플 확인
sample = db.query(NewsDaily).first()
if sample:
    print(f"\n샘플 뉴스:")
    print(f"  제목: {sample.title}")
    print(f"  topic_key: {sample.topic_key}")

db.close()
```

### 2. 뉴스 수집 테스트

```bash
# 새 뉴스 수집 테스트
python -c "
from backend.app.db.session import SessionLocal
from backend.app.collectors.news_collector import build_daily_top5

db = SessionLocal()
try:
    result = build_daily_top5(db)
    print('✅ 뉴스 수집 성공')
    print(f'종합 뉴스: {len(result.get(\"general\", []))}개')
    print(f'경제 뉴스: {len(result.get(\"economy\", []))}개')
except Exception as e:
    print(f'❌ 에러 발생: {e}')
finally:
    db.close()
"
```

### 3. 중복 방지 테스트

```bash
# 동일 제목 뉴스 중복 저장 시도
python -c "
from backend.app.db.session import SessionLocal
from backend.app.db.models import NewsDaily
from backend.app.collectors.news_collector import build_topic_key
from datetime import date

db = SessionLocal()

# 테스트 뉴스 생성
test_title = '테스트 뉴스 제목'
topic_key = build_topic_key(test_title)

# 첫 번째 저장
news1 = NewsDaily(
    date=date.today(),
    title=test_title,
    url='http://test1.com',
    category='general',
    topic_key=topic_key
)
db.add(news1)
db.commit()
print(f'✅ 첫 번째 뉴스 저장: {news1.id}')

# 중복 체크
existing = db.query(NewsDaily).filter(
    NewsDaily.date == date.today(),
    NewsDaily.topic_key == topic_key
).first()

if existing:
    print(f'✅ 중복 감지 성공: 기존 뉴스 ID {existing.id}')
else:
    print('❌ 중복 감지 실패')

# 테스트 데이터 삭제
db.delete(news1)
db.commit()
print('✅ 테스트 데이터 정리 완료')

db.close()
"
```

---

## 🔄 롤백 방법

마이그레이션 실패 시 백업으로 복구:

```bash
# 백업 파일 확인
ls -l morning_bot.db.backup_*

# 가장 최근 백업으로 복구
cp morning_bot.db.backup_20251229_131733 morning_bot.db
```

---

## ⚠️ 주의사항

1. **DB 백업은 자동으로 생성됩니다**
   - 파일명: `morning_bot.db.backup_YYYYMMDD_HHMMSS`
   - 위치: 프로젝트 루트

2. **마이그레이션 중 서버 중지**
   - FastAPI 서버, 텔레그램 봇 모두 중지
   - 스케줄러 작업 중지

3. **재실행 안전**
   - 이미 topic_key가 있으면 건너뜀
   - 중복 실행해도 문제없음

4. **데이터 손실 위험 없음**
   - 필드 추가만 함 (기존 데이터 유지)
   - nullable=True (NULL 허용)

---

## 📊 마이그레이션 후 상태

### NewsDaily 테이블 구조

```sql
CREATE TABLE news_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE,
    source VARCHAR(100),
    title VARCHAR(500),
    url VARCHAR(500),
    category VARCHAR(50),
    is_top BOOLEAN,
    keywords JSON,
    sentiment VARCHAR(50),
    is_breaking BOOLEAN,
    topic_key VARCHAR(100),  -- 👈 새로 추가된 필드
    created_at DATETIME,
    
    -- 인덱스
    INDEX idx_date (date),
    INDEX idx_news_daily_topic_key (topic_key)  -- 👈 새로 추가된 인덱스
);
```

### 샘플 데이터

```
id  | title                          | topic_key
----|--------------------------------|---------------------------
1   | [속보] 주가 급등               | 속보주가급등
2   | [속보] 주가 급등               | 속보주가급등  (중복 방지됨)
3   | 경제 성장률 발표               | 경제성장률발표
```

---

## 🐛 문제 해결

### Q1: "duplicate column name" 에러 발생

**원인:** topic_key 필드가 이미 존재

**해결:**
```bash
# 무시하고 진행 (정상)
# 또는 다음 명령으로 확인
sqlite3 morning_bot.db "PRAGMA table_info(news_daily);"
```

### Q2: 마이그레이션 후에도 topic_key가 NULL

**원인:** 
- 뉴스 수집 코드가 topic_key 생성 안 함
- news_collector.py의 save_news_items() 함수 확인 필요

**해결:**
```bash
# 수동으로 topic_key 생성
python scripts/migrate_topic_keys.py
```

### Q3: 기존 뉴스 중복 확인

**해결:**
```sql
-- 중복된 topic_key 찾기
sqlite3 morning_bot.db "
SELECT topic_key, COUNT(*) as cnt 
FROM news_daily 
WHERE topic_key IS NOT NULL 
GROUP BY topic_key 
HAVING cnt > 1
ORDER BY cnt DESC;
"
```

---

## ✅ 완료 체크리스트

마이그레이션 완료 후 확인:

- [ ] `python scripts/migrate_db.py` 성공
- [ ] 백업 파일 생성 확인
- [ ] 전체 뉴스에 topic_key 존재 확인
- [ ] 뉴스 수집 테스트 성공
- [ ] 중복 방지 테스트 성공
- [ ] FastAPI 서버 재시작 성공
- [ ] 텔레그램 봇 재시작 성공
- [ ] 스케줄러 정상 동작 확인
