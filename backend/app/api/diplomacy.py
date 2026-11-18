"""Alliances, letters, Standing Gauge, gifts."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import IdempotencyKey, commit, idempotent
from app.database import get_db
from app.models import Player
from app.schemas import AllianceIn, AllianceRespondIn, GiftIn, KingdomActionIn, MessageIn, PassageIn
from app.security import get_current_player
from app.services import diplomacy_service as dip
from app.services import economy_service as eco
from app.services import story_service
from app.services.common import get_world

router = APIRouter(tags=["diplomacy"])


@router.post("/alliances")
def propose_alliance(body: AllianceIn, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    a = dip.propose_alliance(db, player, body.kingdom_id, body.target_id, body.duration_turns, body.mutual_defense)
    commit(db)
    return dip.serialize_alliance(a)


@router.get("/alliances")
def list_alliances(world_id: str, _: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    get_world(db, world_id)
    return [dip.serialize_alliance(a) for a in dip.alliances_in_world(db, world_id)]


@router.post("/alliances/{alliance_id}/respond")
def respond_alliance(alliance_id: str, body: AllianceRespondIn, player: Player = Depends(get_current_player),
                     db: Session = Depends(get_db)):
    a = dip.respond_alliance(db, player, alliance_id, body.accept)
    commit(db)
    return dip.serialize_alliance(a)


@router.post("/alliances/{alliance_id}/terminate")
def terminate_alliance(alliance_id: str, body: KingdomActionIn, player: Player = Depends(get_current_player),
                       db: Session = Depends(get_db)):
    event = dip.terminate_alliance(db, player, alliance_id, body.kingdom_id)
    commit(db)
    return {"chronicle_event": story_service.serialize(event)}


@router.post("/messages")
def send_message(body: MessageIn, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    m = dip.send_message(db, player, body.kingdom_id, body.recipient_id, body.subject, body.body, body.tone)
    commit(db)
    return dip.serialize_message(m)


@router.get("/messages")
def list_messages(kingdom_id: str, box: str = "inbox", player: Player = Depends(get_current_player),
                  db: Session = Depends(get_db)):
    return [dip.serialize_message(m) for m in dip.letters(db, player, kingdom_id, "sent" if box == "sent" else "inbox")]


@router.post("/messages/{message_id}/read")
def read_message(message_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    m = dip.mark_read(db, player, message_id)
    commit(db)
    return dip.serialize_message(m)


@router.get("/relations/{kingdom_id}")
def relations(kingdom_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    """Standing Gauge data: score, band, trend, last reasons, unlocked actions and locked reasons."""
    return dip.relations_view(db, player, kingdom_id)


@router.get("/gifts/tiers")
def gift_tiers(kingdom_id: str, target_id: str, player: Player = Depends(get_current_player),
               db: Session = Depends(get_db)):
    """Three coin chests with their exact standing effect, shown *before* confirming."""
    return eco.gift_preview(db, player, kingdom_id, target_id)


@router.post("/gifts")
def send_gift(body: GiftIn, key: str | None = IdempotencyKey, player: Player = Depends(get_current_player),
              db: Session = Depends(get_db)):
    return idempotent(db, player, key, "gifts:create",
                      lambda: eco.send_gift(db, player, body.kingdom_id, body.target_id, body.gold, body.iron))


# ------------------------------------------------------------------ military passage (open roads)
@router.post("/passages")
def grant_passage(body: PassageIn, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    """Open your roads to another realm (Peaceful standing or better). Both realms earn road tolls each turn."""
    p = dip.grant_passage(db, player, body.kingdom_id, body.target_id)
    commit(db)
    return dip.serialize_passage(p)


@router.post("/passages/{passage_id}/close")
def close_passage(passage_id: str, body: KingdomActionIn, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    """Terminate passage: shut your roads to them (a diplomatic slight, not a betrayal)."""
    p = dip.close_passage(db, player, passage_id, body.kingdom_id)
    commit(db)
    return dip.serialize_passage(p)
