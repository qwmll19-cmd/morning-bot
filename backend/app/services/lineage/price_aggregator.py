import statistics
from typing import Dict, List, Tuple

from backend.app.config import settings


def _filter_outliers(values: List[float]) -> List[float]:
    if not values:
        return values
    med = statistics.median(values)
    factor = settings.LINEAGE_OUTLIER_FACTOR
    low = med / factor
    high = med * factor
    return [v for v in values if low <= v <= high]


def aggregate_by_server(offers: List[Dict]) -> Tuple[Dict[str, Dict], Dict[str, List[Dict]]]:
    """
    returns:
      snapshots: {server: {median, average, min, max, count}}
      by_server: {server: [offer,...]}
    """
    by_server: Dict[str, List[Dict]] = {}
    for offer in offers:
        server = offer.get("server")
        if not server:
            continue
        by_server.setdefault(server, []).append(offer)

    snapshots: Dict[str, Dict] = {}
    for server, items in by_server.items():
        values = [i["price_per_10k"] for i in items if i.get("price_per_10k") is not None]
        values = _filter_outliers(values)
        if not values:
            continue
        snapshots[server] = {
            "median": statistics.median(values),
            "average": statistics.mean(values),
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }
    return snapshots, by_server
