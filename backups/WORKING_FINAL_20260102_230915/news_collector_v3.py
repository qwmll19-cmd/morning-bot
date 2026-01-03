"""
Morning Bot v3.0 - 언론사별 수집 + 핫 점수 시스템
"""

from datetime import date, datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import httpx
import re

from backend.app.config import settings
from backend.app.db.models import NewsDaily
from backend.app.utils.filters import extract_press_from_url, PRESS_BREAKING_CONFIG
from backend.app.utils.category_keywords import classify_category

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"

# 20개 언론사
PRESS_LIST = [
    "매일경제", "한국경제", "머니투데이", "서울경제", "헤럴드경제",
    "아시아경제", "이데일리", "조선비즈", "파이낸셜뉴스",
    "연합뉴스", "YTN", "KBS", "SBS", "JTBC",
    "국민일보", "코리아헤럴드", "아이뉴스24", "디지털타임스", "한겨레", "SBS"
]


def build_topic_key(title: str) -> str:
    """중복 판별용 키 생성 (30자로 단축)"""
    if not title:
        return ""
    
    cleaned = title
    cleaned = cleaned.replace("<b>", "").replace("</b>", "")
    cleaned = cleaned.replace("[속보]", "").replace("[단독]", "").replace("[긴급]", "")
    cleaned = re.sub(r"[^0-9가-힣a-zA-Z ]", "", cleaned)
    cleaned = cleaned.replace(" ", "").lower()
    return cleaned[:30]


def check_breaking_tag(title: str) -> bool:
    """속보 태그 확인"""
    breaking_patterns = ["[속보]", "[긴급]", "[단독]", "속보:", "단독:"]
    for pattern in breaking_patterns:
        if pattern in title:
            return True
    return False


def fetch_naver_news_raw(query: str, display: int = 100) -> List[Dict[str, Any]]:
    """네이버 뉴스 API 호출"""
    
    if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
        raise RuntimeError("NAVER credentials not set")
    
    headers = {
        "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
    }
    params = {
        "query": query,
        "display": display,
        "sort": "date",
    }
    
    try:
        resp = httpx.get(NAVER_NEWS_URL, params=params, headers=headers, timeout=10.0)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as e:
        print(f"  ❌ API 오류: {e}")
        return []


def collect_by_press(db: Session) -> List[NewsDaily]:
    """언론사별 수집 (20개 × 100개 = 2,000개)"""
    
    from backend.app.utils.dedup import remove_duplicate_news
    
    today = date.today()
    created = []
    temp_news_list = []  # 중복 제거 전 임시 리스트
    
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📰 언론사별 뉴스 수집 시작")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    total_fetched = 0
    total_saved = 0
    
    for press in PRESS_LIST:
        print(f"\n🔍 [{press}] 수집 중...")
        
        items = fetch_naver_news_raw(query=press, display=100)
        total_fetched += len(items)
        
        if not items:
            print(f"  ⚠️ 결과 없음")
            continue
        
        saved_count = 0
        
        for item in items:
            try:
                # 1. 필수 필드 검증
                raw_title = item.get("title")
                url = item.get("originallink") or item.get("link")
                
                if not raw_title or not url:
                    continue
                
                # 2. 제목 정제
                title = raw_title.replace("<b>", "").replace("</b>", "")
                topic_key = build_topic_key(title)
                
                if not topic_key:
                    continue
                
                # 3. 중복 체크 (오늘만)
                existing = db.query(NewsDaily)\
                    .filter(
                        NewsDaily.date == today,
                        NewsDaily.topic_key == topic_key
                    )\
                    .first()
                
                if existing:
                    continue
                
                # 4. 언론사 확인
                source_press = extract_press_from_url(url)
                if not source_press or source_press not in PRESS_BREAKING_CONFIG:
                    continue
                
                # 5. 카테고리 자동 분류
                category = classify_category(title)
                
                # 6. 속보 태그 확인
                is_breaking = check_breaking_tag(title)
                
                # 7. 저장
                news = NewsDaily(
                    date=today,
                    category=category,
                    title=title,
                    url=url[:200] if url else "",
                    source=source_press,
                    topic_key=topic_key,
                    is_breaking=is_breaking,
                    is_top=False,
                    hot_score=0,
                    keywords=None,
                    sentiment=None,
                )
                
                temp_news_list.append(news)
                saved_count += 1
                
            except Exception as e:
                print(f"  ⚠️ 처리 오류: {e}")
                continue
        
        print(f"  ✅ 저장: {saved_count}개")
        total_saved += saved_count
    
    # 중복 제거
    print(f"\n🔄 중복 제거 중...")
    print(f"\n🔄 중복 제거 중...")
    print(f"  - 수집: {len(temp_news_list)}개")
    unique_news_list = remove_duplicate_news(temp_news_list)
    print(f"  - 중복 제거 후: {len(unique_news_list)}개")
    
    # DB 저장
    for news in unique_news_list:
        # DB에 이미 있는지 체크
        existing = db.query(NewsDaily).filter(
            NewsDaily.date == today,
            NewsDaily.topic_key == news.topic_key
        ).first()
        
        if not existing:
            db.add(news)
            created.append(news)
    
    # Commit
    try:
        db.commit()
        for n in created:
            db.refresh(n)
    except IntegrityError as e:
        db.rollback()
        print(f"  ❌ DB 오류: {e}")
        created = []
    
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 수집 완료:")
    print(f"  - API 요청: {len(PRESS_LIST)}회")
    print(f"  - 받은 뉴스: {total_fetched}개")
    print(f"  - 저장된 뉴스: {total_saved}개")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    
    return created



