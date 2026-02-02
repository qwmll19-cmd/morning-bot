"""로또 핸들러 (25줄: 기존 20줄 + ML 5줄)"""
import json
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from backend.app.db.session import SessionLocal
from backend.app.db.models import LottoStatsCache, LottoRecommendLog, LottoDraw, LottoUserPrediction, LottoMLPerformance
from backend.app.services.lotto.generator import generate_20_lines
from backend.app.services.lotto.stats_calculator import LottoStatsCalculator
from backend.app.services.lotto.ml_predictor import LottoMLPredictor
from backend.app.services.lotto.ml_trainer import LottoMLTrainer


def calculate_line_score(line: list, ai_weights: dict, scores_logic1: dict, scores_logic2: dict,
                         scores_logic3: dict, scores_logic4: dict) -> float:
    """
    Calculate AI combined score for a single line.

    Args:
        line: List of 6 numbers
        ai_weights: AI weights from ML model
        scores_logic1-4: Score dictionaries for each logic

    Returns:
        Combined score (sum of weighted individual number scores)
    """
    total_score = 0.0
    for num in line:
        combined_score = (
            scores_logic1.get(num, 0) * ai_weights.get('logic1', 0.25) +
            scores_logic2.get(num, 0) * ai_weights.get('logic2', 0.25) +
            scores_logic3.get(num, 0) * ai_weights.get('logic3', 0.25) +
            scores_logic4.get(num, 0) * ai_weights.get('logic4', 0.25)
        )
        total_score += combined_score
    return total_score


def select_lines_by_count(all_25_lines_flat: list, count: int, ai_weights: dict,
                          scores_logic1: dict, scores_logic2: dict,
                          scores_logic3: dict, scores_logic4: dict) -> tuple:
    """
    Select N lines from 25 lines using hybrid strategy.

    - 5줄, 10줄: Random selection (다양성)
    - 15줄, 20줄, 25줄: Ranked by AI score (최적화)

    Args:
        all_25_lines_flat: List of (name, numbers, logic) tuples
        count: Number of lines to select (5, 10, 15, 20, 25)
        ai_weights: AI weights
        scores_logic1-4: Score dictionaries

    Returns:
        (selected_lines, selection_method, lines_with_scores)
    """
    # Calculate score for each line
    lines_with_scores = []
    for name, numbers, logic in all_25_lines_flat:
        score = calculate_line_score(numbers, ai_weights, scores_logic1,
                                     scores_logic2, scores_logic3, scores_logic4)
        lines_with_scores.append((name, numbers, logic, score))

    # Sort by score (descending)
    sorted_lines = sorted(lines_with_scores, key=lambda x: x[3], reverse=True)

    # Selection strategy
    if count in [5, 10]:
        # Random selection
        selected = random.sample(sorted_lines, count)
        selection_method = "랜덤"
    else:
        # Ranked selection (top N)
        selected = sorted_lines[:count]
        selection_method = "랭킹순"

    # Re-sort selected lines by score for display (descending)
    selected = sorted(selected, key=lambda x: x[3], reverse=True)

    return selected, selection_method, sorted_lines


