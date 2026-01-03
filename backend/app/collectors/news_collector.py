
from datetime import date, timedelta
from typing import List, Dict, Any

import httpx
import re
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.models import NewsDaily
from backend.app.utils.filters import is_breaking_news

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"


def _ensure_naver_credentials() -> None:
    if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
        raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET not set in environment")


def build_topic_key(title: str) -> str:
    """제목에서 태그/특수문자를 제거하고 중복 판별용 키를 생성합니다."""
    if not title:
        return ""

    cleaned = title
    cleaned = cleaned.replace("<b>", "").replace("</b>", "")
    cleaned = cleaned.replace("[속보]", "").replace("[단독]", "")
    cleaned = re.sub(r"[^0-9가-힣a-zA-Z ]", "", cleaned)
    cleaned = cleaned.replace(" ", "").lower()
    return cleaned[:60]


def fetch_naver_news_raw(
    query: str,
    display: int = 50,
    sort: str = "date",
) -> List[Dict[str, Any]]:
    """네이버 뉴스 검색 API에서 raw item 리스트를 가져옵니다."""
    _ensure_naver_credentials()

    headers = {
        "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
    }
    params = {
        "query": query,
        "display": display,
        "sort": sort,
    }

    with httpx.Client(timeout=10.0) as client:
        resp = client.get(NAVER_NEWS_URL, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    return data.get("items", [])


def save_news_items(
    db: Session,
    items: List[Dict[str, Any]],
    *,
    category: str,
) -> List[NewsDaily]:
    """네이버 뉴스 item 리스트를 받아 중복 제거 후 DB에 저장합니다."""
    today = date.today()
    three_days_ago = today - timedelta(days=3)  # 최근 3일
    created: List[NewsDaily] = []
    
    # 디버깅 카운터
    total_count = len(items)
    blocked_by_press = 0
    blocked_by_keyword = 0
    blocked_by_duplicate = 0
    
    print(f"\n━━━ [{category}] 뉴스 수집 시작 ━━━")
    print(f"📥 네이버에서 받은 뉴스: {total_count}개")

    for item in items:
        raw_title = item.get("title") or ""
        title = raw_title.replace("<b>", "").replace("</b>", "")
        topic_key = build_topic_key(title)

        if not topic_key:
            continue
        
        # pubDate 체크 - 3일 이내 뉴스만 저장
        pub_date_str = item.get("pubDate")
        if pub_date_str:
            try:
                from datetime import datetime
                from email.utils import parsedate_to_datetime
                pub_date = parsedate_to_datetime(pub_date_str)
                pub_date_only = pub_date.date()
                
                # 3일 이상 된 뉴스는 차단
                if (today - pub_date_only).days > 3:
                    continue
            except Exception:
                pass  # pubDate 파싱 실패하면 그냥 통과

        # 최근 3일 이내 같은 뉴스가 있는지 체크 (지난 일은 지난 일)
        existing = (
            db.query(NewsDaily)
            .filter(
                NewsDaily.date >= three_days_ago,
                NewsDaily.topic_key == topic_key
            )
            .first()
        )
        if existing:
            blocked_by_duplicate += 1
            continue

        source = (item.get("originallink") or item.get("link") or "")[:100]
        url = item.get("originallink") or item.get("link") or ""
        
        # pubDate 파싱 - 실제 발행일 확인
        pub_date_str = item.get("pubDate")
        news_date = today  # 기본값은 오늘
        
        if pub_date_str:
            try:
                from datetime import datetime
                from email.utils import parsedate_to_datetime
                pub_datetime = parsedate_to_datetime(pub_date_str)
                news_date = pub_datetime.date()
                
                # 2일 이상 된 뉴스는 차단
                days_old = (today - news_date).days
                if days_old > 2:
                    continue
            except Exception:
                # 파싱 실패하면 오늘 날짜로 저장
                news_date = today

        # 언론사 필터: 허용된 언론사가 아니면 저장 안 함
        from backend.app.utils.filters import extract_press_from_url, PRESS_BREAKING_CONFIG, EXCLUDE_KEYWORDS
        
        press = extract_press_from_url(url)
        
        # 1. 허용된 언론사가 아니면 차단
        if not press or press not in PRESS_BREAKING_CONFIG:
            blocked_by_press += 1
            # 처음 5개만 로그
            if blocked_by_press <= 5:
                print(f"  ❌ [{press or '알수없음'}] {title[:30]}...")
            continue
        
        # 2. 제외 키워드 있으면 차단
        should_exclude = False
        for keyword in EXCLUDE_KEYWORDS:
            if keyword in title:
                should_exclude = True
                break
        if should_exclude:
            blocked_by_keyword += 1
            continue

        # 3. pubDate 파싱 - 오늘 뉴스만
        pub_date_str = item.get("pubDate")
        news_date = today  # 기본값
        
        if pub_date_str:
            try:
                from datetime import datetime
                from email.utils import parsedate_to_datetime
                pub_dt = parsedate_to_datetime(pub_date_str)
                pub_date_only = pub_dt.date()
                
                # 오늘이 아니면 차단
                if pub_date_only != today:
                    continue
                
                news_date = pub_date_only  # 실제 발행일
            except:
                pass  # 파싱 실패하면 오늘로
        
        # 4. 속보 패턴 체크 (is_breaking 플래그용)
        is_breaking = is_breaking_news(title, url, category)
        
        print(f"  ✅ [{press}] {title[:40]}...")

        news = NewsDaily(
            date=news_date,  # 실제 발행일로 저장
            source=source,
            title=title,
            url=url,
            category=category,
            is_top=False,
            is_breaking=is_breaking,
            topic_key=topic_key,
            keywords=None,
            sentiment=None,
        )
        db.add(news)
        created.append(news)

    db.commit()
    for n in created:
        db.refresh(n)
    
    print(f"\n📊 결과:")
    print(f"  - 네이버에서 받음: {total_count}개")
    print(f"  - 언론사 필터 차단: {blocked_by_press}개")
    print(f"  - 키워드 필터 차단: {blocked_by_keyword}개")
    print(f"  - 중복 차단: {blocked_by_duplicate}개")
    print(f"  - ✅ 저장됨: {len(created)}개\n")

    return created


def build_daily_top5(db: Session) -> Dict[str, List[NewsDaily]]:
    """오늘 기준 4개 카테고리(사회/경제/문화/연예) Top5를 구성합니다."""
    today = date.today()

    # 매번 오늘 뉴스 전체 삭제 (최신 뉴스로 갱신)
    db.query(NewsDaily).filter(NewsDaily.date == today).delete()
    db.commit()

    # 카테고리별 뉴스 수집 (100개씩)
    society_items = fetch_naver_news_raw(query="사회 뉴스", display=100, sort="date")
    economy_items = fetch_naver_news_raw(query="경제 뉴스", display=100, sort="date")
    culture_items = fetch_naver_news_raw(query="문화 뉴스", display=100, sort="date")
    entertainment_items = fetch_naver_news_raw(query="연예 뉴스", display=100, sort="date")

    # DB에 저장
    save_news_items(db, society_items, category="society")
    save_news_items(db, economy_items, category="economy")
    save_news_items(db, culture_items, category="culture")
    save_news_items(db, entertainment_items, category="entertainment")

    # 기존 Top5 플래그 초기화
    for cat in ("society", "economy", "culture", "entertainment"):
        (
            db.query(NewsDaily)
            .filter(NewsDaily.date == today, NewsDaily.category == cat, NewsDaily.is_top.is_(True))
            .update({NewsDaily.is_top: False})
        )
    db.commit()

    result: Dict[str, List[NewsDaily]] = {}

    # 각 카테고리별 Top5 선정
    for cat in ("society", "economy", "culture", "entertainment"):
        top_list: List[NewsDaily] = (
            db.query(NewsDaily)
            .filter(NewsDaily.date == today, NewsDaily.category == cat)
            .order_by(NewsDaily.created_at.desc())
            .limit(5)
            .all()
        )
        for news in top_list:
            news.is_top = True
        db.commit()
        result[cat] = top_list

    return result


def collect_breaking_news(db: Session) -> List[NewsDaily]:
    """속보 기사 수집 및 새로 추가된 속보 리스트 반환."""
    items = fetch_naver_news_raw(query="속보", display=20, sort="date")
    created = save_news_items(db, items, category="breaking")
    return created