def filter_repeated_person_names(news_list):
    """같은 인물 이름 3개 이상 → 3개만 유지"""
    from collections import defaultdict
    import re
    
    person_counts = defaultdict(list)
    
    for news in news_list:
        title = news.title
        
        # 인물 이름 추출
        patterns = [
            r'([가-힣]{2,4})\s+(안보실장|대통령|총리|장관|실장|의원|대표|회장)',
            r'\[속보\]\s*([가-힣]{2,4})\s+(안보실장|대통령|총리|장관)',
        ]
        
        person_name = None
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                person_name = match.group(1)
                break
        
        if person_name:
            person_counts[person_name].append(news)
        else:
            person_counts['_no_person'].append(news)
    
    # 각 인물별 최대 3개
    filtered = []
    for person, news_items in person_counts.items():
        if person == '_no_person':
            filtered.extend(news_items)
        else:
            filtered.extend(news_items[:3])
    
    return filtered


def collect_breaking_news(db: Session) -> List[NewsDaily]:
    """속보 라인 수집 (100개) + 중복 제거"""
    
    from backend.app.utils.dedup import remove_duplicate_news
    
    today = date.today()
    created = []
    
    print(f"\n⚡ 속보 라인 수집 중...")
    
    items = fetch_naver_news_raw(query="속보", display=100)
    
    if not items:
        print(f"  ⚠️ 결과 없음")
        return []
    
    # 1단계: 모든 속보를 NewsDaily 객체로 변환 (저장 전)
    temp_news_list = []
    
    for item in items:
        try:
            raw_title = item.get("title")
            url = item.get("originallink") or item.get("link")
            
            if not raw_title or not url:
                continue
            
            title = raw_title.replace("<b>", "").replace("</b>", "")
            topic_key = build_topic_key(title)
            
            if not topic_key:
                continue
            
            # 언론사 확인
            source_press = extract_press_from_url(url)
            if not source_press or source_press not in PRESS_BREAKING_CONFIG:
                continue
            
            # 카테고리 분류
            category = classify_category(title)
            
            # NewsDaily 객체 생성 (아직 DB에 저장 안 함)
            news = NewsDaily(
                date=today,
                category=category,
                title=title,
                url=url[:200] if url else "",
                source=source_press,
                topic_key=topic_key,
                is_breaking=True,
                is_top=False,
                hot_score=0,
                keywords=None,
                sentiment=None,
            )
            
            temp_news_list.append(news)
            
        except Exception as e:
            continue
    
    # 2단계: 유사도 기반 중복 제거
    if temp_news_list:
        print(f"  📋 수집: {len(temp_news_list)}개")
        unique_news_list = remove_duplicate_news(temp_news_list)
        print(f"  ✨ 중복 제거 후: {len(unique_news_list)}개")
        unique_news_list = filter_repeated_person_names(unique_news_list)
        print(f"  🎯 인물 필터 후: {len(unique_news_list)}개")
    else:
        unique_news_list = []
    
    # 3단계: DB에 저장 (topic_key 중복 체크)
    saved_count = 0
    
    for news in unique_news_list:
        try:
            # DB에 이미 있는지 확인
            existing = db.query(NewsDaily)\
                .filter(
                    NewsDaily.date == today,
                    NewsDaily.topic_key == news.topic_key
                )\
                .first()
            
            if existing:
                continue
            
            db.add(news)
            created.append(news)
            saved_count += 1
            
        except Exception as e:
            continue
    
    try:
        db.commit()
        for n in created:
            db.refresh(n)
    except IntegrityError:
        db.rollback()
        created = []
    
    print(f"  ✅ 속보 저장: {saved_count}개\n")
    
    return created


