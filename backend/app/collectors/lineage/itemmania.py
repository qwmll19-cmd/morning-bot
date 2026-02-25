import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def fetch_itemmania(server: Optional[str] = None, page_limit: int = 1) -> List[Dict]:
    """
    아이템매니아 매물 수집 (스켈레톤)
    반환 형식:
      {
        "source": "itemmania",
        "server": str,
        "amount": int,
        "price": int,
        "registered_at": str
      }
    """
    logger.warning("itemmania collector is not implemented yet")
    return []
