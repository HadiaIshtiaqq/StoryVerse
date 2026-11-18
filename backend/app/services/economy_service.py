"""Economy Engine: trades, loans, gifts (spec §2.4 D/E, feature B14).

Every movement of value runs inside one DB transaction with both kingdoms row-locked,
is re-validated at execution time, and is written to the ledger.
"""

import math
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import GameError, conflict, not_found
from app.game.rules import (BASE_PRICES, CREDIT_BASE, CREDIT_PER_BUILDING_LEVEL, DEFAULT_GRACE_TURNS,
                            DEFAULT_PRESTIGE_PENALTY, GIFT_GAIN_CAP_PER_TURN, GIFT_IRON_SHARE, KINGDOM_BY_NAME, LOAN_LIMITS,
                            RESOURCES, STANDING_DELTAS, TRADE_MAX_VALUE_RATIO, band)
from app.models import Kingdom, Loan, LoanRepayment, Player, TradeOffer, World
from app.services import npc_brain, queries, standing_service, story_service
from app.services.common import (apply, get_kingdom, lock_kingdoms, notify, open_transaction, require_owned_kingdom,
                                 require_resources, require_same_world)

MAX_PENDING_TRADES_PER_KINGDOM = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lock_row(db: Session, model, row_id: str):
    row = db.execute(select(model).where(model.id == row_id).with_for_update()
                     .execution_options(populate_existing=True)).scalars().first()
    if row is None:
        raise not_found(model.__name__.replace("Offer", " offer"))
    return row


# =============================== TRADES ======================================================
def serialize_trade(t: TradeOffer) -> dict:
    return {"id": t.id, "world_id": t.world_id, "sender_id": t.sender_id, "receiver_id": t.receiver_id,
            "offered_resource": t.offered_resource, "offered_amount": t.offered_amount,
            "requested_resource": t.requested_resource, "requested_amount": t.requested_amount,
            "status": t.status, "decision": t.decision_reasons, "created_turn": t.created_turn}


def create_trade(db: Session, player: Player, kingdom_id: str, receiver_id: str, offered_resource: str,
                 offered_amount: int, requested_resource: str, requested_amount: int) -> TradeOffer:
    sender = require_owned_kingdom(db, player, kingdom_id)
    return create_trade_for(db, sender, receiver_id, offered_resource, offered_amount, requested_resource, requested_amount)


def create_trade_for(db: Session, sender: Kingdom, receiver_id: str, offered_resource: str, offered_amount: int,
                     requested_resource: str, requested_amount: int) -> TradeOffer:
    receiver = get_kingdom(db, receiver_id)
    require_same_world(sender, receiver)
    world = db.get(World, sender.world_id)
    for res in (offered_resource, requested_resource):
        if res not in RESOURCES:
            raise GameError(f"Unknown resource '{res}'")
    if offered_resource == requested_resource:
        raise GameError("Offer and request must be different resources")
    if offered_amount <= 0 or requested_amount <= 0:
        raise GameError("Amounts must be positive")
    if not queries.has_building(db, sender.id, "market"):
        raise GameError("Build a Market to send trade offers", code="missing_building")
    if queries.active_war(db, sender.id, receiver.id):
        raise GameError(f"You are at war with {receiver.name}", code="at_war")
    if not sender.is_npc and not receiver.is_npc:
        ratio = (BASE_PRICES[offered_resource] * offered_amount) / (BASE_PRICES[requested_resource] * requested_amount)
        if ratio > TRADE_MAX_VALUE_RATIO or ratio < 1 / TRADE_MAX_VALUE_RATIO:
            raise GameError("This trade is too lopsided: use the Gift seal to give value freely", code="lopsided_trade")
    require_resources(sender, {offered_resource: offered_amount})
    pending = db.execute(select(func.count()).select_from(TradeOffer).where(
        TradeOffer.sender_id == sender.id, TradeOffer.status == "PENDING")).scalar_one()
    if pending >= MAX_PENDING_TRADES_PER_KINGDOM:
        raise GameError(f"You already have {pending} open offers; wait for answers first", code="too_many_offers")

    offer = TradeOffer(world_id=world.id, sender_id=sender.id, receiver_id=receiver.id,
                       offered_resource=offered_resource, offered_amount=offered_amount,
                       requested_resource=requested_resource, requested_amount=requested_amount,
                       status="PENDING", created_turn=world.turn)
    db.add(offer)
    db.flush()
    if receiver.is_npc:
        decision = npc_brain.decide_trade(db, receiver, sender, offer)
        if decision["accept"]:
            try:
                _execute_trade(db, offer)  # all checks run before any balance moves
            except GameError as e:
                decision = {**decision, "accept": False, "summary": f"{decision['summary']}, but the deal failed: {e.message}"}
        offer.decision_reasons = decision
        if not decision["accept"]:
            offer.status, offer.resolved_at = "REJECTED", _now()
            notify(db, world, sender.id, "TRADE_REJECTED", f"{receiver.name} declined your trade. {decision['summary']}",
                   "trade", offer.id)
    else:
        notify(db, world, receiver.id, "TRADE_OFFER",
               f"{sender.name} offers {offered_amount} {offered_resource} for {requested_amount} {requested_resource}.",
               "trade", offer.id)
    return offer