def calculate_hot_score(news_id: int, db: Session) -> int:
    """핫 점수 계산"""
    
    news = db.query(NewsDaily).get(news_id)
    if not news:
        return 0
    
    score = 0
    today = date.today()
    now = datetime.now()
    
    # 1. 중복 주제 개수 (최대 100점)
    duplicate_count = db.query(NewsDaily)\
        .filter(
            NewsDaily.topic_key == news.topic_key,
            NewsDaily.date == today
        )\
        .count()
    score += duplicate_count * 10
    
    # 2. 보도 언론사 개수 (최대 50점)
    press_count = db.query(func.count(func.distinct(NewsDaily.source)))\
        .filter(
            NewsDaily.topic_key == news.topic_key,
            NewsDaily.date == today
        )\
        .scalar()
    score += press_count * 5
    
    # 3. 속보 태그 (30점)
    if news.is_breaking:
        score += 30
    
    # 4. 최신도 (최대 10점)
    hours_old = (now - news.created_at).total_seconds() / 3600
    if hours_old < 1:
        score += 10
    elif hours_old < 3:
        score += 5
    elif hours_old < 6:
        score += 2
    
    # 5. 주요 언론사 보너스 (5점)
    major_press = ["연합뉴스", "YTN", "KBS", "SBS", "매일경제", "한국경제"]
    if any(press in news.source for press in major_press):
        score += 5
    
    return score


def update_hot_scores(db: Session):
    """모든 오늘 뉴스의 핫 점수 업데이트"""
    
    print(f"\n🔥 핫 점수 계산 중...")
    
    today = date.today()
    news_list = db.query(NewsDaily)\
        .filter(NewsDaily.date == today)\
        .all()
    
    for news in news_list:
        news.hot_score = calculate_hot_score(news.id, db)
    
    db.commit()
    
    print(f"  ✅ {len(news_list)}개 뉴스 점수 업데이트 완료\n")


def select_top_news(db: Session, category: str, limit: int = 10) -> List[NewsDaily]:
    """카테고리별 TOP 선정"""
    
    today = date.today()
    
    top_news = db.query(NewsDaily)\
        .filter(
            NewsDaily.date == today,
            NewsDaily.category == category
        )\
        .order_by(
            NewsDaily.hot_score.desc(),
            NewsDaily.created_at.desc()
        )\
        .limit(limit)\
        .all()
    
    # is_top 플래그 업데이트
    for news in top_news:
        news.is_top = True
    
    db.commit()
    
    return top_news


def build_daily_rankings(db: Session):
    """전체 랭킹 구성"""
    
    print(f"\n🏆 TOP 10 선정 중...")
    
    # 1. 핫 점수 업데이트
    update_hot_scores(db)
    
    # 2. 각 카테고리별 TOP 10
    rankings = {}
    for category in ["society", "economy", "culture", "entertainment"]:
        top_news = select_top_news(db, category, limit=10)
        rankings[category] = top_news
        print(f"  ✅ {category}: {len(top_news)}개")
    
    print(f"  ✅ TOP 10 선정 완료\n")
    
    return rankings


def get_today_summary(db: Session) -> List[NewsDaily]:
    """오늘의 요약: 각 카테고리 TOP 1"""
    
    summary = []
    today = date.today()
    
    for category in ["society", "economy", "culture", "entertainment"]:
        top1 = db.query(NewsDaily)\
            .filter(
                NewsDaily.date == today,
                NewsDaily.category == category
            )\
            .order_by(
                NewsDaily.hot_score.desc(),
                NewsDaily.created_at.desc()
            )\
            .first()
        
        if top1:
            summary.append(top1)
    
    return summary


def build_daily_top5_v3(db: Session):
    """v3 전체 플로우"""
    
    print(f"\n" + "="*60)
    print(f"  Morning Bot v3.0 - 뉴스 수집 시작")
    print(f"="*60)
    
    try:
        # 1. 언론사별 수집
        collect_by_press(db)
        
        # 2. 속보 라인 수집
        collect_breaking_news(db)
        
        # 3. TOP 10 선정
        build_daily_rankings(db)
        
        print(f"="*60)
        print(f"  ✅ 모든 작업 완료!")
        print(f"="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        raise
