"""WebSocket fan-out for application events (spec §2.1: WebSockets for real-time messaging).

Photon Fusion carries hands, avatars and held objects; this channel carries authoritative
game results (balances, letters, chronicle) after they are committed to PostgreSQL.
Events with `private_to` are delivered only to that kingdom's sockets (spec §6.2).
"""

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class Hub:
    def __init__(self) -> None:
        self.rooms: dict[str, set[tuple[WebSocket, str | None]]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket, world_id: str, kingdom_id: str | None) -> None:
        await ws.accept()
        self.loop = asyncio.get_running_loop()
        self.rooms[world_id].add((ws, kingdom_id))

    def disconnect(self, ws: WebSocket, world_id: str, kingdom_id: str | None) -> None:
        self.rooms[world_id].discard((ws, kingdom_id))

    async def publish(self, events: list[dict]) -> None:
        for event in events:
            private = event.get("private_to")
            for ws, kingdom_id in list(self.rooms.get(event.get("world_id", ""), ())):
                if private and kingdom_id != private:
                    continue
                try:
                    await ws.send_json(event)
                except Exception:  # client went away mid-send
                    self.rooms[event["world_id"]].discard((ws, kingdom_id))

    def publish_threadsafe(self, events: list[dict]) -> None:
        """Called from sync endpoints (worker threads) after commit; never blocks the request."""
        if events and self.loop and self.loop.is_running() and any(self.rooms.values()):
            asyncio.run_coroutine_threadsafe(self.publish(events), self.loop)


hub = Hub()