def accept_trade(db: Session, player: Player, trade_id: str) -> TradeOffer:
    offer = _lock_row(db, TradeOffer, trade_id)
    require_owned_kingdom(db, player, offer.receiver_id)
    return accept_trade_for(db, offer)


def accept_trade_for(db: Session, offer: TradeOffer) -> TradeOffer:
    if offer.status != "PENDING":
        raise conflict(f"This offer is already {offer.status.lower()}")
    _execute_trade(db, offer)
    return offer


def _execute_trade(db: Session, offer: TradeOffer) -> None:
    world = db.get(World, offer.world_id)
    ks = lock_kingdoms(db, offer.sender_id, offer.receiver_id)
    sender, receiver = ks[offer.sender_id], ks[offer.receiver_id]
    if queries.active_war(db, sender.id, receiver.id):
        raise GameError(f"{sender.name} and {receiver.name} are at war", code="at_war")
    # Revalidate both balances at execution time (spec transaction lifecycle).
    require_resources(sender, {offer.offered_resource: offer.offered_amount})
    require_resources(receiver, {offer.requested_resource: offer.requested_amount})
    txn = open_transaction(db, world, "TRADE", sender, receiver, offer.id)
    apply(db, txn, sender, {offer.offered_resource: -offer.offered_amount, offer.requested_resource: offer.requested_amount})
    apply(db, txn, receiver, {offer.offered_resource: offer.offered_amount, offer.requested_resource: -offer.requested_amount})
    offer.status, offer.resolved_at = "ACCEPTED", _now()
    standing_service.change(db, world, sender, receiver, STANDING_DELTAS["trade_completed"], "Trade completed",
                            kind="trade", transaction_id=txn.id)
    story_service.record(db, world, "TRADE_COMPLETED", f"A Bargain Between {sender.name} and {receiver.name}",
                         f"{sender.name} sent {offer.offered_amount:,} {offer.offered_resource} to {receiver.name} "
                         f"in exchange for {offer.requested_amount:,} {offer.requested_resource}.",
                         actors=[sender.name, receiver.name], consequences=["RESOURCES_EXCHANGED", "STANDING_IMPROVED"])
    for k, other in ((sender, receiver), (receiver, sender)):
        notify(db, world, k.id, "TRADE_COMPLETED", f"Trade with {other.name} completed.", "trade", offer.id)


def reject_trade(db: Session, player: Player, trade_id: str) -> TradeOffer:
    offer = _lock_row(db, TradeOffer, trade_id)
    require_owned_kingdom(db, player, offer.receiver_id)
    return _close_trade(db, offer, "REJECTED")


