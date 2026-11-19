from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import commit
from app.database import get_db
from app.models import Alliance, Kingdom, LedgerEntry, Loan, Notification, Player, StoryEvent, TradeOffer, Transaction, War
from app.schemas import DecreeClaimIn
from app.security import get_current_player
from app.services import (court_service, diplomacy_service, economy_service, kingdom_service, prestige_service, story_service,
                          ultimatum_service)
from app.services.common import get_kingdom, get_world, require_owned_kingdom, resources_of
from app.services.military_service import serialize_war
from app.services import turn_service
from app.services.turn_service import kingdom_yield

router = APIRouter(tags=["kingdoms"])


def kingdom_public(k: Kingdom, db: Session) -> dict:
    """What every ruler may see. Exact treasuries and armies stay private (spec §6.2)."""
    return {"id": k.id, "world_id": k.world_id, "name": k.name, "title": k.title, "specialization": k.specialization,
            "ruler_name": k.ruler_name, "emblem_key": k.emblem_key, "color": k.color, "map_x": k.map_x, "map_y": k.map_y,
            "is_npc": k.is_npc, "has_ruler": k.owner_id is not None, "prestige": k.prestige, "population": k.population,
            "army_estimate": int(round(k.soldiers, -1)), "betrayals": k.betrayals,
            "building_count": len(kingdom_service.buildings_of(db, k.id))}


def kingdom_private(k: Kingdom, db: Session) -> dict:
    return {**kingdom_public(k, db), "resources": resources_of(k), "soldiers": k.soldiers,
            "prestige_breakdown": k.prestige_breakdown, "prestige_penalty": k.prestige_penalty,
            "yield_per_turn": kingdom_yield(db, k)}


def _notification(n: Notification) -> dict:
    return {"id": n.id, "kind": n.kind, "text": n.text, "ref_type": n.ref_type, "ref_id": n.ref_id, "read": n.read,
            "turn": n.turn, "created_at": n.created_at.isoformat() if n.created_at else None}


