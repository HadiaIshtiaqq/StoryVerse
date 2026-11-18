"""The ruler's court: Royal Decrees (objectives with rewards) and the Royal Council (advisers who read the state of
the realm and say what they think). Both are computed from authoritative server state, never invented."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.errors import GameError, conflict, not_found
from app.game.rules import COUNCIL, DECREES, DECREES_SHOWN, STANDING_BANDS, band
from app.models import Alliance, Battle, Building, DecreeClaim, Kingdom, Loan, Player, TradeOffer, World  # noqa: F401
from app.services import queries, standing_service, story_service
from app.services.common import apply, emit, lock_kingdoms, notify, open_transaction, require_owned_kingdom

_BAND_RANK = {name: i for i, (_, name) in enumerate(reversed(STANDING_BANDS))}   # HOSTILE=0 ... TRUSTED=4


# =============================== ROYAL DECREES ===============================================
def _progress(db: Session, k: Kingdom, d: dict) -> int:
    kind = d["kind"]
    if kind == "buildings":
        return db.execute(select(func.count()).select_from(Building).where(
            Building.kingdom_id == k.id, Building.building_type == d["target"])).scalar_one()
    if kind == "level":
        return db.execute(select(func.coalesce(func.max(Building.level), 0)).where(Building.kingdom_id == k.id)).scalar_one()
    if kind == "resource":
        return getattr(k, d["target"])
    if kind == "population":
        return k.population
    if kind == "trades":
        return db.execute(select(func.count()).select_from(TradeOffer).where(
            TradeOffer.status == "ACCEPTED", or_(TradeOffer.sender_id == k.id, TradeOffer.receiver_id == k.id))).scalar_one()
    if kind == "band":
        need = _BAND_RANK[d["target"]]
        return int(any(_BAND_RANK[band(r.score)] >= need for r in standing_service.relations_rows(db, k.id)))
    if kind == "alliances":
        return db.execute(select(func.count()).select_from(Alliance).where(
            Alliance.status.in_(("ACTIVE", "EXPIRED", "TERMINATED")),          # ever formed
            or_(Alliance.kingdom_a == k.id, Alliance.kingdom_b == k.id))).scalar_one()
    if kind == "battles_won":
        return db.execute(select(func.count()).select_from(Battle).where(or_(
            and_(Battle.attacker_id == k.id, Battle.outcome == "ATTACKER_VICTORY"),
            and_(Battle.defender_id == k.id, Battle.outcome == "DEFENDER_VICTORY")))).scalar_one()
    raise ValueError(kind)


def decrees(db: Session, k: Kingdom) -> list[dict]:
    """The next few open decrees (like a quest log), each with live progress. Completed ones can be claimed."""
    claimed = {c.key for c in db.execute(select(DecreeClaim).where(DecreeClaim.kingdom_id == k.id)).scalars()}
    out = []
    for d in DECREES:
        if d["key"] in claimed:
            continue
        have = _progress(db, k, d)
        out.append({"key": d["key"], "title": d["title"], "goal": d["goal"], "kind": d["kind"], "target": d.get("target"),
                    "progress": min(have, d["need"]),
                    "need": d["need"], "complete": have >= d["need"], "reward": d["reward"]})
    # Completed decrees first (ready to claim), then the rest in their designed order.
    out.sort(key=lambda x: not x["complete"])
    return out[:DECREES_SHOWN]


def claim_decree(db: Session, player: Player, kingdom_id: str, key: str) -> dict:
    k = require_owned_kingdom(db, player, kingdom_id)
    d = next((x for x in DECREES if x["key"] == key), None)
    if d is None:
        raise not_found("Decree")
    if db.get(DecreeClaim, (k.id, key)):
        raise conflict("This decree has already been fulfilled and rewarded")
    k = lock_kingdoms(db, k.id)[k.id]
    if _progress(db, k, d) < d["need"]:
        raise GameError(f"Not yet: {d['goal']}", code="decree_incomplete")
    world = db.get(World, k.world_id)
    db.add(DecreeClaim(kingdom_id=k.id, key=key, turn=world.turn))
    txn = open_transaction(db, world, "DECREE_REWARD", receiver=k)
    apply(db, txn, k, d["reward"])
    reward = ", ".join(f"{v:,} {r}" for r, v in d["reward"].items())
    notify(db, world, k.id, "DECREE_FULFILLED", f"Decree fulfilled: {d['title']}. The crown receives {reward}.")
    story_service.record(db, world, "DECREE_FULFILLED", f"{k.name} Fulfils the Decree: {d['title']}",
                         f"By royal decree of {k.ruler_name}: {d['goal'].lower()}. It is done, and the treasury is the richer for it.",
                         actors=[k.name], consequences=["DECREE_FULFILLED"], importance=1)
    emit(db, {"type": "kingdom_updated", "world_id": world.id, "private_to": k.id, "kingdom_id": k.id})
    return {"key": key, "title": d["title"], "reward": d["reward"]}


# =============================== ROYAL COUNCIL ===============================================
def _advice(db: Session, k: Kingdom, domain: str) -> tuple[str, int]:
    """(advice, urgency 0..2) for one domain, from the live state of the realm."""
    from app.services.turn_service import kingdom_yield   # local: turn_service imports many services

    others = [o for o in queries.world_kingdoms(db, k.world_id) if o.id != k.id]
    if domain == "treasury":
        debt = queries.outstanding_debt(db, k.id)
        due = db.execute(select(Loan).where(Loan.borrower_id == k.id, Loan.status == "ACTIVE")).scalars().first()
        if debt and k.gold < debt:
            return f"We owe {debt:,} gold and hold only {k.gold:,}. Repay {due.code if due else 'the loan'} before the creditors talk.", 2
        if k.gold > 9000:
            return f"{k.gold:,} gold sleeps in the vaults. Gold that sleeps earns nothing: build, or lend at interest.", 1
        if kingdom_yield(db, k)["gold"] < 0:
            return "Our upkeep outruns our income. Another market or a gold mine would steady the ledgers.", 1
        return "The ledgers balance, Your Majesty. A bank would let us lend to our neighbours at interest.", 0
    if domain == "military":
        wars = [o for o in others if queries.active_war(db, k.id, o.id)]
        if wars:
            foe = max(wars, key=lambda o: o.soldiers)
            return f"We are at war with {foe.name}, who fields about {int(round(foe.soldiers, -1))} soldiers to our {k.soldiers}. Recruit, or sue for peace.", 2
        hostile = [o for o in others if standing_service.score(db, k.world_id, k.id, o.id) < -20]
        if hostile:
            o = min(hostile, key=lambda x: standing_service.score(db, k.world_id, k.id, x.id))
            return f"{o.name} glares at our border. A watchtower and fresh recruits would cool their ambitions.", 1
        if k.soldiers < 25:
            return "Our garrison is thin. Even friends grow bold when the walls look empty.", 1
        return f"Our {k.soldiers} soldiers stand ready, and no banner marches against us.", 0
    if domain == "diplomacy":
        waiting = (db.execute(select(func.count()).select_from(TradeOffer).where(
            TradeOffer.receiver_id == k.id, TradeOffer.status == "PENDING")).scalar_one())
        if waiting:
            return f"{waiting} envoy{'s wait' if waiting > 1 else ' waits'} at the gate with a proposal. A swift answer flatters a court.", 1
        rels = [(o, standing_service.score(db, k.world_id, k.id, o.id)) for o in others]
        near = [(o, s) for o, s in rels if 25 <= s < 40 and not queries.active_alliance(db, k.id, o.id)]
        if near:
            o, s = max(near, key=lambda x: x[1])
            return f"{o.name} stands at {s}. A modest gift would carry them to Friendly, and Friendly courts make allies.", 1
        cold = [(o, s) for o, s in rels if s < 0 and not queries.active_war(db, k.id, o.id)]
        if cold:
            o, s = min(cold, key=lambda x: x[1])
            return f"Relations with {o.name} have soured to {s}. A letter now costs less than a war later.", 1
        return "Our standing is sound in every court. Keep your word, and it will stay so.", 0
    if domain == "welfare":
        food = kingdom_yield(db, k)["food"]
        if food < 0:
            turns = k.food // -food if food else 0
            return f"The granaries lose {-food} food a turn: {turns} turns until hunger. Farms, or a granary, quickly.", 2 if turns < 4 else 1
        if not queries.building_levels(db, k.id, "hospital"):
            return "A hospital would heal the sick and raise the people's spirits, and the People's Crown follows the people.", 0
        return f"{k.population} souls live well under your rule. Houses would let more families settle.", 0
    if domain == "industry":
        if k.iron < 60:
            return "Our forges are starving for ore. A mine or a blacksmith would feed them.", 1
        upgradable = db.execute(select(Building).where(Building.kingdom_id == k.id, Building.level < 3)).scalars().first()
        if upgradable and k.wood >= 300 and k.stone >= 200:
            return f"We have timber and stone to spare. Raising our {upgradable.building_type.replace('_', ' ')} to the next rank would pay for itself.", 0
        return "The workshops hum. Wood and stone are the bones of every plan; keep the mills busy.", 0
    return "", 0


def council(db: Session, k: Kingdom) -> list[dict]:
    out = []
    for name, role, domain, portrait in COUNCIL.get(k.name, []):
        advice, urgency = _advice(db, k, domain)
        out.append({"name": name, "role": role, "domain": domain, "portrait": portrait, "advice": advice, "urgency": urgency})
    return sorted(out, key=lambda a: -a["urgency"])
