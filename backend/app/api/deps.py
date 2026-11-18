"""Request helpers: commit + publish, and idempotent execution (spec §6.1 duplicate requests)."""

from collections.abc import Callable

from fastapi import Header
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import conflict
from app.models import IdempotencyRecord, Player
from app.realtime import hub


def commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        db.info.pop("outbox", None)
        raise conflict("That request was already processed (duplicate)")
    hub.publish_threadsafe(db.info.pop("outbox", []))


def idempotent(db: Session, player: Player, key: str | None, scope: str, action: Callable[[], dict]):
    """Run `action` once per (player, Idempotency-Key). Replays return the original response.

    A rapid double-pinch in VR (test XR-09) sends the same key twice; only one transfer happens.
    """
    if key:
        existing = db.get(IdempotencyRecord, (key, player.id))
        if existing:
            if existing.scope != scope:
                raise conflict("This Idempotency-Key was already used for a different action")
            return JSONResponse(existing.response_body, status_code=existing.status_code,
                                headers={"Idempotent-Replay": "true"})
    result = action()
    if key:
        db.add(IdempotencyRecord(key=key, player_id=player.id, scope=scope, status_code=200, response_body=result))
    commit(db)
    return result


IdempotencyKey = Header(default=None, alias="Idempotency-Key", max_length=80)
