# Morning Bot - 아침 뉴스 & 시장 요약 봇

매일 아침 주요 뉴스와 시장 정보를 텔레그램으로 전달하는 자동화 봇입니다.

## 주요 기능

- 📰 **뉴스 수집**: 네이버 뉴스 API를 통한 실시간 뉴스 수집 (종합/경제/속보)
- 💰 **시장 데이터**: 
  - 환율 (USD/KRW) - UniRate API
  - 암호화폐 (BTC, ETH, SOL, XRP, TRX) - CoinPaprika API
  - 금/은/구리 가격 - MetalpriceAPI
  - 코스피/나스닥 지수 - yfinance
- 🤖 **AI 요약**: Claude/GPT를 활용한 시장 코멘트 자동 생성 (선택사항)
- 📱 **텔레그램 봇**: 사용자 친화적인 버튼 인터페이스
- ⏰ **자동 스케줄링**: 
  - 매일 08:10 뉴스 Top5 생성
  - 매일 08:20 시장 데이터 수집
  - 1분마다 속보 체크

## 기술 스택

- **백엔드**: Python 3.11+, FastAPI, SQLAlchemy
- **데이터베이스**: SQLite (로컬 개발용)
- **데이터 수집**: 
  - 네이버 뉴스 API
  - UniRate API (환율)
  - MetalpriceAPI (금/은/구리)
  - CoinPaprika API (암호화폐)
  - yfinance (주식 지수)
  - BeautifulSoup4 (코스피 Top5 파싱)
- **봇**: python-telegram-bot v20
- **AI**: Claude API, OpenAI GPT (선택)
- **스케줄러**: APScheduler

## 설치 방법

### 1. 가상환경 생성 및 활성화

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고 API 키를 입력하세요:

```bash
cp .env.example .env
```

**필수 API 키:**
- `NAVER_CLIENT_ID` & `NAVER_CLIENT_SECRET`: https://developers.naver.com/apps/ (무료)
- `UNIRATE_API_KEY`: https://unirateapi.com/ (무료 플랜)
- `METALPRICE_API_KEY`: https://metalpriceapi.com/ (무료 플랜)
- `TELEGRAM_TOKEN`: Telegram BotFather에서 발급

**선택 API 키 (AI 요약 기능):**
- `ANTHROPIC_API_KEY`: Claude API (선택)
- `OPENAI_API_KEY`: OpenAI API (선택)

### 4. 데이터베이스 초기화

FastAPI 서버 실행 시 자동으로 SQLite DB가 생성됩니다.

## 실행 방법

### 옵션 1: FastAPI 서버만 실행

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

API 문서: http://localhost:8000/docs

### 옵션 2: 텔레그램 봇만 실행

```bash
python -m backend.app.telegram_bot.bot
```

### 옵션 3: 통합 실행 (추천)

백엔드 + 봇 + 스케줄러를 함께 실행:

```bash
./run.sh
```

## 텔레그램 봇 사용법

### 명령어
- `/start` - 봇 시작 및 메인 키보드 표시
- `/today` - 오늘의 요약 (시세 + Top 5 뉴스)
- `/btc` - 비트코인 시세 (1H/4H/1D 선택 가능)
- `/crypto BTC` - 특정 코인 시세 (BTC, ETH, SOL, XRP, TRX)
- `/fx` - 주요 환율 확인 (USD, EUR, JPY, CNY 등)

### 메인 키보드 버튼
- 🪙 BTC / ETH / SOL / XRP / TRX - 각 코인 시세
- 📈 오늘 요약 - 전체 요약 보기
- 💵 환율 - 환율 정보

## API 엔드포인트

- `GET /api/health` - 헬스체크
- `GET /api/today/summary` - 오늘의 요약 (시장 데이터 + Top 뉴스)
- `GET /api/news` - 뉴스 목록 (날짜, 카테고리 필터 가능)
- `GET /api/markets` - 시장 데이터 목록 (기간 조회 가능)
- `POST /api/dev/collect-markets-today` - 수동 시세 수집 (개발/테스트용)

Swagger 문서: http://localhost:8000/docs

## 프로젝트 구조

```
morning-bot/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI 엔트리포인트
│       ├── config.py            # 환경변수 설정
│       ├── db/
│       │   ├── models.py        # DB 모델
│       │   └── session.py       # DB 세션
│       ├── collectors/
│       │   ├── news_collector.py
│       │   └── market_collector.py
│       ├── ai/
│       │   └── summarizer.py    # AI 요약 생성
│       ├── services/
│       │   └── summary_service.py
│       ├── scheduler/
│       │   └── jobs.py          # 스케줄링 작업
│       └── telegram_bot/
│           └── bot.py           # 텔레그램 봇
├── requirements.txt
├── .env.example
├── run.sh                       # 통합 실행 스크립트
└── README.md
```

## 수동 데이터 수집

스케줄러를 기다리지 않고 즉시 데이터를 수집하려면:

```bash
python collect_now.py
```

또는 API를 통해:
```bash
curl -X POST http://localhost:8000/api/dev/collect-markets-today
```

## 문제 해결

### API 키 에러
- `.env` 파일에 올바른 API 키가 입력되었는지 확인
- 무료 API는 호출 제한이 있으므로 주의

### 데이터베이스 에러
- `morning_bot.db` 파일 삭제 후 재실행

### 봇 응답 없음
- `TELEGRAM_TOKEN`이 올바른지 확인
- BotFather에서 봇이 활성화되어 있는지 확인

## 라이선스

MIT License

## 개발자

CTO & COO - Morning Bot Team
