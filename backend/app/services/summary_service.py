from datetime import date
from sqlalchemy.orm import Session

from backend.app.collectors.news_collector import build_daily_top5
from backend.app.collectors.market_collector import collect_market_daily
from backend.app.ai.summarizer import generate_market_comment


def collect_and_summarize_daily(db: Session) -> dict:
    """
    매일 아침 실행할 전체 데이터 수집 + 요약 프로세스
    
    1. 뉴스 Top5 생성 (종합/경제)
    2. 시장 데이터 수집
    3. AI 요약 코멘트 생성 (선택)
    4. DB 업데이트
    """
    
    print(f"[{date.today()}] 일일 데이터 수집 시작...")
    
    # 1. 뉴스 Top5 생성
    print("1/3 뉴스 Top5 생성 중...")
    try:
        news_dict = build_daily_top5(db)
        news_count = sum(len(v) for v in news_dict.values())
        print(f"  ✓ 뉴스 {news_count}개 생성 완료")
    except Exception as e:
        print(f"  ✗ 뉴스 수집 실패: {e}")
        news_dict = {}
    
    # 2. 시장 데이터 수집
    print("2/3 시장 데이터 수집 중...")
    try:
        market = collect_market_daily(db)
        print(f"  ✓ 시장 데이터 수집 완료")
        print(f"    - USD/KRW: {market.usd_krw}")
        print(f"    - BTC/USDT: {market.btc_usdt}")
        print(f"    - 금: ${market.gold_usd}")
    except Exception as e:
        print(f"  ✗ 시장 데이터 수집 실패: {e}")
        market = None
    
    # 3. AI 요약 생성 (선택)
    print("3/3 AI 요약 생성 중...")
    if market and news_dict:
        try:
            # 전체 뉴스 리스트로 합치기
            all_news = []
            for news_list in news_dict.values():
                all_news.extend(news_list)
            
            comment = generate_market_comment(market, all_news[:5])
            market.summary_comment = comment
            db.commit()
            db.refresh(market)
            print(f"  ✓ AI 요약 생성 완료")
            print(f"    코멘트: {comment}")
        except Exception as e:
            print(f"  ✗ AI 요약 생성 실패: {e}")
    else:
        print("  ⚠ 데이터 부족으로 AI 요약 생략")
    
    print(f"[{date.today()}] 일일 데이터 수집 완료!\n")
    
    return {
        "success": True,
        "news_count": news_count if news_dict else 0,
        "market_collected": market is not None,
        "summary_generated": market.summary_comment is not None if market else False,
    }
