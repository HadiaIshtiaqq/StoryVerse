"""What NPC rulers *do* each world turn: build, recruit, and make one diplomatic move.

A solo player (or judge) therefore gets story beats every turn without waiting for humans.
Each action runs in a SAVEPOINT so a failed attempt never leaves partial state behind.
"""

import math
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import GameError
from app.game.rules import BUILDINGS, KINGDOM_BY_NAME, MAX_BUILDING_LEVEL, building_cost, band
from app.models import Battle, Kingdom, Loan, Message, TradeOffer, World
from app.services import (diplomacy_service, economy_service, kingdom_service, military_service, npc_brain, queries,
                          standing_service)

BUILD_ORDERS = {
    "merchant": ["market", "farm", "gold_mine", "bank", "academy", "hospital", "lumber_mill"],
    "warlord": ["barracks", "lumber_mill", "market", "mine", "farm", "watchtower", "bank"],
    "steward": ["lumber_mill", "farm", "hospital", "market", "bank", "mine"],
    "broker": ["market", "lumber_mill", "bank", "farm", "mine", "academy", "watchtower"],
}
GOLD_RESERVE = 1000


def turn_service_yield(db: Session, k: Kingdom) -> dict[str, int]:
    from app.services.turn_service import kingdom_yield  # local import: turn_service imports this module

    return kingdom_yield(db, k)


def _attempt(db: Session, fn, *args, **kwargs):
    try:
        with db.begin_nested():
            return fn(*args, **kwargs)
    except GameError:
        return None


def act(db: Session, world: World, npc: Kingdom) -> None:
    rng = random.Random(f"{world.seed}:{world.turn}:{npc.id}:npc")
    style = npc_brain.personality(npc)["style"]
    _attempt(db, _build, db, world, npc, style, rng)
    if style == "warlord":
        _attempt(db, _recruit, db, npc)
    for war in queries.wars_of(db, npc.id):
        enemy = db.get(Kingdom, war.defender_id if war.attacker_id == npc.id else war.attacker_id)
        if npc.soldiers < enemy.soldiers * 0.8:
            _attempt(db, military_service.propose_peace_for, db, npc, war.id)
            return
    {"merchant": _merchant, "warlord": _warlord, "steward": _steward, "broker": _broker}[style](db, world, npc)


# --- building ------------------------------------------------------------------------------
def _build(db: Session, world: World, npc: Kingdom, style: str, rng: random.Random) -> None:
    discounts = KINGDOM_BY_NAME.get(npc.name, {}).get("discounts", {})
    owned = {b.building_type for b in kingdom_service.buildings_of(db, npc.id)}
    plan = BUILD_ORDERS[style]
    if turn_service_yield(db, npc)["food"] < 0:
        plan = ["farm"]  # feed the people (and the legions) first
        owned.discard("farm")
    for bt in plan:
        if bt in owned:
            continue
        cost = building_cost(bt, discounts)
        if all(getattr(npc, r) >= a + (GOLD_RESERVE if r == "gold" else 0) for r, a in cost.items()):
            for _ in range(12):
                angle, radius = rng.uniform(0, 2 * math.pi), rng.uniform(0.05, 0.16)
                x, z = round(npc.map_x + radius * math.cos(angle), 4), round(npc.map_y + radius * math.sin(angle), 4)
                try:
                    kingdom_service.construct_for(db, npc, bt, x, z, rotation_y=math.degrees(angle))
                    return
                except GameError as e:
                    if e.code != "invalid_placement":
                        raise
        return  # wait until the next building in the plan is affordable
    # Everything built: upgrade the lowest-level producer.
    producers = [b for b in kingdom_service.buildings_of(db, npc.id)
                 if BUILDINGS[b.building_type]["production"] and b.level < MAX_BUILDING_LEVEL]
    if producers:
        target = min(producers, key=lambda b: b.level)
        cost = building_cost(target.building_type, discounts, target.level + 1)
        if all(getattr(npc, r) >= a + (GOLD_RESERVE if r == "gold" else 0) for r, a in cost.items()):
            kingdom_service.upgrade_for(db, npc, target)


def _recruit(db: Session, npc: Kingdom) -> None:
    if npc.gold > 1500 and queries.has_building(db, npc.id, "barracks"):
        military_service.recruit_for(db, npc, 10)


# --- diplomatic moves --------------------------------------------------------------------------
def _others(db: Session, npc: Kingdom) -> list[Kingdom]:
    return [k for k in queries.world_kingdoms(db, npc.world_id) if k.id != npc.id]


def _has_pending_trade(db: Session, npc: Kingdom) -> bool:
    return db.execute(select(TradeOffer).where(TradeOffer.sender_id == npc.id, TradeOffer.status == "PENDING")).scalars().first() is not None


def _offer_to_human(db: Session, npc: Kingdom, offered: str, offered_amount: int, wanted: str, wanted_amount: int) -> bool:
    """Make sure a solo player's inbox gets real proposals from the NPC courts."""
    if _has_pending_trade(db, npc) or getattr(npc, offered) < offered_amount + 100:
        return False
    humans = [k for k in _others(db, npc) if not k.is_npc and getattr(k, wanted) >= wanted_amount
              and not queries.active_war(db, npc.id, k.id)]
    if not humans:
        return False
    return bool(_attempt(db, economy_service.create_trade_for, db, npc, max(humans, key=lambda k: getattr(k, wanted)).id,
                         offered, offered_amount, wanted, wanted_amount))


