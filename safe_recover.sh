#!/bin/bash
set -u  # 미정의 변수 접근만 막고, exit로 터미널 죽이지 않음

echo "== 0) 위치 확인 =="
pwd

echo "== 1) venv 활성화 =="
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
else
  echo "❌ venv/bin/activate 없음. venv 경로부터 확인 필요"
  exit 0
fi

echo "== 2) 전체 백업(보험) =="
ts=$(date +%Y%m%d_%H%M%S)
tar -czf "../morning-bot_SAFETY_${ts}.tgz" . && echo "✅ 백업 완료: ../morning-bot_SAFETY_${ts}.tgz" || echo "⚠️ 백업 실패(그래도 계속 진행)"

echo "== 3) bot.py 후보 목록 =="
ls -1 backend/app/telegram_bot/bot.py* 2>/dev/null | sed -n '1,120p' || true

echo "== 4) 후보 중 가장 정상적인 파일 선택 후 bot.py로 복구 =="
python3 - <<'PY'
from pathlib import Path
import glob, re

cands=[]
cands += glob.glob("backend/app/telegram_bot/bot.py.fixed_imports_*")
cands += glob.glob("backend/app/telegram_bot/bot.py.SAFETY_*")
cands += glob.glob("backend/app/telegram_bot/bot.py.before_*")
cands += glob.glob("backend/app/telegram_bot/bot.py.bak")
cands = [c for c in cands if Path(c).exists()]

need = [
  r"from telegram\.ext import .*ApplicationBuilder",
  r"\bMAIN_KEYBOARD\b",
  r"\blogger\s*=",
  r"\bhttpx\b",
  r"\bUNIRATE_BASE_URL\b",
  r"\blotto_command\b",
  r"def main\(",
]

def score(t:str)->int:
  s=0
  for pat in need:
    if re.search(pat, t, re.S): s += 2
  if re.search(r"(?m)^\s*n\s*$", t): s -= 5
  if "nload_dotenv" in t: s -= 3
  return s

best=None; best_sc=-10**9
for f in cands:
  t=Path(f).read_text(encoding="utf-8", errors="ignore")
  sc=score(t)
  if sc>best_sc:
    best=f; best_sc=sc

print("SELECTED_BACKUP:", best)
print("SCORE:", best_sc)
if not best:
  print("❌ 복구 후보가 없음(파일명 확인 필요)")
else:
  Path("backend/app/telegram_bot/bot.py").write_text(
    Path(best).read_text(encoding="utf-8", errors="ignore"),
    encoding="utf-8"
  )
  print("✅ bot.py를 선택된 파일로 덮어씀")
PY

echo "== 5) 컴파일 체크 =="
python3 -m py_compile backend/app/telegram_bot/bot.py && echo "✅ 컴파일 OK" || echo "❌ 컴파일 에러(아래 에러 로그 필요)"

echo "== 6) run.sh 실행은 여기서 하지 않음(안전) =="
echo "다음 단계: 컴파일 OK면 'bash run.sh'를 별도로 실행"
