"""뉴스 중복 제거 유틸리티"""

from typing import List, Set, Tuple
import re


def extract_short_topic_key(title: str) -> str:
    """짧은 topic_key 생성 (30자)"""
    if not title:
        return ""
    
    cleaned = title.replace("<b>", "").replace("</b>", "")
    cleaned = cleaned.replace("[속보]", "").replace("[단독]", "").replace("[긴급]", "")
    cleaned = re.sub(r"[^0-9가-힣a-zA-Z ]", "", cleaned)
    cleaned = cleaned.replace(" ", "").lower()
    return cleaned[:30]


def calculate_similarity(title1: str, title2: str) -> float:
    """두 제목의 유사도 계산 (0.0 ~ 1.0)"""
    
    # 특수문자 제거
    clean1 = re.sub(r"[^가-힣a-zA-Z0-9 ]", "", title1.lower())
    clean2 = re.sub(r"[^가-힣a-zA-Z0-9 ]", "", title2.lower())
    
    # 단어 분리
    words1 = set(clean1.split())
    words2 = set(clean2.split())
    
    if not words1 or not words2:
        return 0.0
    
    # Jaccard 유사도
    common = words1 & words2
    total = words1 | words2
    
    return len(common) / len(total)


def extract_key_entities(title: str) -> Tuple[str, ...]:
    """핵심 키워드 추출 (인명, 기관명, 주요 키워드)"""
    
    keywords = []
    title_lower = title.lower()
    
    # 정치/사회
    entities = [
        "국방부", "대통령", "청와대", "국회", "장관", "의원",
        "검찰", "경찰", "법원", "여인형", "이진우", "고현석", "곽종근",
        "파면", "해임", "구속", "기소", "재판"
    ]
    
    # 경제
    entities.extend([
        "코스피", "코스닥", "환율", "달러", "원화", "금리",
        "삼성", "LG", "현대", "SK", "네이버", "카카오", "쿠팡",
        "수출", "수입", "무역", "관세", "GDP"
    ])
    
    # 기업/인물
    entities.extend([
        "임종룡", "우리금융", "폴란드", "천무"
    ])
    
    for entity in entities:
        if entity in title_lower:
            keywords.append(entity)
    
    # 숫자 추출 (금액, 지수 등)
    numbers = re.findall(r'\d+[\.,]?\d*', title)
    if numbers:
        keywords.extend(numbers[:2])  # 첫 2개 숫자만
    
    return tuple(sorted(set(keywords)))


def is_duplicate_news(news1_title: str, news2_title: str) -> bool:
    """두 뉴스가 중복인지 판단"""
    
    # 1. topic_key 비교 (30자)
    key1 = extract_short_topic_key(news1_title)
    key2 = extract_short_topic_key(news2_title)
    
    if key1 == key2:
        return True
    
    # 2. 유사도 계산
    similarity = calculate_similarity(news1_title, news2_title)
    if similarity >= 0.7:
        return True
    
    # 3. 핵심 키워드 비교
    entities1 = extract_key_entities(news1_title)
    entities2 = extract_key_entities(news2_title)
    
    if entities1 and entities2:
        common = set(entities1) & set(entities2)
        total = set(entities1) | set(entities2)
        
        if len(common) / len(total) >= 0.7:
            return True
    
    return False


def remove_duplicate_news(news_list: List) -> List:
    """중복 뉴스 제거 (hot_score 높은 것만 남김)"""
    
    if not news_list:
        return []
    
    # 1. 먼저 hot_score로 정렬 (높은 순)
    sorted_news = sorted(news_list, key=lambda x: (x.hot_score, x.created_at), reverse=True)
    
    # 2. 중복 제거
    unique_news = []
    
    for current_news in sorted_news:
        is_dup = False
        
        # 이미 unique_news에 있는 것과 비교
        for existing_news in unique_news:
            if is_duplicate_news(current_news.title, existing_news.title):
                # 중복 발견! (현재는 이미 정렬되어 있으므로 existing이 더 높은 점수)
                is_dup = True
                break
        
        # 중복이 아니면 추가
        if not is_dup:
            unique_news.append(current_news)
    
    return unique_news
