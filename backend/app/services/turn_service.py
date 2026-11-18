"""World turns (spec §6.4): strategic calculations run in discrete, server-side turns.

Order: production & upkeep -> loan installments -> alliance expiry -> standing decay ->
NPC rulers act -> prestige & crowns -> per-kingdom turn reports.
"""

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.errors import conflict, forbidden
from app.game.rules import (BUILDINGS, CORONATION_WARNING_TURNS, HOUSING_GROWTH, KINGDOM_BY_NAME, PASSAGE_GOLD_PER_TURN,
                            RESOURCES, WORLD_PRESETS)
from app.models import Building, Kingdom, Passage, Player, TurnReady, World
from app.services import (diplomacy_service, economy_service, npc_actor, prestige_service, queries, standing_service,
                          story_service)
from app.services.common import apply, emit, get_world, lock_kingdoms, notify, open_transaction


def calculate_resources(current: int, production: int, consumption: int) -> int:
    """R_new = max(0, R + P - C)  (spec §2.4 C / §5.5 A)."""
    return max(0, current + production - consumption)


def kingdom_yield(db: Session, k: Kingdom) -> dict[str, int]:
    """Net per-turn change for a kingdom (positive = production, negative = upkeep/consumption)."""
    bonus = KINGDOM_BY_NAME.get(k.name, {}).get("production_bonus", {})
    net = {r: 0.0 for r in RESOURCES}
    for b in db.execute(select(Building).where(Building.kingdom_id == k.id, Building.state == "COMPLETE")).scalars():
        spec = BUILDINGS[b.building_type]
        for res, amount in spec["production"].items():
            net[res] += amount * b.level * bonus.get(res, 1.0)
        for res, amount in spec["maintenance"].items():
            net[res] -= amount * b.level
    net["food"] -= k.population // 5 + k.soldiers // 2
    out = {r: int(round(v)) for r, v in net.items()}
    # Road tolls are whole coins: add them after rounding so they never shift the rounding of production.
    roads = db.execute(select(func.count()).select_from(Passage).where(
        Passage.status == "ACTIVE", or_(Passage.grantor_id == k.id, Passage.grantee_id == k.id))).scalar_one()
    out["gold"] += PASSAGE_GOLD_PER_TURN * roads
    return out


def advance(db: Session, player: Player, world_id: str, force: bool = False) -> dict:
    """End-turn request. Solo worlds (one human) advance immediately. With several human rulers the call
    records a ready vote and the turn advances once every human is ready; the world's creator may force it."""
    world = get_world(db, world_id)
    mine = db.execute(select(Kingdom).where(Kingdom.world_id == world.id, Kingdom.owner_id == player.id)).scalars().first()
    is_creator = world.created_by == player.id
    if not mine and not is_creator:
        raise forbidden("Only rulers in this world can advance its turn")
    if world.status == "ENDED":
        raise conflict("This reign has ended: the realm has crowned its High Monarch. Found a new world to play again.")
    if force and not is_creator:
        raise forbidden("Only the world's creator can force the turn")
    # Lock the world row first: concurrent "ready" votes then serialise, so exactly one of them advances.
    world = db.execute(select(World).where(World.id == world.id).with_for_update()
                       .execution_options(populate_existing=True)).scalars().one()
    humans = [k for k in queries.world_kingdoms(db, world.id) if k.owner_id and not k.is_npc]
    if len(humans) > 1 and not force:
        if mine:
            vote = db.get(TurnReady, (world.id, mine.id))
            if vote is None:
                db.add(TurnReady(world_id=world.id, kingdom_id=mine.id, turn=world.turn))
            else:
                vote.turn = world.turn
            db.flush()
        ready = {v.kingdom_id for v in db.execute(select(TurnReady).where(
            TurnReady.world_id == world.id, TurnReady.turn == world.turn)).scalars()}
        waiting = [k.name for k in humans if k.id not in ready]
        if waiting:
            emit(db, {"type": "turn_ready", "world_id": world.id, "turn": world.turn,
                      "ready": sorted(k.name for k in humans if k.id in ready), "waiting_for": waiting})
            return {"world_id": world.id, "turn": world.turn, "advanced": False, "waiting_for": waiting}
    result = advance_world(db, world)
    db.execute(delete(TurnReady).where(TurnReady.world_id == world.id))
    return {**result, "advanced": True, "waiting_for": []}


