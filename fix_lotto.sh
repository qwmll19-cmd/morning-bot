#!/usr/bin/env bash
set -euo pipefail

cd /Users/seobeo1/Downloads/morning-bot

BOT="backend/app/telegram_bot/bot.py"
TS="$(date +%Y%m%d_%H%M%S)"
cp "$BOT" "${BOT}.BAK_${TS}"
echo "✅ backup created: ${BOT}.BAK_${TS}"

python3 - <<'PY'
from pathlib import Path
import re

bot_path = Path("backend/app/telegram_bot/bot.py")
s = bot_path.read_text(encoding="utf-8", errors="ignore")

# 0) 현재 프로젝트에 lotto handler 파일이 있는지 먼저 "검토"
lotto_module_path = Path("backend/app/handlers/lotto/lotto_handler.py")
has_lotto_module_file = lotto_module_path.exists()

# 1) bot.py 안에서 lotto_command가 참조되는지 확인
uses_lotto = ("lotto_command" in s)

# 2) 이미 import 되어 있으면 아무것도 안 함
import_line = "from backend.app.handlers.lotto.lotto_handler import lotto_command"
already_imported = import_line in s

changed = False

# 3) 파일이 있으면: import를 복구(추가)한다 (기능 살리기)
if uses_lotto and has_lotto_module_file and not already_imported:
    # import 블록의 "맨 아래쪽"에 자연스럽게 삽입
    # (from ... import ... 들이 끝나는 지점 근처)
    lines = s.splitlines(True)
    insert_at = 0
    for i, line in enumerate(lines[:200]):  # 상단 200줄 안에서만 찾기
        if line.startswith("import ") or line.startswith("from "):
            insert_at = i + 1
    lines.insert(insert_at, import_line + "\n")
    s = "".join(lines)
    changed = True
    print("✅ lotto handler file exists -> restored import:", import_line)

# 4) 파일이 없으면: 운영 유지용 '임시 로또'를 bot.py에 최소 삽입 (절대 기능 제거 X)
#    (나중에 진짜 lotto_handler 파일 찾으면 그걸로 대체하면 됨)
if uses_lotto and (not has_lotto_module_file):
    # bot.py 안에 lotto_command 정의가 아예 없을 때만 추가
    has_def = re.search(r'(?m)^\s*async\s+def\s+lotto_command\s*\(', s) is not None
    if not has_def:
        # start 함수 위나, 첫 async def 위에 삽입 (최소 영향)
        m = re.search(r'(?m)^\s*async\s+def\s+', s)
        insert_pos = m.start() if m else 0
        fallback = """
# --- fallback lotto_command (auto-added, keep bot running) ---
import random
async def lotto_command(update, context):
    nums = sorted(random.sample(range(1, 46), 6))
    await update.message.reply_text("🎰 로또 번호: " + ", ".join(map(str, nums)))
# -----------------------------------------------------------
"""
        s = s[:insert_pos] + fallback + s[insert_pos:]
        changed = True
        print("⚠️ lotto_handler.py not found -> injected fallback lotto_command into bot.py (minimal)")

# 5) 저장
if changed:
    bot_path.write_text(s, encoding="utf-8")
    print("✅ bot.py patched")
else:
    print("ℹ️ no change needed")

PY

# 6) 문법 체크
python3 -m py_compile backend/app/telegram_bot/bot.py
echo "✅ py_compile OK"

# 7) lotto 모듈이 실제로 있으면 import 테스트까지 확인
python3 - <<'PY'
try:
    from backend.app.handlers.lotto.lotto_handler import lotto_command
    print("✅ lotto_handler import OK (real handler)")
except Exception as e:
    print("ℹ️ lotto_handler import not available:", e)
PY

echo "✅ done. Now run in original ops mode:"
echo "   bash run.sh"
