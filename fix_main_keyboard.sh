#!/usr/bin/env bash
set -euo pipefail

cd /Users/seobeo1/Downloads/morning-bot
source venv/bin/activate

# 0) 프로세스 정리
pkill -f "uvicorn backend.app.main:app" 2>/dev/null || true
pkill -f "backend.app.telegram_bot.bot" 2>/dev/null || true

BOT="backend/app/telegram_bot/bot.py"

# 1) 안전 백업
TS=$(date +%Y%m%d_%H%M%S)
cp "$BOT" "${BOT}.SAFETY_MAINKEY_${TS}"
echo "✅ backup created: ${BOT}.SAFETY_MAINKEY_${TS}"

python3 - <<'PY'
from pathlib import Path
import re, glob, sys

bot = Path("backend/app/telegram_bot/bot.py")
s = bot.read_text(encoding="utf-8", errors="ignore")

# 이미 있으면 종료
if re.search(r'(?m)^\s*MAIN_KEYBOARD\s*=', s):
    print("ℹ️ MAIN_KEYBOARD already exists in current bot.py (no insert needed)")
    sys.exit(0)

# 후보 파일들
candidates = []
candidates += glob.glob("backend/app/telegram_bot/bot.py.fixed_imports_*")
candidates += glob.glob("backend/app/telegram_bot/bot.py.SAFETY_*")
candidates += glob.glob("backend/app/telegram_bot/bot.py.before_*")
candidates += ["backend/app/telegram_bot/bot.py.bak"]

candidates = [c for c in candidates if Path(c).exists()]

def extract_block(text: str):
    # MAIN_KEYBOARD = ... 부터 start 함수 직전까지를 최대한 안전하게 잡음
    m = re.search(r'(?ms)^\s*MAIN_KEYBOARD\s*=.*?(?=^\s*(?:async\s+def|def)\s+start\b)', text)
    if m:
        return m.group(0).rstrip() + "\n\n"
    # 혹시 start가 아니라 다른 함수 앞이면 더 넓게
    m = re.search(r'(?ms)^\s*MAIN_KEYBOARD\s*=.*?(?=^\s*(?:async\s+def|def)\s+\w+\b)', text)
    if m:
        return m.group(0).rstrip() + "\n\n"
    return None

best_file = None
best_block = None
for f in candidates:
    t = Path(f).read_text(encoding="utf-8", errors="ignore")
    blk = extract_block(t)
    if blk:
        best_file = f
        best_block = blk
        break

if not best_block:
    raise SystemExit("❌ MAIN_KEYBOARD block not found in any backup candidates.")

print(f"✅ MAIN_KEYBOARD source: {best_file}")

# start 함수 위치 찾기
pos = re.search(r'(?m)^\s*async\s+def\s+start\b|^\s*def\s+start\b', s)
if not pos:
    raise SystemExit("❌ start() function not found in current bot.py")

# 필요한 import 보강(중복은 그냥 놔도 파이썬이 허용하지만, 최소만)
need = {
    "ReplyKeyboardMarkup": r"\bReplyKeyboardMarkup\b",
    "KeyboardButton": r"\bKeyboardButton\b",
    "InlineKeyboardMarkup": r"\bInlineKeyboardMarkup\b",
    "InlineKeyboardButton": r"\bInlineKeyboardButton\b",
}
existing_imports = s[:pos.start()]

# telegram import 라인 보강: 없으면 추가, 있으면 라인에 심기(최소)
def ensure_telegram_import(name: str):
    nonlocal s
    if re.search(need[name], existing_imports):
        return
    # "from telegram import ..." 라인이 있으면 거기에 추가
    m = re.search(r'(?m)^from\s+telegram\s+import\s+(.+)$', s)
    if m:
        line = m.group(0)
        items = m.group(1)
        if name not in items:
            new_line = line.rstrip() + f", {name}"
            s = s.replace(line, new_line, 1)
        return
    # 없으면 새로 추가
    s = "from telegram import Update, " + name + "\n" + s

for k in ["ReplyKeyboardMarkup","KeyboardButton","InlineKeyboardMarkup","InlineKeyboardButton"]:
    ensure_telegram_import(k)

# MAIN_KEYBOARD 블록 삽입
s = s[:pos.start()] + best_block + s[pos.start():]
bot.write_text(s, encoding="utf-8")
print("✅ MAIN_KEYBOARD inserted into current bot.py")
PY

# 2) 컴파일 체크
python3 -m py_compile backend/app/telegram_bot/bot.py
echo "✅ py_compile OK"

# 3) 원래 운영 방식 실행
bash -lc 'cd /Users/seobeo1/Downloads/morning-bot && source venv/bin/activate && bash run.sh'
