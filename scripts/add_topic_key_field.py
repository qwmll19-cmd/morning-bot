#!/usr/bin/env python3
"""
DB 마이그레이션 스크립트: NewsDaily 테이블에 topic_key 필드 추가

실행 방법:
    python scripts/add_topic_key_field.py
"""

from backend.app.db.session import engine
from sqlalchemy import text

def add_topic_key_field():
    """NewsDaily 테이블에 topic_key 컬럼 추가"""
    
    print("🔧 DB 마이그레이션 시작...")
    
    with engine.connect() as conn:
        try:
            # topic_key 컬럼 추가
            print("  → topic_key 컬럼 추가 중...")
            conn.execute(text("ALTER TABLE news_daily ADD COLUMN topic_key VARCHAR(100)"))
            conn.commit()
            print("  ✅ topic_key 컬럼 추가 완료")
            
            # 인덱스 추가 (성능 향상)
            print("  → 인덱스 생성 중...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_news_daily_topic_key ON news_daily(topic_key)"))
            conn.commit()
            print("  ✅ 인덱스 생성 완료")
            
            print("\n✅ DB 마이그레이션 성공!")
            
        except Exception as e:
            print(f"\n❌ DB 마이그레이션 실패: {e}")
            print("   (이미 topic_key 필드가 존재하는 경우 이 에러가 발생할 수 있습니다)")
            raise

if __name__ == "__main__":
    add_topic_key_field()
