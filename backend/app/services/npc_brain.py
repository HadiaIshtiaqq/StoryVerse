"""NPC rulers' decisions (judging alignment §2.1).

Every decision returns itemised reasons, so a solo player always sees *why* an NPC said
yes or no:  accept  <=>  sum(positive) + sum(negative) >= personality threshold.
"""

from sqlalchemy.orm import Session

from app.game.rules import BASE_PRICES, band
from app.models import Alliance, Kingdom, Loan, TradeOffer, War
from app.services import queries, standing_service

PERSONALITIES = {
    "Aurelia": {"threshold": 3, "style": "merchant", "label": "Pragmatic"},
    "Drakoria": {"threshold": 10, "style": "warlord", "label": "Proud"},
    "Sylvara": {"threshold": 6, "style": "steward", "label": "Cautious"},
    "Valoria": {"threshold": 5, "style": "broker", "label": "Honourable"},
}
_DEFAULT = {"threshold": 5, "style": "broker", "label": "Even-handed"}


def personality(k: Kingdom) -> dict:
    return PERSONALITIES.get(k.name, _DEFAULT)


def verdict(npc: Kingdom, reasons: list[tuple[str, float]]) -> dict:
    items = [(label, int(round(v))) for label, v in reasons if int(round(v)) != 0]
    positive = sum(v for _, v in items if v > 0)
    negative = sum(v for _, v in items if v < 0)
    threshold = personality(npc)["threshold"]
    accept = positive + negative >= threshold
    return {
        "accept": accept, "positive": positive, "negative": negative, "threshold": threshold,
        "decided_by": npc.ruler_name,
        "summary": f"{npc.ruler_name} {'accepts' if accept else 'refuses'} "
                   f"(for {positive}, against {negative}; needs {threshold:+d})",
        "reasons": [{"label": label, "value": v} for label, v in items],
    }


def _standing(db: Session, a: Kingdom, b: Kingdom) -> int:
    return standing_service.score(db, a.world_id, a.id, b.id)


def decide_trade(db: Session, npc: Kingdom, sender: Kingdom, offer: TradeOffer) -> dict:
    s = _standing(db, npc, sender)
    reasons: list[tuple[str, float]] = [(f"Standing ({band(s).title()})", s * 0.3)]
    if queries.active_war(db, npc.id, sender.id):
        reasons.append(("We are at war", -100))
    offered_value = BASE_PRICES[offer.offered_resource] * offer.offered_amount
    requested_value = BASE_PRICES[offer.requested_resource] * offer.requested_amount
    ratio = offered_value / max(requested_value, 1)
    reasons.append(("Value of the deal", max(-30, min(30, (ratio - 1) * 30))))
    if getattr(npc, offer.offered_resource) < 150:
        reasons.append((f"We need {offer.offered_resource}", 10))
    if getattr(npc, offer.requested_resource) - offer.requested_amount < 100:
        reasons.append((f"We cannot spare {offer.requested_resource}", -15))
    if queries.active_alliance(db, npc.id, sender.id):
        reasons.append(("Allied kingdom", 6))
    style = personality(npc)["style"]
    if style == "broker":
        reasons.append(("Trade is Valoria's lifeblood", 5))
    elif style == "warlord" and offer.offered_resource in ("iron", "gold"):
        reasons.append(("Iron and gold feed the legions", 8))
    elif style == "merchant" and offer.offered_resource == "gold":
        reasons.append(("Coin speaks", 4))
    elif style == "steward" and offer.requested_resource in ("food", "wood"):
        reasons.append(("The forest provides", 4))
    return verdict(npc, reasons)


def decide_loan(db: Session, npc: Kingdom, other: Kingdom, loan: Loan) -> dict:
    s = _standing(db, npc, other)
    style = personality(npc)["style"]
    reasons: list[tuple[str, float]]
    if loan.lender_id == npc.id:
        reasons = [(f"Standing ({band(s).title()})", s * 0.3)]
        if not queries.has_building(db, npc.id, "bank"):
            reasons.append(("We have no bank", -100))
        share = loan.principal / max(npc.gold, 1)
        if share > 0.4:
            reasons.append(("Too large a share of our treasury", -20))
        elif share < 0.2:
            reasons.append(("A modest sum", 5))
        reasons.append(("Interest offered", (loan.interest_rate - 8) * (2 if style == "merchant" else 1)))
        if queries.has_overdue_loan(db, other.id):
            reasons.append(("Unpaid debts elsewhere", -30))
        elif queries.outstanding_debt(db, other.id) > 0:
            reasons.append(("Already in debt", -10))
    else:
        need = 2000 - npc.gold
        reasons = [("Our treasury needs gold", min(25, need / 80)) if need > 0 else ("We have no need of gold", -10)]
        if style == "warlord":
            reasons.append(("A war chest for the legions", 10))
        reasons.append(("Interest demanded", -(loan.interest_rate - 5) * 1.5))
        reasons.append((f"Standing ({band(s).title()})", s * 0.2))
    return verdict(npc, reasons)


def decide_alliance(db: Session, npc: Kingdom, proposer: Kingdom, alliance: Alliance) -> dict:
    s = _standing(db, npc, proposer)
    reasons: list[tuple[str, float]] = [(f"Standing ({band(s).title()})", s * 0.4)]
    for other in queries.world_kingdoms(db, npc.world_id):
        if other.id in (npc.id, proposer.id):
            continue
        if _standing(db, npc, other) < 0 and _standing(db, proposer, other) < 0:
            reasons.append((f"A shared rival: {other.name}", 10))
            break
    if proposer.betrayals:
        reasons.append(("Oathbreaker", -25 * proposer.betrayals))
    if queries.has_overdue_loan(db, proposer.id, lender_id=npc.id):
        reasons.append(("They owe us overdue gold", -20))
    style = personality(npc)["style"]
    if style == "warlord":
        if proposer.soldiers < 0.5 * npc.soldiers:
            reasons.append(("Queen Varka values strength: your army is weak", -12))
        else:
            reasons.append(("A worthy sword-arm", 6))
    elif style == "broker":
        reasons.append(("Honour binds Valoria to its friends", 8))
    elif style == "merchant":
        reasons.append(("Allies make good customers", 4))
    elif style == "steward" and proposer.soldiers > npc.soldiers:
        reasons.append(("Protection for the forest", 8))
    return verdict(npc, reasons)


def decide_peace(db: Session, npc: Kingdom, enemy: Kingdom, war: War, turn: int) -> dict:
    ratio = npc.soldiers / max(enemy.soldiers, 1)
    reasons: list[tuple[str, float]] = []
    if ratio < 0.8:
        reasons.append(("Our armies are weaker", 15))
    elif ratio > 1.5:
        reasons.append(("We are winning this war", -15))
    reasons.append(("War wearies the people", min(15, (turn - war.started_turn) * 4)))
    style = personality(npc)["style"]
    if style == "warlord":
        reasons.append(("Drakoria does not kneel", -8))
    elif style == "broker":
        reasons.append(("Trade cannot flow in war", 8))
    elif style == "steward":
        reasons.append(("The forest longs for quiet", 6))
    elif style == "merchant":
        reasons.append(("War is bad for business", 6))
    if war.betrayal and war.defender_id == npc.id:
        reasons.append(("They broke their oath", -10))
    return verdict(npc, reasons)
