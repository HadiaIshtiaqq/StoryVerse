"""Shared helpers: lookups, ownership, row locking, atomic resource movements, outbox."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import GameError, forbidden, not_found
from app.game.rules import RESOURCES
from app.models import Kingdom, LedgerEntry, Notification, Player, Transaction, World


# --- lookups -------------------------------------------------------------------------------
def get_world(db: Session, world_id: str) -> World:
    world = db.get(World, world_id)
    if world is None:
        raise not_found("World")
    return world


def get_kingdom(db: Session, kingdom_id: str) -> Kingdom:
    kingdom = db.get(Kingdom, kingdom_id)
    if kingdom is None:
        raise not_found("Kingdom")
    return kingdom


def require_owned_kingdom(db: Session, player: Player, kingdom_id: str) -> Kingdom:
    kingdom = get_kingdom(db, kingdom_id)
    if kingdom.owner_id != player.id:
        raise forbidden()
    return kingdom


def require_same_world(a: Kingdom, b: Kingdom) -> None:
    if a.world_id != b.world_id:
        raise GameError("Those kingdoms are in different worlds")
    if a.id == b.id:
        raise GameError("A kingdom cannot do that with itself")


def lock_kingdoms(db: Session, *kingdom_ids: str) -> dict[str, Kingdom]:
    """SELECT ... FOR UPDATE in a fixed order (prevents deadlocks). No-op lock on SQLite."""
    ids = sorted(set(kingdom_ids))
    rows = db.execute(
        select(Kingdom).where(Kingdom.id.in_(ids)).order_by(Kingdom.id).with_for_update().execution_options(populate_existing=True)
    ).scalars().all()
    found = {k.id: k for k in rows}
    if len(found) != len(ids):
        raise not_found("Kingdom")
    return found


def resources_of(k: Kingdom) -> dict[str, int]:
    return {r: getattr(k, r) for r in RESOURCES}


# --- transactions & ledger -----------------------------------------------------------------
def open_transaction(db: Session, world: World, transaction_type: str, sender: Kingdom | None = None,
                     receiver: Kingdom | None = None, ref_id: str | None = None) -> Transaction:
    txn = Transaction(world_id=world.id, transaction_type=transaction_type,
                      sender_kingdom_id=sender.id if sender else None,
                      receiver_kingdom_id=receiver.id if receiver else None,
                      ref_id=ref_id, turn=world.turn)
    db.add(txn)
    db.flush()
    return txn


def require_resources(k: Kingdom, cost: dict[str, int]) -> None:
    for res, amount in cost.items():
        have = getattr(k, res)
        if have < amount:
            raise GameError(f"Insufficient {res}: need {amount}, have {have}", code="insufficient_resources",
                            details={"resource": res, "need": amount, "have": have})


def apply(db: Session, txn: Transaction, k: Kingdom, deltas: dict[str, int], allow_clamp: bool = False) -> dict[str, int]:
    """Apply resource deltas to a (locked) kingdom and write ledger lines.

    Raises if any balance would go negative, unless allow_clamp (used only by turn upkeep).
    Returns the deltas actually applied.
    """
    applied: dict[str, int] = {}
    if not allow_clamp:
        require_resources(k, {r: -d for r, d in deltas.items() if d < 0})
    for res, delta in deltas.items():
        if res not in RESOURCES or delta == 0:
            continue
        current = getattr(k, res)
        new = max(0, current + delta) if allow_clamp else current + delta
        actual = new - current
        if actual == 0:
            continue
        setattr(k, res, new)
        applied[res] = actual
        db.add(LedgerEntry(transaction_id=txn.id, kingdom_id=k.id, resource=res, delta=actual,
                           balance_after=new, turn=txn.turn))
    emit_kingdom_update(db, k)
    return applied


# --- outbox (flushed to WebSockets after commit) -------------------------------------------
def emit(db: Session, event: dict) -> None:
    db.info.setdefault("outbox", []).append(event)


def emit_kingdom_update(db: Session, k: Kingdom) -> None:
    emit(db, {"type": "kingdom_updated", "world_id": k.world_id, "private_to": k.id,
              "kingdom_id": k.id, "resources": resources_of(k), "population": k.population, "soldiers": k.soldiers})


def notify(db: Session, world: World, kingdom_id: str, kind: str, text: str,
           ref_type: str | None = None, ref_id: str | None = None) -> None:
    n = Notification(world_id=world.id, kingdom_id=kingdom_id, kind=kind, text=text,
                     ref_type=ref_type, ref_id=ref_id, turn=world.turn)
    db.add(n)
    db.flush()
    emit(db, {"type": "notification", "world_id": world.id, "private_to": kingdom_id,
              "notification": {"id": n.id, "kind": kind, "text": text, "ref_type": ref_type, "ref_id": ref_id, "turn": world.turn}})
