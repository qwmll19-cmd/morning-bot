#!/usr/bin/env python3
"""
전체 API 연동 테스트 스크립트
모든 데이터 수집 API를 실제로 호출하여 오류 검증
"""

import sys
import os

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
import httpx
from datetime import datetime

load_dotenv()

UNIRATE_API_KEY = os.getenv("UNIRATE_API_KEY")
METALSDEV_API_KEY = os.getenv("METALSDEV_API_KEY")
METALPRICE_API_KEY = os.getenv("METALPRICE_API_KEY")

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_unirate_fx():
    """UniRate API - 환율 테스트"""
    print_section("1. UniRate API - USD/KRW 환율 테스트")

    if not UNIRATE_API_KEY:
        print("❌ UNIRATE_API_KEY가 설정되지 않았습니다!")
        return False

    try:
        url = "https://api.unirateapi.com/api/rates"
        params = {
            "api_key": UNIRATE_API_KEY,
            "from": "USD"
        }

        print(f"🔗 요청 URL: {url}")
        print(f"📦 파라미터: {params}")

        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
            print(f"📊 응답 상태: {resp.status_code}")

            resp.raise_for_status()
            data = resp.json()

            print(f"✅ 응답 성공!")
            print(f"📄 응답 데이터 샘플: {str(data)[:300]}")

            # KRW 환율 추출
            rates = data.get("rates") or data.get("data") or {}
            krw = rates.get("KRW")

            if krw:
                print(f"💵 USD/KRW: {krw:,.2f}원")
                return True
            else:
                print(f"❌ KRW 환율을 찾을 수 없습니다. 응답 구조: {data.keys()}")
                return False

    except Exception as e:
        print(f"❌ 오류 발생: {type(e).__name__}: {e}")
        return False

def test_coinpaprika():
    """CoinPaprika API - 암호화폐 테스트"""
    print_section("2. CoinPaprika API - BTC 시세 테스트")

    try:
        url = "https://api.coinpaprika.com/v1/tickers/btc-bitcoin"

        print(f"🔗 요청 URL: {url}")

        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            print(f"📊 응답 상태: {resp.status_code}")

            resp.raise_for_status()
            data = resp.json()

            print(f"✅ 응답 성공!")

            quotes = data.get("quotes", {})
            usd_quote = quotes.get("USD") or {}

            btc_usd = usd_quote.get("price")
            btc_change = usd_quote.get("percent_change_24h")

            if btc_usd:
                print(f"₿ BTC/USD: ${btc_usd:,.2f}")
                print(f"📈 24h 변동: {btc_change:+.2f}%")
                return True
            else:
                print(f"❌ BTC 가격을 찾을 수 없습니다. 응답 구조: {data.keys()}")
                return False

    except Exception as e:
        print(f"❌ 오류 발생: {type(e).__name__}: {e}")
        return False

def test_metalsdev():
    """Metals.Dev API - 금속 시세 테스트"""
    print_section("3. Metals.Dev API - 전체 금속 시세 테스트")

    if not METALSDEV_API_KEY:
        print("❌ METALSDEV_API_KEY가 설정되지 않았습니다!")
        return False

    try:
        url = f"https://api.metals.dev/v1/latest?api_key={METALSDEV_API_KEY}&currency=USD&unit=toz"

        print(f"🔗 요청 URL: {url[:80]}...")

        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            print(f"📊 응답 상태: {resp.status_code}")

            resp.raise_for_status()
            data = resp.json()

            print(f"✅ 응답 성공!")
            print(f"📄 응답 상태: {data.get('status')}")

            if data.get('status') != 'success':
                print(f"❌ API 응답 상태가 'success'가 아닙니다: {data}")
                return False

            metals = data.get('metals', {})

            if metals:
                print(f"🥇 금 (Gold): ${metals.get('gold', 'N/A')}/toz")
                print(f"🥈 은 (Silver): ${metals.get('silver', 'N/A')}/toz")
                print(f"⚪ 백금 (Platinum): ${metals.get('platinum', 'N/A')}/toz")
                print(f"🟠 구리 (Copper): ${metals.get('copper', 'N/A')}/toz")
                print(f"⚪ 팔라듐 (Palladium): ${metals.get('palladium', 'N/A')}/toz")
                print(f"⚪ 알루미늄 (Aluminum): ${metals.get('aluminum', 'N/A')}/toz")
                print(f"⚪ 니켈 (Nickel): ${metals.get('nickel', 'N/A')}/toz")
                print(f"⚪ 아연 (Zinc): ${metals.get('zinc', 'N/A')}/toz")
                print(f"⚪ 납 (Lead): ${metals.get('lead', 'N/A')}/toz")
                return True
            else:
                print(f"❌ 금속 데이터를 찾을 수 없습니다. 응답: {data}")
                return False

    except Exception as e:
        print(f"❌ 오류 발생: {type(e).__name__}: {e}")
        return False

