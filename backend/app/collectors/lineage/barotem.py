import logging
import os
import re
import time
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from backend.app.config import settings
from backend.app.services.lineage.servers import KNOWN_SERVERS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}

_AMOUNT_SINGLE_RE = re.compile(r"([0-9,]+)만\s*아데나")
_AMOUNT_MIN_RE = re.compile(r"최소\s*([0-9,]+)만\s*아데나")
_AMOUNT_MAX_RE = re.compile(r"최대\s*([0-9,]+)만\s*아데나")
_PRICE_PER_10K_RE = re.compile(r"만당\s*([0-9,]+)원|1만당\s*([0-9,]+)원")
_TIME_RE = re.compile(r"(\d+분전|\d+시간전|\d+일전|\d{2}/\d{2})")


def _detect_server(line: str) -> Optional[str]:
    for s in KNOWN_SERVERS:
        if s in line:
            return s
    return None


def _pick_amount(card_text: str) -> Optional[int]:
    """단일 수량 또는 최소 수량을 선택"""
    m = _AMOUNT_SINGLE_RE.search(card_text)
    if m:
        return int(m.group(1).replace(",", "")) * 10000
    m = _AMOUNT_MIN_RE.search(card_text)
    if m:
        return int(m.group(1).replace(",", "")) * 10000
    return None


def _extract_card_texts(soup: BeautifulSoup) -> List[str]:
    texts: List[str] = []
    for node in soup.find_all(string=_PRICE_PER_10K_RE):
        cur = node
        best = None
        for _ in range(4):
            if not cur:
                break
            parent = cur.parent if hasattr(cur, "parent") else None
            if not parent:
                break
            t = parent.get_text(" ", strip=True)
            if "만당" in t and ("아데나" in t or "아덴" in t or "게임머니" in t):
                if best is None or len(t) > len(best):
                    best = t
            cur = parent
        if best:
            texts.append(best)
    return list(dict.fromkeys(texts))  # de-dup preserve order


def fetch_barotem(server: Optional[str] = None, page_limit: int = 1) -> List[Dict]:
    """
    바로템 매물 수집
    환경변수 BAROTEM_TABLE_URL을 사용 (예: https://www.barotem.com/product/productTable/xxxx)
    """
    base_url = os.getenv("BAROTEM_TABLE_URL", "")
    if not base_url:
        logger.warning("BAROTEM_TABLE_URL is not set")
        return []

    offers: List[Dict] = []
    base_params = {
        "sell": "sell",
        "category": "",
        "display": "1",
        "orderby": "1",
        "minpay": "",
        "maxpay": "",
        "search_word": "",
        "brand": "",
        "buyloc": "",
    }

    # 세션 쿠키를 먼저 획득해서 403 가능성을 낮춤
    list_url = base_url.replace("/productTable/", "/lists/")
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(list_url, headers={"Referer": list_url}, params=dict(base_params, page="1"), timeout=15)
    except Exception as e:
        logger.warning("barotem list prefetch failed: %s", e)

    for page in range(1, page_limit + 1):
        params = dict(base_params)
        params["page"] = str(page)
        try:
            res = session.get(
                base_url,
                headers={
                    "Referer": list_url,
                    "X-Requested-With": "XMLHttpRequest",
                },
                params=params,
                timeout=15,
            )
            if res.status_code == 403:
                logger.warning("barotem 403 forbidden (page=%s).", page)
                break
            res.raise_for_status()
        except Exception as e:
            logger.warning("barotem request failed: %s", e)
            break

        soup = BeautifulSoup(res.text, "html.parser")
        card_texts = _extract_card_texts(soup)

        for card_text in card_texts:
            if "수량 부족" in card_text or "거래완료" in card_text:
                continue
            detected = _detect_server(card_text)
            if server and detected != server:
                continue
            if not detected:
                continue
            amount = _pick_amount(card_text)
            price_per_10k_match = _PRICE_PER_10K_RE.search(card_text)
            if not amount or not price_per_10k_match:
                continue
            per_10k_str = price_per_10k_match.group(1) or price_per_10k_match.group(2)
            price_per_10k = int(per_10k_str.replace(",", ""))

            max_price = settings.LINEAGE_MAX_PRICE_PER_10K
            if max_price and price_per_10k > max_price:
                continue

            price = int(price_per_10k * (amount / 10000))
            registered_at = None
            time_match = _TIME_RE.search(card_text)
            if time_match:
                registered_at = time_match.group(1)

            offers.append(
                {
                    "source": "barotem",
                    "server": detected,
                    "amount": amount,
                    "price": price,
                    "price_per_10k": price_per_10k,
                    "registered_at": registered_at,
                }
            )

        logger.info("barotem page %s parsed offers=%s", page, len(offers))
        time.sleep(1.5)

    return offers
