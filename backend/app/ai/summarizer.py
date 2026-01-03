from typing import List, Optional
from backend.app.config import settings
from backend.app.db.models import NewsDaily, MarketDaily


def generate_market_comment(market: MarketDaily, news_list: List[NewsDaily]) -> str:
    """시장 데이터와 뉴스를 기반으로 한줄 코멘트 생성"""
    
    # Claude API 사용 (우선순위 1)
    if settings.ANTHROPIC_API_KEY:
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            
            # 시장 데이터 요약
            market_summary = f"""
오늘의 시장 데이터:
- USD/KRW: {market.usd_krw or 'N/A'}
- 금 가격: ${market.gold_usd or 'N/A'}
- 비트코인 (USDT): ${market.btc_usdt or 'N/A'}

주요 뉴스 헤드라인 Top 5:
"""
            for idx, news in enumerate(news_list[:5], 1):
                market_summary += f"{idx}. {news.title}\n"
            
            prompt = f"""{market_summary}

위 데이터를 바탕으로 오늘 시장 상황을 **한 문장**으로 요약해줘.
투자자에게 유용하고 간결하게 작성해줘."""
            
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return message.content[0].text.strip()
        
        except Exception as e:
            print(f"Claude API 호출 실패: {e}")
    
    # OpenAI API 사용 (우선순위 2)
    if settings.OPENAI_API_KEY:
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            market_summary = f"""
오늘의 시장 데이터:
- USD/KRW: {market.usd_krw or 'N/A'}
- 금 가격: ${market.gold_usd or 'N/A'}
- 비트코인 (USDT): ${market.btc_usdt or 'N/A'}

주요 뉴스 헤드라인 Top 5:
"""
            for idx, news in enumerate(news_list[:5], 1):
                market_summary += f"{idx}. {news.title}\n"
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "당신은 금융 시장 전문가입니다. 한 문장으로 핵심을 요약하세요."},
                    {"role": "user", "content": f"{market_summary}\n\n위 데이터를 바탕으로 오늘 시장 상황을 한 문장으로 요약해주세요."}
                ],
                max_tokens=100,
                temperature=0.7,
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"OpenAI API 호출 실패: {e}")
    
    # API 키가 없을 경우 기본 메시지
    return "오늘의 시장 데이터와 뉴스를 확인하세요."


def extract_keywords(news_title: str) -> Optional[List[str]]:
    """뉴스 제목에서 키워드 추출 (간단한 버전)"""
    # 실전에서는 AI API나 형태소 분석기 사용
    # 현재는 간단하게 처리
    keywords = []
    
    # 자주 등장하는 금융/경제 키워드 매칭
    finance_keywords = [
        "금리", "환율", "주가", "달러", "원화", "투자", "경제",
        "수출", "수입", "무역", "코스피", "나스닥", "비트코인",
        "부동산", "금값", "은행", "증시", "주식", "채권"
    ]
    
    for keyword in finance_keywords:
        if keyword in news_title:
            keywords.append(keyword)
    
    return keywords if keywords else None