def advance_world(db: Session, world: World) -> dict:
    world.turn += 1
    kingdoms = list(lock_kingdoms(db, *[k.id for k in queries.world_kingdoms(db, world.id)]).values())
    reports: dict[str, dict] = {}

    for k in kingdoms:
        net = kingdom_yield(db, k)
        txn = open_transaction(db, world, "PRODUCTION", receiver=k)
        applied = apply(db, txn, k, net, allow_clamp=True)
        if k.food > 0:
            k.population += 2 + 3 * queries.building_levels(db, k.id, "hospital") + sum(
                per * queries.building_levels(db, k.id, b) for b, per in HOUSING_GROWTH.items())
        else:
            lost = max(1, k.population // 20)
            granaries = queries.building_levels(db, k.id, "granary")
            if granaries:
                lost = max(1, lost // (2 ** min(granaries, 3)))   # each granary level halves famine losses
            k.population -= lost
            story_service.record(db, world, "FAMINE", f"Famine in {k.name}",
                                 f"The granaries of {k.name} are empty; {lost} of its people are lost to hunger.",
                                 actors=[k.name], consequences=["POPULATION_LOST"], importance=2)
        reports[k.id] = {"kingdom_id": k.id, "name": k.name, "net": applied, "population": k.population}

    economy_service.process_loans(db, world)
    economy_service.expire_trades(db, world)
    diplomacy_service.expire_alliances(db, world)
    allied_pairs = {standing_service.pair(a.kingdom_a, a.kingdom_b)
                    for k in kingdoms for a in queries.allies_of(db, k.id)}
    standing_service.decay(db, world, allied_pairs)

    for k in kingdoms:
        if k.is_npc:
            npc_actor.act(db, world, k)

    prestige_service.recompute_world(db, world, narrate=True)
    for k in kingdoms:
        if not k.is_npc:
            gains = ", ".join(f"{v:+d} {r}" for r, v in reports[k.id]["net"].items()) or "no change"
            notify(db, world, k.id, "TURN_REPORT", f"Turn {world.turn} begins. Treasury: {gains}.")
    emit(db, {"type": "turn_advanced", "world_id": world.id, "turn": world.turn})
    limit = turn_limit(world)
    if world.turn >= limit:
        end_reign(db, world)
    elif world.turn >= limit - CORONATION_WARNING_TURNS:
        left = limit - world.turn
        for k in kingdoms:
            if not k.is_npc:
                notify(db, world, k.id, "CORONATION_NEAR", f"The coronation approaches: {left} turn{'s' if left > 1 else ''} remain to raise your prestige.")
    return {"world_id": world.id, "turn": world.turn, "reports": list(reports.values()),
            "turn_limit": limit, "ended": world.status == "ENDED"}


def turn_limit(world: World) -> int:
    return WORLD_PRESETS.get(world.preset, {}).get("turn_limit", 30)


def end_reign(db: Session, world: World) -> None:
    """The last turn: the most prestigious ruler is crowned High Monarch and the world closes."""
    board = prestige_service.leaderboard(db, world)
    winner = board[0]
    world.status = "ENDED"
    runners = ", ".join(f"{r['name']} ({r['prestige']})" for r in board[1:])
    story_service.record(db, world, "CORONATION", f"The Coronation of {winner['ruler_name']}",
                         f"After {world.turn} turns, {winner['ruler_name']} of {winner['name']} is crowned High Monarch of the realm "
                         f"with {winner['prestige']} prestige. The other courts bow: {runners}.",
                         actors=[winner["name"]], consequences=["REIGN_ENDED"], importance=3)
    for k in queries.world_kingdoms(db, world.id):
        if not k.is_npc:
            place = next(r["rank"] for r in board if r["kingdom_id"] == k.id)
            notify(db, world, k.id, "REIGN_ENDED", f"The reign is over. {winner['name']} wears the High Crown. You finished #{place} of {len(board)}.")
    emit(db, {"type": "world_ended", "world_id": world.id, "winner": winner["kingdom_id"]})


def coronation(db: Session, world: World) -> dict | None:
    """Winner of an ended reign, read from its CORONATION chronicle entry (no schema change needed)."""
    if world.status != "ENDED":
        return None
    from app.models import StoryEvent
    ev = db.execute(select(StoryEvent).where(StoryEvent.world_id == world.id, StoryEvent.event_type == "CORONATION")
                    .order_by(StoryEvent.created_at.desc())).scalars().first()
    if ev is None:
        return None
    actors = ev.actors or []
    return {"winner_name": actors[0] if actors else None, "title": ev.title, "description": ev.description, "turn": ev.turn}
