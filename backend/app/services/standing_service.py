"""Standing between kingdoms (feature B14): a symmetric score in [-100, 100] that only the
server changes, and only in response to validated actions."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.game.rules import (GIFT_GAIN_CAP_PER_TURN, GIFT_TIER_FRACTIONS, INITIAL_STANDINGS, KINGDOM_BY_NAME,
                            TRADE_GAIN_CAP_PER_TURN, band)
from app.models import Kingdom, Relation, RelationEvent, World
from app.services.common import emit


def pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def get_relation(db: Session, world_id: str, a: str, b: str) -> Relation:
    ka, kb = pair(a, b)
    rel = db.get(Relation, (ka, kb))
    if rel is None:
        rel = Relation(world_id=world_id, kingdom_a=ka, kingdom_b=kb, score=0)
        db.add(rel)
        db.flush()
    return rel


def score(db: Session, world_id: str, a: str, b: str) -> int:
    return get_relation(db, world_id, a, b).score


def seed_world(db: Session, world: World, kingdoms: list[Kingdom]) -> None:
    for i, k1 in enumerate(kingdoms):
        for k2 in kingdoms[i + 1:]:
            initial = INITIAL_STANDINGS.get((k1.name, k2.name), INITIAL_STANDINGS.get((k2.name, k1.name), 10))
            get_relation(db, world.id, k1.id, k2.id).score = initial


def _multiplier(a: Kingdom, b: Kingdom) -> float:
    m = 1.0
    for k in (a, b):
        m = max(m, KINGDOM_BY_NAME.get(k.name, {}).get("standing_gain_multiplier", 1.0))
    return m


def change(db: Session, world: World, a: Kingdom, b: Kingdom, delta: int, reason: str,
           kind: str | None = None, transaction_id: str | None = None) -> int:
    """Apply a standing change with per-turn caps. Returns the delta actually applied."""
    rel = get_relation(db, world.id, a.id, b.id)
    if rel.counters_turn != world.turn:
        rel.counters_turn, rel.trade_gain_this_turn, rel.gift_gain_this_turn = world.turn, 0, 0
    if delta > 0:
        delta = int(round(delta * _multiplier(a, b)))
        if kind == "trade":
            delta = min(delta, max(0, TRADE_GAIN_CAP_PER_TURN - rel.trade_gain_this_turn))
            rel.trade_gain_this_turn += delta
        elif kind == "gift":
            delta = min(delta, max(0, GIFT_GAIN_CAP_PER_TURN - rel.gift_gain_this_turn))
            rel.gift_gain_this_turn += delta
    new = max(-100, min(100, rel.score + delta))
    actual = new - rel.score
    if actual == 0:
        return 0
    old_band = band(rel.score)
    rel.score, rel.last_delta, rel.updated_turn = new, actual, world.turn
    db.add(RelationEvent(world_id=world.id, kingdom_a=rel.kingdom_a, kingdom_b=rel.kingdom_b, delta=actual,
                         reason=reason, transaction_id=transaction_id, turn=world.turn))
    payload = {"type": "standing_changed", "world_id": world.id, "kingdoms": [a.id, b.id], "score": new,
               "band": band(new), "previous_band": old_band, "delta": actual, "reason": reason}
    for k in (a, b):
        emit(db, {**payload, "private_to": k.id})
    return actual


def decay(db: Session, world: World, protected_pairs: set[tuple[str, str]]) -> None:
    """Drift 1 point toward 0 each turn, except between allies."""
    for rel in db.execute(select(Relation).where(Relation.world_id == world.id)).scalars():
        if (rel.kingdom_a, rel.kingdom_b) in protected_pairs or rel.score == 0:
            continue
        rel.score += -1 if rel.score > 0 else 1


def recent_reasons(db: Session, world_id: str, a: str, b: str, limit: int = 5) -> list[dict]:
    ka, kb = pair(a, b)
    rows = db.execute(select(RelationEvent).where(RelationEvent.world_id == world_id, RelationEvent.kingdom_a == ka,
                                                  RelationEvent.kingdom_b == kb)
                      .order_by(RelationEvent.created_at.desc()).limit(limit)).scalars()
    return [{"delta": r.delta, "reason": r.reason, "turn": r.turn} for r in rows]


def relations_rows(db: Session, kingdom_id: str) -> list[Relation]:
    return list(db.execute(select(Relation).where(or_(Relation.kingdom_a == kingdom_id,
                                                      Relation.kingdom_b == kingdom_id))).scalars())


# --- gifts -----------------------------------------------------------------------------------
def gift_gain(gift_gold: int, receiver_gold: int) -> int:
    """Diminishing returns: a gift matters relative to the receiver's wealth."""
    if gift_gold <= 0:
        return 0
    return int(round(20 * gift_gold / (gift_gold + 0.2 * max(receiver_gold, 1))))


def gift_tiers(giver_gold: int) -> list[int]:
    return [int(round(giver_gold * f)) for f in GIFT_TIER_FRACTIONS]
