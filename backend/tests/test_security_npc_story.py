"""Security (spec §6.1), XR-09 idempotency, NPC rulers (judging §2.1), gifts/standing (B14), solo play."""

from tests.conftest import Ruler, advance, chronicle_types, join, new_world


def test_requires_auth_and_ownership(four):
    world, r = four
    client = r["Aurelia"].client
    assert client.get(f"/worlds/{world['id']}").status_code == 401
    a, d = r["Aurelia"], r["Drakoria"]
    steal = d.post("/buildings", {"kingdom_id": a.kid, "building_type": "farm", "x": 0.28, "z": 0.45})
    assert steal.status_code == 403
    assert d.get(f"/kingdoms/{a.kid}/resources").status_code == 403
    public = d.get(f"/kingdoms/{a.kid}").json()
    assert "resources" not in public and "army_estimate" in public  # treasuries stay private


def test_tampered_token_rejected(client):
    p = Ruler(client, "honest")
    bad = {"Authorization": p.headers["Authorization"][:-3] + "abc"}
    assert client.get("/auth/me", headers=bad).status_code == 401


def test_xr09_rapid_repeated_pinch_creates_one_transaction(four):
    _, r = four
    a, d = r["Aurelia"], r["Drakoria"]
    before = a.resources()["gold"]
    first = a.post("/gifts", {"kingdom_id": a.kid, "target_id": d.kid, "gold": 300}, key="pinch-123")
    second = a.post("/gifts", {"kingdom_id": a.kid, "target_id": d.kid, "gold": 300}, key="pinch-123")
    assert first.status_code == second.status_code == 200
    assert second.headers.get("Idempotent-Replay") == "true"
    assert first.json() == second.json()
    assert a.resources()["gold"] == before - 300
    reuse = a.post("/buildings", {"kingdom_id": a.kid, "building_type": "farm", "x": 0.28, "z": 0.45}, key="pinch-123")
    assert reuse.status_code == 409


def test_anti_collusion_lopsided_trade_between_humans(four):
    _, r = four
    s, v = r["Sylvara"], r["Valoria"]
    resp = s.post("/trades", {"kingdom_id": s.kid, "receiver_id": v.kid, "offered_resource": "iron",
                              "offered_amount": 150, "requested_resource": "gold", "requested_amount": 1})
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "lopsided_trade"


def test_gift_tiers_preview_matches_actual_gain(four):
    _, r = four
    a, d = r["Aurelia"], r["Drakoria"]
    preview = a.get(f"/gifts/tiers?kingdom_id={a.kid}&target_id={d.kid}").json()
    assert [t["gold"] for t in preview["tiers"]] == [250, 500, 750]
    assert all(t["standing_gain"] > 0 for t in preview["tiers"])
    tier = preview["tiers"][1]
    sent = a.post("/gifts", {"kingdom_id": a.kid, "target_id": d.kid, "gold": tier["gold"], "iron": tier["iron"]}).json()
    assert sent["standing_gain"] == tier["standing_gain"]
    assert sent["standing"] == tier["new_standing"]
    rel = {x["name"]: x for x in a.get(f"/relations/{a.kid}").json()}["Drakoria"]
    assert rel["recent_reasons"][0]["reason"].startswith("Gift of")


def test_gift_gain_capped_per_turn(four):
    _, r = four
    a, d = r["Aurelia"], r["Drakoria"]
    total = sum(a.post("/gifts", {"kingdom_id": a.kid, "target_id": d.kid, "gold": 750}).json()["standing_gain"]
                for _ in range(4))
    assert total == 20


def test_relations_view_gates_and_reasons(four):
    _, r = four
    a = r["Aurelia"]
    rel = {x["name"]: x for x in a.get(f"/relations/{a.kid}").json()}
    assert rel["Valoria"]["band"] == "FRIENDLY" and rel["Valoria"]["actions"]["alliance"]["allowed"]
    assert not rel["Drakoria"]["actions"]["alliance"]["allowed"]
    assert "Friendly (40)" in rel["Drakoria"]["actions"]["alliance"]["reason"]
    assert not rel["Drakoria"]["actions"]["declare_war"]["allowed"]  # beginner protection


# --- NPC rulers: solo play ------------------------------------------------------------------
def solo(client) -> tuple[dict, Ruler]:
    judge = Ruler(client, "judge")
    world = new_world(judge, preset="solo_court")
    join(judge, world["id"], "Sylvara")
    return world, judge


