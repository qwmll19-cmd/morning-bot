"""로또 핸들러 (20줄 + 3가지 로직 + AI핵심)"""
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from backend.app.db.session import SessionLocal
from backend.app.db.models import LottoStatsCache, LottoRecommendLog, LottoDraw
from backend.app.services.lotto.generator import generate_20_lines
from backend.app.services.lotto.stats_calculator import LottoStatsCalculator

async def lotto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """로또 번호 20줄 생성"""
    db = SessionLocal()
    
    try:
        cache = db.query(LottoStatsCache).first()
        
        if not cache:
            await update.message.reply_text("⚠️ 통계 데이터가 없습니다.")
            return
        
        # 캐시에서 데이터 로드
        most_common = json.loads(cache.most_common)
        least_common = json.loads(cache.least_common)
        ai_scores_data = json.loads(cache.ai_scores)
        
        # 전체 회차 데이터 조회 (3가지 로직 계산용)
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

        # 보너스 번호 출현 빈도 (많이 나온 순)
        bonus_counts = {}
        for d in draws_dict:
            b = d.get('bonus')
            if b:
                bonus_counts[b] = bonus_counts.get(b, 0) + 1
        bonus_top = [num for num, _ in sorted(bonus_counts.items(), key=lambda x: x[1], reverse=True)]
        
        # 3가지 로직 점수 계산
        scores_logic1 = LottoStatsCalculator.calculate_ai_scores_logic1(draws_dict)
        scores_logic2 = LottoStatsCalculator.calculate_ai_scores_logic2(draws_dict)
        scores_logic3 = LottoStatsCalculator.calculate_ai_scores_logic3(draws_dict)
        
        # AI 가중치 (추후 학습으로 업데이트)
        ai_weights = {
            'logic1': 0.33,
            'logic2': 0.33,
            'logic3': 0.34
        }
        
        stats = {
            'most_common': most_common,
            'least_common': least_common,
            'scores_logic1': scores_logic1,
            'scores_logic2': scores_logic2,
            'scores_logic3': scores_logic3,
            'patterns': ai_scores_data.get('patterns', {}),
            'best_patterns': ai_scores_data.get('best_patterns', {}),
            'bonus_top': bonus_top
        }
        
        user_id = update.effective_user.id
        result = generate_20_lines(user_id, stats, ai_weights)
        
        next_draw_no = cache.total_draws + 1
        
        # DB 저장 (20줄)
        all_20_lines = {
            'basic': [{'name': name, 'numbers': line, 'logic': 'basic'} for name, line in zip(
                ["① 믹스(최다+최소+랜덤)", "② 최다 출현 위주", "③ 최소 출현 위주", "④ 최다 줄 기반 믹스"],
                result['basic']
            )],
            'logic1': [{'name': name, 'numbers': line, 'logic': 'logic1'} for name, line in zip(
                ["⑤ AI 홀짝 밸런스", "⑥ AI 구간 밸런스", "⑦ AI 종합 점수"],
                result['logic1']
            )],
            'logic2': [{'name': name, 'numbers': line, 'logic': 'logic2'} for name, line in zip(
                ["⑧ AI 홀짝 최적", "⑨ AI 구간 최적", "⑩ AI 합계 최적"],
                result['logic2']
            )],
            'logic3': [{'name': name, 'numbers': line, 'logic': 'logic3'} for name, line in zip(
                ["⑪ AI 홀짝 밸런스", "⑫ AI 구간 밸런스", "⑬ AI 연속 최적"],
                result['logic3']
            )],
            'final': [{'name': name, 'numbers': line, 'logic': 'final'} for name, line in zip(
                ["⑭ AI 모든 패턴 종합", "⑮ AI 최종 최적화"],
                result['final']
            )],
            'ai_core': [{'name': f"⑯~⑳ AI 핵심번호 #{i+1}", 'numbers': line, 'logic': 'ai_core'} for i, line in enumerate(result['ai_core'])]
        }
        
        log = LottoRecommendLog(
            user_id=user_id,
            target_draw_no=next_draw_no,
            lines=json.dumps(all_20_lines),
            recommend_time=datetime.now(),
            match_results=None
        )
        
        db.add(log)
        db.commit()
        
        # 텔레그램 메시지
        lines = []
        lines.append(f"🎰 로또 번호 추천 (20줄)")
        lines.append(f"🎯 예상 회차: {next_draw_no}회")
        lines.append("")
        
        # 기본 4줄
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("📌 기본 전략 (4줄)")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        for item in all_20_lines['basic']:
            formatted = ", ".join([f"{n:02d}" for n in item['numbers']])
            lines.append(f"{item['name']}")
            lines.append(f"➡️ {formatted}")
            lines.append("")
        
        # 로직1 3줄
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("🧠 AI 로직1 (3줄)")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        for item in all_20_lines['logic1']:
            formatted = ", ".join([f"{n:02d}" for n in item['numbers']])
            lines.append(f"{item['name']}")
            lines.append(f"➡️ {formatted}")
            lines.append("")
        
        # 로직2 3줄
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("🔥 AI 로직2 (3줄)")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        for item in all_20_lines['logic2']:
            formatted = ", ".join([f"{n:02d}" for n in item['numbers']])
            lines.append(f"{item['name']}")
            lines.append(f"➡️ {formatted}")
            lines.append("")
        
        # 로직3 3줄
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 AI 로직3 (3줄)")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        for item in all_20_lines['logic3']:
            formatted = ", ".join([f"{n:02d}" for n in item['numbers']])
            lines.append(f"{item['name']}")
            lines.append(f"➡️ {formatted}")
            lines.append("")
        
        # 종합 2줄
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("🎯 AI 종합 (2줄)")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        for item in all_20_lines['final']:
            formatted = ", ".join([f"{n:02d}" for n in item['numbers']])
            lines.append(f"{item['name']}")
            lines.append(f"➡️ {formatted}")
            lines.append("")
        
        # AI 핵심 5줄
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("🤖 AI 핵심번호 (5줄)")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        for i, item in enumerate(all_20_lines['ai_core'], 16):
            formatted = ", ".join([f"{n:02d}" for n in item['numbers']])
            lines.append(f"⑯⑰⑱⑲⑳"[i-16] + f" AI 핵심 #{i-15}")
            lines.append(f"➡️ {formatted}")
            lines.append("")
        
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append("📊 AI 분석 기반")
        lines.append(f"- 1~{cache.total_draws}회 전체 패턴 분석")
        lines.append("- 3가지 로직 종합 (가중치 자동 조정)")
        lines.append("- AI 핵심번호: 500~1024회 학습")
        lines.append("- 매주 토요일 자동 업데이트")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 회차별 결과 확인")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append("※ 이전 회차는 번호만 입력")
        lines.append("   예) 1024")
        
        text = "\n".join(lines)
        
        # 최근 4주 버튼
        latest_draw = cache.total_draws
        keyboard = [
            [
                InlineKeyboardButton(f"{latest_draw-3}회", callback_data=f"lotto_result:{latest_draw-3}"),
                InlineKeyboardButton(f"{latest_draw-2}회", callback_data=f"lotto_result:{latest_draw-2}")
            ],
            [
                InlineKeyboardButton(f"{latest_draw-1}회", callback_data=f"lotto_result:{latest_draw-1}"),
                InlineKeyboardButton(f"{latest_draw}회", callback_data=f"lotto_result:{latest_draw}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)
        
    except Exception as e:
        print(f"❌ 로또 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        
        await update.message.reply_text("⚠️ 번호 생성 중 오류가 발생했습니다.")
    finally:
        db.close()


async def lotto_result_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """회차별 결과 확인 (버튼 클릭)"""
    query = update.callback_query
    await query.answer()
    
    draw_no = int(query.data.split(":")[1])
    await show_lotto_result(query, draw_no)


async def lotto_result_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """회차별 결과 확인 (숫자 입력)"""
    try:
        draw_no = int(update.message.text.strip())
        
        if draw_no < 1 or draw_no > 1300:
            await update.message.reply_text("⚠️ 올바른 회차를 입력하세요 (1~1300)")
            return
        
        await show_lotto_result(update.message, draw_no)
        
    except ValueError:
        pass


async def show_lotto_result(message_or_query, draw_no: int) -> None:
    """회차별 당첨 결과 표시"""
    db = SessionLocal()
    
    try:
        draw = db.query(LottoDraw).filter(LottoDraw.draw_no == draw_no).first()
        
        if not draw:
            text = f"⚠️ {draw_no}회 데이터가 없습니다."
            if hasattr(message_or_query, 'edit_message_text'):
                await message_or_query.edit_message_text(text)
            else:
                await message_or_query.reply_text(text)
            return
        
        if hasattr(message_or_query, 'from_user'):
            user_id = message_or_query.from_user.id
        else:
            user_id = message_or_query.message.chat.id
        
        log = db.query(LottoRecommendLog).filter(
            LottoRecommendLog.user_id == user_id,
            LottoRecommendLog.target_draw_no == draw_no
        ).first()
        
        lines = []
        lines.append(f"🎰 {draw_no}회 당첨 결과")
        lines.append("")
        lines.append(f"당첨번호: {draw.n1:02d}, {draw.n2:02d}, {draw.n3:02d}, {draw.n4:02d}, {draw.n5:02d}, {draw.n6:02d}")
        lines.append(f"보너스: {draw.bonus:02d}")
        lines.append("")
        
        if not log:
            lines.append("━━━━━━━━━━━━━━━━━━━")
            lines.append("⚠️ 이 회차에 추천 번호가 없습니다.")
            lines.append("")
            lines.append("💡 /lotto 명령어로 번호를 받으면")
            lines.append("   다음 회차부터 자동으로 당첨 확인됩니다!")
        else:
            if not log.match_results:
                lines.append("━━━━━━━━━━━━━━━━━━━")
                lines.append("📊 당첨 분석 진행 중...")
                lines.append("잠시 후 다시 확인해주세요!")
            else:
                lines.append("━━━━━━━━━━━━━━━━━━━")
                lines.append("🎉 회원님의 결과")
                lines.append("━━━━━━━━━━━━━━━━━━━")
                lines.append("")
                lines.append("※ 당첨 내역 분석 준비 중")
        
        text = "\n".join(lines)
        
        if hasattr(message_or_query, 'edit_message_text'):
            await message_or_query.edit_message_text(text)
        else:
            await message_or_query.reply_text(text)
        
    except Exception as e:
        print(f"❌ 결과 조회 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