def cancel_trade(db: Session, player: Player, trade_id: str) -> TradeOffer:
    offer = _lock_row(db, TradeOffer, trade_id)
    require_owned_kingdom(db, player, offer.sender_id)
    return _close_trade(db, offer, "CANCELLED")


def _close_trade(db: Session, offer: TradeOffer, status: str) -> TradeOffer:
    if offer.status != "PENDING":
        raise conflict(f"This offer is already {offer.status.lower()}")
    offer.status, offer.resolved_at = status, _now()
    world = db.get(World, offer.world_id)
    target = offer.sender_id if status == "REJECTED" else offer.receiver_id
    notify(db, world, target, f"TRADE_{status}", f"A trade offer was {status.lower()}.", "trade", offer.id)
    return offer


TRADE_OFFER_TTL_TURNS = 3


def expire_trades(db: Session, world: World) -> None:
    """Turn step: unanswered offers lapse so inboxes never fill with stale deals."""
    stale = db.execute(select(TradeOffer).where(TradeOffer.world_id == world.id, TradeOffer.status == "PENDING",
                                                TradeOffer.created_turn <= world.turn - TRADE_OFFER_TTL_TURNS)).scalars().all()
    for offer in stale:
        offer.status, offer.resolved_at = "EXPIRED", _now()
        notify(db, world, offer.sender_id, "TRADE_EXPIRED", "A trade offer went unanswered and has lapsed.", "trade", offer.id)


def cancel_trades_between(db: Session, a: str, b: str) -> None:
    for offer in db.execute(select(TradeOffer).where(TradeOffer.status == "PENDING")).scalars():
        if {offer.sender_id, offer.receiver_id} == {a, b}:
            offer.status, offer.resolved_at = "CANCELLED", _now()


# =============================== LOANS =======================================================
def serialize_loan(l: Loan) -> dict:
    return {"id": l.id, "code": l.code, "world_id": l.world_id, "lender_id": l.lender_id, "borrower_id": l.borrower_id,
            "proposer_id": l.proposer_id, "principal": l.principal, "interest_rate": l.interest_rate,
            "duration_turns": l.duration_turns, "total_repayment": l.total_repayment, "installment": l.installment,
            "amount_repaid": l.amount_repaid, "remaining": l.total_repayment - l.amount_repaid,
            "missed_payments": l.missed_payments, "status": l.status, "accepted_turn": l.accepted_turn,
            "due_turn": l.due_turn, "decision": l.decision_reasons}


def calculate_total(principal: int, interest_rate: float) -> int:
    """Total = P(1 + r/100)  (spec §2.4 E)."""
    return int(round(principal * (1 + interest_rate / 100)))


def credit_limit(db: Session, borrower: Kingdom, lender: Kingdom) -> int:
    base = CREDIT_BASE + CREDIT_PER_BUILDING_LEVEL * queries.building_levels(db, borrower.id)
    factor = {"HOSTILE": 0.0, "COLD": 0.5}.get(band(standing_service.score(db, borrower.world_id, borrower.id, lender.id)), 1.0)
    return int(base * factor)


def propose_loan(db: Session, player: Player, kingdom_id: str, counterparty_id: str, role: str, principal: int,
                 interest_rate: float, duration_turns: int) -> Loan:
    me = require_owned_kingdom(db, player, kingdom_id)
    return propose_loan_for(db, me, counterparty_id, role, principal, interest_rate, duration_turns)


