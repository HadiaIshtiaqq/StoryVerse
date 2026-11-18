"""Request bodies. Responses are plain dicts produced by the services' serialize_* helpers."""

from typing import Literal

from pydantic import BaseModel, Field

Resource = Literal["gold", "food", "wood", "stone", "iron"]


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_\-]+$")
    password: str = Field(min_length=8, max_length=128)
    email: str | None = Field(default=None, max_length=255)


class LoginIn(BaseModel):
    # Bounded so a giant password cannot be used to burn 200k PBKDF2 iterations of CPU per request.
    username: str = Field(max_length=40)
    password: str = Field(max_length=128)


class WorldCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    preset: Literal["standard", "solo_court"] = "standard"


class WorldJoinIn(BaseModel):
    world_id: str
    kingdom_name: str | None = None


class BuildingIn(BaseModel):
    kingdom_id: str
    building_type: str
    # Bounded and finite: NaN would slip past the distance checks (NaN > r is False) and corrupt the map.
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    z: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(default=0.0, ge=-1, le=1, allow_inf_nan=False)
    rotation_y: float = Field(default=0.0, ge=-360, le=720, allow_inf_nan=False)


class TradeIn(BaseModel):
    kingdom_id: str
    receiver_id: str
    offered_resource: Resource
    offered_amount: int = Field(gt=0, le=1_000_000)
    requested_resource: Resource
    requested_amount: int = Field(gt=0, le=1_000_000)


class LoanIn(BaseModel):
    kingdom_id: str
    counterparty_id: str
    role: Literal["lender", "borrower"]
    principal: int = Field(gt=0, le=1_000_000)
    interest_rate: float = Field(ge=0, le=50, allow_inf_nan=False)
    duration_turns: int = Field(ge=1, le=20)


class RepayIn(BaseModel):
    amount: int = Field(gt=0)


class AllianceIn(BaseModel):
    kingdom_id: str
    target_id: str
    duration_turns: int = Field(default=10, ge=1, le=20)
    mutual_defense: bool = True


class AllianceRespondIn(BaseModel):
    accept: bool


class KingdomActionIn(BaseModel):
    kingdom_id: str


class MessageIn(BaseModel):
    kingdom_id: str
    recipient_id: str
    subject: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)
    tone: Literal["warm", "proud", "cold"] = "warm"


class GiftIn(BaseModel):
    kingdom_id: str
    target_id: str
    gold: int = Field(gt=0, le=1_000_000)
    iron: int = Field(default=0, ge=0, le=1_000_000)   # chests may carry iron too (see /gifts/tiers)


class PassageIn(BaseModel):
    kingdom_id: str
    target_id: str


class DecreeClaimIn(BaseModel):
    kingdom_id: str


class RecruitIn(BaseModel):
    kingdom_id: str
    count: int = Field(gt=0, le=1000)


class WarIn(BaseModel):
    kingdom_id: str
    target_id: str


class BattleIn(BaseModel):
    kingdom_id: str
    target_id: str
    soldiers: int = Field(gt=0)


class MarketIn(BaseModel):
    kingdom_id: str
    resource: str = Field(max_length=10)
    amount: int = Field(gt=0, le=100_000)
    side: str = Field(pattern=r"^(buy|sell)$")
