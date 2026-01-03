from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
import logging
import json
from datetime import datetime, time as time_type
from backend.app.db.session import SessionLocal
from backend.app.db.models import Subscriber, LottoDraw, LottoStatsCache
from backend.app.collectors.news_collector_v3 import build_daily_top5_v3, collect_breaking_news
from backend.app.collectors.market_collector import collect_market_daily, calculate_daily_changes
from backend.app.services.notification_service import send_morning_brief_to_all, send_breaking_batch
from backend.app.collectors.lotto.api_client import LottoAPIClient
from backend.app.services.lotto.stats_calculator import LottoStatsCalculator

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
        logger.error(f"9시 1분 작업 실패: {e}", exc_info=True)
        db.rollback()
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
        logger.error(f"9시 5분 작업 실패: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

def job_lotto_weekly_update() -> None:
    """매주 토요일 21:00: 로또 당첨번호 업데이트"""
    db = _get_db()
    try:
        logger.info("=== 로또 주간 업데이트 시작 ===")

        # 1. DB 최신 회차 확인
        latest_db_row = db.query(LottoDraw).order_by(LottoDraw.draw_no.desc()).first()
        latest_db = latest_db_row.draw_no if latest_db_row else 0
        logger.info(f"DB 최신 회차: {latest_db}회")

        # 2. API로 최신 회차 확인 시도 (폴백 포함)
        api_client = LottoAPIClient(delay=0.5)
        try:
            latest_api = api_client.get_latest_draw_no()
            if latest_api:
                logger.info(f"API 최신 회차: {latest_api}회")
            else:
                logger.warning("API 최신 회차 확인 실패(차단 가능). DB 최신 회차 사용")
                latest_api = latest_db
        except Exception as e:
            # API 실패 시 DB 최신 회차로 유지 (추정 금지)
            logger.warning(f"API 회차 조회 실패, DB 최신 회차 사용: {e}")
            latest_api = latest_db

        # 3. 신규 회차 수집
        new_count = 0
        if latest_api > latest_db:
            logger.info(f"신규 회차 수집 중... ({latest_db + 1}~{latest_api})")

            for draw_no in range(latest_db + 1, latest_api + 1):
                draw_info = api_client.get_lotto_draw(draw_no, retries=3)

                if draw_info is None:
                    logger.warning(f"회차 {draw_no} 데이터 없음 (다음 주 재시도)")
                    continue

                # DB 저장
                existing = db.query(LottoDraw).filter(LottoDraw.draw_no == draw_no).first()
                if not existing:
                    new_draw = LottoDraw(
                        draw_no=draw_no,
                        draw_date=draw_info['date'],
                        n1=draw_info['n1'],
                        n2=draw_info['n2'],
                        n3=draw_info['n3'],
                        n4=draw_info['n4'],
                        n5=draw_info['n5'],
                        n6=draw_info['n6'],
                        bonus=draw_info['bonus']
                    )
                    db.add(new_draw)
                    new_count += 1
                    logger.info(f"✅ 회차 {draw_no} 저장 완료")

            db.commit()
        else:
            logger.info("신규 회차 없음")

        # 3. 통계 캐시 갱신
        logger.info("통계 캐시 갱신 중...")
        draws = db.query(LottoDraw).order_by(LottoDraw.draw_no).all()
        draws_dict = [
            {
                'draw_no': d.draw_no,
                'n1': d.n1, 'n2': d.n2, 'n3': d.n3,
                'n4': d.n4, 'n5': d.n5, 'n6': d.n6,
                'bonus': d.bonus
            }
            for d in draws
        ]

        calculator = LottoStatsCalculator()
        most_common, least_common = calculator.calculate_most_least(draws_dict)
        ai_scores = calculator.calculate_ai_scores(draws_dict)

        # 캐시 업데이트
        cache = db.query(LottoStatsCache).first()
        if cache:
            cache.updated_at = datetime.now()
            cache.total_draws = len(draws_dict)
            cache.most_common = json.dumps(most_common)
            cache.least_common = json.dumps(least_common)
            cache.ai_scores = json.dumps(ai_scores)
        else:
            cache = LottoStatsCache(
                updated_at=datetime.now(),
                total_draws=len(draws_dict),
                most_common=json.dumps(most_common),
                least_common=json.dumps(least_common),
                ai_scores=json.dumps(ai_scores)
            )
            db.add(cache)

        db.commit()
        logger.info("✅ 통계 캐시 갱신 완료")

        logger.info(f"=== 로또 업데이트 완료: 신규 {new_count}개, 전체 {len(draws_dict)}회 ===")

    except Exception as e:
        logger.error(f"로또 업데이트 실패: {e}", exc_info=True)
        db.rollback()
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
        hour="9,13,18",
        minute=1,
        id="morning_data_collection",
        replace_existing=True,
    )
    
    # 9시 5분: 전일대비 계산 + 모닝 브리핑 전송
    scheduler.add_job(
        job_calculate_changes_and_send,
        "cron",
        hour="9,13,18",
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

    # 로또 업데이트: 매주 토요일 21:00
    scheduler.add_job(
        job_lotto_weekly_update,
        "cron",
        day_of_week="sat",
        hour=21,
        minute=0,
        id="lotto_weekly_update",
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
    logger.info("Scheduler started - 9:01 수집, 9:05 계산+전송, Breaking 12/18/22, Lotto 토요일 21:00")

def stop_scheduler() -> None:
    global scheduler
    
    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")
