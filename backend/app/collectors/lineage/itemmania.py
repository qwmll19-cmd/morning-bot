import logging
import re
import time
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from backend.app.services.lineage.servers import KNOWN_SERVERS

logger = logging.getLogger(__name__)

BASE_URL = "https://www.itemmania.com/sell/list.html?search_game=5913"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

_AMOUNT_BLOCK_RE = re.compile(r"\[수량\s*:\s*([0-9,]+)만\]")
_AMOUNT_RE = re.compile(r"([0-9,]+)만")
_PRICE_RE = re.compile(r"([0-9,]+)원")
_PRICE_PER_10K_RE = re.compile(r"만당\s*([0-9,]+)원|1만당\s*([0-9,]+)원")


def _parse_amount(line: str) -> Optional[int]:
    m = _AMOUNT_BLOCK_RE.search(line)
    if m:
        return int(m.group(1).replace(",", "")) * 10000
    m = _AMOUNT_RE.search(line)
    if m:
        return int(m.group(1).replace(",", "")) * 10000
    return None


def _parse_price(line: str) -> Optional[int]:
    matches = _PRICE_RE.findall(line)
    if not matches:
        return None
    return int(matches[-1].replace(",", ""))


def _detect_server(line: str) -> Optional[str]:
    for s in KNOWN_SERVERS:
        if s in line:
            return s
    return None


def fetch_itemmania(server: Optional[str] = None, page_limit: int = 1) -> List[Dict]:
    """
    아이템매니아 매물 수집
    """
    offers: List[Dict] = []

    for page in range(1, page_limit + 1):
        url = BASE_URL
        if page > 1:
            url = f"{BASE_URL}&page={page}"

        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            res.raise_for_status()
        except Exception as e:
            logger.warning("itemmania request failed: %s", e)
            break

        soup = BeautifulSoup(res.text, "html.parser")
        lines = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]

        for line in lines:
            if "아덴" not in line and "아데나" not in line and "게임머니" not in line:
                continue
            amt = _parse_amount(line)
            price_per_10k_match = _PRICE_PER_10K_RE.search(line)
            if not amt or not price_per_10k_match:
                continue
            detected = _detect_server(line)
            if server and detected != server:
                continue
            if not detected:
                continue

            per_10k_str = price_per_10k_match.group(1) or price_per_10k_match.group(2)
            price_per_10k = int(per_10k_str.replace(",", ""))
            price = int(price_per_10k * (amt / 10000))

            offers.append(
                {
                    "source": "itemmania",
                    "server": detected,
                    "amount": amt,
                    "price": price,
                    "price_per_10k": price_per_10k,
                    "registered_at": None,
                }
            )

        time.sleep(1.5)

    return offers
