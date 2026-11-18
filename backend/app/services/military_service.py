"""Military Engine: recruitment, war declaration, server-side battle resolution, peace (spec §2.4 G)."""

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import GameError, conflict, forbidden, not_found
from app.game.rules import (ALLY_DEFENSE_SHARE, BASE_DEFENSE, KINGDOM_BY_NAME, PLUNDER_CAP, PLUNDER_FRACTION,
                            RECRUIT_COST, RECRUIT_PER_BARRACKS_LEVEL, STANDING_DELTAS, WAR_DECLARATION_COST,
                            WATCHTOWER_DEFENSE_PER_LEVEL)
from app.models import Battle, Kingdom, Player, War, World
from app.services import npc_brain, queries, standing_service, story_service
from app.services.common import (apply, emit, emit_kingdom_update, get_kingdom, lock_kingdoms, notify, open_transaction,
                                 require_owned_kingdom, require_same_world)
from app.services.diplomacy_service import break_alliance
from app.services.economy_service import cancel_trades_between


def serialize_war(w: War) -> dict:
    return {"id": w.id, "attacker_id": w.attacker_id, "defender_id": w.defender_id, "status": w.status,
            "peace_proposed_by": w.peace_proposed_by, "betrayal": w.betrayal, "started_turn": w.started_turn,
            "ended_turn": w.ended_turn}


def serialize_battle(b: Battle) -> dict:
    return {"id": b.id, "war_id": b.war_id, "attacker_id": b.attacker_id, "defender_id": b.defender_id,
            "attacker_committed": b.attacker_committed, "defender_soldiers": b.defender_soldiers,
            "attacker_power": round(b.attacker_power, 1), "defender_power": round(b.defender_power, 1),
            "outcome": b.outcome, "attacker_losses": b.attacker_losses, "defender_losses": b.defender_losses,
            "plunder_gold": b.plunder_gold, "place_name": b.place_name, "report": b.report, "turn": b.turn}


# --- recruitment -----------------------------------------------------------------------------
def recruit(db: Session, player: Player, kingdom_id: str, count: int) -> Kingdom:
    k = require_owned_kingdom(db, player, kingdom_id)
    return recruit_for(db, k, count)


def recruit_for(db: Session, k: Kingdom, count: int) -> Kingdom:
    if count <= 0:
        raise GameError("Recruit at least one soldier")
    barracks = queries.building_levels(db, k.id, "barracks")
    if barracks == 0:
        raise GameError("Build Barracks to train soldiers", code="missing_building")
    world = db.get(World, k.world_id)
    k = lock_kingdoms(db, k.id)[k.id]
    if k.recruited_turn != world.turn:
        k.recruited_turn, k.recruited_this_turn = world.turn, 0
    capacity = barracks * RECRUIT_PER_BARRACKS_LEVEL - k.recruited_this_turn
    if count > capacity:
        raise GameError(f"Your barracks can train {max(capacity, 0)} more soldiers this turn", code="recruit_capacity")
    txn = open_transaction(db, world, "RECRUIT", sender=k)
    apply(db, txn, k, {r: -a * count for r, a in RECRUIT_COST.items()})
    k.soldiers += count
    k.recruited_this_turn += count
    emit_kingdom_update(db, k)
    return k


# --- war ---------------------------------------------------------------------------------------
def declare_war(db: Session, player: Player, kingdom_id: str, target_id: str) -> War:
    me = require_owned_kingdom(db, player, kingdom_id)
    return declare_war_for(db, me, get_kingdom(db, target_id))


