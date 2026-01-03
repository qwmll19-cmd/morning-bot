#!/usr/bin/env python3
"""
DB 마이그레이션 통합 실행 스크립트

이 스크립트는 다음을 순서대로 실행합니다:
1. topic_key 필드 추가
2. 기존 뉴스 데이터에 topic_key 생성

실행 방법:
    python scripts/migrate_db.py
"""

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.db.session import engine
from backend.app.db.models import NewsDaily
from backend.app.collectors.news_collector import build_topic_key
from sqlalchemy import text

def backup_database():
    """데이터베이스 백업"""
    import shutil
    from datetime import datetime
    
    db_file = "morning_bot.db"
    if os.path.exists(db_file):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"morning_bot.db.backup_{timestamp}"
        shutil.copy2(db_file, backup_file)
        print(f"✅ DB 백업 완료: {backup_file}")
        return True
    else:
        print("ℹ️  DB 파일이 없습니다. 백업 생략.")
        return False

def add_topic_key_field():
    """NewsDaily 테이블에 topic_key 컬럼 추가"""
    print("\n🔧 Step 1: topic_key 필드 추가")
    
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE news_daily ADD COLUMN topic_key VARCHAR(100)"))
            conn.commit()
            print("  ✅ topic_key 컬럼 추가 완료")
            
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_news_daily_topic_key ON news_daily(topic_key)"))
            conn.commit()
            print("  ✅ 인덱스 생성 완료")
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            if "duplicate column name" in error_msg.lower() or "already exists" in error_msg.lower():
                print("  ℹ️  topic_key 필드가 이미 존재합니다. 건너뜀.")
                return True
            else:
                print(f"  ❌ 필드 추가 실패: {e}")
                return False

def migrate_topic_keys():
    """기존 뉴스 데이터에 topic_key 생성"""
    print("\n🔧 Step 2: 기존 뉴스 데이터에 topic_key 생성")
    
    from backend.app.db.session import SessionLocal
    
    db = SessionLocal()
    
    try:
        news_items = db.query(NewsDaily).filter(NewsDaily.topic_key.is_(None)).all()
        total = len(news_items)
        
        if total == 0:
            print("  ℹ️  마이그레이션할 뉴스가 없습니다.")
            return True
        
        print(f"  → {total}개의 뉴스 항목 처리 중...")
        
        for idx, news in enumerate(news_items, 1):
            news.topic_key = build_topic_key(news.title)
            
            if idx % 100 == 0:
                print(f"    진행 중: {idx}/{total}")
        
        db.commit()
        print(f"  ✅ {total}개 뉴스 topic_key 생성 완료")
        
        remaining = db.query(NewsDaily).filter(NewsDaily.topic_key.is_(None)).count()
        if remaining == 0:
            print("  ✅ 검증 완료: 모든 뉴스에 topic_key가 생성되었습니다.")
            return True
        else:
            print(f"  ⚠️  경고: {remaining}개의 뉴스에 topic_key가 없습니다.")
            return False
    
    except Exception as e:
        db.rollback()
        print(f"  ❌ 마이그레이션 실패: {e}")
        return False
    
    finally:
        db.close()

def verify_migration():
    """마이그레이션 검증"""
    print("\n🔍 Step 3: 마이그레이션 검증")
    
    from backend.app.db.session import SessionLocal
    
    db = SessionLocal()
    
    try:
        # topic_key 필드 존재 확인
        total_news = db.query(NewsDaily).count()
        news_with_key = db.query(NewsDaily).filter(NewsDaily.topic_key.isnot(None)).count()
        
        print(f"  → 전체 뉴스: {total_news}개")
        print(f"  → topic_key 있음: {news_with_key}개")
        
        if total_news > 0 and news_with_key == total_news:
            print("  ✅ 모든 뉴스에 topic_key가 있습니다.")
            return True
        elif total_news == 0:
            print("  ℹ️  뉴스 데이터가 없습니다.")
            return True
        else:
            print(f"  ⚠️  {total_news - news_with_key}개의 뉴스에 topic_key가 없습니다.")
            return False
    
    finally:
        db.close()

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("  Morning Bot DB 마이그레이션")
    print("  - NewsDaily 테이블에 topic_key 필드 추가")
    print("=" * 60)
    
    # 백업
    backup_database()
    
    # Step 1: 필드 추가
    if not add_topic_key_field():
        print("\n❌ 마이그레이션 실패: 필드 추가 단계에서 오류 발생")
        sys.exit(1)
    
    # Step 2: 데이터 마이그레이션
    if not migrate_topic_keys():
        print("\n❌ 마이그레이션 실패: 데이터 마이그레이션 단계에서 오류 발생")
        sys.exit(1)
    
    # Step 3: 검증
    if not verify_migration():
        print("\n⚠️  마이그레이션 검증 실패")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("  ✅ DB 마이그레이션 완료!")
    print("=" * 60)

if __name__ == "__main__":
    main()