def propose_loan_for(db: Session, me: Kingdom, counterparty_id: str, role: str, principal: int,
                     interest_rate: float, duration_turns: int) -> Loan:
    other = get_kingdom(db, counterparty_id)
    require_same_world(me, other)
    if role not in ("lender", "borrower"):
        raise GameError("role must be 'lender' (offer a loan) or 'borrower' (request a loan)")
    lender, borrower = (me, other) if role == "lender" else (other, me)
    if principal < LOAN_LIMITS["min_principal"]:
        raise GameError(f"Minimum loan is {LOAN_LIMITS['min_principal']} gold")
    if not 0 <= interest_rate <= LOAN_LIMITS["max_interest"]:
        raise GameError(f"Interest must be between 0% and {LOAN_LIMITS['max_interest']:.0f}%")
    if not LOAN_LIMITS["min_duration"] <= duration_turns <= LOAN_LIMITS["max_duration"]:
        raise GameError(f"Duration must be {LOAN_LIMITS['min_duration']}–{LOAN_LIMITS['max_duration']} turns")
    if not queries.has_building(db, lender.id, "bank"):
        raise GameError(f"{lender.name} has no Bank: lending requires a Bank", code="missing_building")
    if role == "lender" and me.gold < principal:
        raise GameError(f"You cannot lend more gold than you hold ({me.gold:,})", code="insufficient_resources")
    if queries.active_war(db, me.id, other.id):
        raise GameError(f"You are at war with {other.name}", code="at_war")

    world = db.get(World, me.world_id)
    total = calculate_total(principal, interest_rate)
    count = db.execute(select(func.count()).select_from(Loan).where(Loan.world_id == world.id)).scalar_one()
    loan = Loan(code=f"LN-{count + 1:03d}", world_id=world.id, lender_id=lender.id, borrower_id=borrower.id,
                proposer_id=me.id, principal=principal, interest_rate=interest_rate, duration_turns=duration_turns,
                total_repayment=total, installment=math.ceil(total / duration_turns), status="PROPOSED",
                created_turn=world.turn)
    db.add(loan)
    db.flush()
    verb = "offers to lend you" if role == "lender" else "asks to borrow"
    if other.is_npc:
        decision = npc_brain.decide_loan(db, other, me, loan)
        if decision["accept"]:
            try:
                _activate_loan(db, loan)  # all checks run before any gold moves
            except GameError as e:
                decision = {**decision, "accept": False, "summary": f"{decision['summary']}, but the loan failed: {e.message}"}
        loan.decision_reasons = decision
        if not decision["accept"]:
            loan.status = "REJECTED"
            notify(db, world, me.id, "LOAN_REJECTED", f"{other.name} declined loan {loan.code}. {decision['summary']}",
                   "loan", loan.id)
    else:
        notify(db, world, other.id, "LOAN_PROPOSED",
               f"{me.name} {verb} {principal:,} gold at {interest_rate:g}% over {duration_turns} turns ({loan.code}).",
               "loan", loan.id)
    return loan


def accept_loan(db: Session, player: Player, loan_id: str) -> Loan:
    loan = _lock_row(db, Loan, loan_id)
    counterparty = loan.borrower_id if loan.proposer_id == loan.lender_id else loan.lender_id
    require_owned_kingdom(db, player, counterparty)
    return accept_loan_for(db, loan)


def accept_loan_for(db: Session, loan: Loan) -> Loan:
    if loan.status != "PROPOSED":
        raise conflict(f"Loan {loan.code} is already {loan.status.lower()}")
    _activate_loan(db, loan)
    return loan


