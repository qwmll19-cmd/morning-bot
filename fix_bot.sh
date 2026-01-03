#!/usr/bin/env bash
set -euo pipefail

cd /Users/seobeo1/Downloads/morning-bot

# 0) 실행중 프로세스 정리
pkill -f "uvicorn backend.app.main:app" 2>/dev/null || true
pkill -f "backend\.app\.telegram_bot\.bot" 2>/dev/null || true
pkill -f "telegram_bot/bot\.py" 2>/dev/null || true

# 1) 현재 bot.py 안전 백업
ts=$(date +"%Y%m%d_%H%M%S")
cp backend/app/telegram_bot/bot.py "backend/app/telegram_bot/bot.py.SAFETY_$ts" || true
echo "✅ backup: backend/app/telegram_bot/bot.py.SAFETY_$ts"

# 2) 우선순위 백업에서 복구 (존재하는 첫 파일로)
for cand in \
  backend/app/telegram_bot/bot.py.fixed_imports_20260101_2202 \
  backend/app/telegram_bot/bot.py.bak \
  backend/app/telegram_bot/bot.py.broken \
  backend/app/telegram_bot/bot.py.broken_now \
; do
  if [ -f "$cand" ]; then
    echo "✅ restore from: $cand"
    cp "$cand" backend/app/telegram_bot/bot.py
    break
  fi
done

# 3) 딱 필요한 최소 수정만 적용
python - <<'PY'
from pathlib import Path
import re

p = Path("backend/app/telegram_bot/bot.py")
s = p.read_text(encoding="utf-8", errors="ignore")

# (A) 단독 'n' 같은 찌꺼기 라인 제거 (다른 부분 영향 거의 없음)
s = re.sub(r'(?m)^\s*n\s*$\n?', '', s)

# (B) SUPPORTED_COINS 딕셔너리 닫기: def build_timeframe_keyboard 앞에 '}' 없으면 삽입
pat = r'(?ms)(SUPPORTED_COINS\s*:\s*Dict\[.*?\]\s*=\s*\{.*?"TRX"\s*:\s*".*?",\s*)\n\s*(def\s+build_timeframe_keyboard\b)'
m = re.search(pat, s)
if m:
    # TRX 줄 다음에 바로 def가 오면 닫는 중괄호가 누락된 상태
    s = s[:m.end(1)] + "\n}\n\n" + s[m.start(2):]
    print("✅ fixed: SUPPORTED_COINS closing brace")

# (C) logging / httpx import가 없으면 최상단 import 구역에만 추가
if "import logging" not in s:
    s = "import logging\n" + s
    print("✅ added: import logging")
if "import httpx" not in s:
    s = "import httpx\n" + s
    print("✅ added: import httpx")

# (D) ReplyKeyboardMarkup가 MAIN_KEYBOARD에서 쓰이면 telegram import에 포함되게 보강
# 이미 from telegram import ... 줄이 있으면 거기에만 추가, 없으면 새로 추가(가장 위)
mt = re.search(r'(?m)^from telegram import (.+)$', s)
if mt:
    items = [x.strip() for x in mt.group(1).split(",") if x.strip()]
    for x in ["ReplyKeyboardMarkup", "InlineKeyboardMarkup", "InlineKeyboardButton"]:
        if x not in items:
            items.append(x)
    newline = "from telegram import " + ", ".join(items)
    s = re.sub(r'(?m)^from telegram import .+$', newline, s, count=1)
    print("✅ patched: from telegram import ...")
else:
    s = "from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton\n" + s
    print("✅ added: from telegram import ...")

p.write_text(s, encoding="utf-8")
print("✅ minimal patch done")
PY

# 4) 운영 방식 그대로 실행
source venv/bin/activate
python -m py_compile backend/app/telegram_bot/bot.py
bash run.sh
