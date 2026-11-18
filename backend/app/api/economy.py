"""Buildings, trades, loans (spec §3.5)."""

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import IdempotencyKey, commit, idempotent
from app.database import get_db
from app.models import Loan, Player, TradeOffer
from app.schemas import BuildingIn, LoanIn, MarketIn, RepayIn, TradeIn
from app.security import get_current_player
from app.services import economy_service as eco
from app.services import kingdom_service
from app.services.common import require_owned_kingdom

router = APIRouter(tags=["economy"])


# --- buildings -------------------------------------------------------------------------------
@router.get("/buildings/catalog")
def building_catalog(kingdom_id: str | None = None, player: Player = Depends(get_current_player),
                     db: Session = Depends(get_db)):
    k = require_owned_kingdom(db, player, kingdom_id) if kingdom_id else None
    return kingdom_service.catalog(k)


@router.post("/buildings")
def construct(body: BuildingIn, key: str | None = IdempotencyKey, player: Player = Depends(get_current_player),
              db: Session = Depends(get_db)):
    return idempotent(db, player, key, "buildings:create", lambda: kingdom_service.serialize_building(
        kingdom_service.construct(db, player, body.kingdom_id, body.building_type, body.x, body.z, body.y, body.rotation_y)))


@router.patch("/buildings/{building_id}/upgrade")
def upgrade(building_id: str, key: str | None = IdempotencyKey, player: Player = Depends(get_current_player),
            db: Session = Depends(get_db)):
    return idempotent(db, player, key, f"buildings:upgrade:{building_id}",
                      lambda: kingdom_service.serialize_building(kingdom_service.upgrade(db, player, building_id)))


# --- royal market ----------------------------------------------------------------------------
@router.get("/market")
def market(kingdom_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    """Prices and this turn's remaining capacity at the crown's market."""
    return eco.market_view(db, require_owned_kingdom(db, player, kingdom_id))


@router.post("/market")
def market_trade(body: MarketIn, key: str | None = IdempotencyKey, player: Player = Depends(get_current_player),
                 db: Session = Depends(get_db)):
    """Buy materials with gold, or sell them for gold, at fixed prices."""
    return idempotent(db, player, key, "market:trade", lambda: eco.market_trade(
        db, player, body.kingdom_id, body.resource, body.amount, body.side))


# --- trades ----------------------------------------------------------------------------------
@router.post("/trades")
def create_trade(body: TradeIn, key: str | None = IdempotencyKey, player: Player = Depends(get_current_player),
                 db: Session = Depends(get_db)):
    return idempotent(db, player, key, "trades:create", lambda: eco.serialize_trade(eco.create_trade(
        db, player, body.kingdom_id, body.receiver_id, body.offered_resource, body.offered_amount,
        body.requested_resource, body.requested_amount)))


@router.get("/trades")
def list_trades(kingdom_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    k = require_owned_kingdom(db, player, kingdom_id)
    rows = db.execute(select(TradeOffer).where(or_(TradeOffer.sender_id == k.id, TradeOffer.receiver_id == k.id))
                      .order_by(TradeOffer.created_at.desc()).limit(100)).scalars()
    return [eco.serialize_trade(t) for t in rows]


@router.post("/trades/{trade_id}/accept")
def accept_trade(trade_id: str, key: str | None = IdempotencyKey, player: Player = Depends(get_current_player),
                 db: Session = Depends(get_db)):
    return idempotent(db, player, key, f"trades:accept:{trade_id}",
                      lambda: eco.serialize_trade(eco.accept_trade(db, player, trade_id)))


@router.post("/trades/{trade_id}/reject")
def reject_trade(trade_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    t = eco.reject_trade(db, player, trade_id)
    commit(db)
    return eco.serialize_trade(t)


@router.post("/trades/{trade_id}/cancel")
def cancel_trade(trade_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    t = eco.cancel_trade(db, player, trade_id)
    commit(db)
    return eco.serialize_trade(t)


# --- loans -----------------------------------------------------------------------------------
@router.post("/loans")
def create_loan(body: LoanIn, key: str | None = IdempotencyKey, player: Player = Depends(get_current_player),
                db: Session = Depends(get_db)):
    return idempotent(db, player, key, "loans:create", lambda: eco.serialize_loan(eco.propose_loan(
        db, player, body.kingdom_id, body.counterparty_id, body.role, body.principal, body.interest_rate,
        body.duration_turns)))


@router.get("/loans")
def list_loans(kingdom_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    k = require_owned_kingdom(db, player, kingdom_id)
    rows = db.execute(select(Loan).where(or_(Loan.lender_id == k.id, Loan.borrower_id == k.id))
                      .order_by(Loan.created_at.desc())).scalars()
    return [eco.serialize_loan(l) for l in rows]


@router.post("/loans/{loan_id}/accept")
def accept_loan(loan_id: str, key: str | None = IdempotencyKey, player: Player = Depends(get_current_player),
                db: Session = Depends(get_db)):
    return idempotent(db, player, key, f"loans:accept:{loan_id}",
                      lambda: eco.serialize_loan(eco.accept_loan(db, player, loan_id)))


@router.post("/loans/{loan_id}/reject")
def reject_loan(loan_id: str, player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    l = eco.reject_loan(db, player, loan_id)
    commit(db)
    return eco.serialize_loan(l)


@router.post("/loans/{loan_id}/repay")
def repay_loan(loan_id: str, body: RepayIn, key: str | None = IdempotencyKey,
               player: Player = Depends(get_current_player), db: Session = Depends(get_db)):
    return idempotent(db, player, key, f"loans:repay:{loan_id}",
                      lambda: eco.serialize_loan(eco.repay_loan(db, player, loan_id, body.amount)))