def _activate_loan(db: Session, loan: Loan) -> None:
    world = db.get(World, loan.world_id)
    ks = lock_kingdoms(db, loan.lender_id, loan.borrower_id)
    lender, borrower = ks[loan.lender_id], ks[loan.borrower_id]
    if not queries.has_building(db, lender.id, "bank"):
        raise GameError(f"{lender.name} has no Bank", code="missing_building")
    if lender.gold < loan.principal:
        raise GameError(f"{lender.name} cannot lend more gold than it holds", code="insufficient_resources")
    limit = credit_limit(db, borrower, lender)
    owed = queries.outstanding_debt(db, borrower.id) + loan.total_repayment
    if owed > limit:
        raise GameError(f"Borrowing beyond the credit limit: {borrower.name} would owe {owed:,} gold, limit is {limit:,}",
                        code="credit_limit", details={"limit": limit, "would_owe": owed})
    txn = open_transaction(db, world, "LOAN_PRINCIPAL", lender, borrower, loan.id)
    apply(db, txn, lender, {"gold": -loan.principal})
    apply(db, txn, borrower, {"gold": loan.principal})
    loan.status, loan.accepted_turn, loan.due_turn = "ACTIVE", world.turn, world.turn + loan.duration_turns
    story_service.record(db, world, "LOAN_ACCEPTED", f"The {lender.name} Loan",
                         f"{lender.name} lent {loan.principal:,} gold to {borrower.name} at {loan.interest_rate:g}% interest, "
                         f"to be repaid as {loan.total_repayment:,} gold over {loan.duration_turns} turns.",
                         actors=[lender.name, borrower.name], consequences=["DEBT_CREATED"])
    for k in (lender, borrower):
        notify(db, world, k.id, "LOAN_ACTIVE", f"Loan {loan.code} is now active.", "loan", loan.id)


def repay_loan(db: Session, player: Player, loan_id: str, amount: int) -> Loan:
    loan = _lock_row(db, Loan, loan_id)
    require_owned_kingdom(db, player, loan.borrower_id)
    if loan.status != "ACTIVE":
        raise conflict(f"Loan {loan.code} is {loan.status.lower()}")
    remaining = loan.total_repayment - loan.amount_repaid
    if amount <= 0:
        raise GameError("Repayment must be positive")
    if amount > remaining:
        raise GameError(f"Only {remaining:,} gold remains on {loan.code}", code="overpayment")
    _pay(db, loan, amount, "MANUAL")
    return loan


def _pay(db: Session, loan: Loan, amount: int, source: str) -> None:
    world = db.get(World, loan.world_id)
    ks = lock_kingdoms(db, loan.lender_id, loan.borrower_id)
    lender, borrower = ks[loan.lender_id], ks[loan.borrower_id]
    txn = open_transaction(db, world, "LOAN_REPAYMENT", borrower, lender, loan.id)
    apply(db, txn, borrower, {"gold": -amount})
    apply(db, txn, lender, {"gold": amount})
    db.add(LoanRepayment(loan_id=loan.id, amount=amount, source=source, turn=world.turn))
    loan.amount_repaid += amount
    if loan.amount_repaid >= loan.total_repayment:
        loan.status = "REPAID"
        standing_service.change(db, world, lender, borrower, STANDING_DELTAS["loan_repaid"], f"Loan {loan.code} repaid",
                                transaction_id=txn.id)
        story_service.record(db, world, "LOAN_REPAID", "A Debt Honoured",
                             f"{borrower.name} repaid the {lender.name} loan in full: {loan.total_repayment:,} gold.",
                             actors=[borrower.name, lender.name], consequences=["DEBT_CLEARED", "STANDING_IMPROVED"])
        for k in (lender, borrower):
            notify(db, world, k.id, "LOAN_REPAID", f"Loan {loan.code} is fully repaid.", "loan", loan.id)


def reject_loan(db: Session, player: Player, loan_id: str) -> Loan:
    loan = _lock_row(db, Loan, loan_id)
    counterparty = loan.borrower_id if loan.proposer_id == loan.lender_id else loan.lender_id
    require_owned_kingdom(db, player, counterparty)
    if loan.status != "PROPOSED":
        raise conflict(f"Loan {loan.code} is already {loan.status.lower()}")
    loan.status = "REJECTED"
    notify(db, db.get(World, loan.world_id), loan.proposer_id, "LOAN_REJECTED", f"Loan {loan.code} was declined.", "loan", loan.id)
    return loan


