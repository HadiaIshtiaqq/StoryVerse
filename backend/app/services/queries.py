"""Read-only questions about the political state, shared by every engine (no circular imports)."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Alliance, Building, Kingdom, Loan, TradeOffer, War


def _pair_filter(col_a, col_b, a: str, b: str):
    return or_(and_(col_a == a, col_b == b), and_(col_a == b, col_b == a))


def active_alliance(db: Session, a: str, b: str) -> Alliance | None:
    return db.execute(select(Alliance).where(Alliance.status == "ACTIVE",
                                             _pair_filter(Alliance.kingdom_a, Alliance.kingdom_b, a, b))).scalars().first()


def pending_alliance(db: Session, a: str, b: str) -> Alliance | None:
    return db.execute(select(Alliance).where(Alliance.status == "PENDING",
                                             _pair_filter(Alliance.kingdom_a, Alliance.kingdom_b, a, b))).scalars().first()


def allies_of(db: Session, kingdom_id: str) -> list[Alliance]:
    return list(db.execute(select(Alliance).where(Alliance.status == "ACTIVE",
                                                  or_(Alliance.kingdom_a == kingdom_id, Alliance.kingdom_b == kingdom_id))).scalars())


def ally_ids(db: Session, kingdom_id: str) -> list[str]:
    return [a.kingdom_b if a.kingdom_a == kingdom_id else a.kingdom_a for a in allies_of(db, kingdom_id)]


def active_war(db: Session, a: str, b: str) -> War | None:
    return db.execute(select(War).where(War.status.in_(("ACTIVE", "PEACE_PROPOSED")),
                                        _pair_filter(War.attacker_id, War.defender_id, a, b))).scalars().first()


def wars_of(db: Session, kingdom_id: str) -> list[War]:
    return list(db.execute(select(War).where(War.status.in_(("ACTIVE", "PEACE_PROPOSED")),
                                             or_(War.attacker_id == kingdom_id, War.defender_id == kingdom_id))).scalars())


def building_levels(db: Session, kingdom_id: str, building_type: str | None = None) -> int:
    q = select(func.coalesce(func.sum(Building.level), 0)).where(Building.kingdom_id == kingdom_id)
    if building_type:
        q = q.where(Building.building_type == building_type)
    return int(db.execute(q).scalar_one())


def has_building(db: Session, kingdom_id: str, building_type: str) -> bool:
    return building_levels(db, kingdom_id, building_type) > 0


def outstanding_debt(db: Session, borrower_id: str) -> int:
    loans = db.execute(select(Loan).where(Loan.borrower_id == borrower_id, Loan.status == "ACTIVE")).scalars()
    return sum(l.total_repayment - l.amount_repaid for l in loans)


def has_overdue_loan(db: Session, borrower_id: str, lender_id: str | None = None) -> bool:
    q = select(Loan).where(Loan.borrower_id == borrower_id,
                           or_(Loan.status == "DEFAULTED", and_(Loan.status == "ACTIVE", Loan.missed_payments > 0)))
    if lender_id:
        q = q.where(Loan.lender_id == lender_id)
    return db.execute(q).scalars().first() is not None


def trades_between(db: Session, a: str, b: str) -> int:
    return int(db.execute(select(func.count()).select_from(TradeOffer).where(
        TradeOffer.status == "ACCEPTED", _pair_filter(TradeOffer.sender_id, TradeOffer.receiver_id, a, b))).scalar_one())


def world_kingdoms(db: Session, world_id: str) -> list[Kingdom]:
    return list(db.execute(select(Kingdom).where(Kingdom.world_id == world_id).order_by(Kingdom.name)).scalars())
