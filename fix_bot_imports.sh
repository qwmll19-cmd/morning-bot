#!/bin/bash
set -e

# 0) venv 활성화(운영 방식 유지)
source venv/bin/activate

# 1) 백업
cp backend/app/telegram_bot/bot.py "backend/app/telegram_bot/bot.py.SAFETY_$(date +%Y%m%d_%H%M%S)"

# 2) bot.py import 보강 (필요한 것만 추가)
python3 - <<'PY'
from pathlib import Path
import re

p = Path("backend/app/telegram_bot/bot.py")
s = p.read_text(encoding="utf-8", errors="ignore")

# --- 필수 import 세트 ---
need_lines = [
    "import os",
    "import logging",
    "from typing import Any, Dict, Optional, List",
    "import httpx",
    "from backend.app.config import settings",
    "from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton",
    "from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters",
]

# 1) 이상한 'from backend.app.settings import settings' 있으면 주석처리
s = s.replace(
    "from backend.app.settings import settings",
    "# from backend.app.settings import settings  # disabled (use backend.app.config)"
)

lines = s.splitlines(True)

# 2) import 블록 위치 찾기: 파일 맨 위에서 연속된 import/from 구간 끝
insert_at = 0
for i, line in enumerate(lines[:200]):  # 상단만 보면 충분
    if line.startswith(("import ", "from ")):
        insert_at = i + 1
    else:
        if insert_at > 0:
            break

top = "".join(lines[:insert_at])
rest = "".join(lines[insert_at:])

def has_import(stmt: str, text: str) -> bool:
    # 공백/줄바꿈 차이 무시하고 대충 포함 여부 체크
    key = stmt.strip()
    return key in text

# 3) 누락된 import만 insert_at 위치에 추가
add = []
for stmt in need_lines:
    if not has_import(stmt, s):
        add.append(stmt + "\n")

# 4) telegram/ext import가 부분만 있는 경우를 위해 보강:
#    - telegram.ext에서 ApplicationBuilder 등이 빠져있을 때, 해당 from ... import (...) 라인을 교체
pattern_ext = re.compile(r"^from\s+telegram\.ext\s+import\s+(.+)$", re.M)
m = pattern_ext.search(s)
if m:
    # 이미 telegram.ext import가 존재하면, 필요한 항목들을 포함하도록 합치기
    current = m.group(1)
    # 괄호 포함/미포함 모두 대응
    current_items = re.sub(r"[()\s]", "", current).split(",")
    current_items = [x for x in current_items if x]
    need_items = ["ApplicationBuilder","CommandHandler","CallbackQueryHandler","MessageHandler","ContextTypes","filters"]
    merged = []
    for it in need_items:
        if it not in current_items:
            current_items.append(it)
    merged = ", ".join(need_items)  # 순서 고정
    s = pattern_ext.sub(f"from telegram.ext import {merged}", s, count=1)

# 5) telegram import도 Update만 있는 경우를 위해 보강
pattern_tg = re.compile(r"^from\s+telegram\s+import\s+(.+)$", re.M)
# 우리가 원하는 라인이 이미 있으면 패스, 아니면 Update 포함 라인을 확장 or 추가
if "from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton" not in s:
    m2 = pattern_tg.search(s)
    if m2 and "Update" in m2.group(1):
        s = pattern_tg.sub(
            "from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton",
            s, count=1
        )
    else:
        # 아예 없으면 위에서 add에 들어가게 됨
        pass

# 6) 최종적으로 insert
if add:
    s = top + "".join(add) + rest

p.write_text(s, encoding="utf-8")
print("✅ bot.py imports patched:", len(add), "lines added")
PY

# 3) 문법 체크
python3 -m py_compile backend/app/telegram_bot/bot.py

# 4) 운영 방식 그대로 실행
bash run.sh
