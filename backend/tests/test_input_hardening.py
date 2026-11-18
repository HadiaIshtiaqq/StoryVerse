"""Regression tests for input-validation holes found in review."""


def _raw_post(ruler, path, body: str):
    return ruler.client.post(path, content=body, headers={**ruler.headers, "Content-Type": "application/json"})


def test_nan_and_out_of_range_coordinates_are_rejected(four):
    _, r = four
    a = r["Aurelia"]
    before_buildings, before_wood = len(a.get(f"/kingdoms/{a.kid}/buildings").json()), a.resources()["wood"]
    for x in ("NaN", "Infinity", "-0.5", "1.5"):
        res = _raw_post(a, "/buildings", f'{{"kingdom_id": "{a.kid}", "building_type": "farm", "x": {x}, "z": 0.45}}')
        assert res.status_code == 422, (x, res.text)
        assert res.json()["error"]["code"] == "validation_error"
    # Nothing was built and nothing was charged.
    assert len(a.get(f"/kingdoms/{a.kid}/buildings").json()) == before_buildings
    assert a.resources()["wood"] == before_wood


def test_nan_interest_rate_is_rejected(four):
    _, r = four
    a, d = r["Aurelia"], r["Drakoria"]
    res = _raw_post(a, "/loans", f'{{"kingdom_id": "{a.kid}", "counterparty_id": "{d.kid}", "role": "lender", '
                                 f'"principal": 500, "interest_rate": NaN, "duration_turns": 3}}')
    assert res.status_code == 422, res.text


def test_oversized_login_password_is_rejected_before_hashing(client):
    res = client.post("/auth/login", json={"username": "nobody", "password": "x" * 100_000})
    assert res.status_code == 422


def test_outsider_cannot_listen_to_a_world(four, client):
    from tests.conftest import Ruler

    world, _ = four
    outsider = Ruler(client, "eavesdropper")
    token = outsider.headers["Authorization"].split()[1]
    try:
        with client.websocket_connect(f"/ws/worlds/{world['id']}?token={token}") as ws:
            ws.receive_json()
        raise AssertionError("outsider socket should have been closed")
    except Exception as e:
        assert "4403" in repr(e) or "Disconnect" in type(e).__name__, repr(e)


def test_session_tokens_are_redacted_from_access_logs():
    import logging

    from app.main import _RedactTokens

    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                               ("127.0.0.1:5000", "GET", "/ws/worlds/abc?token=eyJzdWIi.c2ln&x=1", "1.1", 101), None)
    _RedactTokens().filter(record)
    line = record.getMessage()
    assert "eyJzdWIi" not in line and "token=[redacted]&x=1" in line


def test_unknown_user_and_wrong_password_look_identical(client):
    client.post("/auth/register", json={"username": "real_ruler", "password": "correct-horse-1"})
    unknown = client.post("/auth/login", json={"username": "ghost_ruler", "password": "whatever-123"})
    wrong = client.post("/auth/login", json={"username": "real_ruler", "password": "whatever-123"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
