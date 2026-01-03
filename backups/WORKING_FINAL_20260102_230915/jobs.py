from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
import logging
from datetime import datetime, time as time_type
from backend.app.db.session import SessionLocal
from backend.app.db.models import Subscriber
from backend.app.collectors.news_collector_v3 import build_daily_top5_v3, collect_breaking_news
from backend.app.collectors.market_collector import collect_market_daily, calculate_daily_changes
from backend.app.services.notification_service import send_morning_brief_to_all, send_breaking_batch

logger = logging.getLogger(__name__)
scheduler: Optional[BackgroundScheduler] = None

def _get_db() -> Session:
    return SessionLocal()

def job_collect_breaking_news() -> None:
    """속보 수집만 (전송 안 함)"""
    db = _get_db()
    try:
        new_items = collect_breaking_news(db)
        
        if new_items:
            logger.info(f"Collected {len(new_items)} new breaking news items")
        
    except Exception as e:
        logger.error(f"Breaking news collection failed: {e}")
        db.rollback()
    finally:
        db.close()

def job_send_breaking_batch() -> None:
    """속보 배치 전송 (12시, 18시, 22시)"""
    db = _get_db()
    try:
        from backend.app.db.models import NewsDaily
        from datetime import date
        
        # 오늘 알림 안 보낸 속보 조회
        unsent = db.query(NewsDaily).filter(
            NewsDaily.date == date.today(),
            NewsDaily.is_breaking.is_(True),
            NewsDaily.alert_sent.is_(False)
        ).order_by(NewsDaily.hot_score.desc()).all()
        
        if not unsent:
            logger.info("No breaking news to send")
            return
        
        logger.info(f"Sending batch of {len(unsent)} breaking news")
        
        # 배치 전송
        sent_count = send_breaking_batch(db, unsent)
        
        logger.info(f"Breaking batch sent to {sent_count} subscribers")
        
    except Exception as e:
        logger.error(f"Breaking batch send failed: {e}")
        db.rollback()
    finally:
        db.close()

def job_morning_all() -> None:
    """9시 1분: 모든 데이터 수집"""
    db = _get_db()
    try:
        logger.info("=== 9시 1분 데이터 수집 시작 ===")
        
        # 1. 시장 데이터 수집
        collect_market_daily(db)
        logger.info("✅ 시장 데이터 수집")
        
        # 2. 뉴스 수집
        build_daily_top5_v3(db)
        logger.info("✅ 뉴스 수집")
        
        logger.info("=== 9시 1분 데이터 수집 완료 ===")
        
    except Exception as e:
        logger.error(f"9시 1분 작업 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def job_calculate_changes_and_send() -> None:
    """9시 5분: 전일대비 계산 + 모닝 브리핑 전송"""
    db = _get_db()
    try:
        logger.info("=== 9시 5분 전일대비 계산 + 전송 시작 ===")
        
        # 1. 전일대비 계산
        calculate_daily_changes(db)
        logger.info("✅ 전일대비 계산 완료")
        
        # 2. 모닝 브리핑 전송
        send_morning_brief_to_all(db)
        logger.info("✅ 모닝 브리핑 전송")
        
        logger.info("=== 9시 5분 작업 완료 ===")
        
    except Exception as e:
        logger.error(f"9시 5분 작업 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def schedule_user_alerts() -> None:
    """사용자별 맞춤 시간 알림 등록"""
    from backend.app.db.models import Subscriber
    db = _get_db()
    
    try:
        subscribers = db.query(Subscriber).filter(
            Subscriber.subscribed_alert.is_(True)
        ).all()
        
        for subscriber in subscribers:
            if subscriber.custom_time:
                hour, minute = map(int, subscriber.custom_time.split(":"))
                
                job_id = f"user_alert_{subscriber.chat_id}"
                
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
                
                scheduler.add_job(
                    job_calculate_changes_and_send,
                    "cron",
                    hour=hour,
                    minute=minute,
                    id=job_id,
                    replace_existing=True
                )
        
        logger.info(f"Scheduled alerts for {len(subscribers)} subscribers")
    except Exception as e:
        logger.error(f"Failed to schedule user alerts: {e}")
    finally:
        db.close()

def start_scheduler() -> None:
    global scheduler
    
    if scheduler is not None:
        logger.warning("Scheduler already running")
        return
    
    scheduler = BackgroundScheduler()
    
    # 9시 1분: 데이터 수집만
    scheduler.add_job(
        job_morning_all,
        "cron",
        hour=9,
        minute=1,
        id="morning_data_collection",
        replace_existing=True,
    )
    
    # 9시 5분: 전일대비 계산 + 모닝 브리핑 전송
    scheduler.add_job(
        job_calculate_changes_and_send,
        "cron",
        hour=9,
        minute=5,
        id="morning_calculate_and_send",
        replace_existing=True,
    )
    
    # 매시간: 속보 수집만
    scheduler.add_job(
        job_collect_breaking_news,
        "interval",
        hours=1,
        id="collect_breaking_news",
        replace_existing=True,
    )
    
    # 속보 모음 전송: 12시, 18시, 22시
    scheduler.add_job(
        job_send_breaking_batch,
        "cron",
        hour="12,18,22",
        minute=0,
        id="send_breaking_batch",
        replace_existing=True,
    )
    
    # 사용자별 맞춤 시간 알림 스케줄 등록
    schedule_user_alerts()
    
    # 매시간 스케줄 재등록
    scheduler.add_job(
        schedule_user_alerts,
        "interval",
        hours=1,
        id="refresh_user_schedules",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started - 9:01 수집, 9:05 계산+전송, Breaking 12/18/22")

def stop_scheduler() -> None:
    global scheduler
    
    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")
