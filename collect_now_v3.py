"""
Morning Bot v3.0 테스트 스크립트
"""

import sys
sys.path.insert(0, "/Users/seobeo1/Downloads/morning-bot")

from backend.app.db.session import SessionLocal
from backend.app.collectors.news_collector_v3 import build_daily_top5_v3

def main():
    db = SessionLocal()
    
    try:
        print("\n🚀 Morning Bot v3.0 - 언론사별 수집 + 핫 점수 시스템")
        print("="*60 + "\n")
        
        build_daily_top5_v3(db)
        
        # 결과 확인
        from backend.app.collectors.news_collector_v3 import get_today_summary
        from datetime import date
        
        summary = get_today_summary(db)
        
        print("\n📰 오늘의 요약 (각 카테고리 TOP 1):")
        print("="*60)
        
        category_names = {
            "society": "사회",
            "economy": "경제", 
            "culture": "문화",
            "entertainment": "연예"
        }
        
        for news in summary:
            cat_name = category_names.get(news.category, news.category)
            print(f"\n[{cat_name}] 핫 점수: {news.hot_score}점")
            print(f"{news.title}")
            print(f"🔗 {news.url}")
        
        print("\n" + "="*60)
        print("✅ 완료!\n")
        
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
