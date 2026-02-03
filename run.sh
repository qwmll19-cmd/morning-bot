#!/bin/bash

set -e

echo "🌅 Morning Bot 시작..."
echo "✓ 환경 설정 완료"

# 가상환경 준비
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

# 가상환경 python/uvicorn 경로
VENV_PY="./venv/bin/python"

# 백그라운드에서 FastAPI 서버 시작 (스케줄러 포함)
echo "🚀 FastAPI 서버 시작 중..."
RELOAD_FLAG=""
if [ "${RELOAD:-0}" = "1" ]; then
  RELOAD_FLAG="--reload"
fi
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8001}"
$VENV_PY -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT" $RELOAD_FLAG &
FASTAPI_PID=$!

# 잠시 대기 (서버 초기화)
sleep 3

# 텔레그램 봇 시작
echo "🤖 텔레그램 봇 시작 중..."
$VENV_PY -m backend.app.telegram_bot.bot &
BOT_PID=$!

echo ""
echo "✅ Morning Bot이 실행 중입니다!"
echo "📍 FastAPI 서버: http://${HOST}:${PORT}"
echo "📍 API 문서: http://${HOST}:${PORT}/docs"
echo "📍 텔레그램 봇: 활성화됨"
echo ""
echo "⏰ 스케줄러:"
echo "   - 기본 알림 시간: 09:10 (사용자 변경 가능)"
echo "   - 기본 수집 시간: 09:05 (알림 5분 전 자동 수집)"
echo "   - 사용자 알림 5분 전 데이터 수집 (환율, 지수, 금속, 뉴스)"
echo "   - 사용자 알림 시간에 모닝 브리핑 전송"
echo "   - 매시 55분 속보 수집"
echo "   - 12시/18시/22시 속보 배치 전송 (최근 6시간)"
echo ""
echo "종료하려면 Ctrl+C를 누르세요."

# Ctrl+C 시 정상 종료
trap "echo '종료 중...'; kill $FASTAPI_PID $BOT_PID 2>/dev/null; exit 0" INT TERM

# 백그라운드 프로세스 대기
wait
