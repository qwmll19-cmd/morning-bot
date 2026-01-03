"""긴급 속보 키워드 정의"""

URGENT_KEYWORDS = [
    "특보", "재난", "산불", "화재", "폭발",
    "건물붕괴", "붕괴", "지진", "해일", "쓰나미",
    "폭우", "태풍", "홍수", "산사태",
    "대형사고", "대형 사고", "대형교통사고", "전복", "추락", "침몰",
    "사망", "실종", "인명피해", "사상자",
    "전쟁", "전투", "폭격", "미사일", "공습", "테러", "총격",
    "비상사태", "계엄",
]

def has_urgent_keyword(title: str) -> bool:
    if not title:
        return False
    title_lower = title.lower()
    for keyword in URGENT_KEYWORDS:
        if keyword in title_lower:
            return True
    return False

def extract_urgent_keywords(title: str) -> list:
    if not title:
        return []
    title_lower = title.lower()
    found = []
    for keyword in URGENT_KEYWORDS:
        if keyword in title_lower:
            found.append(keyword)
    return found
