from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import commit
from app.api.kingdoms import kingdom_private, kingdom_public
from app.database import get_db
from app.models import Building, Kingdom, Player, StoryEvent, World
from app.schemas import WorldCreateIn, WorldJoinIn
from app.security import get_current_player
from app.services import diplomacy_service, kingdom_service, prestige_service, queries, story_service, turn_service
from app.services.common import get_world

router = APIRouter(tags=["worlds"])


def world_view(db: Session, world: World, player: Player) -> dict:
    return {"id": world.id, "name": world.name, "status": world.status, "preset": world.preset, "turn": world.turn,
            "beginner_protection_turns": world.beginner_protection_turns, "crowns": world.crowns,
            "kingdoms": [kingdom_private(k, db) if k.owner_id == player.id else kingdom_public(k, db)
                         for k in queries.world_kingdoms(db, world.id)]}


@router.post("/worlds")
def create_world(body: WorldCreateIn, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    world = kingdom_service.create_world(db, player, body.name, body.preset)
    commit(db)
    return world_view(db, world, player)


@router.get("/worlds")
def list_worlds(player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    worlds = db.execute(select(World).order_by(World.created_at.desc()).limit(50)).scalars()
    out = []
    for w in worlds:
        ks = queries.world_kingdoms(db, w.id)
        out.append({"id": w.id, "name": w.name, "preset": w.preset, "turn": w.turn, "status": w.status,
                    "turn_limit": turn_service.turn_limit(w),
                    "open_seats": [k.name for k in ks if not k.owner_id],
                    "my_kingdom_id": next((k.id for k in ks if k.owner_id == player.id), None)})
    return out


@router.post("/worlds/join")
def join_world(body: WorldJoinIn, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    kingdom = kingdom_service.join_world(db, player, body.world_id, body.kingdom_name)
    commit(db)
    return kingdom_private(kingdom, db)


@router.get("/worlds/{world_id}")
def get_world_view(world_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    return world_view(db, get_world(db, world_id), player)


@router.get("/worlds/{world_id}/map")
def world_map(world_id: str, _: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    """Shared Realm Map: kingdoms, every building, and the public treaty web (ribbons)."""
    world = get_world(db, world_id)
    buildings = db.execute(select(Building).join(Kingdom, Building.kingdom_id == Kingdom.id)
                           .where(Kingdom.world_id == world.id)).scalars()
    return {"turn": world.turn,
            "kingdoms": [{"id": k.id, "name": k.name, "color": k.color, "emblem_key": k.emblem_key,
                          "map_x": k.map_x, "map_y": k.map_y, "is_npc": k.is_npc} for k in queries.world_kingdoms(db, world.id)],
            "buildings": [kingdom_service.serialize_building(b) for b in buildings],
            "treaties": diplomacy_service.public_treaty_web(db, world.id)}


@router.post("/worlds/{world_id}/turn")
def advance_turn(world_id: str, force: bool = False, player: Player = Depends(get_current_player),
                 db: Session = Depends(get_db)):
    """End turn. Solo: advances now. Shared world: records your ready vote; the turn advances when every human
    ruler is ready (`advanced: true`), otherwise returns `waiting_for`. The world's creator may pass `force=true`."""
    result = turn_service.advance(db, player, world_id, force)
    commit(db)
    return result


@router.get("/worlds/{world_id}/chronicle")
def chronicle(world_id: str, since_turn: int = 0, limit: int = Query(100, le=500),
              _: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    world = get_world(db, world_id)
    events = db.execute(select(StoryEvent).where(StoryEvent.world_id == world.id, StoryEvent.turn >= since_turn)
                        .order_by(StoryEvent.created_at.desc()).limit(limit)).scalars()
    return [story_service.serialize(e) for e in events]


@router.get("/leaderboard/{world_id}")
def leaderboard(world_id: str, _: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    return prestige_service.leaderboard(db, get_world(db, world_id))
