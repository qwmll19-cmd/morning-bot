#!/usr/bin/env python3
"""
API 테스트 스크립트
각 API가 제대로 응답하는지 확인
"""

import os
import sys
import httpx
from dotenv import load_dotenv

# .env 로드
load_dotenv()

UNIRATE_API_KEY = os.getenv("UNIRATE_API_KEY")
METALPRICE_API_KEY = os.getenv("METALPRICE_API_KEY")

print("=" * 60)
print("🔍 API 테스트 시작")
print("=" * 60)
print()

# 1. UniRate API 테스트 (환율)
print("1️⃣ UniRate API (환율)")
print(f"   API Key: {UNIRATE_API_KEY[:10]}..." if UNIRATE_API_KEY else "   API Key: ❌ 없음")

if UNIRATE_API_KEY:
    try:
        url = "https://api.unirateapi.com/api/rates"
        params = {"api_key": UNIRATE_API_KEY, "from": "USD"}
        
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
            print(f"   Status Code: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get("rates") or data.get("data") or {}
                krw = rates.get("KRW")
                
                if krw:
                    print(f"   ✅ USD/KRW: {krw:,.2f}")
                else:
                    print(f"   ❌ KRW 없음")
                    print(f"   응답: {data}")
            else:
                print(f"   ❌ 실패: {resp.text[:200]}")
    except Exception as e:
        print(f"   ❌ 에러: {e}")
else:
    print("   ⚠️ 스킵 (API 키 없음)")

print()

# 2. CoinPaprika API 테스트 (BTC)
print("2️⃣ CoinPaprika API (BTC)")
print("   API Key: 불필요 (무료)")

try:
    # 문서에 따른 올바른 방법
    url = "https://api.coinpaprika.com/v1/tickers/btc-bitcoin"
    
    with httpx.Client(timeout=10) as client:
        print(f"   요청 URL: {url}")
        resp = client.get(url)
        print(f"   Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            quotes = data.get("quotes", {})
            
            usd_quote = quotes.get("USD") or {}
            
            btc_usd = usd_quote.get("price")
            btc_change_24h = usd_quote.get("percent_change_24h")
            
            if btc_usd:
                print(f"   ✅ BTC-USD: ${btc_usd:,.2f}")
                print(f"   ✅ 24h 변동: {btc_change_24h:+.2f}%")
            else:
                print(f"   ❌ USD 데이터 없음")
                print(f"   응답 구조: {list(data.keys())}")
        else:
            print(f"   ❌ 실패: {resp.text[:200]}")
except Exception as e:
    print(f"   ❌ 에러: {e}")

print()

# 3. MetalPrice API 테스트 (금/은/구리)
print("3️⃣ MetalPrice API (금/은/구리)")
print(f"   API Key: {METALPRICE_API_KEY[:10]}..." if METALPRICE_API_KEY else "   API Key: ❌ 없음")

if METALPRICE_API_KEY:
    try:
        url = "https://api.metalpriceapi.com/v1/latest"
        params = {
            "api_key": METALPRICE_API_KEY,
            "base": "USD",
            "currencies": "XAU,XAG,XCU"
        }
        
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
            print(f"   Status Code: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get("rates", {})
                
                xau = rates.get("XAU")  # 금
                xag = rates.get("XAG")  # 은
                xcu = rates.get("XCU")  # 구리
                
                if xau:
                    gold_usd = 1.0 / xau if xau else None
                    if gold_usd:
                        print(f"   ✅ Gold: ${gold_usd:,.2f}/oz")
                
                if xag:
                    silver_usd = 1.0 / xag if xag else None
                    if silver_usd:
                        print(f"   ✅ Silver: ${silver_usd:,.2f}/oz")
                
                if xcu:
                    copper_usd = 1.0 / xcu if xcu else None
                    if copper_usd:
                        print(f"   ✅ Copper: ${copper_usd:,.2f}")
                
                if not any([xau, xag, xcu]):
                    print(f"   ❌ 데이터 없음")
                    print(f"   응답: {data}")
            else:
                print(f"   ❌ 실패: {resp.text[:200]}")
    except Exception as e:
        print(f"   ❌ 에러: {e}")
else:
    print("   ⚠️ 스킵 (API 키 없음)")

print()
print("=" * 60)
print("✅ 테스트 완료")
print("=" * 60)
