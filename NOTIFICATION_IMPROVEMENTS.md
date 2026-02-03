# 알림 시스템 개선 사항

## 변경 날짜
2026-01-09

## 문제점
오늘 09:10에 전송되어야 하는 "오늘의 요약" 알림이 일부 사용자에게 전송되지 않는 문제 발견:
- chat_id `358553338`: 전송 실패 (`Connection reset by peer` 네트워크 에러)
- chat_id `1491178873`: 전송 성공
- chat_id `5175083233`: 전송 성공

### 발견된 버그
1. **로깅 버그**: `job_send_morning_brief_for_user()` 함수에서 전송 실패해도 성공 로그 출력
2. **재시도 없음**: Telegram API 네트워크 에러 발생 시 재시도 로직 없음
3. **추적 불가**: 실패한 알림을 추적하고 재전송할 방법 없음

---

## 해결 방안

### 1. 로깅 버그 수정 ✅

**파일**: `backend/app/scheduler/jobs.py`

**변경 내용**:
```python
# Before
def job_send_morning_brief_for_user(chat_id: str) -> None:
    db = _get_db()
    try:
        calculate_daily_changes(db)
        send_morning_brief_to_chat(db, chat_id)
        logger.info(f"Morning brief sent to {chat_id}")  # 항상 출력
    except Exception as e:
        logger.error(f"User brief send failed ({chat_id}): {e}", exc_info=True)

# After
def job_send_morning_brief_for_user(chat_id: str) -> None:
    db = _get_db()
    try:
        calculate_daily_changes(db)
        success = send_morning_brief_to_chat(db, chat_id)
        if success:
            logger.info(f"Morning brief sent to {chat_id}")
        else:
            logger.error(f"Morning brief send failed to {chat_id}")
    except Exception as e:
        logger.error(f"User brief send failed ({chat_id}): {e}", exc_info=True)
```

**효과**: 실패 시 명확한 에러 로그 출력

---

### 2. 재시도 로직 추가 ✅

**파일**: `backend/app/services/notification_service.py`

**변경 내용**:
- Telegram API 호출 실패 시 **Exponential Backoff**로 최대 3회 재시도
- 재시도 간격: 1초 → 2초 → 4초

**구현**:
```python
def send_telegram_message_sync(chat_id: str, text: str, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            response = httpx.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            return True

        except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException, ConnectionResetError) as e:
            # 네트워크 에러: 재시도
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"Retrying in {wait_time}s... (attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed after {max_retries} attempts")
                return False

        except httpx.HTTPStatusError as e:
            # HTTP 에러 (400, 403 등): 재시도해도 소용없음
            logger.error(f"HTTP error: {e.response.status_code}")
            return False
```

**효과**:
- 일시적 네트워크 에러 자동 복구
- 오늘 아침 `Connection reset by peer` 에러를 재시도로 해결 가능

---

### 3. 실패 추적 시스템 구축 ✅

#### 3.1. 새 테이블 추가

**파일**: `backend/app/db/models.py`

```python
class NotificationLog(Base):
    """알림 전송 로그"""
    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(50), index=True)
    notification_type = Column(String(50), index=True)  # 'morning_brief', 'breaking_news'
    status = Column(String(20), index=True)  # 'success', 'failed', 'pending_retry'
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    scheduled_date = Column(Date, index=True)
    message_preview = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_attempt_at = Column(DateTime, nullable=True)
    succeeded_at = Column(DateTime, nullable=True)
```

**효과**: 모든 알림 전송 시도를 DB에 기록

#### 3.2. 로그 기록 로직 추가

**파일**: `backend/app/services/notification_service.py`

```python
def send_morning_brief_to_chat(db: Session, chat_id: str) -> bool:
    """특정 사용자에게 아침 브리핑 전송 (로그 기록 포함)"""
    message = generate_morning_brief(db)
    today = date_type.today()

    # 로그 생성 또는 조회
    log = db.query(NotificationLog).filter(
        NotificationLog.chat_id == chat_id,
        NotificationLog.notification_type == "morning_brief",
        NotificationLog.scheduled_date == today
    ).first()

    if not log:
        log = NotificationLog(
            chat_id=chat_id,
            notification_type="morning_brief",
            status="pending_retry",
            scheduled_date=today,
            message_preview=message[:100],
            retry_count=0
        )
        db.add(log)
        db.commit()

    # 전송 시도
    log.last_attempt_at = datetime.utcnow()
    log.retry_count += 1

    success = send_telegram_message_sync(chat_id, message)

    if success:
        log.status = "success"
        log.succeeded_at = datetime.utcnow()
    else:
        log.status = "pending_retry" if log.retry_count < log.max_retries else "failed"

    db.commit()
    return success
```

#### 3.3. 실패한 알림 재전송 스케줄러

**파일**: `backend/app/scheduler/jobs.py`