def test_npc_trade_decision_returns_itemised_reasons(client):
    world, judge = solo(client)
    kingdoms = {k["name"]: k for k in judge.get(f"/worlds/{world['id']}").json()["kingdoms"]}
    good = judge.post("/trades", {"kingdom_id": judge.kid, "receiver_id": kingdoms["Valoria"]["id"],
                                  "offered_resource": "food", "offered_amount": 150,
                                  "requested_resource": "gold", "requested_amount": 100}).json()
    assert good["status"] == "ACCEPTED"
    assert good["decision"]["accept"] and good["decision"]["decided_by"] == "High King Cassian Valor"
    labels = [x["label"] for x in good["decision"]["reasons"]]
    assert "Value of the deal" in labels and "Trade is Valoria's lifeblood" in labels
    bad = judge.post("/trades", {"kingdom_id": judge.kid, "receiver_id": kingdoms["Drakoria"]["id"],
                                 "offered_resource": "wood", "offered_amount": 10,
                                 "requested_resource": "iron", "requested_amount": 150}).json()
    assert bad["status"] == "REJECTED" and not bad["decision"]["accept"]
    assert bad["decision"]["positive"] + bad["decision"]["negative"] < bad["decision"]["threshold"]


def test_npc_alliance_and_loan_decisions(client):
    world, judge = solo(client)
    kingdoms = {k["name"]: k for k in judge.get(f"/worlds/{world['id']}").json()["kingdoms"]}
    # Sylvara-Aurelia standing is 30: gift up to Friendly, then propose.
    for _ in range(2):
        judge.post("/gifts", {"kingdom_id": judge.kid, "target_id": kingdoms["Aurelia"]["id"], "gold": 750})
        advance(judge, world["id"])
    rel = {x["name"]: x for x in judge.get(f"/relations/{judge.kid}").json()}["Aurelia"]
    assert rel["standing"] >= 40, rel
    ally = judge.post("/alliances", {"kingdom_id": judge.kid, "target_id": kingdoms["Aurelia"]["id"]}).json()
    assert ally["decision"] is not None and ally["status"] in ("ACTIVE", "REJECTED")
    loan = judge.post("/loans", {"kingdom_id": judge.kid, "counterparty_id": kingdoms["Aurelia"]["id"], "role": "borrower",
                                 "principal": 500, "interest_rate": 12, "duration_turns": 5}).json()
    assert loan["status"] in ("ACTIVE", "REJECTED") and loan["decision"]["reasons"]


def test_solo_world_runs_many_turns_with_npc_story(client):
    world, judge = solo(client)
    for _ in range(12):
        advance(judge, world["id"])
    types = chronicle_types(judge, world["id"])
    assert "WORLD_FOUNDED" in types and "RULER_CROWNED" in types
    # NPCs did things on their own: built, traded, lent or fought.
    assert {"BUILDING_RAISED", "TRADE_COMPLETED", "LOAN_ACCEPTED", "ALLIANCE_FORMED", "BATTLE",
            "WAR_DECLARED", "ALLIANCE_BROKEN"} & set(types)
    inbox = judge.get(f"/kingdoms/{judge.kid}/dashboard").json()
    assert inbox["world"]["turn"] == 13
    assert len(inbox["leaderboard"]) == 4
    away = judge.get(f"/kingdoms/{judge.kid}/since?turn=5").json()
    assert away["current_turn"] == 13 and away["chronicle"]


def test_npc_letter_reply(client):
    world, judge = solo(client)
    kingdoms = {k["name"]: k for k in judge.get(f"/worlds/{world['id']}").json()["kingdoms"]}
    judge.post("/messages", {"kingdom_id": judge.kid, "recipient_id": kingdoms["Drakoria"]["id"],
                             "subject": "Peace?", "body": "Shall we end our quarrel?", "tone": "warm"})
    inbox = judge.get(f"/messages?kingdom_id={judge.kid}").json()
    assert inbox and inbox[0]["subject"] == "Re: Peace?" and "Queen Varka Embermane" in inbox[0]["body"]


def test_borrowed_gold_is_not_economic_prestige(four):
    world, r = four
    a, d = r["Aurelia"], r["Drakoria"]
    before = {x["name"]: x for x in d.get(f"/leaderboard/{world['id']}").json()}["Drakoria"]["breakdown"]["economic"]
    loan = a.post("/loans", {"kingdom_id": a.kid, "counterparty_id": d.kid, "role": "lender",
                             "principal": 2000, "interest_rate": 10, "duration_turns": 5}).json()
    d.post(f"/loans/{loan['id']}/accept")
    advance(a, world["id"])
    after = {x["name"]: x for x in d.get(f"/leaderboard/{world['id']}").json()}["Drakoria"]["breakdown"]["economic"]
    assert after <= before + 5  # +2,000 gold borrowed must not buy economic prestige


def test_prestige_and_crowns(four):
    world, r = four
    advance(r["Aurelia"], world["id"], 2)
    board = r["Aurelia"].get(f"/leaderboard/{world['id']}").json()
    assert board[0]["prestige"] >= board[-1]["prestige"]
    crowns = [c for row in board for c in row["crowns"]]
    assert set(crowns) == {"Golden Crown", "Iron Crown", "Diplomat's Crown", "Builder's Crown", "People's Crown"}
