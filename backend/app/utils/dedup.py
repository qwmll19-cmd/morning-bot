"""뉴스 중복 제거 유틸리티"""

from typing import List, Set, Tuple
from difflib import SequenceMatcher
import html
import re
from urllib.parse import urlparse, urlunparse


def normalize_title(title: str) -> str:
    """중복 비교용 정규화 제목"""
    if not title:
        return ""
    cleaned = html.unescape(title)
    cleaned = cleaned.replace("<b>", "").replace("</b>", "")
    cleaned = cleaned.replace("[속보]", "").replace("[단독]", "").replace("[긴급]", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_url(url: str) -> str:
    """중복 비교용 URL 정규화 (query/fragment 제거)"""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    except Exception:
        return url.strip()


def extract_short_topic_key(title: str) -> str:
    """짧은 topic_key 생성 (30자)"""
    if not title:
        return ""
    
    cleaned = normalize_title(title)
    cleaned = re.sub(r"[^0-9가-힣a-zA-Z ]", "", cleaned)
    cleaned = cleaned.replace(" ", "").lower()
    return cleaned[:30]


def calculate_similarity(title1: str, title2: str) -> float:
    """두 제목의 유사도 계산 (0.0 ~ 1.0)"""
    
    # 특수문자 제거
    clean1 = re.sub(r"[^가-힣a-zA-Z0-9 ]", "", normalize_title(title1).lower())
    clean2 = re.sub(r"[^가-힣a-zA-Z0-9 ]", "", normalize_title(title2).lower())
    
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


def extract_primary_topic(title: str) -> str:
    """핵심 주제(키워드) 1개 추출"""
    if not title:
        return ""
    title_lower = title.lower()
    topic_priority = [
        "코스피", "코스닥", "나스닥", "환율", "달러", "원화", "금리",
        "삼성", "LG", "현대", "SK", "네이버", "카카오", "쿠팡",
        "수출", "수입", "무역", "관세", "GDP",
        "대통령", "국회", "청와대", "검찰", "경찰", "법원",
        "구속", "기소", "영장", "재판", "사퇴", "사임", "별세", "사망",
        "화재", "폭발", "추돌", "사고", "지진",
    ]
    for keyword in topic_priority:
        if keyword in title_lower:
            return keyword
    return ""


def extract_issue_key(title: str) -> str:
    """인물/사건 기준 그룹핑 키 생성 (같은 이슈 1건만 남기기)"""
    if not title:
        return ""

    cleaned = normalize_title(title)
    event_keywords = [
        "별세", "사망", "사퇴", "사임", "구속", "기소", "영장", "재판",
        "파면", "탄핵", "해임", "선고", "항소", "압수수색", "의혹",
        "화재", "폭발", "추돌", "사고", "지진",
    ]
    obit_keywords = [
        "별세", "사망", "향년", "부고", "빈소", "발인", "장례", "추모", "영면", "고 ",
    ]

    name = extract_person_name(cleaned)
    if name:
        if any(k in cleaned for k in obit_keywords):
            return f"person:{name}:obit"
        for keyword in event_keywords:
            if keyword in cleaned:
                return f"person:{name}:{keyword}"

    entities = extract_key_entities(cleaned)
    if entities:
        return "entity:" + "|".join(entities[:2])

    return ""


def extract_person_name(title: str) -> str:
    """인물 이름 추출 (강한 규칙 기반)"""
    if not title:
        return ""

    obit_keywords = [
        "별세", "사망", "향년", "부고", "추모", "영면", "빈소", "발인", "장례",
    ]
    event_keywords = set(obit_keywords + [
        "사퇴", "사임", "구속", "기소", "영장", "재판", "파면", "탄핵", "해임", "선고",
        "항소", "압수수색", "의혹", "화재", "폭발", "추돌", "사고", "지진",
    ])
    stopwords = {
        "국민", "배우", "가수", "감독", "개그맨", "MC", "회장", "의원",
        "대표", "장관", "대통령", "총리", "실장", "아역",
        "국민배우", "국민배우", "국민배우", "국민배우", "국민배우",
    }
    patterns = [
        r"(?:고\s*)?([가-힣]{2,4})\s*(?:별세|사망|향년|부고|추모|영면|빈소|발인|장례)",
        r"(?:[가-힣]{1,4}\s*)?(?:배우|가수|감독|개그맨|MC)\s*([가-힣]{2,4})",
        r"([가-힣]{2,4})\s*(?:배우|가수|감독|개그맨|MC)",
        r"(?:고\s*)([가-힣]{2,4})",
    ]
    if any(k in title for k in obit_keywords):
        match = re.search(r"(?:고\s*)?([가-힣]{2,4})[^가-힣]{0,6}(?:별세|사망|향년|부고|추모|영면|빈소|발인|장례)", title)
        if match:
            candidate = match.group(1)
            if candidate not in stopwords:
                return candidate
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            candidate = match.group(1)
            if candidate in stopwords:
                continue
            return candidate
    # 토큰 기반 fallback: 키워드/직함 제외 후 첫 번째 인물 후보
    tokens = re.findall(r"[가-힣]{2,4}", normalize_title(title))
    for token in tokens:
        if token in stopwords or token in event_keywords:
            continue
        return token
    return ""


def extract_person_candidates(title: str) -> Set[str]:
    """제목에서 인물 후보를 폭넓게 추출 (중복 이슈 묶기용)"""
    if not title:
        return set()

    stopwords = {
        "국민", "배우", "가수", "감독", "개그맨", "MC", "회장", "의원",
        "대표", "장관", "대통령", "총리", "실장", "아역", "국민배우",
        "별세", "사망", "향년", "부고", "추모", "영면", "빈소", "발인", "장례",
        "사퇴", "사임", "구속", "기소", "영장", "재판", "파면", "탄핵", "해임",
        "선고", "항소", "압수수색", "의혹", "화재", "폭발", "추돌", "사고", "지진",
    }
    tokens = re.findall(r"[가-힣]{2,4}", normalize_title(title))
    return {t for t in tokens if t not in stopwords}


def has_obit_keywords(title: str) -> bool:
    if not title:
        return False
    obit_keywords = ["별세", "사망", "향년", "부고", "추모", "영면", "빈소", "발인", "장례"]
    return any(k in title for k in obit_keywords)


def is_duplicate_news(news1_title: str, news2_title: str) -> bool:
    """두 뉴스가 중복인지 판단"""
    
    # 0. 인물/사건 키가 동일하면 중복
    issue1 = extract_issue_key(news1_title)
    issue2 = extract_issue_key(news2_title)
    if issue1 and issue1 == issue2:
        return True

    # 1. topic_key 비교 (30자)
    key1 = extract_short_topic_key(news1_title)
    key2 = extract_short_topic_key(news2_title)
    
    if key1 == key2:
        return True
    
    # 2. 유사도 계산 (단어 기반)
    similarity = calculate_similarity(news1_title, news2_title)
    if similarity >= 0.5:
        return True

    # 2-1. 문자열 기반 유사도 (문장 거의 동일한 경우)
    clean1 = re.sub(r"[^가-힣a-zA-Z0-9 ]", "", normalize_title(news1_title).lower())
    clean2 = re.sub(r"[^가-힣a-zA-Z0-9 ]", "", normalize_title(news2_title).lower())
    if clean1 and clean2:
        ratio = SequenceMatcher(None, clean1, clean2).ratio()
        if ratio >= 0.78:
            return True
    
    # 3. 핵심 키워드 비교
    entities1 = extract_key_entities(news1_title)
    entities2 = extract_key_entities(news2_title)
    
    if entities1 and entities2:
        common = set(entities1) & set(entities2)
        total = set(entities1) | set(entities2)
        
        if len(common) / len(total) >= 0.5:
            return True

    # 4. 부고/별세 이슈: 인물 후보가 겹치면 중복 처리
    if has_obit_keywords(news1_title) and has_obit_keywords(news2_title):
        c1 = extract_person_candidates(news1_title)
        c2 = extract_person_candidates(news2_title)
        if c1 and c2 and (c1 & c2):
            return True

    # 5. 동일 인물 반복: 인물 후보가 겹치면 중복 처리
    c1 = extract_person_candidates(news1_title)
    c2 = extract_person_candidates(news2_title)
    if c1 and c2 and (c1 & c2):
        return True
    
    return False


def remove_duplicate_news(news_list: List) -> List:
    """중복 뉴스 제거 (hot_score 높은 것만 남김)"""
    
    if not news_list:
        return []
    
    # 1. 먼저 hot_score로 정렬 (높은 순)
    sorted_news = sorted(news_list, key=lambda x: (x.hot_score, x.created_at), reverse=True)
    name_counts = {}
    for item in sorted_news:
        candidates = extract_person_candidates(normalize_title(item.title))
        for name in candidates:
            name_counts[name] = name_counts.get(name, 0) + 1
    frequent_names = {name for name, count in name_counts.items() if count >= 2}
    
    # 2. 중복 제거
    unique_news = []
    seen_urls = set()
    seen_issue_keys = set()
    
    for current_news in sorted_news:
        is_dup = False

        # 인물/사건 키가 동일하면 중복으로 처리
        issue_key = extract_issue_key(current_news.title)
        primary_topic = extract_primary_topic(current_news.title)
        candidates = extract_person_candidates(normalize_title(current_news.title))
        common_names = candidates & frequent_names
        if common_names:
            # 여러 이름 중 하나로 묶어서 중복 제거 (인물 기준 최우선)
            name = sorted(common_names)[0]
            issue_key = f"person:{name}"

        if primary_topic:
            issue_key = issue_key or f"topic:{primary_topic}"
        if issue_key and issue_key in seen_issue_keys:
            continue

        # URL이 동일하면 중복으로 처리
        current_url = normalize_url(getattr(current_news, "url", "") or "")
        if current_url and current_url in seen_urls:
            continue
        
        # 이미 unique_news에 있는 것과 비교
        for existing_news in unique_news:
            if is_duplicate_news(current_news.title, existing_news.title):
                # 중복 발견! (현재는 이미 정렬되어 있으므로 existing이 더 높은 점수)
                is_dup = True
                break
        
        # 중복이 아니면 추가
        if not is_dup:
            unique_news.append(current_news)
            if current_url:
                seen_urls.add(current_url)
            if issue_key:
                seen_issue_keys.add(issue_key)
    
    return unique_news
