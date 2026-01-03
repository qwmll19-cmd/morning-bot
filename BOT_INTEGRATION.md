# bot.py 수정 가이드

이 파일은 기존 `backend/app/bot.py`에 추가할 코드입니다.

## 1. 파일 상단에 import 추가

```python
# 기존 imports 아래에 추가
import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# 로또 핸들러
from app.handlers.lotto.lotto_handler import lotto_command
from app.schedulers.lotto.weekly_update import weekly_lotto_update
from config import DATABASE_URL, ADMIN_CHAT_ID  # ADMIN_CHAT_ID 추가 필요
```

## 2. config.py에 필요한 설정 추가

```python
# config.py에 다음 변수들이 있는지 확인하고 없으면 추가

# Database
DATABASE_URL = "postgresql://your_user:your_password@localhost/morning_bot"

# Admin
ADMIN_CHAT_ID = 123456789  # 실제 관리자 텔레그램 chat ID로 변경
```

## 3. DB 풀 초기화 함수 추가

```python
async def post_init(application):
    """봇 시작 시 DB 풀 생성"""
    try:
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60,
            max_inactive_connection_lifetime=300
        )
        application.bot_data['db_pool'] = pool
        print("✅ DB 풀 생성 완료")
    except Exception as e:
        print(f"❌ DB 풀 생성 실패: {e}")
        raise
```

## 4. 스케줄러 설정 함수 추가

```python
def setup_schedulers(application):
    """스케줄러 설정"""
    scheduler = AsyncIOScheduler(timezone=timezone('Asia/Seoul'))
    
    # 매주 토요일 21:00
    scheduler.add_job(
        weekly_lotto_update,
        'cron',
        day_of_week='sat',
        hour=21,
        minute=0,
        max_instances=1,
        coalesce=True,
        args=[application.bot_data['db_pool'], application.bot, ADMIN_CHAT_ID]
    )
    
    scheduler.start()
    print("✅ 로또 스케줄러 시작 (매주 토 21:00)")
```

## 5. 봇 종료 시 정리 함수 추가

```python
async def post_shutdown(application):
    """봇 종료 시 DB 연결 해제"""
    pool = application.bot_data.get('db_pool')
    if pool:
        await pool.close()
        print("✅ DB 연결 종료")
```

## 6. Application 설정 수정

```python
# main() 함수 내부 또는 Application 생성 부분

# Application 생성
application = Application.builder().token(TELEGRAM_TOKEN).build()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 기존 뉴스 핸들러들
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
application.add_handler(CommandHandler("today", today_news))
application.add_handler(CommandHandler("breaking", breaking_news))
# ... 기존 핸들러들 ...

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 로또 핸들러 추가
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
application.add_handler(CommandHandler("lotto", lotto_command))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 초기화 및 종료 핸들러 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
application.post_init = post_init
application.post_shutdown = post_shutdown

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 스케줄러 시작 (초기화 후)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# post_init 내부에서 호출하거나 여기서 직접 호출
setup_schedulers(application)

# 봇 실행
application.run_polling()
```

## 전체 구조 예시

```python
# backend/app/bot.py

import asyncpg
from telegram.ext import Application, CommandHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

from app.handlers.news_handlers import today_news, breaking_news
from app.handlers.lotto.lotto_handler import lotto_command
from app.schedulers.lotto.weekly_update import weekly_lotto_update
from config import TELEGRAM_TOKEN, DATABASE_URL, ADMIN_CHAT_ID

async def post_init(application):
    """봇 시작 시 DB 풀 생성"""
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60,
        max_inactive_connection_lifetime=300
    )
    application.bot_data['db_pool'] = pool
    print("✅ DB 풀 생성 완료")

async def post_shutdown(application):
    """봇 종료 시 DB 연결 해제"""
    pool = application.bot_data.get('db_pool')
    if pool:
        await pool.close()
        print("✅ DB 연결 종료")

def setup_schedulers(application):
    """스케줄러 설정"""
    scheduler = AsyncIOScheduler(timezone=timezone('Asia/Seoul'))
    
    scheduler.add_job(
        weekly_lotto_update,
        'cron',
        day_of_week='sat',
        hour=21,
        minute=0,
        max_instances=1,
        coalesce=True,
        args=[application.bot_data['db_pool'], application.bot, ADMIN_CHAT_ID]
    )
    
    scheduler.start()
    print("✅ 로또 스케줄러 시작 (매주 토 21:00)")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # 핸들러 등록
    application.add_handler(CommandHandler("today", today_news))
    application.add_handler(CommandHandler("breaking", breaking_news))
    application.add_handler(CommandHandler("lotto", lotto_command))  # ✅ 추가
    
    # 초기화/종료 핸들러
    application.post_init = post_init
    application.post_shutdown = post_shutdown
    
    # 스케줄러 시작
    setup_schedulers(application)
    
    # 봇 실행
    print("🤖 봇 시작...")
    application.run_polling()

if __name__ == "__main__":
    main()
```

## 주의사항

1. **기존 코드 백업 필수**
   ```bash
   cp backend/app/bot.py backend/app/bot.py.backup
   ```

2. **config.py 확인**
   - `DATABASE_URL` 존재 여부
   - `ADMIN_CHAT_ID` 추가 필요

3. **기존 DB 연결 방식 확인**
   - 만약 기존에 psycopg2 쓰고 있다면 별도 안내
   - asyncpg 사용 중이면 OK

4. **점진적 적용**
   - 먼저 핸들러만 추가해서 테스트
   - 정상 동작 확인 후 스케줄러 추가
