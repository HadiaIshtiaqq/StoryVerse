import os
import uuid

# In-memory SQLite by default; set TEST_DATABASE_URL to run the suite against PostgreSQL. Set before app import.
# WARNING: tests drop and recreate every table in that database. Never point it at real game data.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


class Ruler:
    """A logged-in test player bound to one kingdom."""

    def __init__(self, client: TestClient, name: str):
        self.client = client
        r = client.post("/auth/register", json={"username": name, "password": "correct-horse-1"})
        assert r.status_code == 200, r.text
        self.headers = {"Authorization": f"Bearer {r.json()['token']}"}
        self.kingdom: dict = {}

    def get(self, path, **kw):
        return self.client.get(path, headers=self.headers, **kw)

    def post(self, path, json=None, key: str | None = None):
        headers = dict(self.headers)
        if key:
            headers["Idempotency-Key"] = key
        return self.client.post(path, json=json, headers=headers)

    def patch(self, path):
        return self.client.patch(path, headers=self.headers)

    @property
    def kid(self) -> str:
        return self.kingdom["id"]

    def resources(self) -> dict:
        r = self.get(f"/kingdoms/{self.kid}/resources")
        assert r.status_code == 200, r.text
        return r.json()


def new_world(host: Ruler, preset: str = "standard") -> dict:
    r = host.post("/worlds", {"name": f"Test Realm {uuid.uuid4().hex[:4]}", "preset": preset})
    assert r.status_code == 200, r.text
    return r.json()


def join(ruler: Ruler, world_id: str, kingdom_name: str | None = None) -> dict:
    r = ruler.post("/worlds/join", {"world_id": world_id, "kingdom_name": kingdom_name})
    assert r.status_code == 200, r.text
    ruler.kingdom = r.json()
    return ruler.kingdom


@pytest.fixture()
def four(client):
    """Four human rulers in one world: Aurelia, Drakoria, Sylvara, Valoria."""
    names = ["Aurelia", "Drakoria", "Sylvara", "Valoria"]
    rulers = [Ruler(client, f"player_{n.lower()}") for n in names]
    world = new_world(rulers[0])
    for ruler, name in zip(rulers, names):
        join(ruler, world["id"], name)
        ruler.table = rulers          # everyone at the table, for the end-turn ready check
    return world, dict(zip(names, rulers))


def advance(ruler: Ruler, world_id: str, times: int = 1) -> dict:
    """End the turn. In a shared world every human ruler votes ready first (the real multiplayer flow)."""
    out = {}
    for _ in range(times):
        for other in getattr(ruler, "table", []):
            if other is not ruler:
                r = other.post(f"/worlds/{world_id}/turn")
                assert r.status_code == 200 and r.json()["advanced"] is False, r.text
        r = ruler.post(f"/worlds/{world_id}/turn")
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["advanced"] is True, out
    return out


def chronicle_types(ruler: Ruler, world_id: str) -> list[str]:
    return [e["event_type"] for e in ruler.get(f"/worlds/{world_id}/chronicle").json()]
