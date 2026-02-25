import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.collectors.lineage.itembay import fetch_itembay
from backend.app.collectors.lineage.itemmania import fetch_itemmania
from backend.app.collectors.lineage.barotem import fetch_barotem
from backend.app.db.models import LineagePrice, LineagePriceSnapshot
from backend.app.services.lineage.price_aggregator import aggregate_by_server

logger = logging.getLogger(__name__)


def _calc_price_per_10k(amount: int, price: int) -> Optional[float]:
    if not amount or amount <= 0:
        return None
    return price / (amount / 10000)


def collect_all_offers(page_limit: int = 1) -> Dict[str, List[Dict]]:
    offers: List[Dict] = []
    source_offers = {
        "itembay": fetch_itembay(page_limit=page_limit),
        "itemmania": fetch_itemmania(page_limit=page_limit),
        "barotem": fetch_barotem(page_limit=page_limit),
    }
    for items in source_offers.values():
        offers.extend(items)

    normalized: List[Dict] = []
    for o in offers:
        try:
            amount = int(o.get("amount", 0))
            if amount < settings.LINEAGE_MIN_AMOUNT:
                continue
            price = int(o.get("price", 0))
            price_per_10k = o.get("price_per_10k")
            if price_per_10k is None:
                price_per_10k = _calc_price_per_10k(amount, price)
            if price_per_10k is None:
                continue
            normalized.append(
                {
                    "source": o.get("source"),
                    "server": o.get("server"),
                    "amount": amount,
                    "price": price,
                    "price_per_10k": price_per_10k,
                    "registered_at": o.get("registered_at"),
                }
            )
        except Exception:
            continue

    source_offers["normalized"] = normalized
    return source_offers


def save_offers(db: Session, offers: List[Dict]) -> None:
    for o in offers:
        db.add(
            LineagePrice(
                source=o.get("source"),
                server=o.get("server"),
                amount=o.get("amount"),
                price=o.get("price"),
                price_per_10k=o.get("price_per_10k"),
                registered_at=o.get("registered_at"),
            )
        )


def save_snapshots(db: Session, snapshots: Dict[str, Dict]) -> None:
    for server, data in snapshots.items():
        row = db.query(LineagePriceSnapshot).filter(LineagePriceSnapshot.server == server).first()
        if not row:
            row = LineagePriceSnapshot(server=server)
            db.add(row)
        row.median_price_per_10k = data.get("median")
        row.average_price_per_10k = data.get("average")
        row.min_price_per_10k = data.get("min")
        row.max_price_per_10k = data.get("max")
        row.updated_at = datetime.now(timezone.utc)


def cleanup_old_offers(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    deleted = db.query(LineagePrice).filter(LineagePrice.created_at < cutoff).delete()
    return deleted


def collect_and_store(db: Session, page_limit: int = 1) -> Dict[str, Dict]:
    source_offers = collect_all_offers(page_limit=page_limit)
    offers = source_offers.get("normalized", [])
    if not offers:
        return {}

    snapshots, _ = aggregate_by_server(offers)
    save_offers(db, offers)
    save_snapshots(db, snapshots)
    cleanup_old_offers(db)
    return {
        "snapshots": snapshots,
        "counts": {
            "itembay": len(source_offers.get("itembay", [])),
            "itemmania": len(source_offers.get("itemmania", [])),
            "barotem": len(source_offers.get("barotem", [])),
            "normalized": len(offers),
        },
    }


def get_latest_snapshots(db: Session) -> List[LineagePriceSnapshot]:
    return db.query(LineagePriceSnapshot).order_by(LineagePriceSnapshot.server.asc()).all()


def get_server_offers(db: Session, server: str, limit: int = 5) -> List[LineagePrice]:
    return (
        db.query(LineagePrice)
        .filter(LineagePrice.server == server)
        .order_by(LineagePrice.created_at.desc())
        .limit(limit)
        .all()
    )