async def lotto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """로또 번호 생성 - 줄 수 선택 UI 표시"""
    db = SessionLocal()

    try:
        cache = db.query(LottoStatsCache).first()
        if not cache:
            await update.message.reply_text("⚠️ 통계 데이터가 없습니다.")
            return

        next_draw_no = cache.total_draws + 1

        # 줄 수 선택 버튼
        keyboard = [
            [
                InlineKeyboardButton("🎲 5줄 (랜덤)", callback_data="lotto_gen:5"),
                InlineKeyboardButton("🎲 10줄 (랜덤)", callback_data="lotto_gen:10")
            ],
            [
                InlineKeyboardButton("🏆 15줄 (랭킹순)", callback_data="lotto_gen:15"),
                InlineKeyboardButton("🏆 20줄 (랭킹순)", callback_data="lotto_gen:20")
            ],
            [
                InlineKeyboardButton("🏆 25줄 전체 (랭킹순)", callback_data="lotto_gen:25")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            f"🎰 로또 번호 생성\n"
            f"🎯 예상 회차: {next_draw_no}회\n"
            f"\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💡 원하는 줄 수를 선택하세요\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"🎲 랜덤 선택 (5줄, 10줄)\n"
            f"   → 다양한 조합 제공\n"
            f"\n"
            f"🏆 랭킹순 선택 (15줄, 20줄, 25줄)\n"
            f"   → AI 점수 높은 순서대로 제공\n"
            f"\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 당첨번호 조회: /lotto_result [회차]\n"
            f"   예) /lotto_result 1206\n"
            f"\n"
            f"📈 성능 평가 조회: /lotto_performance\n"
            f"   예) /lotto_performance 10"
        )

        await update.message.reply_text(text, reply_markup=reply_markup)

    except Exception as e:
        print(f"❌ 로또 명령어 오류: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text("⚠️ 오류가 발생했습니다.")
    finally:
        db.close()


async def lotto_generate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """로또 번호 생성 (콜백 핸들러)"""
    query = update.callback_query
    await query.answer()

    db = SessionLocal()

    try:
        # Parse requested count from callback data
        requested_count = int(query.data.split(":")[1])

        cache = db.query(LottoStatsCache).first()

        if not cache:
            await query.edit_message_text("⚠️ 통계 데이터가 없습니다.")
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
        
        # 4가지 로직 점수 계산 (Logic4 추가)
        scores_logic1 = LottoStatsCalculator.calculate_ai_scores_logic1(draws_dict)
        scores_logic2 = LottoStatsCalculator.calculate_ai_scores_logic2(draws_dict)
        scores_logic3 = LottoStatsCalculator.calculate_ai_scores_logic3(draws_dict)
        scores_logic4 = LottoStatsCalculator.calculate_ai_scores_logic4(draws_dict)

        # AI 가중치 (ML 모델에서 로드, 없으면 기본값)
        ai_weights = {'logic1': 0.25, 'logic2': 0.25, 'logic3': 0.25, 'logic4': 0.25}
        try:
            trainer = LottoMLTrainer()
            if trainer.load_model() and trainer.ai_weights:
                ai_weights = trainer.ai_weights
        except Exception:
            pass
        
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

        # ML 5줄 생성 (기존 20줄과 중복 방지)
        ml_lines = []
        try:
            trainer = LottoMLTrainer()
            model_loaded = trainer.load_model()

            # 모델이 없으면 자동 학습 시도
            if not model_loaded and len(draws_dict) >= 100:
                print("⚠️ ML 모델 없음. 자동 학습 시작...")
                try:
                    train_result = trainer.train(draws_dict, test_size=0.2)
                    print(f"✅ ML 모델 자동 학습 완료 - Acc: {train_result['test_accuracy']:.4f}")
                    model_loaded = True
                except Exception as train_e:
                    print(f"⚠️ ML 자동 학습 실패: {train_e}")

            if model_loaded:
                predictor = LottoMLPredictor(trainer)

                # 기존 20줄 수집 (중복 방지용)
                existing_20_lines = []
                existing_20_lines.extend(result['basic'])
                existing_20_lines.extend(result['logic1'])
                existing_20_lines.extend(result['logic2'])
                existing_20_lines.extend(result['logic3'])
                existing_20_lines.extend(result['final'])
                existing_20_lines.extend(result['ai_core'])

                # 사용자 정의 패턴 (5개)
                user_patterns = [
                    {'type': 'top_probability', 'params': {}},               # ㉑ ML 확률 상위
                    {'type': 'balanced_zones', 'params': {'zones': (2, 2, 2)}},  # ㉒ ML 구간 밸런스
                    {'type': 'odd_even_balanced', 'params': {'ratio': (3, 3)}},  # ㉓ ML 홀짝 밸런스
                    {'type': 'consecutive_optimal', 'params': {}},           # ㉔ ML 연속 최적
                    {'type': 'sum_range', 'params': {'min': 130, 'max': 140}}  # ㉕ ML 합계 최적
                ]

                ml_lines = predictor.generate_ml_5_lines(draws_dict, user_patterns, existing_20_lines)
        except Exception as e:
            print(f"⚠️ ML 5줄 생성 실패: {e}")
            ml_lines = []

        # Prepare all 25 lines as flat list for selection
        all_25_lines_flat = []

        # Basic 4 lines
        for name, line in zip(
            ["① 믹스(최다+최소+랜덤)", "② 최다 출현 위주", "③ 최소 출현 위주", "④ 최다 줄 기반 믹스"],
            result['basic']
        ):
            all_25_lines_flat.append((name, line, 'basic'))

        # Logic1 3 lines
        for name, line in zip(
            ["⑤ AI 홀짝 밸런스", "⑥ AI 구간 밸런스", "⑦ AI 종합 점수"],
            result['logic1']
        ):
            all_25_lines_flat.append((name, line, 'logic1'))

        # Logic2 3 lines
        for name, line in zip(
            ["⑧ AI 홀짝 최적", "⑨ AI 구간 최적", "⑩ AI 합계 최적"],
            result['logic2']
        ):
            all_25_lines_flat.append((name, line, 'logic2'))

        # Logic3 3 lines
        for name, line in zip(
            ["⑪ AI 홀짝 밸런스", "⑫ AI 구간 밸런스", "⑬ AI 연속 최적"],
            result['logic3']
        ):
            all_25_lines_flat.append((name, line, 'logic3'))

        # Final 2 lines
        for name, line in zip(
            ["⑭ AI 모든 패턴 종합", "⑮ AI 최종 최적화"],
            result['final']
        ):
            all_25_lines_flat.append((name, line, 'final'))

        # AI Core 5 lines
        for i, line in enumerate(result['ai_core']):
            all_25_lines_flat.append((f"⑯~⑳ AI 핵심번호 #{i+1}", line, 'ai_core'))

        # ML 5 lines (if available)
        if ml_lines:
            for name, line in zip(
                ["㉑ ML 확률 상위", "㉒ ML 구간 밸런스", "㉓ ML 홀짝 밸런스", "㉔ ML 연속 최적", "㉕ ML 합계 최적"],
                ml_lines
            ):
                all_25_lines_flat.append((name, line, 'ml'))

        # Select N lines using hybrid strategy
        selected_lines, selection_method, all_sorted = select_lines_by_count(
            all_25_lines_flat, requested_count, ai_weights,
            scores_logic1, scores_logic2, scores_logic3, scores_logic4
        )

        # DB 저장 1: 기존 로그 (하위 호환성)
        all_lines_for_db = {
            'selected': [
                {'name': name, 'numbers': numbers, 'logic': logic, 'score': score}
                for name, numbers, logic, score in selected_lines
            ]
        }

        log = LottoRecommendLog(
            user_id=user_id,
            target_draw_no=next_draw_no,
            lines=json.dumps(all_lines_for_db),
            recommend_time=datetime.now(),
            match_results=None
        )

        db.add(log)

        # DB 저장 2: 사용자 예측 (성능 평가용)
        chat_id = str(update.effective_chat.id)

        # 기존 예측이 있으면 삭제 (최신 예측으로 덮어쓰기)
        db.query(LottoUserPrediction).filter(
            LottoUserPrediction.chat_id == chat_id,
            LottoUserPrediction.target_draw_no == next_draw_no
        ).delete()

        user_prediction = LottoUserPrediction(
            chat_id=chat_id,
            target_draw_no=next_draw_no,
            lines=[
                {'name': name, 'numbers': numbers, 'logic': logic}
                for name, numbers, logic, score in selected_lines
            ],
            line_count=requested_count,
            created_at=datetime.now()
        )

        db.add(user_prediction)
        db.commit()
        
        # 텔레그램 메시지
        lines = []
        total_available = len(all_25_lines_flat)
        lines.append(f"🎰 로또 번호 추천 ({requested_count}줄)")
        lines.append(f"🎯 예상 회차: {next_draw_no}회")
        lines.append(f"📋 선택 방법: {selection_method} (전체 {total_available}줄 중)")
        lines.append("")

        # Display selected lines
        lines.append("━━━━━━━━━━━━━━━━━━━")
        if selection_method == "랭킹순":
            lines.append(f"🏆 AI 점수 상위 {requested_count}줄")
        else:
            lines.append(f"🎲 랜덤 선택 {requested_count}줄")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")

        for rank, (name, numbers, logic, score) in enumerate(selected_lines, 1):
            formatted = ", ".join([f"{n:02d}" for n in numbers])
            if selection_method == "랭킹순":
                lines.append(f"#{rank} [{score:.1f}점] {name}")
            else:
                lines.append(f"#{rank} {name}")
            lines.append(f"➡️ {formatted}")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append("📊 AI 분석 기반")
        lines.append(f"- 1~{cache.total_draws}회 전체 패턴 분석")
        lines.append("- 4가지 로직 종합 (가중치 자동 조정)")
        w1 = ai_weights.get('logic1', 0) * 100
        w2 = ai_weights.get('logic2', 0) * 100
        w3 = ai_weights.get('logic3', 0) * 100
        w4 = ai_weights.get('logic4', 0) * 100
        lines.append(f"  Logic1: {w1:.1f}% | Logic2: {w2:.1f}%")
        lines.append(f"  Logic3: {w3:.1f}% | Logic4: {w4:.1f}%")
        if ml_lines:
            lines.append("- 🔮 ML 예측: 15개 특성 분석")
        lines.append("- 매주 토요일 자동 업데이트")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 당첨번호 조회")
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append("/lotto_result [회차]")
        lines.append("예) /lotto_result 1206")

        text = "\n".join(lines)

        await query.edit_message_text(text)

    except Exception as e:
        print(f"❌ 로또 생성 오류: {e}")
        import traceback
        traceback.print_exc()

        try:
            await query.edit_message_text("⚠️ 번호 생성 중 오류가 발생했습니다.")
        except:
            pass
    finally:
        db.close()


async def lotto_result_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """당첨번호 조회 명령어: /lotto_result [회차]"""
    db = SessionLocal()

    try:
        # Parse draw number from command args
        if not context.args or len(context.args) == 0:
            # Show usage with recent draw buttons
            cache = db.query(LottoStatsCache).first()
            if not cache:
                await update.message.reply_text("⚠️ 데이터가 없습니다.")
                return

            latest_draw = cache.total_draws

            # Recent 4 draws buttons
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

            text = (
                f"📊 로또 당첨번호 조회\n"
                f"\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💡 사용법\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"\n"
                f"/lotto_result [회차번호]\n"
                f"예) /lotto_result 1206\n"
                f"\n"
                f"또는 아래 버튼을 클릭하세요"
            )

            await update.message.reply_text(text, reply_markup=reply_markup)
            return

        try:
            draw_no = int(context.args[0])
            if draw_no < 1 or draw_no > 1300:
                await update.message.reply_text("⚠️ 올바른 회차를 입력하세요 (1~1300)")
                return

            await show_lotto_result(update.message, draw_no)

        except ValueError:
            await update.message.reply_text(
                "⚠️ 올바른 숫자를 입력하세요.\n"
                "예) /lotto_result 1206"
            )

    except Exception as e:
        print(f"❌ 당첨번호 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text("⚠️ 오류가 발생했습니다.")
    finally:
        db.close()


async def lotto_result_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """회차별 결과 확인 (버튼 클릭)"""
    query = update.callback_query
    await query.answer()

    draw_no = int(query.data.split(":")[1])
    await show_lotto_result(query, draw_no)


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

        # Get chat_id
        if hasattr(message_or_query, 'from_user'):
            chat_id = str(message_or_query.from_user.id)
        elif hasattr(message_or_query, 'message'):
            chat_id = str(message_or_query.message.chat.id)
        else:
            chat_id = str(message_or_query.chat.id)

        # Check user prediction
        user_prediction = db.query(LottoUserPrediction).filter(
            LottoUserPrediction.chat_id == chat_id,
            LottoUserPrediction.target_draw_no == draw_no
        ).first()

        lines = []
        lines.append(f"🎰 {draw_no}회 당첨 결과")
        lines.append("")
        lines.append(f"🎯 당첨번호: {draw.n1:02d}, {draw.n2:02d}, {draw.n3:02d}, {draw.n4:02d}, {draw.n5:02d}, {draw.n6:02d}")
        lines.append(f"🎁 보너스: {draw.bonus:02d}")
        lines.append("")

        if not user_prediction:
            lines.append("━━━━━━━━━━━━━━━━━━━")
            lines.append("⚠️ 이 회차에 추천 번호가 없습니다.")
            lines.append("")
            lines.append("💡 /lotto 명령어로 번호를 받으면")
            lines.append("   다음 회차부터 자동으로 당첨 확인됩니다!")
        else:
            # Analyze if not already done
            if not user_prediction.analyzed:
                winning_numbers = {draw.n1, draw.n2, draw.n3, draw.n4, draw.n5, draw.n6}

                match_3 = match_4 = match_5 = match_6 = 0
                total_matches = 0

                for line_data in user_prediction.lines:
                    line_numbers = set(line_data['numbers'])
                    matches = len(line_numbers & winning_numbers)
                    total_matches += matches

                    if matches == 3:
                        match_3 += 1
                    elif matches == 4:
                        match_4 += 1
                    elif matches == 5:
                        match_5 += 1
                    elif matches == 6:
                        match_6 += 1

                # Update prediction with results
                user_prediction.analyzed = True
                user_prediction.match_3 = match_3
                user_prediction.match_4 = match_4
                user_prediction.match_5 = match_5
                user_prediction.match_6 = match_6
                user_prediction.total_matches = total_matches
                user_prediction.analyzed_at = datetime.now()
                db.commit()

            lines.append("━━━━━━━━━━━━━━━━━━━")
            lines.append("🎉 회원님의 결과")
            lines.append("━━━━━━━━━━━━━━━━━━━")
            lines.append("")
            lines.append(f"📊 생성한 줄 수: {user_prediction.line_count}줄")
            lines.append("")

            if user_prediction.match_6 > 0:
                lines.append(f"🏆🏆🏆 1등 당첨! (6개 맞음) - {user_prediction.match_6}줄")
            elif user_prediction.match_5 > 0:
                lines.append(f"🏆🏆 2등/3등 당첨! (5개 맞음) - {user_prediction.match_5}줄")
            elif user_prediction.match_4 > 0:
                lines.append(f"🏆 4등 당첨! (4개 맞음) - {user_prediction.match_4}줄")
            elif user_prediction.match_3 > 0:
                lines.append(f"🎯 5등 당첨! (3개 맞음) - {user_prediction.match_3}줄")
            else:
                lines.append("😢 당첨되지 않았습니다.")

            lines.append("")
            lines.append("📈 상세 통계:")
            lines.append(f"  • 3개 맞은 줄: {user_prediction.match_3}줄")
            lines.append(f"  • 4개 맞은 줄: {user_prediction.match_4}줄")
            lines.append(f"  • 5개 맞은 줄: {user_prediction.match_5}줄")
            lines.append(f"  • 6개 맞은 줄: {user_prediction.match_6}줄")
            lines.append(f"  • 총 맞은 번호: {user_prediction.total_matches}개")
            avg_per_line = user_prediction.total_matches / user_prediction.line_count
            lines.append(f"  • 줄당 평균: {avg_per_line:.2f}개")

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


async def lotto_performance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ML 성능 평가 결과 조회: /lotto_performance [회차_수]"""
    db = SessionLocal()

    try:
        # 조회할 회차 수 (기본 5회)
        count = 5
        if context.args and len(context.args) > 0:
            try:
                count = int(context.args[0])
                if count < 1 or count > 20:
                    await update.message.reply_text("⚠️ 1~20 사이의 숫자를 입력하세요.")
                    return
            except ValueError:
                await update.message.reply_text("⚠️ 올바른 숫자를 입력하세요.")
                return

        # 최근 N회 성능 평가 조회
        performances = db.query(LottoMLPerformance).order_by(
            LottoMLPerformance.draw_no.desc()
        ).limit(count).all()

        if not performances:
            await update.message.reply_text(
                "⚠️ 성능 평가 데이터가 없습니다.\n\n"
                "💡 성능 평가는 매주 토요일 22시에 자동으로 실행됩니다."
            )
            return

        lines = []
        lines.append("📊 ML 성능 평가 결과")
        lines.append("")
        lines.append(f"최근 {len(performances)}회 평가 기록")
        lines.append("")

        for perf in performances:
            lines.append("=" * 40)
            lines.append(f"🎯 {perf.draw_no}회")
            lines.append(f"📅 평가 시각: {perf.evaluated_at.strftime('%Y-%m-%d %H:%M')}")
            lines.append("")

            lines.append(f"📈 전체 성능 ({perf.total_lines}줄 기준):")
            lines.append(f"  • 3개 맞음: {perf.match_3}줄")
            lines.append(f"  • 4개 맞음: {perf.match_4}줄")
            lines.append(f"  • 5개 맞음: {perf.match_5}줄")
            lines.append(f"  • 6개 맞음: {perf.match_6}줄")
            lines.append(f"  • 줄당 평균: {perf.avg_matches_per_line:.2f}개")
            lines.append("")

            # 성능 점수
            score_emoji = "🟢" if perf.performance_score >= 60 else "🟡" if perf.performance_score >= 40 else "🔴"
            lines.append(f"{score_emoji} 성능 점수: {perf.performance_score:.1f}/100")
            lines.append("")

            # 로직별 성능
            lines.append("📊 로직별 평균 (개/줄):")
            lines.append(f"  • Logic1: {perf.logic1_score:.2f}")
            lines.append(f"  • Logic2: {perf.logic2_score:.2f}")
            lines.append(f"  • Logic3: {perf.logic3_score:.2f}")
            lines.append(f"  • Logic4: {perf.logic4_score:.2f}")
            if perf.ml_score > 0:
                lines.append(f"  • ML: {perf.ml_score:.2f}")
            lines.append("")

            # 가중치 정보
            if perf.weights_logic1:
                lines.append("⚖️ 사용된 가중치:")
                lines.append(f"  • Logic1: {perf.weights_logic1*100:.1f}%")
                lines.append(f"  • Logic2: {perf.weights_logic2*100:.1f}%")
                lines.append(f"  • Logic3: {perf.weights_logic3*100:.1f}%")
                lines.append(f"  • Logic4: {perf.weights_logic4*100:.1f}%")
                lines.append("")

            # 재학습 정보
            if perf.retrained:
                lines.append("🔄 재학습 완료")
                lines.append(f"  • 시각: {perf.retrained_at.strftime('%Y-%m-%d %H:%M')}")
                if perf.new_weights:
                    lines.append(f"  • 새 가중치 적용됨")
                lines.append("")
            elif perf.needs_retraining:
                lines.append("⚠️ 재학습 필요 (성능 저하)")
                lines.append("")

        lines.append("=" * 40)
        lines.append("")
        lines.append("💡 사용법:")
        lines.append("/lotto_performance [회차수]")
        lines.append("예) /lotto_performance 10")

        text = "\n".join(lines)

        # 텔레그램 메시지 길이 제한 (4096자)
        if len(text) > 4000:
            # 너무 길면 최근 3회만 표시
            await update.message.reply_text(
                f"⚠️ 결과가 너무 깁니다. 최근 3회만 표시합니다.\n\n"
                f"/lotto_performance 3 명령을 사용해주세요."
            )
        else:
            await update.message.reply_text(text)

    except Exception as e:
        print(f"❌ 성능 평가 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text("⚠️ 오류가 발생했습니다.")
    finally:
        db.close()
