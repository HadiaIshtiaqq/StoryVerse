"""Worlds, kingdom seats, buildings (Kingdom Manager + Building System)."""

import math
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import GameError, conflict, not_found
from app.game.rules import (BUILDING_CATEGORIES, BUILDING_LORE, BUILDINGS, KINGDOM_BY_NAME, KINGDOMS, MAX_BUILD_RADIUS, MAX_BUILDING_LEVEL,
                            MIN_BUILDING_SPACING, STARTING_POPULATION, STARTING_RESOURCES, WORLD_PRESETS,
                            building_cost)
from app.models import Building, Kingdom, Player, World
from app.services import prestige_service, queries, standing_service, story_service
from app.services.common import apply, emit, lock_kingdoms, notify, open_transaction, require_owned_kingdom

NOTABLE_FIRSTS = {"bank", "barracks", "academy", "hospital", "gold_mine", "market"}


def serialize_building(b: Building) -> dict:
    return {"id": b.id, "kingdom_id": b.kingdom_id, "building_type": b.building_type,
            "label": BUILDINGS[b.building_type]["label"], "level": b.level, "state": b.state,
            "x": b.x, "y": b.y, "z": b.z, "rotation_y": b.rotation_y, "created_turn": b.created_turn}


def catalog(kingdom: Kingdom | None = None) -> list[dict]:
    discounts = KINGDOM_BY_NAME.get(kingdom.name, {}).get("discounts", {}) if kingdom else {}
    category = {t: c for c, ts in BUILDING_CATEGORIES.items() for t in ts}
    return [{"building_type": t, "label": d["label"], "function": d["function"],
             "category": category.get(t, "economy"), "lore": BUILDING_LORE.get(t, ""),
             "cost": building_cost(t, discounts), "production": d["production"], "maintenance": d["maintenance"],
             "max_level": MAX_BUILDING_LEVEL,
             "upgrade_costs": {lvl: building_cost(t, discounts, lvl) for lvl in range(2, MAX_BUILDING_LEVEL + 1)}}
            for t, d in BUILDINGS.items()]


# --- worlds ----------------------------------------------------------------------------------
def create_world(db: Session, player: Player, name: str, preset: str) -> World:
    if preset not in WORLD_PRESETS:
        raise GameError(f"Unknown preset '{preset}'. Choose one of: {', '.join(WORLD_PRESETS)}")
    world = World(name=name, preset=preset, seed=random.randrange(1, 2**31 - 1), created_by=player.id,
                  beginner_protection_turns=WORLD_PRESETS[preset]["beginner_protection_turns"])
    db.add(world)
    db.flush()
    kingdoms = []
    for spec in KINGDOMS:
        k = Kingdom(world_id=world.id, name=spec["name"], title=spec["title"], specialization=spec["specialization"],
                    ruler_name=spec["ruler"], emblem_key=spec["emblem"], color=spec["color"],
                    map_x=spec["map"][0], map_y=spec["map"][1], is_npc=True,
                    population=STARTING_POPULATION, soldiers=spec["soldiers"], **STARTING_RESOURCES)
        db.add(k)
        db.flush()
        n = len(spec["starting_buildings"])
        for i, bt in enumerate(spec["starting_buildings"]):
            angle = 2 * math.pi * i / n
            db.add(Building(kingdom_id=k.id, building_type=bt, x=round(k.map_x + 0.07 * math.cos(angle), 4),
                            z=round(k.map_y + 0.07 * math.sin(angle), 4), rotation_y=math.degrees(angle), created_turn=1))
        kingdoms.append(k)
    db.flush()
    standing_service.seed_world(db, world, kingdoms)
    story_service.record(db, world, "WORLD_FOUNDED", f"The Founding of {world.name}",
                         "Four crowns rise over the continent: Aurelia of gold, Drakoria of iron, "
                         "Sylvara of the green wood and Valoria of the sea. Their history begins now.",
                         actors=[k.name for k in kingdoms], importance=3)
    prestige_service.recompute_world(db, world, narrate=False)
    return world


def join_world(db: Session, player: Player, world_id: str, kingdom_name: str | None) -> Kingdom:
    world = db.get(World, world_id)
    if world is None:
        raise not_found("World")
    mine = db.execute(select(Kingdom).where(Kingdom.world_id == world_id, Kingdom.owner_id == player.id)).scalars().first()
    if mine:
        return mine  # rejoin: the kingdom was saved exactly as it was left (TC-20)
    seats = queries.world_kingdoms(db, world_id)
    if kingdom_name:
        seat = next((k for k in seats if k.name.lower() == kingdom_name.lower()), None)
        if seat is None:
            raise not_found(f"Kingdom '{kingdom_name}'")
        if seat.owner_id:
            raise conflict(f"{seat.name} already has a human ruler")
    else:
        seat = next((k for k in sorted(seats, key=lambda k: [s['name'] for s in KINGDOMS].index(k.name)) if not k.owner_id), None)
        if seat is None:
            raise conflict("This world is full: all four thrones are taken")
    seat = lock_kingdoms(db, seat.id)[seat.id]
    if seat.owner_id:
        raise conflict(f"{seat.name} was just claimed by another player")
    seat.owner_id, seat.is_npc = player.id, False
    story_service.record(db, world, "RULER_CROWNED", f"{player.username} Takes the Throne of {seat.name}",
                         f"The court of {seat.name} kneels as {player.username} accepts the crown from "
                         f"{seat.ruler_name}'s regents. {seat.title} has a living ruler once more.",
                         actors=[seat.name], importance=2)
    for other in seats:
        if other.id != seat.id:
            notify(db, world, other.id, "RULER_JOINED", f"A human ruler now sits on the throne of {seat.name}.")
    emit(db, {"type": "kingdom_claimed", "world_id": world.id, "kingdom_id": seat.id})
    return seat