def process_loans(db: Session, world: World) -> None:
    """Turn step: collect one installment per active loan; default after the grace period."""
    for loan in db.execute(select(Loan).where(Loan.world_id == world.id, Loan.status == "ACTIVE")).scalars().all():
        if world.turn <= (loan.accepted_turn or 0):
            continue
        remaining = loan.total_repayment - loan.amount_repaid
        due = min(loan.installment, remaining)
        borrower = db.get(Kingdom, loan.borrower_id)
        if borrower.gold >= due:
            _pay(db, loan, due, "AUTO")
            continue
        loan.missed_payments += 1
        lender = db.get(Kingdom, loan.lender_id)
        if world.turn > (loan.due_turn or 0) + DEFAULT_GRACE_TURNS:
            loan.status = "DEFAULTED"
            borrower.prestige_penalty += DEFAULT_PRESTIGE_PENALTY
            standing_service.change(db, world, lender, borrower, STANDING_DELTAS["loan_defaulted"], f"Loan {loan.code} defaulted")
            story_service.record(db, world, "LOAN_DEFAULTED", f"{borrower.name} Defaults on the {lender.name} Loan",
                                 f"{borrower.name} has failed to repay {remaining:,} gold owed to {lender.name}. "
                                 f"Trust in {borrower.name}'s word has collapsed across the continent.",
                                 actors=[borrower.name, lender.name], consequences=["LOAN_DEFAULTED", "STANDING_COLLAPSED"],
                                 importance=3)
        for k in (lender, borrower):
            notify(db, world, k.id, "LOAN_PAYMENT_MISSED",
                   f"{borrower.name} missed a payment of {due:,} gold on {loan.code}.", "loan", loan.id)


# =============================== GIFTS =======================================================
def gift_preview(db: Session, player: Player, kingdom_id: str, target_id: str) -> dict:
    me = require_owned_kingdom(db, player, kingdom_id)
    target = get_kingdom(db, target_id)
    require_same_world(me, target)
    world = db.get(World, me.world_id)
    rel = standing_service.get_relation(db, world.id, me.id, target.id)
    used = rel.gift_gain_this_turn if rel.counters_turn == world.turn else 0
    mult = max(KINGDOM_BY_NAME.get(k.name, {}).get("standing_gain_multiplier", 1.0) for k in (me, target))
    tiers = []
    for gold in standing_service.gift_tiers(me.gold):
        iron = gift_iron(gold, me.iron)
        gain = min(int(round(standing_service.gift_gain(gift_value(gold, iron), target.gold) * mult)), max(0, GIFT_GAIN_CAP_PER_TURN - used))
        tiers.append({"gold": gold, "iron": iron, "standing_gain": gain, "new_standing": max(-100, min(100, rel.score + gain)),
                      "new_band": band(max(-100, min(100, rel.score + gain)))})
    return {"target_id": target.id, "current_standing": rel.score, "band": band(rel.score),
            "remaining_gift_gain_this_turn": max(0, GIFT_GAIN_CAP_PER_TURN - used), "tiers": tiers}


def gift_iron(gold: int, have_iron: int) -> int:
    """A chest carries iron alongside the gold (GIFT_IRON_SHARE of the gold, by count), if the giver has it."""
    return max(0, min(int(round(gold * GIFT_IRON_SHARE)), have_iron))


def gift_value(gold: int, iron: int) -> int:
    return gold + int(round(iron * BASE_PRICES["iron"]))


