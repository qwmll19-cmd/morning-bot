#!/usr/bin/env python3
"""
오늘 뉴스 중복 정리 (URL/제목 기준) + Top 랭킹 재계산
"""
from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db.session import SessionLocal
from backend.app.db.models import NewsDaily
from backend.app.collectors.news_collector_v3 import build_daily_rankings
from backend.app.utils.dedup import normalize_url, extract_short_topic_key


def main() -> None:
    db = SessionLocal()
    today = date.today()
    try:
        news_list = (
            db.query(NewsDaily)
            .filter(NewsDaily.date == today)
            .order_by(NewsDaily.hot_score.desc(), NewsDaily.created_at.desc())
            .all()
        )

        seen = set()
        to_delete = []

        for news in news_list:
            url_key = normalize_url(news.url or "")
            if url_key:
                key = f"url:{url_key}"
            else:
                key = f"title:{extract_short_topic_key(news.title or '')}"

            if key in seen:
                to_delete.append(news)
            else:
                seen.add(key)

        for news in to_delete:
            db.delete(news)

        db.commit()

        # Top 랭킹 재계산
        build_daily_rankings(db)

        print(f"deleted={len(to_delete)} remaining={len(news_list) - len(to_delete)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
