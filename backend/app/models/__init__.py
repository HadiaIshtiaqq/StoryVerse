"""ORM models. UUIDs are stored as 36-char strings so the same schema runs on PostgreSQL and SQLite.

Note: resources live directly on the `kingdoms` row (instead of a separate
RESOURCE_INVENTORIES table, spec §3.4) so a single row lock protects a kingdom's
whole treasury during atomic transfers.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Player(Base):
    __tablename__ = "players"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class World(Base):
    __tablename__ = "worlds"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    preset: Mapped[str] = mapped_column(String(20), default="standard")
    turn: Mapped[int] = mapped_column(Integer, default=1)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    beginner_protection_turns: Mapped[int] = mapped_column(Integer, default=3)
    crowns: Mapped[dict] = mapped_column(JSON, default=dict)  # crown category -> kingdom_id
    created_by: Mapped[str] = mapped_column(ForeignKey("players.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Kingdom(Base):
    __tablename__ = "kingdoms"
    __table_args__ = (UniqueConstraint("world_id", "name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"), nullable=True, index=True)
    is_npc: Mapped[bool] = mapped_column(Boolean, default=True)
    name: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(80))
    specialization: Mapped[str] = mapped_column(String(20))
    ruler_name: Mapped[str] = mapped_column(String(80))
    emblem_key: Mapped[str] = mapped_column(String(40))
    color: Mapped[str] = mapped_column(String(9))
    map_x: Mapped[float] = mapped_column(Float)
    map_y: Mapped[float] = mapped_column(Float)
    gold: Mapped[int] = mapped_column(Integer, default=0)
    food: Mapped[int] = mapped_column(Integer, default=0)
    wood: Mapped[int] = mapped_column(Integer, default=0)
    stone: Mapped[int] = mapped_column(Integer, default=0)
    iron: Mapped[int] = mapped_column(Integer, default=0)
    population: Mapped[int] = mapped_column(Integer, default=0)
    soldiers: Mapped[int] = mapped_column(Integer, default=0)
    prestige: Mapped[int] = mapped_column(Integer, default=0)
    prestige_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    prestige_penalty: Mapped[int] = mapped_column(Integer, default=0)
    betrayals: Mapped[int] = mapped_column(Integer, default=0)
    recruited_turn: Mapped[int] = mapped_column(Integer, default=0)
    recruited_this_turn: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Building(Base):
    __tablename__ = "buildings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kingdom_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"), index=True)
    building_type: Mapped[str] = mapped_column(String(30))
    level: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(20), default="COMPLETE")
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float, default=0.0)
    z: Mapped[float] = mapped_column(Float)
    rotation_y: Mapped[float] = mapped_column(Float, default=0.0)
    created_turn: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Transaction(Base):
    """Header for any economic movement (spec TRANSACTIONS). Lines live in LedgerEntry."""

    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    transaction_type: Mapped[str] = mapped_column(String(30))
    sender_kingdom_id: Mapped[str | None] = mapped_column(ForeignKey("kingdoms.id"), nullable=True)
    receiver_kingdom_id: Mapped[str | None] = mapped_column(ForeignKey("kingdoms.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETED")
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), index=True)
    kingdom_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"), index=True)
    resource: Mapped[str] = mapped_column(String(10))
    delta: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TradeOffer(Base):
    __tablename__ = "trade_offers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    receiver_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    offered_resource: Mapped[str] = mapped_column(String(10))
    offered_amount: Mapped[int] = mapped_column(Integer)
    requested_resource: Mapped[str] = mapped_column(String(10))
    requested_amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    decision_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Loan(Base):
    __tablename__ = "loans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(12))
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    lender_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    borrower_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    proposer_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    principal: Mapped[int] = mapped_column(Integer)
    interest_rate: Mapped[float] = mapped_column(Float)
    duration_turns: Mapped[int] = mapped_column(Integer)
    total_repayment: Mapped[int] = mapped_column(Integer)
    installment: Mapped[int] = mapped_column(Integer)
    amount_repaid: Mapped[int] = mapped_column(Integer, default=0)
    missed_payments: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="PROPOSED")
    decision_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    accepted_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LoanRepayment(Base):
    __tablename__ = "loan_repayments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    loan_id: Mapped[str] = mapped_column(ForeignKey("loans.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(10))
    turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Alliance(Base):
    __tablename__ = "alliances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    kingdom_a: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    kingdom_b: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    proposer_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    duration_turns: Mapped[int] = mapped_column(Integer)
    mutual_defense: Mapped[bool] = mapped_column(Boolean, default=True)
    trade_benefits: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    decision_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_turn: Mapped[int] = mapped_column(Integer)
    expires_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ended_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    sender_kingdom_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    recipient_kingdom_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"), index=True)
    subject: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(10), default="warm")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class War(Base):
    __tablename__ = "wars"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    attacker_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    defender_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    peace_proposed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    betrayal: Mapped[bool] = mapped_column(Boolean, default=False)
    started_turn: Mapped[int] = mapped_column(Integer)
    ended_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Battle(Base):
    __tablename__ = "battles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    war_id: Mapped[str] = mapped_column(ForeignKey("wars.id"))
    attacker_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    defender_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    attacker_committed: Mapped[int] = mapped_column(Integer)
    defender_soldiers: Mapped[int] = mapped_column(Integer)
    attacker_power: Mapped[float] = mapped_column(Float)
    defender_power: Mapped[float] = mapped_column(Float)
    outcome: Mapped[str] = mapped_column(String(20))
    attacker_losses: Mapped[int] = mapped_column(Integer)
    defender_losses: Mapped[int] = mapped_column(Integer)
    plunder_gold: Mapped[int] = mapped_column(Integer, default=0)
    place_name: Mapped[str] = mapped_column(String(80))
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Relation(Base):
    """Symmetric standing between two kingdoms; kingdom_a < kingdom_b (string order)."""

    __tablename__ = "relations"
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    kingdom_a: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"), primary_key=True)
    kingdom_b: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"), primary_key=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    last_delta: Mapped[int] = mapped_column(Integer, default=0)
    counters_turn: Mapped[int] = mapped_column(Integer, default=0)
    trade_gain_this_turn: Mapped[int] = mapped_column(Integer, default=0)
    gift_gain_this_turn: Mapped[int] = mapped_column(Integer, default=0)
    updated_turn: Mapped[int] = mapped_column(Integer, default=1)


class RelationEvent(Base):
    __tablename__ = "relation_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    kingdom_a: Mapped[str] = mapped_column(String(36), index=True)
    kingdom_b: Mapped[str] = mapped_column(String(36), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(120))
    transaction_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class StoryEvent(Base):
    __tablename__ = "story_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    actors: Mapped[list] = mapped_column(JSON, default=list)
    consequences: Mapped[list] = mapped_column(JSON, default=list)
    importance: Mapped[int] = mapped_column(Integer, default=1)
    turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    kingdom_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Passage(Base):
    """Military passage / open roads: the grantor lets the grantee's merchants and armies cross its land.
    One-way and unilateral (like opening your gates). Both realms earn road tolls each turn while it stands."""
    __tablename__ = "passages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    grantor_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    grantee_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"))
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE")     # ACTIVE | CLOSED
    created_turn: Mapped[int] = mapped_column(Integer, default=0)
    closed_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DecreeClaim(Base):
    """A Royal Decree (objective) whose reward a kingdom has already collected."""
    __tablename__ = "decree_claims"
    kingdom_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TurnReady(Base):
    """A human ruler's "end turn" vote. In a world with several human rulers the turn advances only when
    every one of them is ready (or the world's creator forces it), so nobody can fast-forward the others'
    loans and wars while they are away. Rows are cleared each time the turn advances."""
    __tablename__ = "turn_ready"
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), primary_key=True)
    kingdom_id: Mapped[str] = mapped_column(ForeignKey("kingdoms.id"), primary_key=True)
    turn: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    player_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope: Mapped[str] = mapped_column(String(80))
    status_code: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
