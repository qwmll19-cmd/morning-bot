#!/usr/bin/env python3
"""
로컬 SQLite 로또 데이터를 Render PostgreSQL로 마이그레이션

사용법:
    python scripts/migrate_lotto_to_render.py

환경변수 필요:
    - RENDER_APP_URL: Render 앱 URL (예: https://morning-bot-xxxx.onrender.com)
    - CRON_SECRET: API 인증 시크릿
"""
import os
import sys
import json
import requests
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()


def get_local_lotto_data():
    """로컬 SQLite에서 로또 데이터 추출"""
    from backend.app.db.session import SessionLocal
    from backend.app.db.models import LottoDraw

    db = SessionLocal()
    try:
        draws = db.query(LottoDraw).order_by(LottoDraw.draw_no).all()
        data = [
            {
                "draw_no": d.draw_no,
                "draw_date": d.draw_date,
                "n1": d.n1, "n2": d.n2, "n3": d.n3,
                "n4": d.n4, "n5": d.n5, "n6": d.n6,
                "bonus": d.bonus
            }
            for d in draws
        ]
        return data
    finally:
        db.close()


def migrate_to_render(render_url: str, cron_secret: str, draws: list):
    """Render PostgreSQL로 데이터 전송"""
    url = f"{render_url.rstrip('/')}/api/admin/lotto-import"
    headers = {
        "Content-Type": "application/json",
        "X-Cron-Secret": cron_secret
    }
    payload = {"draws": draws}

    print(f"전송 중... ({len(draws)}개 회차)")
    print(f"URL: {url}")

    response = requests.post(url, json=payload, headers=headers, timeout=300)

    if response.status_code == 200:
        result = response.json()
        print(f"✅ 마이그레이션 완료!")
        print(f"   - imported: {result.get('imported', 0)}")
        print(f"   - skipped: {result.get('skipped', 0)}")
        print(f"   - total_in_db: {result.get('total_in_db', 0)}")
        print(f"   - ml_trained: {result.get('ml_trained', False)}")
        if result.get('ml_accuracy'):
            print(f"   - ml_accuracy: {result['ml_accuracy']:.4f}")
        return result
    else:
        print(f"❌ 전송 실패: {response.status_code}")
        print(response.text)
        return None


def check_render_status(render_url: str):
    """Render DB 상태 확인"""
    url = f"{render_url.rstrip('/')}/api/admin/lotto-status"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            result = response.json()
            print(f"📊 Render DB 상태:")
            print(f"   - total_draws: {result.get('total_draws', 0)}")
            print(f"   - latest_draw_no: {result.get('latest_draw_no')}")
            print(f"   - stats_cache_exists: {result.get('stats_cache_exists', False)}")
            return result
        else:
            print(f"❌ 상태 확인 실패: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return None


def main():
    # 환경변수 확인
    render_url = os.getenv("RENDER_APP_URL")
    cron_secret = os.getenv("CRON_SECRET")

    if not render_url:
        print("❌ RENDER_APP_URL 환경변수가 필요합니다.")
        print("   예: export RENDER_APP_URL=https://morning-bot-xxxx.onrender.com")
        render_url = input("Render URL 입력: ").strip()
        if not render_url:
            sys.exit(1)

    if not cron_secret:
        print("❌ CRON_SECRET 환경변수가 필요합니다.")
        cron_secret = input("CRON_SECRET 입력: ").strip()
        if not cron_secret:
            sys.exit(1)

    print("=" * 50)
    print("로또 데이터 마이그레이션 (로컬 → Render)")
    print("=" * 50)

    # 1. Render 상태 확인
    print("\n[1/3] Render DB 상태 확인...")
    status = check_render_status(render_url)

    # 2. 로컬 데이터 추출
    print("\n[2/3] 로컬 SQLite에서 데이터 추출...")
    draws = get_local_lotto_data()
    print(f"   로컬 데이터: {len(draws)}개 회차")

    if not draws:
        print("❌ 로컬에 로또 데이터가 없습니다.")
        sys.exit(1)

    # 이미 Render에 데이터가 있는 경우
    if status and status.get('total_draws', 0) >= len(draws):
        print(f"✅ Render에 이미 {status['total_draws']}개 데이터 존재. 마이그레이션 불필요.")
        sys.exit(0)

    # 3. Render로 전송
    print("\n[3/3] Render PostgreSQL로 마이그레이션...")
    result = migrate_to_render(render_url, cron_secret, draws)

    if result and result.get('status') == 'success':
        print("\n" + "=" * 50)
        print("✅ 마이그레이션 성공! 파이프라인 준비 완료.")
        print("=" * 50)
    else:
        print("\n❌ 마이그레이션 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
