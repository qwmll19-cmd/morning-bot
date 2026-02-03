#!/usr/bin/env python3
"""
SQLite → PostgreSQL 마이그레이션 스크립트

사용법:
  1. Render PostgreSQL 생성 후 연결 문자열 획득
  2. 환경변수 설정:
     export POSTGRES_URL="postgresql://user:pass@host:5432/dbname"
  3. 실행:
     python scripts/migrate_sqlite_to_postgres.py
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 소스 (SQLite)
SQLITE_PATH = Path(__file__).parent.parent / "morning_bot.db"

# 대상 (PostgreSQL)
POSTGRES_URL = os.getenv("POSTGRES_URL")

if not POSTGRES_URL:
    print("❌ POSTGRES_URL 환경변수를 설정해주세요")
    print("   export POSTGRES_URL='postgresql://user:pass@host:5432/dbname'")
    sys.exit(1)

if not SQLITE_PATH.exists():
    print(f"❌ SQLite DB를 찾을 수 없습니다: {SQLITE_PATH}")
    sys.exit(1)


def get_sqlite_tables(conn):
    """SQLite에서 테이블 목록 조회"""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return [row[0] for row in cursor.fetchall()]


def get_table_schema(conn, table_name):
    """테이블 컬럼 정보 조회"""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def get_table_data(conn, table_name):
    """테이블 데이터 조회"""
    cursor = conn.execute(f"SELECT * FROM {table_name}")
    return cursor.fetchall()


def sqlite_type_to_postgres(sqlite_type):
    """SQLite 타입을 PostgreSQL 타입으로 변환"""
    sqlite_type = sqlite_type.upper()
    mapping = {
        "INTEGER": "INTEGER",
        "TEXT": "TEXT",
        "REAL": "DOUBLE PRECISION",
        "BLOB": "BYTEA",
        "BOOLEAN": "BOOLEAN",
        "DATETIME": "TIMESTAMP",
        "DATE": "DATE",
        "FLOAT": "DOUBLE PRECISION",
        "VARCHAR": "VARCHAR",
        "JSON": "JSONB",
    }
    for sqlite_t, pg_t in mapping.items():
        if sqlite_t in sqlite_type:
            return pg_t
    return "TEXT"


def migrate():
    print("🚀 SQLite → PostgreSQL 마이그레이션 시작")
    print(f"   소스: {SQLITE_PATH}")
    print(f"   대상: {POSTGRES_URL[:50]}...")
    print()

    # SQLite 연결
    sqlite_conn = sqlite3.connect(SQLITE_PATH)

    # PostgreSQL 연결
    pg_engine = create_engine(POSTGRES_URL)
    PgSession = sessionmaker(bind=pg_engine)
    pg_session = PgSession()

    try:
        tables = get_sqlite_tables(sqlite_conn)
        print(f"📋 마이그레이션할 테이블: {tables}")
        print()

        for table_name in tables:
            print(f"── {table_name} ──")

            # 스키마 조회
            schema = get_table_schema(sqlite_conn, table_name)
            columns = []
            for col in schema:
                col_id, col_name, col_type, not_null, default_val, is_pk = col
                pg_type = sqlite_type_to_postgres(col_type)

                col_def = f'"{col_name}" {pg_type}'
                if is_pk:
                    col_def += " PRIMARY KEY"
                if not_null and not is_pk:
                    col_def += " NOT NULL"
                columns.append(col_def)

            # 기존 테이블 삭제 및 생성
            drop_sql = f'DROP TABLE IF EXISTS "{table_name}" CASCADE'
            create_sql = f'CREATE TABLE "{table_name}" ({", ".join(columns)})'

            pg_session.execute(text(drop_sql))
            pg_session.execute(text(create_sql))
            pg_session.commit()
            print(f"   ✅ 테이블 생성 완료")

            # 데이터 마이그레이션
            data = get_table_data(sqlite_conn, table_name)
            if not data:
                print(f"   ⚠️ 데이터 없음")
                continue

            col_names = [col[1] for col in schema]
            placeholders = ", ".join([f":{c}" for c in col_names])
            quoted_cols = ", ".join([f'"{c}"' for c in col_names])
            insert_sql = f'INSERT INTO "{table_name}" ({quoted_cols}) VALUES ({placeholders})'

            # 배치 삽입
            batch_size = 500
            total = len(data)
            for i in range(0, total, batch_size):
                batch = data[i:i + batch_size]
                for row in batch:
                    row_dict = dict(zip(col_names, row))
                    pg_session.execute(text(insert_sql), row_dict)
                pg_session.commit()
                print(f"   📦 {min(i + batch_size, total)}/{total} 행 삽입")

            print(f"   ✅ 데이터 마이그레이션 완료 ({total}행)")
            print()

        print("🎉 마이그레이션 완료!")

    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        pg_session.rollback()
        raise
    finally:
        sqlite_conn.close()
        pg_session.close()


if __name__ == "__main__":
    migrate()
