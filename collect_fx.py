#!/usr/bin/env python3
"""환율 데이터 수집 스크립트 - 전일대비 표시를 위한 데이터 생성"""

import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import httpx
from datetime import date

from backend.app.config import settings
from backend.app.db.session import SessionLocal
from backend.app.db.models import MarketDaily


async def collect_exchange_rate():
    """현재 환율 데이터 수집"""
    
    if not settings.UNIRATE_API_KEY:
        print("❌ UNIRATE_API_KEY가 설정되지 않았습니다.")
        return None
    
    url = "https://api.unirateapi.com/api/rates"
    params = {
        "api_key": settings.UNIRATE_API_KEY,
        "from": "USD"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
        rates = data.get("rates") or data.get("data") or {}
        usd_krw = rates.get("KRW")
        
        if not usd_krw:
            print("❌ 환율 데이터를 가져오지 못했습니다.")
            return None
        
        print(f"✅ 환율 데이터 수집 성공: $1 = ₩{usd_krw:,.2f}")
        return usd_krw
        
    except Exception as e:
        print(f"❌ API 호출 실패: {e}")
        return None


async def main():
    """메인 함수"""
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("📊 환율 데이터 수집 시작")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("")
    
    # 환율 수집
    usd_krw = await collect_exchange_rate()
    
    if not usd_krw:
        print("")
        print("❌ 환율 수집 실패")
        return
    
    # DB에 저장
    db = SessionLocal()
    
    try:
        today = date.today()
        
        # 오늘자 데이터가 이미 있는지 확인
        existing = db.query(MarketDaily).filter(
            MarketDaily.date == today
        ).first()
        
        if existing:
            # 업데이트
            existing.usd_krw = usd_krw
            db.commit()
            print(f"✅ 오늘({today}) 환율 데이터 업데이트")
        else:
            # 신규 생성
            market = MarketDaily(
                date=today,
                usd_krw=usd_krw
            )
            db.add(market)
            db.commit()
            print(f"✅ 오늘({today}) 환율 데이터 저장")
        
        print("")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✨ 완료!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("")
        print("💡 내일부터 전일대비가 표시됩니다!")
        print("")
        
    except Exception as e:
        print(f"❌ DB 저장 실패: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