def declare_war_for(db: Session, me: Kingdom, target: Kingdom) -> War:
    require_same_world(me, target)
    world = db.get(World, me.world_id)
    if queries.active_war(db, me.id, target.id):
        raise conflict(f"You are already at war with {target.name}")
    if world.turn <= world.beginner_protection_turns:
        raise GameError(f"Beginner protection: wars may begin from turn {world.beginner_protection_turns + 1}",
                        code="beginner_protection")
    me = lock_kingdoms(db, me.id)[me.id]
    txn = open_transaction(db, world, "WAR_DECLARATION", me, target)
    apply(db, txn, me, {"gold": -WAR_DECLARATION_COST})
    alliance = queries.active_alliance(db, me.id, target.id)
    from app.services.diplomacy_service import close_passages_between
    close_passages_between(db, world, me.id, target.id)   # war shuts the roads both ways
    war = War(world_id=world.id, attacker_id=me.id, defender_id=target.id, status="ACTIVE",
              betrayal=alliance is not None, started_turn=world.turn)
    db.add(war)
    db.flush()
    cancel_trades_between(db, me.id, target.id)
    if alliance:
        break_alliance(db, world, alliance, me, attacking=True)
    else:
        story_service.record(db, world, "WAR_DECLARED", f"{me.name} Declares War on {target.name}",
                             f"Heralds of {me.name} rode to {target.name} with a declaration of war.",
                             actors=[me.name, target.name], consequences=["WAR_DECLARED"], importance=2)
    standing_service.change(db, world, me, target, STANDING_DELTAS["war_declared"], "War declared")
    notify(db, world, target.id, "WAR_DECLARED", f"{me.name} has declared war on you!", "war", war.id)
    emit(db, {"type": "war_changed", "world_id": world.id, "war": serialize_war(war)})
    return war


def battle(db: Session, player: Player, kingdom_id: str, target_id: str, soldiers: int) -> Battle:
    me = require_owned_kingdom(db, player, kingdom_id)
    return battle_for(db, me, get_kingdom(db, target_id), soldiers)


