"""yfinance로 나스닥 지수, TOP5, 구리 선물 수집"""

import yfinance as yf
from typing import Tuple, List, Dict, Any, Optional


def fetch_nasdaq_and_copper() -> Tuple[Optional[float], Optional[List[Dict[str, Any]]], Optional[float]]:
    """
    Yahoo Finance에서 나스닥 + 구리 데이터 수집
    
    Returns:
        nasdaq_index: 나스닥 지수 (^IXIC)
        nasdaq_top5: 나스닥 TOP5 종목 리스트
        copper_usd: 구리 선물 가격 ($/lb)
    """
    
    nasdaq_index = None
    nasdaq_top5 = None
    copper_usd = None
    
    try:
        # 1. 나스닥 지수
        print("  📊 나스닥 지수 수집 중...")
        nasdaq = yf.Ticker("^IXIC")
        nasdaq_hist = nasdaq.history(period="1d")
        
        if not nasdaq_hist.empty:
            nasdaq_index = float(nasdaq_hist["Close"].iloc[-1])
            print(f"    ✅ 나스닥 지수: {nasdaq_index:,.2f}")
        
    except Exception as e:
        print(f"    ❌ 나스닥 지수 오류: {e}")
    
    try:
        # 2. 나스닥 TOP5 (시가총액 상위)
        print("  📈 나스닥 TOP5 수집 중...")
        top5_tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "META"]
        
        nasdaq_top5 = []
        
        for ticker in top5_tickers:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="2d")  # 2일 (전일 대비 계산용)
                info = stock.info
                
                if len(hist) >= 2:
                    current_price = float(hist["Close"].iloc[-1])
                    prev_price = float(hist["Close"].iloc[-2])
                    change = current_price - prev_price
                    change_rate = (change / prev_price) * 100
                    
                    nasdaq_top5.append({
                        "ticker": ticker,
                        "name": info.get("shortName", ticker),
                        "price": f"${current_price:.2f}",
                        "change": f"${change:+.2f}",
                        "change_rate": f"{change_rate:+.2f}%"
                    })
                    
                    print(f"    ✅ {ticker}: ${current_price:.2f} ({change_rate:+.2f}%)")
                    
            except Exception as e:
                print(f"    ⚠️ {ticker} 오류: {e}")
                continue
        
        if not nasdaq_top5:
            nasdaq_top5 = None
            
    except Exception as e:
        print(f"    ❌ 나스닥 TOP5 오류: {e}")
    
    try:
        # 3. 구리 선물 (COMEX)
        print("  🔶 구리 선물 수집 중...")
        copper = yf.Ticker("HG=F")
        copper_hist = copper.history(period="1d")
        
        if not copper_hist.empty:
            # $/lb (파운드당 달러)
            copper_usd = float(copper_hist["Close"].iloc[-1])
            print(f"    ✅ 구리 선물: ${copper_usd:.4f}/lb")
        
    except Exception as e:
        print(f"    ❌ 구리 선물 오류: {e}")
    
    return nasdaq_index, nasdaq_top5, copper_usd


if __name__ == "__main__":
    print("🚀 Yahoo Finance 데이터 수집 테스트\n")
    print("=" * 60)
    
    nasdaq_idx, nasdaq_t5, copper = fetch_nasdaq_and_copper()
    
    print("\n" + "=" * 60)
    print("📊 수집 결과:")
    print(f"  나스닥 지수: {nasdaq_idx}")
    print(f"  나스닥 TOP5: {len(nasdaq_t5) if nasdaq_t5 else 0}개")
    print(f"  구리 가격: ${copper}/lb" if copper else "  구리 가격: None")
    print("=" * 60)
