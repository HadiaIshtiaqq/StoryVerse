"""Living History Engine (spec §2.4 H, §5.6).

Deterministic, template-based narration: validated action -> event -> consequences ->
narrative -> notifications -> World Chronicle. No LLM decides anything here.
"""

from sqlalchemy.orm import Session

from app.models import Kingdom, StoryEvent, World
from app.services.common import emit


def serialize(e: StoryEvent) -> dict:
    return {"id": e.id, "event_type": e.event_type, "title": e.title, "description": e.description,
            "actors": e.actors, "consequences": e.consequences, "importance": e.importance, "turn": e.turn,
            "created_at": e.created_at.isoformat() if e.created_at else None}


def record(db: Session, world: World, event_type: str, title: str, description: str,
           actors: list[str] | None = None, consequences: list[str] | None = None, importance: int = 1) -> StoryEvent:
    event = StoryEvent(world_id=world.id, event_type=event_type, title=title, description=description,
                       actors=actors or [], consequences=consequences or [], importance=importance, turn=world.turn)
    db.add(event)
    db.flush()
    emit(db, {"type": "chronicle", "world_id": world.id, "event": serialize(event)})
    return event


def compass_side(victim: Kingdom, attacker: Kingdom) -> str:
    """Which side of the victim's realm faces the attacker ('eastern', 'northern', ...). Map y grows southward."""
    dx, dy = attacker.map_x - victim.map_x, attacker.map_y - victim.map_y
    if abs(dx) >= abs(dy):
        return "eastern" if dx > 0 else "western"
    return "southern" if dy > 0 else "northern"


def fmt_amount(amount: int, resource: str) -> str:
    return f"{amount:,} {resource}"
