"""Royal Market (gold has a use) and Drakoria's ultimatums (a solo ruler faces a real decision)."""

from app.database import SessionLocal
from app.game.rules import MARKET_UNITS_PER_LEVEL, ULTIMATUM_DEADLINE_TURNS
from app.models import Kingdom
from app.services.ultimatum_service import DEMAND_SUBJECT, tribute_for
from tests.conftest import Ruler, advance, join, new_world


def _set(kid: str, **fields):
    with SessionLocal() as db:
        k = db.get(Kingdom, kid)
        for f, v in fields.items():
            setattr(k, f, v)
        db.commit()


def _solo(client, kingdom="Aurelia") -> tuple[dict, Ruler]:
    me = Ruler(client, "solo_ruler")
    world = new_world(me, "solo_court")
    join(me, world["id"], kingdom)
    return world, me


def test_market_buys_and_sells_at_fixed_prices_with_a_cap(client):
    _, me = _solo(client)
    view = me.get(f"/market?kingdom_id={me.kid}").json()
    assert view["open"] and view["units_left"] == MARKET_UNITS_PER_LEVEL
    wood_price = view["prices"]["wood"]["buy"]
    before = me.resources()
    r = me.post("/market", {"kingdom_id": me.kid, "resource": "wood", "amount": 100, "side": "buy"}, key="m1")
    assert r.status_code == 200, r.text
    after = me.resources()
    assert after["wood"] == before["wood"] + 100 and after["gold"] == before["gold"] - 100 * wood_price
    # Replaying the same key does not charge twice.
    assert me.post("/market", {"kingdom_id": me.kid, "resource": "wood", "amount": 100, "side": "buy"}, key="m1").status_code == 200
    assert me.resources()["wood"] == after["wood"]
    # Selling back loses value: no arbitrage.
    assert view["prices"]["wood"]["sell"] < wood_price
    # The cap counts units bought and sold this turn.
    r = me.post("/market", {"kingdom_id": me.kid, "resource": "stone", "amount": MARKET_UNITS_PER_LEVEL, "side": "buy"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "market_capacity"
    advance(me, me.kingdom["world_id"])
    assert me.get(f"/market?kingdom_id={me.kid}").json()["units_left"] == MARKET_UNITS_PER_LEVEL


def test_market_needs_a_market_and_rejects_gold(client):
    _, me = _solo(client, "Drakoria")      # Drakoria starts without a market
    r = me.post("/market", {"kingdom_id": me.kid, "resource": "wood", "amount": 10, "side": "buy"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "missing_building"
    r = me.post("/market", {"kingdom_id": me.kid, "resource": "gold", "amount": 10, "side": "buy"})
    assert r.status_code == 400


def _drakoria(me: Ruler) -> dict:
    return next(r for r in me.get(f"/kingdoms/{me.kid}/dashboard").json()["relations"] if r["name"] == "Drakoria")


def _run_to_ultimatum(me: Ruler, world_id: str) -> dict:
    drak = _drakoria(me)
    _set(drak["kingdom_id"], soldiers=200, gold=3000)    # make sure Drakoria is strong enough to threaten
    for _ in range(8):
        advance(me, world_id)
        demands = me.get(f"/kingdoms/{me.kid}/dashboard").json()["ultimatums"]
        if demands:
            return demands[0]
    raise AssertionError("Drakoria never issued an ultimatum")


def test_ignored_ultimatum_means_war(client):
    world, me = _solo(client)
    demand = _run_to_ultimatum(me, world["id"])
    assert demand["from"] == "Drakoria" and demand["owed"] == tribute_for(demand["deadline_turn"] - ULTIMATUM_DEADLINE_TURNS)
    assert not demand["safe"]
    letters = me.get(f"/messages?kingdom_id={me.kid}").json()
    assert any(m["subject"] == DEMAND_SUBJECT for m in letters)
    for _ in range(demand["turns_left"]):
        advance(me, world["id"])
    dash = me.get(f"/kingdoms/{me.kid}/dashboard").json()
    assert _drakoria(me)["war_id"], "Drakoria should march when tribute is ignored"
    assert dash["ultimatums"] == []
    assert any(e["event_type"] == "ULTIMATUM_IGNORED" for e in me.get(f"/worlds/{world['id']}/chronicle").json())


def test_paid_tribute_keeps_the_peace(client):
    world, me = _solo(client)
    demand = _run_to_ultimatum(me, world["id"])
    r = me.post("/gifts", {"kingdom_id": me.kid, "target_id": demand["from_id"], "gold": demand["owed"]}, key="tribute")
    assert r.status_code == 200, r.text
    assert me.get(f"/kingdoms/{me.kid}/dashboard").json()["ultimatums"][0]["owed"] == 0
    for _ in range(demand["turns_left"] + 1):
        advance(me, world["id"])
    assert not _drakoria(me)["war_id"]
    subjects = [m["subject"] for m in me.get(f"/messages?kingdom_id={me.kid}").json()]
    assert "Tribute Accepted" in subjects


def test_strong_defences_make_drakoria_back_down(client):
    world, me = _solo(client)
    demand = _run_to_ultimatum(me, world["id"])
    _set(me.kid, soldiers=400)                           # the ruler arms instead of paying
    assert me.get(f"/kingdoms/{me.kid}/dashboard").json()["ultimatums"][0]["safe"]
    for _ in range(demand["turns_left"]):
        advance(me, world["id"])
    assert not _drakoria(me)["war_id"]
    assert any(e["event_type"] == "ULTIMATUM_DEFIED" for e in me.get(f"/worlds/{world['id']}/chronicle").json())
