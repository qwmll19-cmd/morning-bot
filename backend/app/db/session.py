from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool, NullPool
from backend.app.config import settings

# PostgreSQL인 경우 connection pooling 설정
db_url = settings.DB_URL
is_postgres = db_url.startswith("postgresql")

if is_postgres:
    engine = create_engine(
        db_url,
        future=True,
        echo=False,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # 연결 유효성 검사
    )
else:
    # SQLite (로컬 개발용)
    engine = create_engine(
        db_url,
        future=True,
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
    )

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
