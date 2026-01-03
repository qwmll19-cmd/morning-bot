# DB에 nasdaq_index 컬럼 추가
from backend.app.db.session import SessionLocal, engine
from sqlalchemy import text

db = SessionLocal()

try:
    # nasdaq_index 컬럼 추가
    db.execute(text("ALTER TABLE market_daily ADD COLUMN nasdaq_index REAL"))
    db.commit()
    print("✅ nasdaq_index 컬럼 추가 완료")
except Exception as e:
    print(f"⚠️ 컬럼 추가 실패 (이미 있을 수 있음): {e}")
finally:
    db.close()
