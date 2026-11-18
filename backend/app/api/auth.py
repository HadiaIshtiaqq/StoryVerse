from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import commit
from app.database import get_db
from app.errors import GameError, conflict
from app.models import Kingdom, Player
from app.schemas import LoginIn, RegisterIn
from app.security import create_token, get_current_player, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
_DUMMY_HASH = hash_password("timing-equaliser")


def _player(p: Player) -> dict:
    return {"id": p.id, "username": p.username}


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.execute(select(Player).where(Player.username == body.username)).scalars().first():
        raise conflict("That username is taken")
    player = Player(username=body.username, email=body.email, password_hash=hash_password(body.password))
    db.add(player)
    commit(db)
    return {"token": create_token(player.id), "player": _player(player)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    player = db.execute(select(Player).where(Player.username == body.username)).scalars().first()
    # Always run one PBKDF2 check so unknown and known usernames take the same time (no account enumeration).
    valid = verify_password(body.password, player.password_hash if player else _DUMMY_HASH)
    if player is None or not valid:
        raise GameError("Wrong username or password", code="unauthorized", status=401)
    return {"token": create_token(player.id), "player": _player(player)}


@router.get("/me")
def me(player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    kingdoms = db.execute(select(Kingdom).where(Kingdom.owner_id == player.id)).scalars()
    return {"player": _player(player),
            "kingdoms": [{"kingdom_id": k.id, "world_id": k.world_id, "name": k.name} for k in kingdoms]}
