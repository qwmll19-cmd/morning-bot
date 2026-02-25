from typing import Optional
from pathlib import Path
import json
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
import logging
import json
from datetime import datetime, time as time_type, timedelta, timezone
from backend.app.db.session import SessionLocal
from backend.app.config import settings
from backend.app.db.models import Subscriber, LottoDraw, LottoStatsCache, NotificationLog
from backend.app.collectors.news_collector_v3 import build_daily_top5_v3, collect_breaking_news
from backend.app.collectors.market_collector import collect_market_daily, calculate_daily_changes
from backend.app.collectors.koreagoldx_collector import collect_korea_metal_daily
from backend.app.services.notification_service import send_morning_brief_to_all, send_breaking_batch, send_morning_brief_to_chat
from backend.app.collectors.lotto.api_client import LottoAPIClient
from backend.app.services.lotto.stats_calculator import LottoStatsCalculator
from backend.app.services.lotto.performance_evaluator import evaluate_latest_draw
from backend.app.services.lotto.grid_search_retrainer import check_and_retrain_if_needed

logger = logging.getLogger(__name__)
scheduler: Optional[BackgroundScheduler] = None

def job_collect_breaking_news() -> None:
    """속보 수집만 (전송 안 함)"""
    db = SessionLocal()
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
    db = SessionLocal()
    try:
        from backend.app.db.models import NewsDaily
        from datetime import date, datetime, timedelta, timezone

        now_kst = datetime.now(timezone(timedelta(hours=9)))
        if now_kst.minute != 0 or now_kst.hour not in (12, 18, 22):
            logger.info(
                "Breaking batch skipped (outside schedule): %s",
                now_kst.strftime("%H:%M"),
            )
            return

        # 오늘 알림 안 보낸 속보 조회 (최근 6시간만, KST 기준)
        cutoff = now_kst.replace(tzinfo=None) - timedelta(hours=6)
        today_kst = now_kst.date()
        unsent = db.query(NewsDaily).filter(
            NewsDaily.date == today_kst,
            NewsDaily.is_breaking.is_(True),
            NewsDaily.alert_sent.is_(False),
            NewsDaily.created_at >= cutoff,
        ).order_by(NewsDaily.hot_score.desc()).all()
        
        if not unsent:
            logger.info("No breaking news to send (unsent=0)")
            return
        
        try:
            newest = max(n.created_at for n in unsent if n.created_at)
            oldest = min(n.created_at for n in unsent if n.created_at)
            logger.info("Sending breaking batch: count=%s range=%s..%s", len(unsent), oldest, newest)
        except Exception:
            logger.info("Sending breaking batch: count=%s", len(unsent))
        
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
    db = SessionLocal()
    try:
        logger.info("=== 9시 1분 데이터 수집 시작 ===")

        # 1. 시장 데이터 수집 (하루 1회만)
        from datetime import date as date_type
        from backend.app.db.models import MarketDaily

        today = date_type.today()
        latest_market = (
            db.query(MarketDaily)
            .filter(MarketDaily.date == today)
            .order_by(MarketDaily.id.desc())
            .first()
        )

        if latest_market and latest_market.usd_krw:
            logger.info("✅ 시장 데이터 수집 스킵 (오늘 데이터 존재)")
        else:
            collect_market_daily(db)
            logger.info("✅ 시장 데이터 수집")

        # 1-1. 국내 금/은/백금 시세 수집
        collected = collect_korea_metal_daily(db)
        if collected:
            logger.info("✅ 국내 금속 시세 수집: %s건", len(collected))
        else:
            logger.info("ℹ️ 국내 금속 시세 수집 결과 없음")

        # 2. 뉴스 수집
        build_daily_top5_v3(db)
        logger.info("✅ 뉴스 수집")

        logger.info("=== 9시 1분 데이터 수집 완료 ===")

    except Exception as e:
        logger.error(f"9시 1분 작업 실패: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def job_retry_market_collection() -> None:
    """시장 데이터 재수집 (오늘 데이터가 없거나 주요 항목 누락 시)"""
    db = SessionLocal()
    try:
        from backend.app.db.models import MarketDaily
        from backend.app.db.session import SessionLocal

        # KST 기준 오늘 날짜 (타임존 안전)
        kst = timezone(timedelta(hours=9))
        today = datetime.now(kst).date()
        latest = (
            db.query(MarketDaily)
            .filter(MarketDaily.date == today)
            .order_by(MarketDaily.id.desc())
            .first()
        )

        def _is_incomplete(row: MarketDaily) -> bool:
            return any(
                value is None
                for value in (
                    row.usd_krw,
                    row.kospi_index,
                    row.nasdaq_index,
                    row.gold_usd,
                    row.silver_usd,
                )
            )

        # 재시도 최소 간격 (API 호출 과다 방지)
        state_path = Path("logs") / "market_retry_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        last_attempt = None
        if state_path.exists():
            try:
                data = json.loads(state_path.read_text())
                last_attempt = datetime.fromisoformat(data.get("last_attempt"))
            except Exception:
                last_attempt = None

        min_interval = timedelta(minutes=90)
        if last_attempt and datetime.now() - last_attempt < min_interval:
            logger.info("시장 데이터 재수집 건너뜀 (쿨다운)")
            return

        if not latest or _is_incomplete(latest):
            logger.warning("시장 데이터 재수집 실행 (오늘 데이터 부족)")
            state_path.write_text(json.dumps({"last_attempt": datetime.now().isoformat()}))
            collect_market_daily(db)
        else:
            logger.info("시장 데이터 재수집 건너뜀 (오늘 데이터 정상)")
    except Exception as e:
        logger.error(f"시장 데이터 재수집 실패: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

def job_calculate_changes_and_send() -> None:
    """9시 5분: 전일대비 계산 + 모닝 브리핑 전송"""
    db = SessionLocal()
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


def job_collect_lineage_prices() -> None:
    """라인리지 아데나 시세 수집 (스냅샷 업데이트)"""
    if not settings.LINEAGE_ENABLED:
        return
    db = SessionLocal()
    try:
        from backend.app.services.lineage.lineage_service import collect_and_store
        collect_and_store(db, page_limit=1)
        db.commit()
        logger.info("Lineage price snapshot updated")
    except Exception as e:
        logger.error(f"Lineage price collection failed: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

def job_send_morning_brief_for_user(chat_id: str) -> None:
    """사용자 1명에게만 아침 브리핑 전송"""
    db = SessionLocal()
    try:
        calculate_daily_changes(db)
        success = send_morning_brief_to_chat(db, chat_id)
        if success:
            logger.info(f"Morning brief sent to {chat_id}")
        else:
            logger.error(f"Morning brief send failed to {chat_id} (send_morning_brief_to_chat returned False)")
    except Exception as e:
        logger.error(f"User brief send failed ({chat_id}): {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

def job_lotto_weekly_update() -> None:
    """매주 토요일 21:00: 로또 당첨번호 업데이트"""
    db = SessionLocal()
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

        # 4. ML 모델 재학습 (신규 회차가 있을 때만)
        if new_count > 0:
            logger.info("ML 모델 재학습 시작...")
            try:
                from backend.app.services.lotto.ml_trainer import LottoMLTrainer
                trainer = LottoMLTrainer()
                result = trainer.train(draws_dict, test_size=0.2)
                logger.info(f"✅ ML 모델 재학습 완료 - Train: {result['train_accuracy']:.4f}, Test: {result['test_accuracy']:.4f}")
                logger.info(f"   가중치: L1={result['ai_weights']['logic1']:.4f}, L2={result['ai_weights']['logic2']:.4f}, L3={result['ai_weights']['logic3']:.4f}, L4={result['ai_weights']['logic4']:.4f}")
            except Exception as e:
                logger.error(f"⚠️ ML 모델 재학습 실패: {e}")
        else:
            logger.info("신규 회차 없음, ML 재학습 스킵")

        logger.info(f"=== 로또 업데이트 완료: 신규 {new_count}개, 전체 {len(draws_dict)}회 ===")

    except Exception as e:
        logger.error(f"로또 업데이트 실패: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def job_lotto_performance_evaluation() -> None:
    """매주 일요일 10:00: 로또 ML 성능 평가 및 자동 재학습"""
    try:
        logger.info("=== 로또 ML 성능 평가 시작 ===")

        # 1. 최신 회차 성능 평가 (내부적으로만 실행, 사용자에게 알림 없음)
        evaluate_latest_draw()
        logger.info("✅ 성능 평가 완료")

        # 2. 성능이 낮으면 자동 재학습 (Grid Search)
        check_and_retrain_if_needed()
        logger.info("✅ 재학습 확인 완료")

        logger.info("=== 로또 ML 성능 평가 완료 ===")

    except Exception as e:
        logger.error(f"로또 ML 성능 평가 실패: {e}", exc_info=True)

def job_retry_failed_notifications() -> None:
    """실패한 알림 재전송 (매 30분마다)"""
    db = SessionLocal()
    try:
        # KST 기준 날짜 사용 (타임존 안전)
        kst = timezone(timedelta(hours=9))
        today = datetime.now(kst).date()
        yesterday = today - timedelta(days=1)

        # 재시도 대상: 오늘/어제 알림 중 pending_retry 상태이고 max_retries 미만
        failed_logs = db.query(NotificationLog).filter(
            NotificationLog.status == "pending_retry",
            NotificationLog.retry_count < NotificationLog.max_retries,
            NotificationLog.scheduled_date.in_([today, yesterday])
        ).all()

        if not failed_logs:
            logger.info("No failed notifications to retry")
            return

        logger.info(f"Retrying {len(failed_logs)} failed notifications")

        success_count = 0
        still_failed_count = 0

        for log in failed_logs:
            # 재전송 시도
            from backend.app.services.notification_service import send_morning_brief_to_chat
            success = send_morning_brief_to_chat(db, log.chat_id)

            if success:
                success_count += 1
            else:
                still_failed_count += 1

        logger.info(
            f"Notification retry complete: {success_count} succeeded, {still_failed_count} still failed"
        )

    except Exception as e:
        logger.error(f"Failed notification retry job failed: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def schedule_user_alerts() -> None:
    """사용자별 맞춤 시간 알림 등록"""
    from backend.app.db.models import Subscriber
    db = SessionLocal()

    try:
        subscribers = db.query(Subscriber).filter(
            Subscriber.subscribed_alert.is_(True)
        ).all()
        
        collect_times = set()
        for subscriber in subscribers:
            alert_time = subscriber.custom_time or "09:10"
            hour, minute = map(int, alert_time.split(":"))

            alert_job_id = f"user_alert_{subscriber.chat_id}"

            if scheduler.get_job(alert_job_id):
                scheduler.remove_job(alert_job_id)

            # 발송 스케줄
            scheduler.add_job(
                job_send_morning_brief_for_user,
                "cron",
                hour=hour,
                minute=minute,
                id=alert_job_id,
                replace_existing=True,
                args=[subscriber.chat_id],
            )

            # 수집 스케줄 (발송 5분 전)
            collect_minute = (minute - 5) % 60
            collect_hour = hour if minute >= 5 else (hour - 1) % 24
            collect_times.add((collect_hour, collect_minute))

        # 시간별 수집 스케줄은 1회만 등록
        active_collect_ids = {f"collect_time_{h:02d}_{m:02d}" for h, m in collect_times}
        for job in scheduler.get_jobs():
            if job.id.startswith("collect_time_") and job.id not in active_collect_ids:
                scheduler.remove_job(job.id)

        for collect_hour, collect_minute in collect_times:
            collect_job_id = f"collect_time_{collect_hour:02d}_{collect_minute:02d}"
            if not scheduler.get_job(collect_job_id):
                scheduler.add_job(
                    job_morning_all,
                    "cron",
                    hour=collect_hour,
                    minute=collect_minute,
                    id=collect_job_id,
                    replace_existing=True,
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

    # APScheduler 타임존 설정: 한국 시간 (KST)
    from apscheduler.schedulers.background import BackgroundScheduler
    from datetime import timezone, timedelta

    kst = timezone(timedelta(hours=9))
    scheduler = BackgroundScheduler(timezone=kst)
    
    # 전일대비 계산 + 브리핑 전송은 사용자별 스케줄로만 처리
    
    # 매시간: 속보 수집만 (매시 55분, 배치 전 5분 확보)
    scheduler.add_job(
        job_collect_breaking_news,
        "cron",
        minute=55,
        id="collect_breaking_news",
        replace_existing=True,
    )
    # 시작 직후 1회 즉시 수집 (첫 배치 전 공백 방지)
    from datetime import timezone
    scheduler.add_job(
        job_collect_breaking_news,
        "date",
        run_date=datetime.now(timezone.utc),
        id="collect_breaking_news_bootstrap",
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

    # 로또 ML 성능 평가 및 재학습: 매주 토요일 22:00 (내부 평가만, 사용자 알림 없음)
    # 로또 당첨번호 수집(21시) 1시간 후 실행
    scheduler.add_job(
        job_lotto_performance_evaluation,
        "cron",
        day_of_week="sat",
        hour=22,
        minute=0,
        id="lotto_performance_evaluation",
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

    # 실패한 알림 재전송 (매 30분)
    scheduler.add_job(
        job_retry_failed_notifications,
        "interval",
        minutes=30,
        id="retry_failed_notifications",
        replace_existing=True
    )

    # 리니지 아데나 시세 수집 (기본 30분, 설정으로 변경 가능)
    if settings.LINEAGE_ENABLED:
        scheduler.add_job(
            job_collect_lineage_prices,
            "interval",
            minutes=settings.LINEAGE_SCHEDULE_MINUTES,
            id="lineage_price_collect",
            replace_existing=True
        )

    # 시장 데이터 재수집은 비활성화 (하루 1회 수집 유지)

    scheduler.start()
    logger.info("Scheduler started - user-specific alerts + pre-collection, Breaking 12/18/22, Lotto 토요일 21:00, Lotto ML 토요일 22:00, Retry every 30min")

def stop_scheduler() -> None:
    global scheduler
    
    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")
