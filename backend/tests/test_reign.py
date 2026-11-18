"""A reign has an ending: at the turn limit the most prestigious ruler is crowned and the world closes."""

from app.database import SessionLocal
from app.game.rules import WORLD_PRESETS
from app.models import World
from tests.conftest import Ruler, new_world


def _solo(client, name="reign_judge"):
    judge = Ruler(client, name)
    world = new_world(judge, preset="solo_court")
    judge.post("/worlds/join", {"world_id": world["id"], "kingdom_name": "Sylvara"})
    judge.kingdom = judge.get("/auth/me").json()["kingdoms"][0]
    judge.kingdom["id"] = judge.kingdom["kingdom_id"]
    return world, judge


def test_dashboard_shows_turn_limit_and_status(client):
    world, judge = _solo(client)
    w = judge.get(f"/kingdoms/{judge.kid}/dashboard").json()["world"]
    assert w["turn_limit"] == WORLD_PRESETS["solo_court"]["turn_limit"] and w["status"] == "ACTIVE" and w["coronation"] is None
    listed = next(x for x in judge.get("/worlds").json() if x["id"] == world["id"])
    assert listed["status"] == "ACTIVE" and listed["turn_limit"] == w["turn_limit"]


def test_reign_ends_with_a_coronation_and_no_more_turns(client):
    world, judge = _solo(client, "reign_judge2")
    limit = WORLD_PRESETS["solo_court"]["turn_limit"]
    with SessionLocal() as db:                       # fast-forward to the eve of the coronation
        db.get(World, world["id"]).turn = limit - 1
        db.commit()
    last = judge.post(f"/worlds/{world['id']}/turn").json()
    assert last["turn"] == limit and last["ended"] is True
    w = judge.get(f"/kingdoms/{judge.kid}/dashboard").json()["world"]
    assert w["status"] == "ENDED" and w["coronation"]["winner_name"] in ("Aurelia", "Drakoria", "Sylvara", "Valoria")
    board = judge.get(f"/kingdoms/{judge.kid}/dashboard").json()["leaderboard"]
    assert w["coronation"]["winner_name"] == board[0]["name"]
    events = [e["event_type"] for e in judge.get(f"/worlds/{world['id']}/chronicle").json()]
    assert "CORONATION" in events
    again = judge.post(f"/worlds/{world['id']}/turn")
    assert again.status_code == 409 and "reign has ended" in again.json()["error"]["message"]


def test_coronation_warning_in_the_final_turns(client):
    world, judge = _solo(client, "reign_judge3")
    limit = WORLD_PRESETS["solo_court"]["turn_limit"]
    with SessionLocal() as db:
        db.get(World, world["id"]).turn = limit - 3
        db.commit()
    judge.post(f"/worlds/{world['id']}/turn")
    notes = judge.get(f"/kingdoms/{judge.kid}/dashboard").json()["notifications"]
    assert any(n["kind"] == "CORONATION_NEAR" for n in notes)
