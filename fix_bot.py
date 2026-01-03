#!/usr/bin/env python3
"""bot.py에 로또 기능을 추가하는 스크립트"""

def modify_bot_py():
    with open('backend/app/telegram_bot/bot.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    modified = []
    
    for i, line in enumerate(lines):
        modified.append(line)
        
        # 1. import 추가 (from backend.app.config import settings 다음)
        if 'from backend.app.config import settings' in line and i < 30:
            modified.append('from backend.app.handlers.lotto.lotto_handler import lotto_command\n')
        
        # 2. MAIN_KEYBOARD에 로또 버튼 추가 (["🥇 금·은 시세"], 줄 찾기)
        if '["🥇 금·은 시세"],' in line:
            modified.append('        ["🎰 로또 번호"],\n')
        
        # 3. handle_text_buttons에 로또 처리 추가
        if 'elif text == "🥇 금·은 시세":' in line:
            # 다음 줄 (await metal_command) 추가
            if i + 1 < len(lines):
                modified.append(lines[i+1])  # await metal_command
                # 그 다음에 로또 추가
                modified.append('    elif text == "🎰 로또 번호":\n')
                modified.append('        await lotto_command(update, context)\n')
                # 다음 줄(i+2)은 건너뛰기 위해 표시
                lines[i+1] = None
        
        # 4. CommandHandler 등록 (set_time 다음)
        if 'application.add_handler(CommandHandler("set_time", set_time_command))' in line:
            modified.append('    application.add_handler(CommandHandler("lotto", lotto_command))\n')
    
    # None인 줄 제거 (중복 방지)
    result = [line for line in modified if line is not None]
    
    with open('backend/app/telegram_bot/bot.py', 'w', encoding='utf-8') as f:
        f.writelines(result)
    
    print("✅ bot.py 수정 완료!")
    print("   ✓ import 추가")
    print("   ✓ 키보드 버튼 추가")
    print("   ✓ 버튼 핸들러 추가")
    print("   ✓ CommandHandler 등록")

if __name__ == '__main__':
    modify_bot_py()
