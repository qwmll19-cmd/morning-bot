from __future__ import annotations

from datetime import date as date_type, datetime
import logging
import re
import time
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from backend.app.db.models import KoreaMetalDaily

logger = logging.getLogger(__name__)

KOREAGOLDX_URLS = {
    "gold": "https://www.koreagoldx.co.kr/price/gold",
    "silver": "https://www.koreagoldx.co.kr/price/silver",
    "platinum": "https://www.koreagoldx.co.kr/price/platinum",
}

KOREAGOLDX_TYPES = {
    "gold": "Au",
    "silver": "Ag",
    "platinum": "Pt",
}

KOREAGOLDX_API_URL = "https://www.koreagoldx.co.kr/api/price/chart/list"

KOREAGOLDX_FIELDS = {
    "gold": ("s_pure", "p_pure", "p_18k", "p_14k"),
    "silver": ("s_silver", "p_silver", None, None),
    "platinum": ("s_white", "p_white", None, None),
}

def _get_with_retry(
    url: str,
    timeout: float = 12.0,
    retries: int = 3,
    backoff: float = 1.5,
) -> Optional[httpx.Response]:
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp
        except Exception as exc:
            if attempt >= retries:
                logger.error("KoreaGoldX HTTP 실패 %s attempt %s/%s: %s", url, attempt, retries, exc)
                return None
            wait = backoff * attempt
            logger.warning("KoreaGoldX HTTP 재시도 %s attempt %s/%s -> %.1fs", url, attempt, retries, wait)
            time.sleep(wait)


def _post_with_retry(
    url: str,
    json_body: Dict[str, Any],
    timeout: float = 12.0,
    retries: int = 3,
    backoff: float = 1.5,
) -> Optional[httpx.Response]:
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, json=json_body)
                resp.raise_for_status()
                return resp
        except Exception as exc:
            if attempt >= retries:
                logger.error("KoreaGoldX HTTP 실패 %s attempt %s/%s: %s", url, attempt, retries, exc)
                return None
            wait = backoff * attempt
            logger.warning("KoreaGoldX HTTP 재시도 %s attempt %s/%s -> %.1fs", url, attempt, retries, wait)
            time.sleep(wait)


def _to_int(text: str) -> Optional[int]:
    digits = re.sub(r"[^0-9]", "", text or "")
    if not digits:
        return None
    try:
        return int(digits)
    except Exception:
        return None


def _to_int_value(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return _to_int(str(value))


def _parse_date(text: str) -> Optional[date_type]:
    cleaned = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%y.%m.%d", "%y-%m-%d", "%y/%m/%d"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except Exception:
            continue
    return None


def parse_koreagoldx(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("div.tabulator-row")
    data = []
    for row in rows:
        get = lambda f: row.select_one(f'div.tabulator-cell[tabulator-field="{f}"]')
        date_cell = get("date")
        s_pure = get("s_pure")
        p_pure = get("p_pure")
        p_18k = get("p_18k")
        p_14k = get("p_14k")

        if not date_cell or not s_pure or not p_pure:
            continue

        data.append({
            "date": date_cell.text.strip(),
            "buy_3_75g": _to_int(s_pure.text),
            "sell_3_75g": _to_int(p_pure.text),
            "sell_18k": _to_int(p_18k.text) if p_18k else None,
            "sell_14k": _to_int(p_14k.text) if p_14k else None,
        })
    return data


def _subtract_months(d: date_type, months: int) -> date_type:
    year = d.year
    month = d.month - months
    while month <= 0:
        month += 12
        year -= 1
    last_day = [
        31,
        29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31
    ][month - 1]
    day = min(d.day, last_day)
    return date_type(year, month, day)


def fetch_koreagoldx_latest(metal: str) -> Optional[Dict[str, Any]]:
    type_code = KOREAGOLDX_TYPES.get(metal)
    if not type_code:
        return None

    today = date_type.today()
    start = _subtract_months(today, 5)
    payload = {
        "srchDt": "5M",
        "type": type_code,
        "dataDateStart": start.strftime("%Y.%m.%d"),
        "dataDateEnd": today.strftime("%Y.%m.%d"),
    }

    resp = _post_with_retry(KOREAGOLDX_API_URL, payload)
    if resp is None:
        return None

    try:
        data = resp.json()
    except Exception as exc:
        logger.error("KoreaGoldX API 응답 파싱 실패: %s", exc)
        return None

    rows = data.get("list") or []
    if not rows:
        logger.warning("KoreaGoldX API 결과 없음: %s", metal)
        return None

    def _parse_dt(text: str) -> Optional[datetime]:
        cleaned = (text or "").strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(cleaned, fmt)
            except Exception:
                continue
        return None

    latest = None
    latest_dt = None
    for row in rows:
        dt = _parse_dt(str(row.get("date", "")))
        if dt and (latest_dt is None or dt > latest_dt):
            latest = row
            latest_dt = dt

    if not latest:
        return None

    date_text = latest.get("date")
    parsed_date = latest_dt.date() if latest_dt else _parse_date(str(date_text))
    buy_field, sell_field, sell_18k_field, sell_14k_field = KOREAGOLDX_FIELDS.get(
        metal, ("s_pure", "p_pure", "p_18k", "p_14k")
    )
    return {
        "date": parsed_date.isoformat() if parsed_date else str(date_text),
        "buy_3_75g": _to_int_value(latest.get(buy_field)) if buy_field else None,
        "sell_3_75g": _to_int_value(latest.get(sell_field)) if sell_field else None,
        "sell_18k": _to_int_value(latest.get(sell_18k_field)) if sell_18k_field else None,
        "sell_14k": _to_int_value(latest.get(sell_14k_field)) if sell_14k_field else None,
        "source_url": KOREAGOLDX_API_URL,
    }


def collect_korea_metal_daily(db: Session) -> List[KoreaMetalDaily]:
    collected: List[KoreaMetalDaily] = []

    for metal in KOREAGOLDX_URLS.keys():
        latest = fetch_koreagoldx_latest(metal)
        if not latest:
            continue

        date_text = latest.get("date")
        parsed_date = _parse_date(date_text)

        existing = (
            db.query(KoreaMetalDaily)
            .filter(KoreaMetalDaily.metal == metal)
            .order_by(KoreaMetalDaily.date.desc(), KoreaMetalDaily.id.desc())
            .first()
        )

        def _matches(row: KoreaMetalDaily) -> bool:
            if parsed_date:
                return row.date == parsed_date
            return row.date is None and row.date_text == date_text

        def _apply(row: KoreaMetalDaily) -> None:
            row.date = parsed_date
            row.date_text = date_text
            row.buy_3_75g = latest.get("buy_3_75g")
            row.sell_3_75g = latest.get("sell_3_75g")
            row.sell_18k = latest.get("sell_18k")
            row.sell_14k = latest.get("sell_14k")
            row.source_url = latest.get("source_url")

        if existing and _matches(existing):
            before = (
                existing.buy_3_75g,
                existing.sell_3_75g,
                existing.sell_18k,
                existing.sell_14k,
                existing.source_url,
            )
            _apply(existing)
            after = (
                existing.buy_3_75g,
                existing.sell_3_75g,
                existing.sell_18k,
                existing.sell_14k,
                existing.source_url,
            )
            if before != after:
                collected.append(existing)
        else:
            row = KoreaMetalDaily(metal=metal)
            _apply(row)
            db.add(row)
            collected.append(row)

    if collected:
        db.commit()
        for row in collected:
            db.refresh(row)

    return collected
