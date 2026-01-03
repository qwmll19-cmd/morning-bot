"""20개 언론사 필터"""

DOMAIN_TO_PRESS = {
    "mk.co.kr": "매일경제",
    "hankyung.com": "한국경제",
    "mt.co.kr": "머니투데이",
    "sedaily.com": "서울경제",
    "heraldcorp.com": "헤럴드경제",
    "asiae.co.kr": "아시아경제",
    "edaily.co.kr": "이데일리",
    "hankyungbiz.com": "한경비즈니스",
    "biz.chosun.com": "조선비즈",
    "fnnews.com": "파이낸셜뉴스",
    "yna.co.kr": "연합뉴스",
    "yonhapnews.co.kr": "연합뉴스",
    "ytn.co.kr": "YTN",
    "kbs.co.kr": "KBS",
    "sbs.co.kr": "SBS",
    "jtbc.co.kr": "JTBC",
    "jtbc.joins.com": "JTBC",
    "kmib.co.kr": "국민일보",
    "koreaherald.com": "코리아헤럴드",
    "inews24.com": "아이뉴스24",
    "dt.co.kr": "디지털타임스"
}

PRESS_BREAKING_CONFIG = {
    "매일경제": {"categories": ["경제", "사회"]},
    "한국경제": {"categories": ["경제", "사회"]},
    "머니투데이": {"categories": ["경제", "사회"]},
    "서울경제": {"categories": ["경제", "사회"]},
    "헤럴드경제": {"categories": ["경제", "사회"]},
    "아시아경제": {"categories": ["경제", "사회"]},
    "이데일리": {"categories": ["경제", "사회"]},
    "한경비즈니스": {"categories": ["경제"]},
    "조선비즈": {"categories": ["경제", "사회"]},
    "파이낸셜뉴스": {"categories": ["경제"]},
    "연합뉴스": {"categories": ["사회", "경제", "문화", "연예"]},
    "YTN": {"categories": ["사회", "경제"]},
    "KBS": {"categories": ["사회", "경제", "문화", "연예"]},
    "SBS": {"categories": ["사회", "경제", "문화", "연예"]},
    "JTBC": {"categories": ["사회", "경제"]},
    "국민일보": {"categories": ["사회", "문화"]},
    "코리아헤럴드": {"categories": ["사회", "경제"]},
    "아이뉴스24": {"categories": ["경제", "사회"]},
    "디지털타임스": {"categories": ["경제", "사회"]}
}

EXCLUDE_KEYWORDS = [
    "축제", "페스티벌", "기탁", "기부", "장례", "추모", "봉사"
]

def is_breaking_news(title, url, category):
    """진짜 속보만 True"""
    # 제외 키워드 있으면 속보 아님
    for kw in EXCLUDE_KEYWORDS:
        if kw in title:
            return False
    
    # 속보 패턴 확인
    breaking_patterns = ["[속보]", "[긴급]", "속보:", "[단독]", "단독"]
    for pattern in breaking_patterns:
        if pattern in title:
            return True
    
    # 속보 패턴 없으면 속보 아님
    return False

def extract_press_from_url(url):
    if not url:
        return ""
    for domain, press in DOMAIN_TO_PRESS.items():
        if domain in url:
            return press
    return ""

def get_category_name(category):
    category_map = {
        "society": "사회",
        "economy": "경제",
        "culture": "문화",
        "entertainment": "연예"
    }
    return category_map.get(category, category)

def get_allowed_press_list():
    return list(PRESS_BREAKING_CONFIG.keys())