@router.get("/kingdoms/{kingdom_id}")
def get_kingdom_view(kingdom_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    k = get_kingdom(db, kingdom_id)
    return kingdom_private(k, db) if k.owner_id == player.id else kingdom_public(k, db)


@router.get("/kingdoms/{kingdom_id}/resources")
def get_resources(kingdom_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    k = require_owned_kingdom(db, player, kingdom_id)
    return {**resources_of(k), "population": k.population, "soldiers": k.soldiers, "yield_per_turn": kingdom_yield(db, k)}


@router.get("/kingdoms/{kingdom_id}/buildings")
def get_buildings(kingdom_id: str, _: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    get_kingdom(db, kingdom_id)
    return [kingdom_service.serialize_building(b) for b in kingdom_service.buildings_of(db, kingdom_id)]


@router.get("/kingdoms/{kingdom_id}/ledger")
def get_ledger(kingdom_id: str, limit: int = Query(100, le=500), player: Player = Depends(get_current_player),
               db: Session = Depends(get_db)):
    """Transaction history (FR-10): every resource movement with the balance after it."""
    require_owned_kingdom(db, player, kingdom_id)
    rows = db.execute(select(LedgerEntry, Transaction).join(Transaction, LedgerEntry.transaction_id == Transaction.id)
                      .where(LedgerEntry.kingdom_id == kingdom_id).order_by(LedgerEntry.created_at.desc()).limit(limit)).all()
    return [{"transaction_id": t.id, "type": t.transaction_type, "resource": e.resource, "delta": e.delta,
             "balance_after": e.balance_after, "turn": e.turn, "counterparty_id":
                 t.receiver_kingdom_id if t.sender_kingdom_id == kingdom_id else t.sender_kingdom_id,
             "created_at": e.created_at.isoformat()} for e, t in rows]


@router.get("/kingdoms/{kingdom_id}/notifications")
def get_notifications(kingdom_id: str, unread_only: bool = False, mark_read: bool = False,
                      player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    require_owned_kingdom(db, player, kingdom_id)
    q = select(Notification).where(Notification.kingdom_id == kingdom_id)
    if unread_only:
        q = q.where(Notification.read.is_(False))
    rows = list(db.execute(q.order_by(Notification.created_at.desc()).limit(100)).scalars())
    out = [_notification(n) for n in rows]
    if mark_read:
        for n in rows:
            n.read = True
        commit(db)
    return out


@router.get("/kingdoms/{kingdom_id}/since")
def while_you_were_away(kingdom_id: str, turn: int, player: Player = Depends(get_current_player),
                        db: Session = Depends(get_db)):
    """'While you were away' (judging alignment §1.2): everything since the given turn."""
    k = require_owned_kingdom(db, player, kingdom_id)
    world = get_world(db, k.world_id)
    notes = db.execute(select(Notification).where(Notification.kingdom_id == k.id, Notification.turn >= turn)
                       .order_by(Notification.created_at)).scalars()
    chronicle = db.execute(select(StoryEvent).where(StoryEvent.world_id == world.id, StoryEvent.turn >= turn)
                           .order_by(StoryEvent.created_at)).scalars()
    return {"from_turn": turn, "current_turn": world.turn, "notifications": [_notification(n) for n in notes],
            "chronicle": [story_service.serialize(e) for e in chronicle]}


@router.get("/kingdoms/{kingdom_id}/dashboard")
def dashboard(kingdom_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    """Everything the Kingdom dashboard / wrist ledger / diplomatic desk needs, in one call."""
    k = require_owned_kingdom(db, player, kingdom_id)
    world = get_world(db, k.world_id)
    incoming_trades = db.execute(select(TradeOffer).where(TradeOffer.receiver_id == k.id, TradeOffer.status == "PENDING")).scalars()
    outgoing_trades = db.execute(select(TradeOffer).where(TradeOffer.sender_id == k.id, TradeOffer.status == "PENDING")).scalars()
    loans = db.execute(select(Loan).where(or_(Loan.lender_id == k.id, Loan.borrower_id == k.id))
                       .order_by(Loan.created_at.desc())).scalars().all()
    alliances_pending = db.execute(select(Alliance).where(Alliance.status == "PENDING", Alliance.proposer_id != k.id,
                                                          or_(Alliance.kingdom_a == k.id, Alliance.kingdom_b == k.id))).scalars()
    peace_offers = db.execute(select(War).where(War.status == "PEACE_PROPOSED", War.peace_proposed_by != k.id,
                                                or_(War.attacker_id == k.id, War.defender_id == k.id))).scalars()
    unread = db.execute(select(Notification).where(Notification.kingdom_id == k.id, Notification.read.is_(False))
                        .order_by(Notification.created_at.desc()).limit(20)).scalars()
    return {
        "world": {"id": world.id, "name": world.name, "turn": world.turn, "preset": world.preset,
                  "beginner_protection_turns": world.beginner_protection_turns,
                  "turn_limit": turn_service.turn_limit(world), "status": world.status,
                  "coronation": turn_service.coronation(db, world)},
        "kingdom": kingdom_private(k, db),
        "buildings": [kingdom_service.serialize_building(b) for b in kingdom_service.buildings_of(db, k.id)],
        "relations": diplomacy_service.relations_view(db, player, k.id),
        "inbox": {
            "trades": [economy_service.serialize_trade(t) for t in incoming_trades],
            "loans": [economy_service.serialize_loan(l) for l in loans if l.status == "PROPOSED" and l.proposer_id != k.id],
            "alliances": [diplomacy_service.serialize_alliance(a) for a in alliances_pending],
            "peace": [serialize_war(w) for w in peace_offers],
        },
        "outgoing_trades": [economy_service.serialize_trade(t) for t in outgoing_trades],
        "loans": [economy_service.serialize_loan(l) for l in loans],
        "notifications": [_notification(n) for n in unread],
        "leaderboard": prestige_service.leaderboard(db, world),
        "decrees": court_service.decrees(db, k),
        "council": court_service.council(db, k),
        "market": economy_service.market_view(db, k),
        "ultimatums": ultimatum_service.demands_for(db, k),
    }


@router.get("/kingdoms/{kingdom_id}/decrees")
def get_decrees(kingdom_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    """Royal Decrees: the next objectives with live progress; completed ones can be claimed for a reward."""
    return court_service.decrees(db, require_owned_kingdom(db, player, kingdom_id))


@router.post("/decrees/{key}/claim")
def claim_decree(key: str, body: DecreeClaimIn, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    result = court_service.claim_decree(db, player, body.kingdom_id, key)
    commit(db)
    return result


@router.get("/kingdoms/{kingdom_id}/council")
def get_council(kingdom_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    """The Royal Council: each adviser reads the realm's live state and gives counsel (most urgent first)."""
    return court_service.council(db, require_owned_kingdom(db, player, kingdom_id))
