#!/usr/bin/env bash
set -euo pipefail

cd /Users/seobeo1/Downloads/morning-bot
BOT="backend/app/telegram_bot/bot.py"
TS="$(date +%Y%m%d_%H%M%S)"
cp "$BOT" "${BOT}.BAK_${TS}"
echo "✅ backup: ${BOT}.BAK_${TS}"

python3 - <<'PY'
from pathlib import Path
import re

bot = Path("backend/app/telegram_bot/bot.py")
s = bot.read_text(encoding="utf-8", errors="ignore")

# 1) fallback lotto_command 블록이 있으면 제거 (있어도 없어도 안전)
s2 = re.sub(
    r'(?ms)^\s*# --- fallback lotto_command.*?^# -----------------------------------------------------------\s*\n',
    '',
    s
)

# 2) 로또 핸들러 import 라인 보장
import_line = "from backend.app.handlers.lotto.lotto_handler import lotto_command"
if import_line not in s2:
    lines = s2.splitlines(True)
    insert_at = 0
    for i, line in enumerate(lines[:250]):
        if line.startswith("import ") or line.startswith("from "):
            insert_at = i + 1
    lines.insert(insert_at, import_line + "\n")
    s2 = "".join(lines)
    print("✅ added import:", import_line)
else:
    print("ℹ️ import already present")

# 3) 예전 잘못된 settings import가 남아있으면 주석화(있을 때만)
s2 = s2.replace("from backend.app.settings import settings",
                "# from backend.app.settings import settings  # disabled (use backend.app.config)")

bot.write_text(s2, encoding="utf-8")
print("✅ bot.py saved")
PY

python3 -m py_compile backend/app/telegram_bot/bot.py
echo "✅ py_compile OK"

# run.sh는 bash로 실행 (zsh parse error 회피)
bash run.sh