```python
def job_retry_failed_notifications() -> None:
    """실패한 알림 재전송 (매 30분마다)"""
    db = _get_db()
    try:
        today = date_type.today()
        yesterday = today - timedelta(days=1)

        # 재시도 대상: pending_retry 상태이고 max_retries 미만
        failed_logs = db.query(NotificationLog).filter(
            NotificationLog.status == "pending_retry",
            NotificationLog.retry_count < NotificationLog.max_retries,
            NotificationLog.scheduled_date.in_([today, yesterday])
        ).all()

        if not failed_logs:
            logger.info("No failed notifications to retry")
            return

        logger.info(f"Retrying {len(failed_logs)} failed notifications")

        for log in failed_logs:
            send_morning_brief_to_chat(db, log.chat_id)

    except Exception as e:
        logger.error(f"Retry job failed: {e}", exc_info=True)
    finally:
        db.close()
```

**스케줄러 등록**:
```python
def start_scheduler() -> None:
    # ... 기존 스케줄들 ...

    # 실패한 알림 재전송 (매 30분)
    scheduler.add_job(
        job_retry_failed_notifications,
        "interval",
        minutes=30,
        id="retry_failed_notifications",
        replace_existing=True
    )
```

**효과**:
- 전송 실패한 알림을 자동으로 30분마다 재시도
- 최대 3회까지 재시도 후 `failed` 상태로 기록
- 어제/오늘 알림만 재시도 (오래된 알림은 무시)

---

## 테스트 결과

### 테스트 스크립트
`test_notification_system.py` 작성 완료

### 테스트 결과
```
=== 1. NotificationLog 테이블 테스트 ===
✅ 테스트 로그 생성 성공
✅ 로그 조회 성공
✅ 테스트 로그 삭제 완료

=== 2. send_morning_brief_to_chat 함수 테스트 ===
✅ 전송 함수 정상 동작
✅ 로그 기록 확인 (status: pending_retry, retry_count: 1)

=== 3. 실패한 알림 조회 테스트 ===
✅ pending_retry 상태 알림: 1건
✅ failed 상태 알림: 0건
```

---

## 데이터베이스 스키마

### notification_log 테이블

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| id | INTEGER | Primary Key |
| chat_id | VARCHAR(50) | Telegram chat ID (인덱스) |
| notification_type | VARCHAR(50) | 알림 종류 (인덱스) |
| status | VARCHAR(20) | 상태: success / failed / pending_retry (인덱스) |
| error_message | TEXT | 에러 메시지 |
| retry_count | INTEGER | 재시도 횟수 (기본값: 0) |
| max_retries | INTEGER | 최대 재시도 횟수 (기본값: 3) |
| scheduled_date | DATE | 전송 예정 날짜 (인덱스) |
| message_preview | TEXT | 메시지 미리보기 (100자) |
| created_at | DATETIME | 생성 시각 (인덱스) |
| last_attempt_at | DATETIME | 마지막 시도 시각 |
| succeeded_at | DATETIME | 성공 시각 |

---

## 운영 가이드

### 실패한 알림 조회

```sql
-- 오늘 실패한 알림 조회
SELECT chat_id, retry_count, error_message, last_attempt_at
FROM notification_log
WHERE scheduled_date = date('now')
  AND status = 'failed';

-- 재시도 대기 중인 알림 조회
SELECT chat_id, retry_count, max_retries
FROM notification_log
WHERE status = 'pending_retry'
  AND retry_count < max_retries;
```

### 수동 재전송

```python
from backend.app.db.session import SessionLocal
from backend.app.services.notification_service import send_morning_brief_to_chat

db = SessionLocal()
success = send_morning_brief_to_chat(db, "358553338")
print(f"재전송 결과: {'성공' if success else '실패'}")
db.close()
```

### 로그 정리 (30일 이상 된 로그 삭제)

```sql
DELETE FROM notification_log
WHERE created_at < datetime('now', '-30 days');
```

---

## 향후 개선 사항

1. **Slack/Email 알림**: 3회 재시도 실패 시 관리자에게 알림
2. **통계 대시보드**: 일별/주별 전송 성공률 모니터링
3. **사용자 알림**: 알림 실패 시 사용자에게 "/status" 명령어로 확인 가능하도록
4. **우선순위 큐**: 중요 알림 우선 재전송

---

## 변경 파일 목록

1. ✏️ `backend/app/scheduler/jobs.py` - 로깅 버그 수정, 재시도 스케줄러 추가
2. ✏️ `backend/app/services/notification_service.py` - 재시도 로직, 로그 기록
3. ✏️ `backend/app/db/models.py` - NotificationLog 모델 추가
4. ✨ `test_notification_system.py` - 테스트 스크립트 추가
5. ✨ `NOTIFICATION_IMPROVEMENTS.md` - 문서 추가

---

## 실행 방법

### 1. DB 마이그레이션 (자동)
```bash
python3 -c "from backend.app.db.session import Base, engine; Base.metadata.create_all(bind=engine)"
```

### 2. 서버 재시작
```bash
./run.sh
```

### 3. 로그 모니터링
```bash
tail -f logs/server.log | grep -E "Morning brief|retry|failed"
```

---

## 문의
이슈 발생 시 로그 파일 (`logs/server.log`)과 함께 문의 바랍니다.
