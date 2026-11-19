"""Features from the reference pictures: settlement buildings, military passage, gifts with iron,
Royal Decrees (objectives) and the Royal Council (advisers)."""

from app.database import SessionLocal
from app.game.rules import BUILDINGS, DECREES_SHOWN, PASSAGE_GOLD_PER_TURN
from app.models import Kingdom
from tests.conftest import advance


def _set(kid: str, **fields):
    with SessionLocal() as db:
        k = db.get(Kingdom, kid)
        for f, v in fields.items():
            setattr(k, f, v)
        db.commit()


def test_catalog_has_settlement_buildings_with_lore_and_categories(four):
    _, r = four
    cat = r["Aurelia"].get(f"/buildings/catalog?kingdom_id={r['Aurelia'].kid}").json()
    types = {b["building_type"]: b for b in cat}
    assert len(types) == len(BUILDINGS) == 15
    for t in ("houses", "tavern", "mansions", "blacksmith", "granary"):
        assert types[t]["lore"] and types[t]["category"] in ("economy", "military", "civic", "housing")
    assert types["houses"]["category"] == "housing" and types["blacksmith"]["category"] == "military"


def test_houses_grow_the_population(four):
    world, r = four
    s = r["Sylvara"]
    before = s.get(f"/kingdoms/{s.kid}/dashboard").json()["kingdom"]["population"]
    assert s.post("/buildings", {"kingdom_id": s.kid, "building_type": "houses", "x": 0.30, "z": 0.75}).status_code == 200
    advance(s, world["id"])
    after = s.get(f"/kingdoms/{s.kid}/dashboard").json()["kingdom"]["population"]
    assert after - before >= 2 + 3          # base growth + one level of houses


def test_granary_halves_famine_losses(four):
    world, r = four
    a, d = r["Aurelia"], r["Drakoria"]
    gr = a.post("/buildings", {"kingdom_id": a.kid, "building_type": "granary", "x": 0.20, "z": 0.32})
    assert gr.status_code == 200, gr.text
    for k in (a, d):
        _set(k.kid, food=0, population=400)
    advance(a, world["id"])
    lost_a = 400 - a.get(f"/kingdoms/{a.kid}/dashboard").json()["kingdom"]["population"]
    lost_d = 400 - d.get(f"/kingdoms/{d.kid}/dashboard").json()["kingdom"]["population"]
    assert lost_d == 20 and lost_a == 10    # 1/20 of the people, halved by the granary


def test_passage_rules_tolls_and_closing(four):
    world, r = four
    a, v, d, s = r["Aurelia"], r["Valoria"], r["Drakoria"], r["Sylvara"]
    # Drakoria and Sylvara start Cold (-10): roads stay shut.
    assert d.post("/passages", {"kingdom_id": d.kid, "target_id": s.kid}).status_code == 403
    before = next(x for x in a.get(f"/kingdoms/{a.kid}/dashboard").json()["relations"] if x["kingdom_id"] == v.kid)["standing"]
    res = a.post("/passages", {"kingdom_id": a.kid, "target_id": v.kid})
    assert res.status_code == 200, res.text
    pid = res.json()["id"]
    assert a.post("/passages", {"kingdom_id": a.kid, "target_id": v.kid}).status_code == 409      # already open
    rel = next(x for x in a.get(f"/kingdoms/{a.kid}/dashboard").json()["relations"] if x["kingdom_id"] == v.kid)
    assert rel["standing"] >= before + 5 and rel["passage_granted"]["id"] == pid   # Valoria's +10% diplomacy bonus may round up
    assert rel["actions"]["passage"]["allowed"] is False
    # Both realms earn road tolls (it shows in their per-turn yield) and the treaty is public on the map.
    ya = a.get(f"/kingdoms/{a.kid}/dashboard").json()["kingdom"]["yield_per_turn"]["gold"]
    assert any(p["id"] == pid for p in a.get(f"/worlds/{world['id']}/map").json()["treaties"]["passages"])
    assert v.post(f"/passages/{pid}/close", {"kingdom_id": v.kid}).status_code == 403            # only the grantor
    assert a.post(f"/passages/{pid}/close", {"kingdom_id": a.kid}).status_code == 200
    yb = a.get(f"/kingdoms/{a.kid}/dashboard").json()["kingdom"]["yield_per_turn"]["gold"]
    assert ya - yb == PASSAGE_GOLD_PER_TURN
    assert "PASSAGE_CLOSED" in [e["event_type"] for e in a.get(f"/worlds/{world['id']}/chronicle").json()]


