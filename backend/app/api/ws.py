from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database import SessionLocal
from app.errors import GameError
from app.models import Kingdom, World
from app.realtime import hub
from app.security import decode_token

router = APIRouter()


@router.websocket("/ws/worlds/{world_id}")
async def world_socket(ws: WebSocket, world_id: str, token: str):
    """Live world events. Private events (letters, balances) reach only the owning kingdom."""
    try:
        player_id = decode_token(token)
    except GameError:
        await ws.close(code=4401)
        return
    with SessionLocal() as db:
        world = db.get(World, world_id)
        if world is None:
            await ws.close(code=4404)
            return
        mine = db.execute(select(Kingdom).where(Kingdom.world_id == world_id, Kingdom.owner_id == player_id)).scalars().first()
        # Only rulers of this world (or its creator) may listen in: treaties, battles and turn votes are table talk.
        if mine is None and world.created_by != player_id:
            await ws.close(code=4403)
            return
        kingdom_id = mine.id if mine else None
    await hub.connect(ws, world_id, kingdom_id)
    try:
        await ws.send_json({"type": "connected", "world_id": world_id, "kingdom_id": kingdom_id})
        while True:
            if (await ws.receive_text()) == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(ws, world_id, kingdom_id)
