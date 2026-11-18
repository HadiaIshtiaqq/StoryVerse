"""Prestige = E + M + D + B + W (spec §4.8), each category with diminishing returns and a cap."""

import math

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.game.rules import BASE_PRICES, CROWNS, MANSION_WELFARE_PRESTIGE, PRESTIGE_CATEGORY_CAP, PRESTIGE_SCALE, RESOURCES
from app.models import Battle, Kingdom, Loan, TradeOffer, World
from app.services import queries, standing_service, story_service
from app.services.common import emit

CROWN_MARGIN = 5  # prestige points a challenger needs above the current holder


def _score(raw: float) -> int:
    return int(round(PRESTIGE_CATEGORY_CAP * (1 - math.exp(-max(raw, 0) / PRESTIGE_SCALE))))


def compute(db: Session, k: Kingdom) -> dict[str, int]:
    resource_value = sum(getattr(k, r) * BASE_PRICES[r] for r in RESOURCES)
    lent = db.execute(select(Loan).where(Loan.lender_id == k.id, Loan.status.in_(("ACTIVE", "REPAID")))).scalars()
    interest_earned = sum(max(0, l.amount_repaid - l.principal) for l in lent)
    battles_won = db.execute(select(func.count()).select_from(Battle).where(or_(
        and_(Battle.attacker_id == k.id, Battle.outcome == "ATTACKER_VICTORY"),
        and_(Battle.defender_id == k.id, Battle.outcome == "DEFENDER_VICTORY")))).scalar_one()
    trades = db.execute(select(func.count()).select_from(TradeOffer).where(
        TradeOffer.status == "ACCEPTED", or_(TradeOffer.sender_id == k.id, TradeOffer.receiver_id == k.id))).scalar_one()
    loans_honoured = db.execute(select(func.count()).select_from(Loan).where(
        Loan.status == "REPAID", or_(Loan.lender_id == k.id, Loan.borrower_id == k.id))).scalar_one()
    rels = standing_service.relations_rows(db, k.id)
    avg_standing = sum(r.score for r in rels) / len(rels) if rels else 0
    levels = queries.building_levels(db, k.id)

    raw = {
        # Net worth: borrowed gold is not wealth, so outstanding debt is subtracted.
        "economic": (resource_value - queries.outstanding_debt(db, k.id)) / 20 + interest_earned,
        "military": k.soldiers + 60 * battles_won,
        "diplomatic": 50 * len(queries.allies_of(db, k.id)) + 12 * trades + 20 * loans_honoured + max(0.0, avg_standing),
        "development": 20 * levels + 40 * queries.building_levels(db, k.id, "academy"),
        "welfare": k.population + 30 * queries.building_levels(db, k.id, "hospital") + k.food / 20
                   + MANSION_WELFARE_PRESTIGE * queries.building_levels(db, k.id, "mansions"),
    }
    return {cat: _score(v) for cat, v in raw.items()}


def recompute_world(db: Session, world: World, narrate: bool = True) -> None:
    kingdoms = queries.world_kingdoms(db, world.id)
    for k in kingdoms:
        breakdown = compute(db, k)
        k.prestige_breakdown = breakdown
        k.prestige = max(0, sum(breakdown.values()) - k.prestige_penalty)

    crowns = dict(world.crowns or {})
    by_id = {k.id: k for k in kingdoms}
    for category, crown_name in CROWNS.items():
        holder = crowns.get(category)
        best = max(kingdoms, key=lambda k: (k.prestige_breakdown.get(category, 0), k.id == holder))
        held_score = by_id[holder].prestige_breakdown.get(category, 0) if holder in by_id else -1
        # Hysteresis: a crown changes hands only on a clear lead, so it doesn't flip every turn.
        if best.id != holder and best.prestige_breakdown.get(category, 0) > max(0, held_score + CROWN_MARGIN):
            crowns[category] = best.id
            if narrate:
                story_service.record(db, world, "CROWN_CLAIMED", f"{best.name} Claims the {crown_name}",
                                     f"{best.name} now leads the realm in {category} matters and holds the {crown_name}.",
                                     actors=[best.name], consequences=["CROWN_CHANGED"], importance=2)
    world.crowns = crowns
    emit(db, {"type": "leaderboard_changed", "world_id": world.id})


def leaderboard(db: Session, world: World) -> list[dict]:
    holders = {kid: [CROWNS[c] for c, h in (world.crowns or {}).items() if h == kid] for kid in [k.id for k in queries.world_kingdoms(db, world.id)]}
    rows = sorted(queries.world_kingdoms(db, world.id), key=lambda k: k.prestige, reverse=True)
    return [{"rank": i + 1, "kingdom_id": k.id, "name": k.name, "ruler_name": k.ruler_name, "is_npc": k.is_npc,
             "prestige": k.prestige, "breakdown": k.prestige_breakdown, "penalty": k.prestige_penalty,
             "crowns": holders.get(k.id, [])} for i, k in enumerate(rows)]
