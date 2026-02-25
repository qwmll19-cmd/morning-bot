import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def fetch_barotem(server: Optional[str] = None, page_limit: int = 1) -> List[Dict]:
    """
    바로템 매물 수집 (스켈레톤)
    반환 형식:
      {
        "source": "barotem",
        "server": str,
        "amount": int,
        "price": int,
        "registered_at": str
      }
    """
    logger.warning("barotem collector is not implemented yet")
    return []