# --- buildings -------------------------------------------------------------------------------
def _validate_placement(db: Session, k: Kingdom, x: float, z: float, ignore_id: str | None = None) -> None:
    if not (0.0 <= x <= 1.0 and 0.0 <= z <= 1.0):
        raise GameError("That spot is off the map", code="invalid_placement")
    if math.dist((x, z), (k.map_x, k.map_y)) > MAX_BUILD_RADIUS:
        raise GameError("Outside your realm's borders: build closer to your capital", code="invalid_placement")
    world_buildings = db.execute(select(Building).join(Kingdom, Building.kingdom_id == Kingdom.id)
                                 .where(Kingdom.world_id == k.world_id)).scalars()
    for b in world_buildings:
        if b.id != ignore_id and math.dist((x, z), (b.x, b.z)) < MIN_BUILDING_SPACING:
            raise GameError(f"Insufficient space: too close to a {BUILDINGS[b.building_type]['label']}",
                            code="invalid_placement", details={"blocking_building_id": b.id})


def construct(db: Session, player: Player, kingdom_id: str, building_type: str, x: float, z: float,
              y: float = 0.0, rotation_y: float = 0.0) -> Building:
    if building_type not in BUILDINGS:
        raise GameError(f"Unknown building type '{building_type}'", code="unknown_building")
    k = require_owned_kingdom(db, player, kingdom_id)
    return construct_for(db, k, building_type, x, z, y, rotation_y)


def construct_for(db: Session, k: Kingdom, building_type: str, x: float, z: float,
                  y: float = 0.0, rotation_y: float = 0.0) -> Building:
    world = db.get(World, k.world_id)
    _validate_placement(db, k, x, z)
    k = lock_kingdoms(db, k.id)[k.id]
    cost = building_cost(building_type, KINGDOM_BY_NAME.get(k.name, {}).get("discounts", {}))
    first_of_type = not queries.has_building(db, k.id, building_type)
    txn = open_transaction(db, world, "BUILD", sender=k)
    apply(db, txn, k, {r: -a for r, a in cost.items()})
    b = Building(kingdom_id=k.id, building_type=building_type, x=x, y=y, z=z, rotation_y=rotation_y,
                 created_turn=world.turn)
    db.add(b)
    db.flush()
    txn.ref_id = b.id
    if first_of_type and building_type in NOTABLE_FIRSTS:
        label = BUILDINGS[building_type]["label"]
        story_service.record(db, world, "BUILDING_RAISED", f"{k.name} Raises Its First {label}",
                             f"Masons of {k.name} complete a {label.lower()}: {BUILDINGS[building_type]['function'].lower()}.",
                             actors=[k.name])
    emit(db, {"type": "building_placed", "world_id": world.id, "building": serialize_building(b)})
    return b


def upgrade(db: Session, player: Player, building_id: str) -> Building:
    b = db.get(Building, building_id)
    if b is None:
        raise not_found("Building")
    k = require_owned_kingdom(db, player, b.kingdom_id)
    return upgrade_for(db, k, b)


def upgrade_for(db: Session, k: Kingdom, b: Building) -> Building:
    if b.level >= MAX_BUILDING_LEVEL:
        raise GameError(f"Already at the maximum level ({MAX_BUILDING_LEVEL})", code="max_level")
    world = db.get(World, k.world_id)
    k = lock_kingdoms(db, k.id)[k.id]
    cost = building_cost(b.building_type, KINGDOM_BY_NAME.get(k.name, {}).get("discounts", {}), b.level + 1)
    txn = open_transaction(db, world, "UPGRADE", sender=k, ref_id=b.id)
    apply(db, txn, k, {r: -a for r, a in cost.items()})
    b.level += 1
    if b.level == MAX_BUILDING_LEVEL:
        label = BUILDINGS[b.building_type]["label"]
        story_service.record(db, world, "GREAT_WORK", f"The Great {label} of {k.name}",
                             f"{k.name}'s {label.lower()} reaches its full glory, admired across the continent.",
                             actors=[k.name])
    emit(db, {"type": "building_updated", "world_id": world.id, "building": serialize_building(b)})
    return b


def buildings_of(db: Session, kingdom_id: str) -> list[Building]:
    return list(db.execute(select(Building).where(Building.kingdom_id == kingdom_id).order_by(Building.created_at)).scalars())
