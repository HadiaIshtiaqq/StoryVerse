"""WebSocket channel: public chronicle reaches everyone; private letters only reach the recipient."""

from tests.conftest import Ruler


def _drain_until(ws, wanted_type: str, limit: int = 20) -> dict:
    for _ in range(limit):
        event = ws.receive_json()
        if event["type"] == wanted_type:
            return event
    raise AssertionError(f"no {wanted_type} event")


def test_private_letter_and_public_chronicle_delivery(four):
    world, r = four
    a, s, d = r["Aurelia"], r["Sylvara"], r["Drakoria"]
    client = a.client
    token_s = s.headers["Authorization"].split()[1]
    token_d = d.headers["Authorization"].split()[1]
    with client.websocket_connect(f"/ws/worlds/{world['id']}?token={token_s}") as ws_s, \
         client.websocket_connect(f"/ws/worlds/{world['id']}?token={token_d}") as ws_d:
        assert ws_s.receive_json()["kingdom_id"] == s.kid
        assert ws_d.receive_json()["kingdom_id"] == d.kid
        a.post("/messages", {"kingdom_id": a.kid, "recipient_id": s.kid, "subject": "Secret", "body": "For your eyes only."})
        letter = _drain_until(ws_s, "letter")
        assert letter["message"]["subject"] == "Secret"
        # Drakoria must not see the letter; the next thing it sees is the public trade chronicle.
        offer = s.post("/trades", {"kingdom_id": s.kid, "receiver_id": a.kid, "offered_resource": "food",
                                   "offered_amount": 50, "requested_resource": "gold", "requested_amount": 60}).json()
        a.post(f"/trades/{offer['id']}/accept")
        seen = []
        for _ in range(20):
            e = ws_d.receive_json()
            seen.append(e["type"])
            if e["type"] == "chronicle":
                break
        assert "letter" not in seen and "chronicle" in seen


def test_socket_rejects_bad_token(client):
    Ruler(client, "someone")
    try:
        with client.websocket_connect("/ws/worlds/nope?token=garbage") as ws:
            ws.receive_json()
        raise AssertionError("socket should have been closed")
    except Exception as e:  # starlette raises WebSocketDisconnect with code 4401
        assert "4401" in repr(e) or "Disconnect" in type(e).__name__
