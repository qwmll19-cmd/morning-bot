import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def fetch_itembay(server: Optional[str] = None, page_limit: int = 1) -> List[Dict]:
    """
    아이템베이 매물 수집 (스켈레톤)
    반환 형식:
      {
        "source": "itembay",
        "server": str,
        "amount": int,
        "price": int,
        "registered_at": str
      }
    """
    logger.warning("itembay collector is not implemented yet")
    return []
