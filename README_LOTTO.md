# 🎰 로또봇 기능 추가 패키지

기존 morning-bot 프로젝트에 로또 기능을 추가하는 패키지입니다.

---

## 🚀 설치 방법 (매우 간단)

### 1. morning-bot 프로젝트 루트로 이동
```bash
cd ~/projects/morning-bot
```

### 2. ZIP 파일 압축 해제
```bash
unzip lotto-bot-merge.zip
```

**끝! 파일들이 자동으로 제자리에 들어갑니다.**

---

## 📂 추가되는 파일들

```
morning-bot/                    # 기존 프로젝트
├── backend/
│   ├── app/
│   │   ├── collectors/
│   │   │   ├── news_collector.py    # 기존
│   │   │   └── lotto/               # ✅ 신규 추가
│   │   ├── handlers/
│   │   │   ├── news_handlers.py     # 기존
│   │   │   └── lotto/               # ✅ 신규 추가
│   │   ├── services/lotto/          # ✅ 신규 추가
│   │   └── schedulers/lotto/        # ✅ 신규 추가
│   └── scripts/lotto/               # ✅ 신규 추가
├── db/lotto/                        # ✅ 신규 추가
├── CHECKLIST_COMPLETE.md            # ✅ 전체 가이드
├── BOT_INTEGRATION.md               # ✅ bot.py 수정 방법
└── README_LOTTO.md                  # ✅ 이 파일
```

---

## 📋 다음 단계

### 1. 체크리스트 읽기
```bash
cat CHECKLIST_COMPLETE.md
```

### 2. Phase 0부터 순서대로 진행
- Phase 0: 백업 + 사전 확인
- Phase 1: 패키지 설치
- Phase 2: DB 스키마 생성
- Phase 3: config.py 설정
- Phase 4: 초기 데이터 수집
- Phase 5: 통계 캐시 생성
- Phase 6: bot.py 통합
- Phase 7~9: 테스트 및 완료

---

## ⚠️ 중요 사항

### 1. 반드시 백업 먼저!
```bash
git add .
git commit -m "로또 기능 추가 전 백업"
pg_dump -U your_user -d morning_bot > ~/backups/backup_$(date +%Y%m%d).sql
```

### 2. config.py 수정 필요
```python
DATABASE_URL = "postgresql://your_user:your_password@localhost/morning_bot"
ADMIN_CHAT_ID = 123456789
```

### 3. bot.py 수정 필요
**BOT_INTEGRATION.md** 파일 참고

---

## 🎯 핵심 기능

- 6줄 생성 전략 (최다/최소/랜덤/AI 믹스)
- 매주 토요일 21:00 자동 업데이트
- 추천 이력 저장 (패턴 분석용)

---

## 📚 참고 문서

- **CHECKLIST_COMPLETE.md** - 전체 가이드
- **BOT_INTEGRATION.md** - bot.py 수정 방법

---

**Made with ❤️ by CEO & CTO**
