#!/usr/bin/env python3
"""
DB 업데이트 스크립트
1. Subscriber 테이블에 custom_time 컬럼 추가
2. NewsDaily 테이블에 alert_sent 컬럼 추가 (속보 중복 방지!)
"""

import os
import sys

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app.db.session import engine
from backend.app.db.models import Base
from sqlalchemy import text

def update_database():
    print("🔧 DB 업데이트 시작...")
    
    try:
        with engine.connect() as conn:
            # 1. Subscriber 테이블에 custom_time 추가
            result = conn.execute(text("PRAGMA table_info(subscriber)"))
            columns = [row[1] for row in result]
            
            if 'custom_time' in columns:
                print("✅ Subscriber.custom_time 이미 존재")
            else:
                print("➕ Subscriber.custom_time 추가 중...")
                conn.execute(text("ALTER TABLE subscriber ADD COLUMN custom_time VARCHAR(10) DEFAULT '08:30'"))
                conn.commit()
                print("✅ Subscriber.custom_time 추가 완료!")
            
            # 2. NewsDaily 테이블에 alert_sent 추가
            result = conn.execute(text("PRAGMA table_info(news_daily)"))
            columns = [row[1] for row in result]
            
            if 'alert_sent' in columns:
                print("✅ NewsDaily.alert_sent 이미 존재")
            else:
                print("➕ NewsDaily.alert_sent 추가 중...")
                conn.execute(text("ALTER TABLE news_daily ADD COLUMN alert_sent BOOLEAN DEFAULT 0"))
                conn.commit()
                print("✅ NewsDaily.alert_sent 추가 완료!")
                
                # 기존 속보는 모두 알림 보낸 것으로 처리 (중복 방지)
                print("📝 기존 속보에 alert_sent=True 설정 중...")
                conn.execute(text("UPDATE news_daily SET alert_sent = 1 WHERE is_breaking = 1"))
                conn.commit()
                print("✅ 기존 속보 처리 완료!")
        
        print("\n✅ DB 업데이트 완료!")
        print("\n🎯 중복 방지 기능 활성화:")
        print("  - 속보는 1번만 알림")
        print("  - 시간 설정 버튼 작동")
        
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        print("\n대안: DB를 삭제하고 새로 만들기")
        print("실행: rm morning_bot.db && python3 init_db.py")

if __name__ == "__main__":
    update_database()