def _merchant(db: Session, world: World, npc: Kingdom) -> None:
    """Aurelia lends to the needy and buys food."""
    for other in sorted(_others(db, npc), key=lambda k: k.gold):
        if other.gold >= 1500 or queries.active_war(db, npc.id, other.id):
            continue
        if standing_service.score(db, world.id, npc.id, other.id) < 0:
            continue
        open_loan = db.execute(select(Loan).where(Loan.lender_id == npc.id, Loan.borrower_id == other.id,
                                                  Loan.status.in_(("PROPOSED", "ACTIVE")))).scalars().first()
        if not open_loan and _attempt(db, economy_service.propose_loan_for, db, npc, other.id, "lender", 1000, 10.0, 5):
            return
    if _offer_to_human(db, npc, "gold", 150, "food", 60):
        return
    if npc.food < 300 and not _has_pending_trade(db, npc):
        seller = max(_others(db, npc), key=lambda k: k.food)
        _attempt(db, economy_service.create_trade_for, db, npc, seller.id, "gold", 150, "food", 60)


WARLORD_COOLDOWN = 3
GRACE_FOR_NEW_RULERS = 4


def _warlord(db: Session, world: World, npc: Kingdom) -> None:
    """Drakoria borrows a war chest, threatens, then strikes, at most every few turns."""
    in_debt = db.execute(select(Loan).where(Loan.borrower_id == npc.id, Loan.status.in_(("PROPOSED", "ACTIVE")))).scalars().first()
    if npc.gold < 2000 and not in_debt:
        lenders = [k for k in _others(db, npc) if queries.has_building(db, k.id, "bank")
                   and band(standing_service.score(db, world.id, npc.id, k.id)) != "HOSTILE"]
        if lenders and _attempt(db, economy_service.propose_loan_for, db, npc, max(lenders, key=lambda k: k.gold).id,
                                "borrower", 2000, 10.0, 5):
            return
    last = db.execute(select(Battle).where(Battle.attacker_id == npc.id).order_by(Battle.turn.desc())).scalars().first()
    ready = world.turn > world.beginner_protection_turns and (last is None or world.turn - last.turn >= WARLORD_COOLDOWN)
    if ready:
        rng = random.Random(f"{world.seed}:{world.turn}:{npc.id}:war")
        allies = set(queries.ally_ids(db, npc.id))
        # The betrayal arc: late in the game, a strong Drakoria may turn on a weak ally.
        weak_allies = [db.get(Kingdom, a) for a in allies]
        weak_allies = [k for k in weak_allies if npc.soldiers > 2 * max(k.soldiers, 1)]
        if world.turn >= 8 and weak_allies and rng.random() < 0.35:
            if _attempt(db, military_service.battle_for, db, npc, min(weak_allies, key=lambda k: k.soldiers), npc.soldiers // 2):
                return
        targets = [k for k in _others(db, npc) if k.id not in allies
                   and standing_service.score(db, world.id, npc.id, k.id) < 0 and npc.soldiers >= 1.5 * max(k.soldiers, 1)]
        if targets:
            target = min(targets, key=lambda k: k.soldiers)
            if not target.is_npc and world.turn <= GRACE_FOR_NEW_RULERS:
                _threaten(db, npc, target)
            elif _attempt(db, military_service.battle_for, db, npc, target, npc.soldiers // 2):
                return
    _offer_to_human(db, npc, "iron", 60, "food", 120)


def _threaten(db: Session, npc: Kingdom, target: Kingdom) -> None:
    already = db.execute(select(Message).where(Message.sender_kingdom_id == npc.id,
                                               Message.recipient_kingdom_id == target.id)).scalars().first()
    if not already:
        _attempt(db, diplomacy_service.send_message_for, db, npc, target.id, "A warning from Cinderhold",
                 f"{target.name} grows fat while Drakoria's legions sharpen their blades. Send tribute, or our "
                 f"banners will darken your fields.\n\n— {npc.ruler_name}", "cold", False)


def _steward(db: Session, world: World, npc: Kingdom) -> None:
    """Sylvara feeds the continent: food for iron (spec example)."""
    if npc.food < 300 or _has_pending_trade(db, npc):
        return
    partners = [k for k in _others(db, npc) if not queries.active_war(db, npc.id, k.id) and k.iron >= 80]
    if partners:
        _attempt(db, economy_service.create_trade_for, db, npc, max(partners, key=lambda k: k.iron).id, "food", 100, "iron", 80)


def _broker(db: Session, world: World, npc: Kingdom) -> None:
    """Valoria seeks friends, then trades for whatever it lacks."""
    for other in sorted(_others(db, npc), key=lambda k: -standing_service.score(db, world.id, npc.id, k.id)):
        if (standing_service.score(db, world.id, npc.id, other.id) >= 40
                and not queries.active_alliance(db, npc.id, other.id)
                and not queries.pending_alliance(db, npc.id, other.id)
                and not queries.active_war(db, npc.id, other.id)):
            if _attempt(db, diplomacy_service.propose_alliance_for, db, npc, other.id, 10, True):
                return
    scarce = min(("wood", "stone", "iron"), key=lambda r: getattr(npc, r))
    if _offer_to_human(db, npc, "gold", 120, scarce, 50) or _has_pending_trade(db, npc):
        return
    sellers = [k for k in _others(db, npc) if getattr(k, scarce) >= 200 and not queries.active_war(db, npc.id, k.id)]
    if sellers:
        _attempt(db, economy_service.create_trade_for, db, npc, max(sellers, key=lambda k: getattr(k, scarce)).id,
                 "gold", 120, scarce, 50)
