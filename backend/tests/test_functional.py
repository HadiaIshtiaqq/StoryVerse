"""Spec §7.3 functional test cases TC-01 … TC-20."""

from tests.conftest import Ruler, advance, chronicle_types, join, new_world


def test_tc01_register_and_login(client):
    r = client.post("/auth/register", json={"username": "aldric", "password": "golden-sun-99"})
    assert r.status_code == 200 and r.json()["token"]
    assert client.post("/auth/login", json={"username": "aldric", "password": "golden-sun-99"}).status_code == 200
    bad = client.post("/auth/login", json={"username": "aldric", "password": "wrong-password"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "unauthorized"
    assert client.post("/auth/register", json={"username": "aldric", "password": "another-pass1"}).status_code == 409


def test_tc02_tc03_join_world_assigns_distinct_kingdoms(four):
    world, rulers = four
    ids = {r.kid for r in rulers.values()}
    assert len(ids) == 4
    assert rulers["Aurelia"].kingdom["resources"]["gold"] == 5000
    view = rulers["Sylvara"].get(f"/worlds/{world['id']}").json()
    assert all(not k["is_npc"] for k in view["kingdoms"])
    extra = Ruler(rulers["Aurelia"].client, "latecomer")
    r = extra.post("/worlds/join", {"world_id": world["id"]})
    assert r.status_code == 409 and "full" in r.json()["error"]["message"]


def test_tc04_place_a_farm(four):
    _, r = four
    a = r["Aurelia"]
    before = a.resources()
    resp = a.post("/buildings", {"kingdom_id": a.kid, "building_type": "farm", "x": 0.28, "z": 0.45})
    assert resp.status_code == 200, resp.text
    assert resp.json()["building_type"] == "farm"
    assert a.resources()["wood"] == before["wood"] - 100
    assert any(b["id"] == resp.json()["id"] for b in a.get(f"/kingdoms/{a.kid}/buildings").json())


def test_tc05_build_without_resources_is_rejected_with_reason(four):
    _, r = four
    a = r["Aurelia"]
    # A farm costs 100 wood; Aurelia starts with 400 wood -> the fifth farm is unaffordable.
    for x in (0.16, 0.20, 0.36, 0.40):
        assert a.post("/buildings", {"kingdom_id": a.kid, "building_type": "farm", "x": x, "z": 0.45}).status_code == 200
    resp = a.post("/buildings", {"kingdom_id": a.kid, "building_type": "farm", "x": 0.28, "z": 0.20})
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "insufficient_resources" and err["resource"] == "wood"


def test_invalid_placement_reasons(four):
    _, r = four
    a = r["Aurelia"]
    far = a.post("/buildings", {"kingdom_id": a.kid, "building_type": "farm", "x": 0.9, "z": 0.9})
    assert far.status_code == 400 and "borders" in far.json()["error"]["message"]
    a.post("/buildings", {"kingdom_id": a.kid, "building_type": "farm", "x": 0.28, "z": 0.45})
    near = a.post("/buildings", {"kingdom_id": a.kid, "building_type": "farm", "x": 0.285, "z": 0.45})
    assert near.status_code == 400 and "Insufficient space" in near.json()["error"]["message"]


def test_tc06_upgrade_building(four):
    _, r = four
    a = r["Aurelia"]
    farm = a.post("/buildings", {"kingdom_id": a.kid, "building_type": "farm", "x": 0.28, "z": 0.45}).json()
    up = a.patch(f"/buildings/{farm['id']}/upgrade")
    assert up.status_code == 200 and up.json()["level"] == 2
    other = r["Drakoria"].patch(f"/buildings/{farm['id']}/upgrade")
    assert other.status_code == 403


def test_tc07_collect_resources_on_turn(four):
    world, r = four
    s = r["Sylvara"]
    before = s.resources()
    advance(s, world["id"])
    after = s.resources()
    # Two farms (40 * 1.15 each) minus population/soldier food upkeep -> net positive food.
    assert after["food"] > before["food"]
    assert after["wood"] > before["wood"]


def test_tc08_09_trade_offer_and_accept_updates_both(four):
    _, r = four
    s, d = r["Sylvara"], r["Drakoria"]
    s_before, d_before = s.resources(), d.resources()
    offer = s.post("/trades", {"kingdom_id": s.kid, "receiver_id": d.kid, "offered_resource": "food",
                               "offered_amount": 100, "requested_resource": "iron", "requested_amount": 80})
    assert offer.status_code == 200 and offer.json()["status"] == "PENDING"
    inbox = d.get(f"/kingdoms/{d.kid}/dashboard").json()["inbox"]["trades"]
    assert [t["id"] for t in inbox] == [offer.json()["id"]]
    acc = d.post(f"/trades/{offer.json()['id']}/accept")
    assert acc.status_code == 200 and acc.json()["status"] == "ACCEPTED"
    assert s.resources()["food"] == s_before["food"] - 100 and s.resources()["iron"] == s_before["iron"] + 80
    assert d.resources()["food"] == d_before["food"] + 100 and d.resources()["iron"] == d_before["iron"] - 80
    ledger = s.get(f"/kingdoms/{s.kid}/ledger").json()
    assert {e["type"] for e in ledger} == {"TRADE"}
    # accepting twice is impossible
    assert d.post(f"/trades/{offer.json()['id']}/accept").status_code == 409


def test_tc10_reject_trade_moves_nothing(four):
    _, r = four
    s, v = r["Sylvara"], r["Valoria"]
    before = s.resources()
    offer = s.post("/trades", {"kingdom_id": s.kid, "receiver_id": v.kid, "offered_resource": "food",
                               "offered_amount": 50, "requested_resource": "gold", "requested_amount": 60}).json()
    assert v.post(f"/trades/{offer['id']}/reject").json()["status"] == "REJECTED"
    assert s.resources() == before


def test_trade_revalidates_balance_at_accept(four):
    _, r = four
    s, v = r["Sylvara"], r["Valoria"]
    offer = s.post("/trades", {"kingdom_id": s.kid, "receiver_id": v.kid, "offered_resource": "stone",
                               "offered_amount": 300, "requested_resource": "gold", "requested_amount": 600}).json()
    # Sylvara spends its stone before Valoria accepts.
    s.post("/buildings", {"kingdom_id": s.kid, "building_type": "hospital", "x": 0.27, "z": 0.85})
    s.post("/buildings", {"kingdom_id": s.kid, "building_type": "hospital", "x": 0.37, "z": 0.80})
    resp = v.post(f"/trades/{offer['id']}/accept")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "insufficient_resources"


def test_tc11_12_13_loan_offer_accept_repay(four):
    world, r = four
    a, d = r["Aurelia"], r["Drakoria"]
    loan = a.post("/loans", {"kingdom_id": a.kid, "counterparty_id": d.kid, "role": "lender",
                             "principal": 2000, "interest_rate": 10, "duration_turns": 5})
    assert loan.status_code == 200, loan.text
    loan = loan.json()
    assert loan["status"] == "PROPOSED" and loan["total_repayment"] == 2200 and loan["code"] == "LN-001"
    a_gold, d_gold = a.resources()["gold"], d.resources()["gold"]
    acc = d.post(f"/loans/{loan['id']}/accept").json()
    assert acc["status"] == "ACTIVE"
    assert a.resources()["gold"] == a_gold - 2000 and d.resources()["gold"] == d_gold + 2000
    rep = d.post(f"/loans/{loan['id']}/repay", {"amount": 500}).json()
    assert rep["amount_repaid"] == 500 and rep["remaining"] == 1700
    over = d.post(f"/loans/{loan['id']}/repay", {"amount": 5000})
    assert over.status_code == 400 and over.json()["error"]["code"] == "overpayment"
    d.post(f"/loans/{loan['id']}/repay", {"amount": 1700})
    final = [l for l in d.get(f"/loans?kingdom_id={d.kid}").json() if l["id"] == loan["id"]][0]
    assert final["status"] == "REPAID"
    assert "LOAN_REPAID" in chronicle_types(a, world["id"])


def test_loan_rules(four):
    _, r = four
    a, d, s = r["Aurelia"], r["Drakoria"], r["Sylvara"]
    no_bank = d.post("/loans", {"kingdom_id": d.kid, "counterparty_id": s.kid, "role": "lender",
                                "principal": 500, "interest_rate": 5, "duration_turns": 3})
    assert no_bank.status_code == 400 and "Bank" in no_bank.json()["error"]["message"]
    too_much = a.post("/loans", {"kingdom_id": a.kid, "counterparty_id": d.kid, "role": "lender",
                                 "principal": 999_999, "interest_rate": 5, "duration_turns": 3})
    assert too_much.status_code == 400
    # Credit limit: Drakoria has 3 building levels -> limit 2000 + 900 = 2900; 2,200 owed is fine, 4,400 is not.
    big = a.post("/loans", {"kingdom_id": a.kid, "counterparty_id": d.kid, "role": "lender",
                            "principal": 4000, "interest_rate": 10, "duration_turns": 5}).json()
    resp = d.post(f"/loans/{big['id']}/accept")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "credit_limit"
    # only the counterparty may accept
    assert a.post(f"/loans/{big['id']}/accept").status_code == 403


def test_loan_auto_installments_and_default(four):
    world, r = four
    a, d = r["Aurelia"], r["Drakoria"]
    loan = a.post("/loans", {"kingdom_id": a.kid, "counterparty_id": d.kid, "role": "lender",
                             "principal": 1000, "interest_rate": 10, "duration_turns": 2}).json()
    d.post(f"/loans/{loan['id']}/accept")
    advance(a, world["id"])
    l = [x for x in d.get(f"/loans?kingdom_id={d.kid}").json() if x["id"] == loan["id"]][0]
    assert l["amount_repaid"] == 550  # first auto installment
    # Drakoria gives all its gold away so it cannot pay the rest.
    gold = d.resources()["gold"]
    d.post("/gifts", {"kingdom_id": d.kid, "target_id": r["Sylvara"].kid, "gold": gold})
    advance(a, world["id"], 4)
    l = [x for x in d.get(f"/loans?kingdom_id={d.kid}").json() if x["id"] == loan["id"]][0]
    assert l["status"] == "DEFAULTED" and l["missed_payments"] >= 1
    assert "LOAN_DEFAULTED" in chronicle_types(a, world["id"])


def test_tc14_15_alliance_request_and_accept(four):
    world, r = four
    a, v = r["Aurelia"], r["Valoria"]
    prop = a.post("/alliances", {"kingdom_id": a.kid, "target_id": v.kid, "duration_turns": 5})
    assert prop.status_code == 200 and prop.json()["status"] == "PENDING"
    notes = v.get(f"/kingdoms/{v.kid}/notifications").json()
    assert any(n["kind"] == "ALLIANCE_PROPOSED" for n in notes)
    acc = v.post(f"/alliances/{prop.json()['id']}/respond", {"accept": True})
    assert acc.json()["status"] == "ACTIVE"
    assert "ALLIANCE_FORMED" in chronicle_types(a, world["id"])


def test_alliance_requires_friendly_standing(four):
    _, r = four
    d, s = r["Drakoria"], r["Sylvara"]  # seeded at -10
    resp = d.post("/alliances", {"kingdom_id": d.kid, "target_id": s.kid})
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "standing_too_low"


def test_tc16_private_message_reaches_only_recipient(four):
    _, r = four
    a, s, d = r["Aurelia"], r["Sylvara"], r["Drakoria"]
    sent = a.post("/messages", {"kingdom_id": a.kid, "recipient_id": s.kid, "subject": "Grain",
                                "body": "We would buy your grain.", "tone": "warm"})
    assert sent.status_code == 200
    assert [m["subject"] for m in s.get(f"/messages?kingdom_id={s.kid}").json()] == ["Grain"]
    assert d.get(f"/messages?kingdom_id={d.kid}").json() == []
    assert d.get(f"/messages?kingdom_id={s.kid}").status_code == 403  # cannot read someone else's inbox


def test_tc17_18_declare_war_and_resolve_battle(four):
    world, r = four
    d, s = r["Drakoria"], r["Sylvara"]
    early = d.post("/wars", {"kingdom_id": d.kid, "target_id": s.kid})
    assert early.status_code == 400 and early.json()["error"]["code"] == "beginner_protection"
    advance(d, world["id"], 3)
    war = d.post("/wars", {"kingdom_id": d.kid, "target_id": s.kid})
    assert war.status_code == 200 and war.json()["status"] == "ACTIVE"
    battle = d.post("/battles", {"kingdom_id": d.kid, "target_id": s.kid, "soldiers": 50})
    assert battle.status_code == 200, battle.text
    b = battle.json()
    assert b["outcome"] in ("ATTACKER_VICTORY", "DEFENDER_VICTORY") and b["place_name"]
    again = d.post("/battles", {"kingdom_id": d.kid, "target_id": s.kid, "soldiers": 5})
    assert again.status_code == 400 and again.json()["error"]["code"] == "battle_window"
    assert "BATTLE" in chronicle_types(d, world["id"])


def test_tc19_betrayal_generates_historical_event(four):
    world, r = four
    d, v, a = r["Drakoria"], r["Valoria"], r["Aurelia"]
    ally = d.post("/alliances", {"kingdom_id": d.kid, "target_id": v.kid}).json()
    v.post(f"/alliances/{ally['id']}/respond", {"accept": True})
    # Aurelia allied to Valoria too, so it should "reconsider its military commitments".
    a_ally = a.post("/alliances", {"kingdom_id": a.kid, "target_id": v.kid}).json()
    v.post(f"/alliances/{a_ally['id']}/respond", {"accept": True})
    advance(d, world["id"], 3)
    battle = d.post("/battles", {"kingdom_id": d.kid, "target_id": v.kid, "soldiers": 40})
    assert battle.status_code == 200, battle.text
    events = d.get(f"/worlds/{world['id']}/chronicle").json()
    betrayal = next(e for e in events if e["event_type"] == "ALLIANCE_BROKEN")
    assert betrayal["title"] == "THE BETRAYAL OF VALORIA"
    assert "launched an attack on its" in betrayal["description"]
    assert "Aurelia is now reconsidering its military commitments." in betrayal["description"]
    assert betrayal["consequences"][:3] == ["ALLIANCE_TERMINATED", "RELATIONSHIP_CHANGED", "DIPLOMATIC_TENSION"]
    rel = {x["name"]: x for x in v.get(f"/relations/{v.kid}").json()}
    assert rel["Drakoria"]["band"] == "HOSTILE"
    assert battle.json()["report"]["allied_support"] == ["Aurelia"]
    board = {row["name"]: row for row in d.get(f"/leaderboard/{world['id']}").json()}
    assert board["Drakoria"]["penalty"] >= 50


def test_tc20_leave_and_rejoin_restores_kingdom(client):
    host = Ruler(client, "host_player")
    world = new_world(host)
    k = join(host, world["id"], "Valoria")
    host.post("/buildings", {"kingdom_id": k["id"], "building_type": "farm", "x": 0.73, "z": 0.85})
    snapshot = host.resources()
    again = Ruler.__new__(Ruler)  # same account logs in again (fresh token)
    again.client = client
    token = client.post("/auth/login", json={"username": "host_player", "password": "correct-horse-1"}).json()["token"]
    again.headers = {"Authorization": f"Bearer {token}"}
    rejoined = join(again, world["id"])
    assert rejoined["id"] == k["id"]
    assert again.resources() == snapshot
