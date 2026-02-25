import logging
import re
import time
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from backend.app.services.lineage.servers import KNOWN_SERVERS

logger = logging.getLogger(__name__)

BASE_URL = "https://www.itembay.com/item/sell/game-3828"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


_AMOUNT_RANGE_RE = re.compile(r"([0-9,]+)만\s*~\s*([0-9,]+)만")
_PRICE_RE = re.compile(r"([0-9,]+)원")
_PRICE_PER_10K_RE = re.compile(r"만당\s*([0-9,]+)원|1만당\s*([0-9,]+)원")
_TIME_RE = re.compile(r"(\d+분전|\d+시간전|\d+일전|\d{2}/\d{2})")


def _parse_amount(line: str) -> Optional[int]:
    m = _AMOUNT_RANGE_RE.search(line)
    if not m:
        return None
    min_amount = int(m.group(1).replace(",", ""))
    return min_amount * 10000


def _parse_price(line: str) -> Optional[int]:
    m = _PRICE_RE.search(line)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def _parse_time(line: str) -> Optional[str]:
    m = _TIME_RE.search(line)
    return m.group(1) if m else None


def fetch_itembay(server: Optional[str] = None, page_limit: int = 1) -> List[Dict]:
    """
    아이템베이 매물 수집
    반환 형식:
      {
        "source": "itembay",
        "server": str,
        "amount": int,
        "price": int,
        "registered_at": str
      }
    """
    offers: List[Dict] = []

    for page in range(1, page_limit + 1):
        url = BASE_URL
        if page > 1:
            url = f"{BASE_URL}?page={page}"

        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            res.raise_for_status()
        except Exception as e:
            logger.warning("itembay request failed: %s", e)
            break

        soup = BeautifulSoup(res.text, "html.parser")
        lines = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]

        current_server: Optional[str] = None
        current_is_money = False
        i = 0
        while i < len(lines):
            line = lines[i]

            if line in KNOWN_SERVERS:
                current_server = line
                i += 1
                continue

            if line == "게임머니":
                current_is_money = True
                i += 1
                continue
            if line in ("아이템", "계정", "기타"):
                current_is_money = False
                i += 1
                continue

            if current_server and current_is_money and "미리보기버튼" in line:
                amount = _parse_amount(line)
                price_per_10k_match = _PRICE_PER_10K_RE.search(line)
                registered_at = _parse_time(line)

                if price_per_10k_match is None and i + 1 < len(lines):
                    price_per_10k_match = _PRICE_PER_10K_RE.search(lines[i + 1])
                if registered_at is None and i + 1 < len(lines):
                    registered_at = _parse_time(lines[i + 1])

                if amount and price_per_10k_match:
                    per_10k_str = price_per_10k_match.group(1) or price_per_10k_match.group(2)
                    price_per_10k = int(per_10k_str.replace(",", ""))
                    total_price = int(price_per_10k * (amount / 10000))
                    offers.append(
                        {
                            "source": "itembay",
                            "server": current_server,
                            "amount": amount,
                            "price": total_price,
                            "price_per_10k": price_per_10k,
                            "registered_at": registered_at,
                        }
                    )

            i += 1

        logger.info("itembay page %s parsed offers=%s", page, len(offers))
        time.sleep(1.5)

    return offers