def battle_for(db: Session, me: Kingdom, target: Kingdom, soldiers: int) -> Battle:
    require_same_world(me, target)
    world = db.get(World, me.world_id)
    if soldiers <= 0 or soldiers > me.soldiers:
        raise GameError(f"Commit between 1 and {me.soldiers} soldiers", code="invalid_army")
    already = db.execute(select(Battle).where(Battle.attacker_id == me.id, Battle.defender_id == target.id,
                                              Battle.turn == world.turn)).scalars().first()
    if already:
        raise GameError("Your armies already fought this enemy this turn (battle window)", code="battle_window")
    war = queries.active_war(db, me.id, target.id) or declare_war_for(db, me, target)

    ks = lock_kingdoms(db, me.id, target.id)
    me, target = ks[me.id], ks[target.id]
    rng = random.Random(f"{world.seed}:{world.turn}:{me.id}:{target.id}")
    supply = 1.0 if me.food >= soldiers else 0.8
    strength = 1.0 + 0.1 * queries.building_levels(db, me.id, "barracks")
    attacker_power = soldiers * strength * supply * rng.uniform(0.85, 1.15)

    helpers = []
    for ally_id in queries.ally_ids(db, target.id):
        alliance = queries.active_alliance(db, ally_id, target.id)
        if ally_id != me.id and alliance and alliance.mutual_defense:
            helpers.append(db.get(Kingdom, ally_id))
    ally_soldiers = sum(h.soldiers for h in helpers) * ALLY_DEFENSE_SHARE
    towers = queries.building_levels(db, target.id, "watchtower")
    defender_power = ((target.soldiers + ally_soldiers) * (1 + WATCHTOWER_DEFENSE_PER_LEVEL * towers) + BASE_DEFENSE) \
        * rng.uniform(0.85, 1.15)

    won = attacker_power > defender_power
    attacker_losses = min(soldiers, round(soldiers * (0.2 if won else 0.4)))
    defender_losses = min(target.soldiers, round(target.soldiers * (0.4 if won else 0.2)))
    plunder = min(PLUNDER_CAP, int(target.gold * PLUNDER_FRACTION)) if won else 0

    txn = open_transaction(db, world, "BATTLE", me, target, war.id)
    apply(db, txn, me, {"food": -min(me.food, soldiers // 2), "gold": plunder})
    if plunder:
        apply(db, txn, target, {"gold": -plunder})
    me.soldiers -= attacker_losses
    target.soldiers -= defender_losses
    place = rng.choice(KINGDOM_BY_NAME.get(target.name, {}).get("places", [f"the {target.name} Marches"]))
    outcome = "ATTACKER_VICTORY" if won else "DEFENDER_VICTORY"
    report = {"supply_factor": supply, "attacker_strength": round(strength, 2), "watchtower_levels": towers,
              "allied_support": [h.name for h in helpers], "allied_soldiers_counted": round(ally_soldiers, 1)}
    b = Battle(world_id=world.id, war_id=war.id, attacker_id=me.id, defender_id=target.id, attacker_committed=soldiers,
               defender_soldiers=target.soldiers + defender_losses, attacker_power=attacker_power,
               defender_power=defender_power, outcome=outcome, attacker_losses=attacker_losses,
               defender_losses=defender_losses, plunder_gold=plunder, place_name=place, report=report, turn=world.turn)
    db.add(b)
    db.flush()

    if won:
        text = (f"{me.name}'s army of {soldiers} broke {target.name}'s defenders at {place}. {target.name} lost "
                f"{defender_losses} soldiers; {me.name} lost {attacker_losses} and carried off {plunder:,} gold.")
    else:
        text = (f"{target.name} held {place} against {me.name}'s assault. {me.name} lost {attacker_losses} soldiers; "
                f"{target.name} lost {defender_losses}.")
    if helpers:
        text += f" Soldiers of {', '.join(h.name for h in helpers)} stood beside {target.name}."
    story_service.record(db, world, "BATTLE", f"The Battle of {place}",
                         text, actors=[me.name, target.name], consequences=[outcome], importance=3)
    for k in (me, target):
        notify(db, world, k.id, "BATTLE", text, "battle", b.id)
        emit_kingdom_update(db, k)
    emit(db, {"type": "battle", "world_id": world.id, "battle": serialize_battle(b)})
    return b


def propose_peace(db: Session, player: Player, kingdom_id: str, war_id: str) -> dict:
    me = require_owned_kingdom(db, player, kingdom_id)
    return propose_peace_for(db, me, war_id)


def propose_peace_for(db: Session, me: Kingdom, war_id: str) -> dict:
    war = db.get(War, war_id)
    if war is None:
        raise not_found("War")
    if me.id not in (war.attacker_id, war.defender_id):
        raise forbidden("Your kingdom is not part of this war")
    if war.status == "ENDED":
        raise conflict("This war is already over")
    world = db.get(World, war.world_id)
    enemy = db.get(Kingdom, war.defender_id if war.attacker_id == me.id else war.attacker_id)
    if war.status == "PEACE_PROPOSED" and war.peace_proposed_by == enemy.id:
        _end_war(db, world, war, me, enemy)
        return {"war": serialize_war(war), "decision": None}
    war.status, war.peace_proposed_by = "PEACE_PROPOSED", me.id
    decision = None
    if enemy.is_npc:
        decision = npc_brain.decide_peace(db, enemy, me, war, world.turn)
        if decision["accept"]:
            _end_war(db, world, war, me, enemy)
        else:
            war.status, war.peace_proposed_by = "ACTIVE", None
            notify(db, world, me.id, "PEACE_REJECTED", f"{enemy.name} refuses peace. {decision['summary']}", "war", war.id)
    else:
        notify(db, world, enemy.id, "PEACE_PROPOSED", f"{me.name} offers peace.", "war", war.id)
    return {"war": serialize_war(war), "decision": decision}


def _end_war(db: Session, world: World, war: War, a: Kingdom, b: Kingdom) -> None:
    war.status, war.ended_turn = "ENDED", world.turn
    standing_service.change(db, world, a, b, STANDING_DELTAS["peace_made"], "Peace made")
    turns = world.turn - war.started_turn
    story_service.record(db, world, "PEACE", f"Peace Between {a.name} and {b.name}",
                         f"After {turns} turn{'s' if turns != 1 else ''} of war, {a.name} and {b.name} laid down their arms.",
                         actors=[a.name, b.name], consequences=["WAR_ENDED"], importance=2)
    emit(db, {"type": "war_changed", "world_id": world.id, "war": serialize_war(war)})


def wars_in_world(db: Session, world_id: str) -> list[War]:
    return list(db.execute(select(War).where(War.world_id == world_id).order_by(War.created_at.desc())).scalars())


def battles_in_world(db: Session, world_id: str) -> list[Battle]:
    return list(db.execute(select(Battle).where(Battle.world_id == world_id).order_by(Battle.created_at.desc())).scalars())