def test_kospi_scraping():
    """네이버 KOSPI 지수 크롤링 테스트"""
    print_section("4. 네이버 KOSPI 지수 크롤링 테스트")

    try:
        from bs4 import BeautifulSoup

        url = "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"

        print(f"🔗 요청 URL: {url}")

        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            print(f"📊 응답 상태: {resp.status_code}")

            resp.raise_for_status()
            html = resp.text

            soup = BeautifulSoup(html, "html.parser")

            now_val = soup.select_one("#now_value")
            if not now_val:
                print(f"❌ KOSPI 지수를 찾을 수 없습니다. (셀렉터: #now_value)")
                return False

            current = float(now_val.get_text(strip=True).replace(",", ""))

            change_val = soup.select_one("#change_value_and_rate span.num")
            change = 0.0
            if change_val:
                change_text = change_val.get_text(strip=True).replace(",", "")
                change = float(change_text)

            print(f"✅ 크롤링 성공!")
            print(f"📊 KOSPI 지수: {current:,.2f}")
            print(f"📈 등락: {change:+.2f}")
            return True

    except Exception as e:
        print(f"❌ 오류 발생: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_nasdaq_scraping():
    """네이버 나스닥 100 크롤링 테스트"""
    print_section("5. 네이버 나스닥 100 크롤링 테스트")

    try:
        from bs4 import BeautifulSoup

        url = "https://finance.naver.com/world/sise.naver?symbol=NAS@NDX"

        print(f"🔗 요청 URL: {url}")

        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            print(f"📊 응답 상태: {resp.status_code}")

            resp.raise_for_status()
            html = resp.text

            soup = BeautifulSoup(html, "html.parser")

            em_tags = soup.select("em.no_down, em.no_up")
            if len(em_tags) < 2:
                print(f"❌ 나스닥 지수를 찾을 수 없습니다. (찾은 em 태그: {len(em_tags)}개)")
                return False

            current = float(em_tags[0].get_text().strip().replace(",", ""))
            change = float(em_tags[1].get_text().strip().replace(",", ""))

            print(f"✅ 크롤링 성공!")
            print(f"📊 나스닥 100: {current:,.2f}")
            print(f"📈 등락: {change:+.2f}")
            return True

    except Exception as e:
        print(f"❌ 오류 발생: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_kospi_top5_scraping():
    """네이버 KOSPI TOP5 크롤링 테스트"""
    print_section("6. 네이버 KOSPI TOP5 크롤링 테스트")

    try:
        from bs4 import BeautifulSoup

        url = "https://finance.naver.com/sise/sise_market_sum.nhn?sosok=0&page=1"

        print(f"🔗 요청 URL: {url}")

        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            print(f"📊 응답 상태: {resp.status_code}")

            resp.raise_for_status()
            html = resp.text

            soup = BeautifulSoup(html, "html.parser")
            rows = soup.select("table.type_2 tr")

            top5 = []
            for row in rows:
                cols = row.select("td")
                if len(cols) < 10:
                    continue

                name = cols[1].get_text(strip=True)
                price = cols[2].get_text(strip=True)
                change = cols[3].get_text(strip=True)
                change_rate = cols[9].get_text(strip=True)

                if not name:
                    continue

                top5.append({
                    "name": name,
                    "price": price,
                    "change": change,
                    "change_rate": change_rate
                })

                if len(top5) >= 5:
                    break

            if len(top5) >= 5:
                print(f"✅ 크롤링 성공! TOP5 종목:")
                for i, stock in enumerate(top5, 1):
                    print(f"  {i}. {stock['name']}: {stock['price']}원 ({stock['change_rate']})")
                return True
            else:
                print(f"❌ TOP5를 모두 찾지 못했습니다. (찾은 개수: {len(top5)}개)")
                return False

    except Exception as e:
        print(f"❌ 오류 발생: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "Morning-Bot API 연동 전체 테스트" + " "*24 + "║")
    print("║" + " "*78 + "║")
    print("║" + f"  실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " "*48 + "║")
    print("╚" + "="*78 + "╝")

    results = {}

    # 각 API 테스트 실행
    results["UniRate (환율)"] = test_unirate_fx()
    results["CoinPaprika (암호화폐)"] = test_coinpaprika()
    results["Metals.Dev (금속)"] = test_metalsdev()
    results["KOSPI 지수"] = test_kospi_scraping()
    results["나스닥 100"] = test_nasdaq_scraping()
    results["KOSPI TOP5"] = test_kospi_top5_scraping()

    # 결과 요약
    print_section("테스트 결과 요약")

    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    for name, success in results.items():
        status = "✅ 성공" if success else "❌ 실패"
        print(f"  {name:30} {status}")

    print()
    print(f"총 {total_count}개 테스트 중 {success_count}개 성공, {total_count - success_count}개 실패")

    if success_count == total_count:
        print("\n🎉 모든 API 연동이 정상 작동합니다!")
        return 0
    else:
        print(f"\n⚠️  {total_count - success_count}개의 API에서 문제가 발견되었습니다. 위의 오류 메시지를 확인하세요.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