def test_war_closes_open_roads(four):
    world, r = four
    a, v = r["Aurelia"], r["Valoria"]
    pid = a.post("/passages", {"kingdom_id": a.kid, "target_id": v.kid}).json()["id"]
    advance(a, world["id"], 3)                                    # past beginner protection
    assert a.post("/wars", {"kingdom_id": a.kid, "target_id": v.kid}).status_code == 200
    assert not any(p["id"] == pid for p in a.get(f"/worlds/{world['id']}/map").json()["treaties"]["passages"])


def test_gift_chest_carries_iron(four):
    _, r = four
    a, v = r["Aurelia"], r["Valoria"]
    tiers = a.get(f"/gifts/tiers?kingdom_id={a.kid}&target_id={v.kid}").json()["tiers"]
    assert all(t["iron"] > 0 for t in tiers)
    t = tiers[0]
    before_a, before_v = a.resources(), v.resources()
    res = a.post("/gifts", {"kingdom_id": a.kid, "target_id": v.kid, "gold": t["gold"], "iron": t["iron"]}, key="iron-gift-1")
    assert res.status_code == 200 and res.json()["iron"] == t["iron"]
    assert a.resources()["iron"] == before_a["iron"] - t["iron"] and v.resources()["iron"] == before_v["iron"] + t["iron"]
    assert a.post("/gifts", {"kingdom_id": a.kid, "target_id": v.kid, "gold": 10, "iron": 10**9}).status_code == 422


def test_decrees_progress_claim_and_no_double_claim(four):
    _, r = four
    a = r["Aurelia"]
    decrees = a.get(f"/kingdoms/{a.kid}/decrees").json()
    assert 0 < len(decrees) <= DECREES_SHOWN and all("progress" in d and "need" in d for d in decrees)
    assert a.post("/decrees/sow_fields/claim", {"kingdom_id": a.kid}).status_code in (400, 409, 422)  # not done yet
    for x in (0.30, 0.34):
        a.post("/buildings", {"kingdom_id": a.kid, "building_type": "farm", "x": x, "z": 0.40})
    sow = next(d for d in a.get(f"/kingdoms/{a.kid}/decrees").json() if d["key"] == "sow_fields")
    assert sow["complete"] is True
    wood = a.resources()["wood"]
    res = a.post("/decrees/sow_fields/claim", {"kingdom_id": a.kid})
    assert res.status_code == 200, res.text
    assert a.resources()["wood"] == wood + 150
    assert a.post("/decrees/sow_fields/claim", {"kingdom_id": a.kid}).status_code == 409
    assert all(d["key"] != "sow_fields" for d in a.get(f"/kingdoms/{a.kid}/decrees").json())
    ledger = a.get(f"/kingdoms/{a.kid}/ledger?limit=5").json()
    assert any(e["type"] == "DECREE_REWARD" for e in ledger)


def test_royal_council_reads_the_realm(four):
    _, r = four
    s = r["Sylvara"]
    council = s.get(f"/kingdoms/{s.kid}/council").json()
    assert {c["name"] for c in council} == {"Lord Wren Fernhallow", "Elder Mossa", "Princess Lirael"}
    assert all(c["advice"] and c["portrait"] for c in council)
    _set(s.kid, food=30, population=600)                          # starving realm: the herbalist must warn, urgently
    mossa = next(c for c in s.get(f"/kingdoms/{s.kid}/council").json() if c["name"] == "Elder Mossa")
    assert mossa["urgency"] == 2 and "food" in mossa["advice"]
    assert "decrees" in s.get(f"/kingdoms/{s.kid}/dashboard").json()