def send_gift(db: Session, player: Player, kingdom_id: str, target_id: str, gold: int, iron: int = 0) -> dict:
    me = require_owned_kingdom(db, player, kingdom_id)
    target = get_kingdom(db, target_id)
    require_same_world(me, target)
    if gold <= 0:
        raise GameError("A gift must contain gold")
    if iron < 0:
        raise GameError("Iron in a gift cannot be negative")
    world = db.get(World, me.world_id)
    ks = lock_kingdoms(db, me.id, target.id)
    me, target = ks[me.id], ks[target.id]
    txn = open_transaction(db, world, "GIFT", me, target)
    raw_gain = standing_service.gift_gain(gift_value(gold, iron), target.gold)
    chest = {"gold": gold, **({"iron": iron} if iron else {})}
    apply(db, txn, me, {r: -v for r, v in chest.items()})
    apply(db, txn, target, chest)
    what = f"{gold:,} gold" + (f" and {iron:,} iron" if iron else "")
    gain = standing_service.change(db, world, me, target, raw_gain, f"Gift of {what}", kind="gift", transaction_id=txn.id)
    if gold >= 500:
        story_service.record(db, world, "TRIBUTE_SENT", f"{me.name} Sends Tribute to {target.name}",
                             f"A chest of {gold:,} gold travels from {me.name} to the court of {target.name}.",
                             actors=[me.name, target.name], consequences=["STANDING_IMPROVED"])
    notify(db, world, target.id, "GIFT_RECEIVED", f"{me.name} sent you a gift of {what}.")
    return {"gold": gold, "iron": iron, "standing_gain": gain,
            "standing": standing_service.score(db, world.id, me.id, target.id)}



# =============================== ROYAL MARKET ================================================
def market_prices() -> dict[str, dict[str, int]]:
    """Gold per unit when buying from / selling to the crown's market (gold itself is not traded)."""
    from app.game.rules import MARKET_BUY_MARKUP, MARKET_SELL_RATE
    return {r: {"buy": int(math.ceil(BASE_PRICES[r] * MARKET_BUY_MARKUP)),
                "sell": max(1, int(BASE_PRICES[r] * MARKET_SELL_RATE))} for r in RESOURCES if r != "gold"}


def market_capacity(db: Session, k: Kingdom, turn: int) -> tuple[int, int]:
    """(units allowed per turn, units already moved this turn). Read from the ledger, so no extra state."""
    from app.game.rules import MARKET_UNITS_PER_LEVEL
    from app.models import LedgerEntry, Transaction
    allowed = MARKET_UNITS_PER_LEVEL * queries.building_levels(db, k.id, "market")
    used = db.execute(select(func.coalesce(func.sum(func.abs(LedgerEntry.delta)), 0))
                      .join(Transaction, LedgerEntry.transaction_id == Transaction.id)
                      .where(LedgerEntry.kingdom_id == k.id, LedgerEntry.resource != "gold",
                             Transaction.transaction_type == "MARKET", Transaction.turn == turn)).scalar_one()
    return allowed, int(used)


def market_view(db: Session, k: Kingdom) -> dict:
    world = db.get(World, k.world_id)
    allowed, used = market_capacity(db, k, world.turn)
    return {"open": allowed > 0, "prices": market_prices(), "units_per_turn": allowed,
            "units_left": max(0, allowed - used)}


def market_trade(db: Session, player: Player, kingdom_id: str, resource: str, amount: int, side: str) -> dict:
    k = require_owned_kingdom(db, player, kingdom_id)
    if resource not in RESOURCES or resource == "gold":
        raise GameError("The market trades food, wood, stone and iron for gold", code="invalid_resource")
    if side not in ("buy", "sell"):
        raise GameError("Choose to buy or to sell", code="invalid_side")
    if amount <= 0:
        raise GameError("Trade at least one unit")
    world = db.get(World, k.world_id)
    k = lock_kingdoms(db, k.id)[k.id]
    allowed, used = market_capacity(db, k, world.turn)
    if allowed == 0:
        raise GameError("Build a Market to trade with the crown's merchants", code="missing_building")
    if amount > allowed - used:
        raise GameError(f"The merchants can move {max(0, allowed - used)} more units this turn "
                        f"(upgrade your Market for more)", code="market_capacity")
    price = market_prices()[resource][side]
    gold = price * amount
    txn = open_transaction(db, world, "MARKET", sender=k)
    deltas = {resource: amount, "gold": -gold} if side == "buy" else {resource: -amount, "gold": gold}
    apply(db, txn, k, deltas)
    return {"resource": resource, "amount": amount, "side": side, "gold": gold, "price": price,
            "units_left": allowed - used - amount, "resources": {r: getattr(k, r) for r in RESOURCES}}
