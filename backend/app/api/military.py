"""Recruitment, war, battles, peace (spec §2.4 G)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import IdempotencyKey, commit, idempotent
from app.api.kingdoms import kingdom_private
from app.database import get_db
from app.models import Player
from app.schemas import BattleIn, KingdomActionIn, RecruitIn, WarIn
from app.security import get_current_player
from app.services import military_service as mil
from app.services.common import get_world

router = APIRouter(tags=["military"])


@router.post("/soldiers/recruit")
def recruit(body: RecruitIn, key: str | None = IdempotencyKey, player: Player = Depends(get_current_player),
            db: Session = Depends(get_db)):
    return idempotent(db, player, key, "soldiers:recruit",
                      lambda: kingdom_private(mil.recruit(db, player, body.kingdom_id, body.count), db))


@router.post("/wars")
def declare_war(body: WarIn, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    war = mil.declare_war(db, player, body.kingdom_id, body.target_id)
    commit(db)
    return mil.serialize_war(war)


@router.get("/wars")
def list_wars(world_id: str, _: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    get_world(db, world_id)
    return [mil.serialize_war(w) for w in mil.wars_in_world(db, world_id)]


@router.post("/wars/{war_id}/peace")
def peace(war_id: str, body: KingdomActionIn, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    result = mil.propose_peace(db, player, body.kingdom_id, war_id)
    commit(db)
    return result


@router.post("/battles")
def start_battle(body: BattleIn, key: str | None = IdempotencyKey, player: Player = Depends(get_current_player),
                 db: Session = Depends(get_db)):
    """Server-side strategic battle. Declares war first if needed (attacking an ally = Betrayal)."""
    return idempotent(db, player, key, "battles:create",
                      lambda: mil.serialize_battle(mil.battle(db, player, body.kingdom_id, body.target_id, body.soldiers)))


@router.get("/battles")
def list_battles(world_id: str, _: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    get_world(db, world_id)
    return [mil.serialize_battle(b) for b in mil.battles_in_world(db, world_id)]
