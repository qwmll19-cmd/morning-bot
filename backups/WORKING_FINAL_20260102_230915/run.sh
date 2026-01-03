#!/bin/bash

echo "🌅 Morning Bot 시작..."
echo "✓ 환경 설정 완료"

# 백그라운드에서 FastAPI 서버 시작
echo "🚀 FastAPI 서버 시작 중..."
uvicorn backend.app.api:app --host 0.0.0.0 --port 8000 --reload &
FASTAPI_PID=$!

# 잠시 대기 (서버 초기화)
sleep 3

# 텔레그램 봇 시작
echo "🤖 텔레그램 봇 시작 중..."
python3 -m backend.app.telegram_bot.bot &
BOT_PID=$!

echo ""
echo "✅ Morning Bot이 실행 중입니다!"
echo "📍 FastAPI 서버: http://localhost:8000"
echo "📍 API 문서: http://localhost:8000/docs"
echo "📍 텔레그램 봇: 활성화됨"
echo ""
echo "⏰ 스케줄러:"
echo "   - 09:01 데이터 수집 (환율, 지수, 금속, 뉴스)"
echo "   - 09:05 전일대비 계산 + 모닝 브리핑 전송"
echo "   - 매시간 속보 수집"
echo "   - 12시/18시/22시 속보 배치 전송"
echo ""
echo "종료하려면 Ctrl+C를 누르세요."

# Ctrl+C 시 정상 종료
trap "echo '종료 중...'; kill $FASTAPI_PID $BOT_PID 2>/dev/null; exit 0" INT TERM

# 백그라운드 프로세스 대기
wait
