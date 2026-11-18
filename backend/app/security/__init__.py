"""Password hashing (PBKDF2, stdlib) and signed bearer tokens (HMAC-SHA256, stdlib).

No third-party crypto dependency keeps the backend installable on locked-down machines
and on Quest-side tooling. Tokens are `base64url(payload).base64url(signature)`.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.errors import GameError

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except ValueError:
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_token(player_id: str) -> str:
    payload = _b64(json.dumps({"sub": player_id, "exp": int(time.time()) + settings.token_ttl_seconds}).encode())
    signature = _b64(hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def decode_token(token: str) -> str:
    """Return the player id, or raise GameError(401)."""
    try:
        payload, signature = token.split(".")
        expected = _b64(hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        data = json.loads(_unb64(payload))
        if data["exp"] < time.time():
            raise ValueError("expired")
        return data["sub"]
    except (ValueError, KeyError, json.JSONDecodeError):
        raise GameError("Invalid or expired session; please log in again", code="unauthorized", status=401)


def get_current_player(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    from app.models import Player

    if not authorization or not authorization.lower().startswith("bearer "):
        raise GameError("Authentication required", code="unauthorized", status=401)
    player = db.get(Player, decode_token(authorization.split(" ", 1)[1].strip()))
    if player is None:
        raise GameError("Player no longer exists", code="unauthorized", status=401)
    return player
