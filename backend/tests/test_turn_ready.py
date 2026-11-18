"""Shared-world end-turn ready check: nobody can fast-forward the other rulers' loans and wars."""

from tests.conftest import Ruler, advance, new_world


def test_one_ruler_cannot_advance_a_shared_world_alone(four):
    world, r = four
    before = r["Aurelia"].get(f"/worlds/{world['id']}").json()["turn"]
    res = r["Drakoria"].post(f"/worlds/{world['id']}/turn")
    assert res.status_code == 200
    body = res.json()
    assert body["advanced"] is False
    assert set(body["waiting_for"]) == {"Aurelia", "Sylvara", "Valoria"}
    assert r["Aurelia"].get(f"/worlds/{world['id']}").json()["turn"] == before


def test_repeated_votes_do_not_count_twice(four):
    world, r = four
    for _ in range(5):
        r["Drakoria"].post(f"/worlds/{world['id']}/turn")
    body = r["Sylvara"].post(f"/worlds/{world['id']}/turn").json()
    assert body["advanced"] is False and set(body["waiting_for"]) == {"Aurelia", "Valoria"}


def test_turn_advances_when_everyone_is_ready_and_votes_reset(four):
    world, r = four
    before = r["Aurelia"].get(f"/worlds/{world['id']}").json()["turn"]
    out = advance(r["Valoria"], world["id"])
    assert out["advanced"] is True and out["turn"] == before + 1
    # Votes from the previous turn must not carry over.
    body = r["Drakoria"].post(f"/worlds/{world['id']}/turn").json()
    assert body["advanced"] is False and "Drakoria" not in body["waiting_for"]


def test_only_the_creator_can_force_the_turn(four):
    world, r = four
    assert r["Drakoria"].post(f"/worlds/{world['id']}/turn?force=true").status_code == 403
    before = r["Aurelia"].get(f"/worlds/{world['id']}").json()["turn"]
    forced = r["Aurelia"].post(f"/worlds/{world['id']}/turn?force=true").json()   # Aurelia created the world
    assert forced["advanced"] is True and forced["turn"] == before + 1


def test_solo_world_advances_immediately(client):
    judge = Ruler(client, "solo_judge")
    world = new_world(judge, preset="solo_court")
    judge.post("/worlds/join", {"world_id": world["id"], "kingdom_name": "Sylvara"})
    body = judge.post(f"/worlds/{world['id']}/turn").json()
    assert body["advanced"] is True
