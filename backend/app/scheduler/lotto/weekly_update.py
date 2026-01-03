"""매주 토요일 21:00 자동 업데이트"""
import asyncio
import json
from datetime import datetime

from app.collectors.lotto.api_client import LottoAPIClient
from app.collectors.lotto.db_manager import LottoDBManager
from app.services.lotto.stats_calculator import LottoStatsCalculator

async def weekly_lotto_update(db_pool, bot, admin_chat_id):
    """
    주간 로또 업데이트
    
    1. 최신 회차 수집
    2. 통계 캐시 갱신
    3. 관리자에게 알림
    
    Args:
        db_pool: asyncpg pool
        bot: telegram bot instance
        admin_chat_id: 관리자 chat ID
    """
    try:
        print(f"\n{'='*60}")
        print(f"[{datetime.now()}] 주간 로또 업데이트 시작")
        print(f"{'='*60}")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # [1/3] 최신 회차 수집
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        api_client = LottoAPIClient(delay=0.5)
        db_manager = LottoDBManager(db_pool)
        
        latest_api = api_client.get_latest_draw_no()
        latest_db = await db_manager.get_max_draw_no()
        
        print(f"   API 최신 회차: {latest_api}")
        print(f"   DB 최신 회차: {latest_db}")
        
        # 신규 회차 수집
        new_count = 0
        if latest_api > latest_db:
            print(f"   신규 회차 수집 중... ({latest_db + 1}~{latest_api})")
            for draw_no in range(latest_db + 1, latest_api + 1):
                draw_info = api_client.get_lotto_draw(draw_no, retries=3)
                if draw_info is None:
                    # 데이터 아직 없음 (다음 주에 다시 시도)
                    print(f"   ⚠️  회차 {draw_no} 데이터 아직 없음 (다음 주 재시도)")
                    await bot.send_message(
                        chat_id=admin_chat_id, 
                        text=f"⚠️ 회차 {draw_no} 수집 실패 (다음 주 재시도)"
                    )
                    continue
                
                saved = await db_manager.save_draw(draw_info)
                if saved:
                    new_count += 1
                    print(f"   ✅ 회차 {draw_no} 저장 완료")
        else:
            print("   ℹ️  신규 회차 없음")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # [2/3] 통계 캐시 갱신
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        print("   통계 캐시 갱신 중...")
        draws = await db_manager.get_recent_draws(n=10000)
        draws.reverse()
        
        calculator = LottoStatsCalculator()
        most, least = calculator.calculate_most_least(draws)
        ai_scores = calculator.calculate_ai_scores(draws)
        
        query = """
        INSERT INTO lotto_stats_cache (id, updated_at, total_draws, most_common, least_common, ai_scores)
        VALUES (1, $1, $2, $3, $4, $5)
        ON CONFLICT (id) DO UPDATE SET
            updated_at = $1,
            total_draws = $2,
            most_common = $3,
            least_common = $4,
            ai_scores = $5
        """
        await db_pool.execute(
            query,
            datetime.now(),
            len(draws),
            json.dumps(most),
            json.dumps(least),
            json.dumps(ai_scores)
        )
        print("   ✅ 통계 캐시 갱신 완료")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # [3/3] 관리자에게 알림
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        current_db_max = await db_manager.get_max_draw_no()
        msg = (
            f"✅ 로또 데이터 업데이트 완료\n\n"
            f"최신 회차: {current_db_max}회\n"
            f"신규 수집: {new_count}개\n"
            f"통계 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await bot.send_message(chat_id=admin_chat_id, text=msg)
        
        print(f"[{datetime.now()}] 주간 로또 업데이트 완료")
        print(f"{'='*60}\n")
        
    except Exception as e:
        error_msg = f"❌ 로또 업데이트 실패: {e}"
        print(error_msg)
        try:
            await bot.send_message(chat_id=admin_chat_id, text=error_msg)
        except:
            pass
