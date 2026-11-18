class GameError(Exception):
    """A rule violation the player should see, e.g. 'Insufficient wood: need 100, have 40'.

    Clients show `message` directly (VR: on the building preview, the seal, the letter).
    """

    def __init__(self, message: str, code: str = "invalid_action", status: int = 400, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.details = details or {}


def not_found(what: str) -> GameError:
    return GameError(f"{what} not found", code="not_found", status=404)


def forbidden(message: str = "You do not rule this kingdom") -> GameError:
    return GameError(message, code="forbidden", status=403)


def conflict(message: str) -> GameError:
    return GameError(message, code="conflict", status=409)
