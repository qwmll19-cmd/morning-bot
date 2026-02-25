import logging
import os
import re
import time
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from backend.app.services.lineage.servers import KNOWN_SERVERS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

_AMOUNT_RE = re.compile(r"([0-9,]+)만")
_PRICE_RE = re.compile(r"([0-9,]+)원")
_TIME_RE = re.compile(r"(\d+분전|\d+시간전|\d+일전|\d{2}/\d{2})")


def _detect_server(line: str) -> Optional[str]:
    for s in KNOWN_SERVERS:
        if s in line:
            return s
    return None


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
        "opt1": "24489",
        "opt2": "",
        "opt3": "",
        "opt4": "",
        "opt5": "",
        "opt6": "",
        "opt7": "",
        "opt8": "",
        "opt9": "",
        "opt10": "",
    }

    for page in range(1, page_limit + 1):
        params = dict(base_params)
        params["page"] = str(page)
        try:
            res = requests.get(base_url, headers=HEADERS, params=params, timeout=15)
            res.raise_for_status()
        except Exception as e:
            logger.warning("barotem request failed: %s", e)
            break

        soup = BeautifulSoup(res.text, "html.parser")
        lines = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]

        for line in lines:
            if "아덴" not in line and "아데나" not in line and "게임머니" not in line:
                continue
            detected = _detect_server(line)
            if server and detected != server:
                continue
            if not detected:
                continue
            amount_match = _AMOUNT_RE.search(line)
            price_match = _PRICE_RE.search(line)
            if not amount_match or not price_match:
                continue
            amount = int(amount_match.group(1).replace(",", "")) * 10000
            price = int(price_match.group(1).replace(",", ""))
            registered_at = None
            time_match = _TIME_RE.search(line)
            if time_match:
                registered_at = time_match.group(1)

            offers.append(
                {
                    "source": "barotem",
                    "server": detected,
                    "amount": amount,
                    "price": price,
                    "registered_at": registered_at,
                }
            )

        time.sleep(1.5)

    return offers
