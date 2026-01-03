#!/usr/bin/env python3
"""
기존 뉴스 데이터에 topic_key 생성

실행 방법:
    python scripts/migrate_topic_keys.py
"""

from backend.app.db.session import SessionLocal
from backend.app.db.models import NewsDaily
from backend.app.collectors.news_collector import build_topic_key

def migrate_existing_news():
    """기존 뉴스 데이터에 topic_key 생성"""
    
    print("🔧 기존 뉴스 데이터 마이그레이션 시작...")
    
    db = SessionLocal()
    
    try:
        # topic_key가 없는 뉴스 조회
        news_items = db.query(NewsDaily).filter(NewsDaily.topic_key.is_(None)).all()
        total = len(news_items)
        
        if total == 0:
            print("  ℹ️  마이그레이션할 뉴스가 없습니다.")
            return
        
        print(f"  → {total}개의 뉴스 항목 처리 중...")
        
        # topic_key 생성
        for idx, news in enumerate(news_items, 1):
            news.topic_key = build_topic_key(news.title)
            
            if idx % 100 == 0:
                print(f"    진행 중: {idx}/{total}")
        
        # DB 저장
        db.commit()
        print(f"\n✅ {total}개 뉴스 topic_key 생성 완료!")
        
        # 검증
        remaining = db.query(NewsDaily).filter(NewsDaily.topic_key.is_(None)).count()
        if remaining == 0:
            print("✅ 검증 완료: 모든 뉴스에 topic_key가 생성되었습니다.")
        else:
            print(f"⚠️  경고: {remaining}개의 뉴스에 topic_key가 없습니다.")
    
    except Exception as e:
        db.rollback()
        print(f"\n❌ 마이그레이션 실패: {e}")
        raise
    
    finally:
        db.close()

if __name__ == "__main__":
    migrate_existing_news()
