"""카테고리 분류용 키워드"""

CATEGORY_KEYWORDS = {
    "economy": {
        "primary": [  # 핵심 키워드 (3점)
            "코스피", "코스닥", "주가", "증시", "환율", "달러", "원화",
            "금리", "채권", "상장", "IPO", "펀드",
            "매출", "실적", "영업이익", "순이익", "수출", "수입",
            "GDP", "경제성장", "성장률"
        ],
        "secondary": [  # 보조 키워드 (1점)
            "투자", "경제", "기업", "산업", "무역", "관세",
            "물가", "인플레", "인플레이션",
            "부동산", "아파트", "집값", "주택", "전세", "월세",
            "세금", "재정", "예산", "경영", "M&A", "인수합병"
        ]
    },
    
    "society": {
        "primary": [
            "정치", "국회", "청와대", "대통령", "총리", "장관", "의원",
            "법원", "검찰", "경찰", "재판", "판결", "선고", "기소",
            "사고", "화재", "폭발", "붕괴", "참사",
            "범죄", "살인", "강도", "절도", "사기", "피해"
        ],
        "secondary": [
            "정부", "정책", "법안", "조례", "규제", "개정",
            "교육", "학교", "대학", "입시", "학생", "교사",
            "날씨", "기상", "태풍", "지진", "홍수", "가뭄",
            "재난", "안전", "구조", "소방", "응급"
        ]
    },
    
    "culture": {
        "primary": [
            "전시", "전시회", "공연", "미술", "음악회", "콘서트", "공연장",
            "영화", "개봉", "박스오피스", "영화제", "칸", "오스카",
            "책", "도서", "작가", "소설", "시집", "출판", "베스트셀러"
        ],
        "secondary": [
            "문화", "예술", "작품", "문화재", "유적", "유물",
            "박물관", "미술관", "갤러리", "전시관",
            "축제", "페스티벌", "행사", "이벤트", "문화행사"
        ]
    },
    
    "entertainment": {
        "primary": [
            "아이돌", "걸그룹", "보이그룹", "가수", "배우", "연예인", "탤런트",
            "드라마", "예능", "방송", "TV프로그램", "시청률",
            "컴백", "데뷔", "신곡", "앨범", "타이틀곡", "뮤비", "뮤직비디오"
        ],
        "secondary": [
            "스타", "셀럽", "연기", "출연", "캐스팅", "주연",
            "결혼", "열애", "이혼", "파경", "스캔들", "루머",
            "팬", "팬미팅", "콘서트", "인스타그램", "인스타", "SNS"
        ]
    }
}


def classify_category(title: str) -> str:
    """제목 기반 카테고리 분류"""
    
    if not title:
        return "society"
    
    scores = {
        "economy": 0,
        "society": 0,
        "culture": 0,
        "entertainment": 0
    }
    
    title_lower = title.lower()
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        # 핵심 키워드: 3점
        for keyword in keywords["primary"]:
            if keyword in title_lower:
                scores[category] += 3
        
        # 보조 키워드: 1점
        for keyword in keywords["secondary"]:
            if keyword in title_lower:
                scores[category] += 1
    
    # 최고 점수 카테고리
    max_category = max(scores, key=scores.get)
    
    # 점수 0이면 society (기본)
    if scores[max_category] == 0:
        return "society"
    
    return max_category
