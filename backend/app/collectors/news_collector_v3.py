"""
Morning Bot v3.0 - 언론사별 수집 + 핫 점수 시스템
"""

from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
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
KST_TZ = timezone(timedelta(hours=9))

# 20개 언론사
PRESS_LIST = [
    "매일경제", "한국경제", "머니투데이", "서울경제", "헤럴드경제",
    "아시아경제", "이데일리", "조선비즈", "파이낸셜뉴스",
    "연합뉴스", "YTN", "KBS", "SBS", "JTBC",
    "국민일보", "코리아헤럴드", "아이뉴스24", "디지털타임스", "한겨레", "SBS"
]

# 카테고리별 검색 키워드 (경제, 문화 뉴스 수집 보장)
CATEGORY_SEARCH_KEYWORDS = {
    "economy": [
        "코스피", "증시", "환율", "금리", "주가", "경제", "부동산", "아파트",
        "달러", "원화", "채권", "펀드", "매출", "실적", "영업이익", "수출",
        "GDP", "물가", "인플레", "주택", "전세", "세금", "투자", "기업"
    ],
    "culture": [
        "영화", "전시", "공연", "책", "문화", "미술", "음악회",
        "개봉", "박스오피스", "영화제", "소설", "출판", "베스트셀러",
        "박물관", "미술관", "갤러리", "축제"
    ],
    "entertainment": [
        "아이돌", "드라마", "예능", "연예", "걸그룹", "배우",
        "보이그룹", "가수", "탤런트", "컴백", "데뷔", "신곡",
        "앨범", "타이틀곡", "뮤비", "뮤직비디오"
    ],
    "society": []  # 기본 카테고리이므로 별도 수집 불필요
}


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
    
    today = datetime.now(KST_TZ).date()
    now_kst = datetime.now(KST_TZ)
    min_dt = now_kst - timedelta(hours=24)  # 24시간 이내만 허용 (구형 뉴스 필터)
    created = []
    stats = {
        "missing_fields": 0,
        "bad_pubdate": 0,
        "old_pubdate": 0,
        "no_topic_key": 0,
        "press_filtered": 0,
        "duplicate_url": 0,
        "saved": 0,
    }
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
                pub_raw = item.get("pubDate")
                
                if not raw_title or not url:
                    continue

                # 1.5. 발행일 파싱 및 신선도 필터
                pub_dt = None
                try:
                    if pub_raw:
                        pub_dt = parsedate_to_datetime(pub_raw)
                        if pub_dt.tzinfo:
                            pub_dt = pub_dt.astimezone(KST_TZ)
                        else:
                            pub_dt = pub_dt.replace(tzinfo=KST_TZ)
                except Exception:
                    pub_dt = None

                # pubDate가 없으면 버리고, 48시간 이전 뉴스는 스킵
                if not pub_dt or pub_dt < min_dt:
                    continue

                pub_dt_naive = pub_dt.replace(tzinfo=None)
                item_date = pub_dt.date()
                
                # 2. 제목 정제
                title = raw_title.replace("<b>", "").replace("</b>", "")
                topic_key = build_topic_key(title)
                
                if not topic_key:
                    continue
                
                # 3. 중복 체크 (동일 일자 기준)
                existing = db.query(NewsDaily)\
                    .filter(
                        NewsDaily.date == item_date,
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
                    date=item_date,
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
                    published_at=pub_dt_naive,
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
            NewsDaily.date == news.date,
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


def collect_by_category_keywords(db: Session) -> List[NewsDaily]:
    """카테고리별 키워드 검색으로 뉴스 수집 (경제/문화 보장)"""

    from backend.app.utils.dedup import remove_duplicate_news

    today = datetime.now(KST_TZ).date()
    now_kst = datetime.now(KST_TZ)
    min_dt = now_kst - timedelta(hours=24)
    created = []
    temp_news_list = []

    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"🎯 카테고리별 뉴스 수집 시작")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    total_fetched = 0

    for category, keywords in CATEGORY_SEARCH_KEYWORDS.items():
        # 빈 카테고리는 스킵 (society는 기본 분류로 충분)
        if not keywords:
            continue

        print(f"\n📂 [{category.upper()}] 카테고리 수집 중...")

        # 각 키워드로 검색 (키워드당 30개씩)
        for keyword in keywords:
            items = fetch_naver_news_raw(query=keyword, display=30)
            total_fetched += len(items)

            if not items:
                continue

            for item in items:
                try:
                    raw_title = item.get("title")
                    url = item.get("originallink") or item.get("link")
                    pub_raw = item.get("pubDate")

                    if not raw_title or not url:
                        continue

                    # 발행일 파싱
                    pub_dt = None
                    try:
                        if pub_raw:
                            pub_dt = parsedate_to_datetime(pub_raw)
                            if pub_dt.tzinfo:
                                pub_dt = pub_dt.astimezone(KST_TZ)
                            else:
                                pub_dt = pub_dt.replace(tzinfo=KST_TZ)
                    except Exception:
                        pub_dt = None

                    if not pub_dt or pub_dt < min_dt:
                        continue

                    pub_dt_naive = pub_dt.replace(tzinfo=None)
                    item_date = pub_dt.date()

                    # 제목 정제
                    title = raw_title.replace("<b>", "").replace("</b>", "")
                    topic_key = build_topic_key(title)

                    if not topic_key:
                        continue

                    # 중복 체크
                    existing = db.query(NewsDaily)\
                        .filter(
                            NewsDaily.date == item_date,
                            NewsDaily.topic_key == topic_key
                        )\
                        .first()

                    if existing:
                        continue

                    # 언론사 확인
                    source_press = extract_press_from_url(url)
                    if not source_press or source_press not in PRESS_BREAKING_CONFIG:
                        continue

                    # 카테고리 자동 분류 (재확인)
                    detected_category = classify_category(title)

                    # 속보 태그 확인
                    is_breaking = check_breaking_tag(title)

                    # 저장
                    news = NewsDaily(
                        date=item_date,
                        category=detected_category,  # 자동 분류된 카테고리 사용
                        title=title,
                        url=url[:200] if url else "",
                        source=source_press,
                        topic_key=topic_key,
                        is_breaking=is_breaking,
                        is_top=False,
                        hot_score=0,
                        keywords=None,
                        sentiment=None,
                        published_at=pub_dt_naive,
                    )

                    temp_news_list.append(news)

                except Exception as e:
                    continue

        print(f"  ✅ {category}: {len([n for n in temp_news_list if n.category == category])}개")

    # 중복 제거
    print(f"\n🔄 중복 제거 중...")
    print(f"  - 수집: {len(temp_news_list)}개")
    unique_news_list = remove_duplicate_news(temp_news_list)
    print(f"  - 중복 제거 후: {len(unique_news_list)}개")

    # DB 저장 (개별 커밋, 카테고리 업데이트 지원)
    updated_count = 0
    for news in unique_news_list:
        try:
            # 기존 뉴스 확인
            existing = db.query(NewsDaily).filter(
                NewsDaily.date == news.date,
                NewsDaily.topic_key == news.topic_key
            ).first()

            if existing:
                # 이미 존재하면 카테고리가 society이고 새 분류가 더 구체적이면 업데이트
                if existing.category == "society" and news.category != "society":
                    existing.category = news.category
                    db.commit()
                    updated_count += 1
            else:
                # 새 뉴스면 추가
                db.add(news)
                db.commit()
                db.refresh(news)
                created.append(news)
        except IntegrityError:
            # 중복이면 롤백하고 다음으로
            db.rollback()
            continue
        except Exception as e:
            # 다른 에러도 롤백하고 다음으로
            db.rollback()
            print(f"  ⚠️ 저장 실패: {news.title[:30]}... - {e}")
            continue

    if updated_count > 0:
        print(f"  🔄 카테고리 업데이트: {updated_count}개")

    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 카테고리별 수집 완료:")
    print(f"  - API 요청: {len(CATEGORY_SEARCH_KEYWORDS) * sum(len(k) for k in CATEGORY_SEARCH_KEYWORDS.values())}회")
    print(f"  - 받은 뉴스: {total_fetched}개")
    print(f"  - 저장된 뉴스: {len(created)}개")

    # 카테고리별 통계
    for category in CATEGORY_SEARCH_KEYWORDS.keys():
        count = len([n for n in created if n.category == category])
        print(f"  - {category}: {count}개")

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
    
    today = datetime.now(KST_TZ).date()
    now_kst = datetime.now(KST_TZ)
    min_dt = now_kst - timedelta(hours=24)
    created = []
    stats = {
        "missing_fields": 0,
        "bad_pubdate": 0,
        "old_pubdate": 0,
        "no_topic_key": 0,
        "press_filtered": 0,
        "duplicate_url": 0,
        "saved": 0,
    }
    
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
            pub_raw = item.get("pubDate")
            
            if not raw_title or not url:
                stats["missing_fields"] += 1
                continue

            pub_dt = None
            try:
                if pub_raw:
                    pub_dt = parsedate_to_datetime(pub_raw)
                    if pub_dt.tzinfo:
                        pub_dt = pub_dt.astimezone(KST_TZ)
                    else:
                        pub_dt = pub_dt.replace(tzinfo=KST_TZ)
            except Exception:
                pub_dt = None

            if not pub_dt:
                stats["bad_pubdate"] += 1
                continue

            if pub_dt < min_dt:
                stats["old_pubdate"] += 1
                continue

            pub_dt_naive = pub_dt.replace(tzinfo=None)
            item_date = pub_dt.date()
            
            title = raw_title.replace("<b>", "").replace("</b>", "")
            topic_key = build_topic_key(title)
            
            if not topic_key:
                stats["no_topic_key"] += 1
                continue
            
            # 언론사 확인
            source_press = extract_press_from_url(url)
            if not source_press or source_press not in PRESS_BREAKING_CONFIG:
                stats["press_filtered"] += 1
                continue
            
            # 카테고리 분류
            category = classify_category(title)
            
            # NewsDaily 객체 생성 (아직 DB에 저장 안 함)
            news = NewsDaily(
                date=item_date,
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
                published_at=pub_dt_naive,
                created_at=pub_dt_naive,
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
            existing = (
                db.query(NewsDaily)
                .filter(
                    NewsDaily.date == news.date,
                    NewsDaily.url == news.url,
                )
                .first()
            )
            
            if existing:
                stats["duplicate_url"] += 1
                continue
            
            db.add(news)
            created.append(news)
            saved_count += 1
            stats["saved"] += 1
            
        except Exception as e:
            continue
    
    try:
        db.commit()
        for n in created:
            db.refresh(n)
    except IntegrityError:
        db.rollback()
        created = []
    
    print(f"  ✅ 속보 저장: {saved_count}개")
    print(
        f"  📌 스킵 사유: missing={stats['missing_fields']} "
        f"bad_pub={stats['bad_pubdate']} old_pub={stats['old_pubdate']} "
        f"no_topic={stats['no_topic_key']} press={stats['press_filtered']} "
        f"dup_url={stats['duplicate_url']}"
    )
    print("")
    
    return created


def calculate_hot_score(news_id: int, db: Session) -> int:
    """핫 점수 계산"""

    news = db.query(NewsDaily).filter(NewsDaily.id == news_id).first()
    if not news:
        return 0

    score = 0
    # KST 기준 날짜/시간 (타임존 안전)
    today = datetime.now(KST_TZ).date()
    now = datetime.now(KST_TZ)
    
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
    # created_at이 타임존 정보가 없으면 KST로 간주
    created_at = news.created_at if news.created_at.tzinfo else news.created_at.replace(tzinfo=KST_TZ)
    hours_old = (now - created_at).total_seconds() / 3600
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

    # KST 기준 오늘 날짜 (타임존 안전)
    today = datetime.now(KST_TZ).date()
    news_list = db.query(NewsDaily)\
        .filter(NewsDaily.date == today)\
        .all()
    
    for news in news_list:
        news.hot_score = calculate_hot_score(news.id, db)
    
    db.commit()
    
    print(f"  ✅ {len(news_list)}개 뉴스 점수 업데이트 완료\n")


def select_top_news(db: Session, category: str, limit: int = 10) -> List[NewsDaily]:
    """카테고리별 TOP 선정"""

    from backend.app.utils.dedup import remove_duplicate_news

    # KST 기준 오늘 날짜 (타임존 안전)
    today = datetime.now(KST_TZ).date()
    
    candidate_limit = max(limit * 5, 50)
    candidates = db.query(NewsDaily)\
        .filter(
            NewsDaily.date == today,
            NewsDaily.category == category
        )\
        .order_by(
            NewsDaily.hot_score.desc(),
            NewsDaily.created_at.desc()
        )\
        .limit(candidate_limit)\
        .all()

    top_news = remove_duplicate_news(candidates)[:limit]
    
    # is_top 플래그 업데이트
    for news in top_news:
        news.is_top = True
    
    db.commit()
    
    return top_news


def build_daily_rankings(db: Session):
    """전체 랭킹 구성"""
    
    print(f"\n🏆 TOP 10 선정 중...")
    
    # 1. 핫 점수 업데이트 (당일 + 전일 수집분도 반영)
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
    # KST 기준 오늘 날짜 (타임존 안전)
    today = datetime.now(KST_TZ).date()
    
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

        # 2. 카테고리별 키워드 수집 (경제/문화 보장)
        collect_by_category_keywords(db)

        # 3. 속보 라인 수집
        collect_breaking_news(db)

        # 4. TOP 10 선정
        build_daily_rankings(db)
        
        print(f"="*60)
        print(f"  ✅ 모든 작업 완료!")
        print(f"="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        raise
