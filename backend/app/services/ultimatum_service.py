"""Ultimatums: a warlord NPC demands tribute from a weaker human ruler, with a deadline.

This gives a solo player a real decision a few turns in: pay the gold, raise enough defence (soldiers,
watchtowers, a mutual-defence ally) that the threat collapses, or ignore it and face the army.

No extra tables: a demand is a letter with a known subject, tribute is the GIFT ledger, and a demand is
answered by a follow-up letter. Everything stays readable in the Letters tab and the ledger.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import GameError
from app.game.rules import (ULTIMATUM_COOLDOWN_TURNS, ULTIMATUM_DEADLINE_TURNS, ULTIMATUM_FIRST_TURN,
                            ULTIMATUM_TRIBUTE_BASE, ULTIMATUM_TRIBUTE_PER_TURN)
from app.models import Kingdom, LedgerEntry, Message, Transaction, World
from app.services import diplomacy_service, military_service, queries, story_service
from app.services.common import notify

DEMAND_SUBJECT = "An Ultimatum from Cinderhold"
ANSWERS = {"paid": "Tribute Accepted", "march": "Drakoria Marches", "deterred": "Drakoria Stays Its Hand"}
COMMIT_SHARE = 0.85    # an NPC never sends more than this share of its army; the rest guards home
MARGIN = 1.3           # expected attack must beat expected defence by this much (dice are +-15%)
WARLORD_RECRUITS_PER_TURN = 10   # what a warlord NPC trains each turn while its treasury allows (npc_actor)


def tribute_for(turn: int) -> int:
    return ULTIMATUM_TRIBUTE_BASE + ULTIMATUM_TRIBUTE_PER_TURN * turn


def _letters(db: Session, sender_id: str, recipient_id: str, subjects) -> list[Message]:
    return list(db.execute(select(Message).where(Message.sender_kingdom_id == sender_id,
                                                 Message.recipient_kingdom_id == recipient_id,
                                                 Message.subject.in_(list(subjects)))
                           .order_by(Message.created_at.desc())).scalars())


def _latest(db: Session, npc_id: str, human_id: str) -> tuple[Message | None, Message | None]:
    """(latest demand, its answer if already given)."""
    demands = _letters(db, npc_id, human_id, [DEMAND_SUBJECT])
    if not demands:
        return None, None
    demand = demands[0]
    answer = next((m for m in _letters(db, npc_id, human_id, ANSWERS.values()) if m.created_at >= demand.created_at), None)
    return demand, answer


def tribute_paid(db: Session, payer_id: str, receiver_id: str, since_turn: int) -> int:
    """Gold gifted by payer to receiver from `since_turn` on."""
    return int(db.execute(select(func.coalesce(func.sum(LedgerEntry.delta), 0))
                          .join(Transaction, LedgerEntry.transaction_id == Transaction.id)
                          .where(Transaction.transaction_type == "GIFT", Transaction.sender_kingdom_id == payer_id,
                                 Transaction.receiver_kingdom_id == receiver_id, Transaction.turn >= since_turn,
                                 LedgerEntry.kingdom_id == receiver_id, LedgerEntry.resource == "gold")).scalar_one())


def can_threaten(db: Session, npc: Kingdom, target: Kingdom) -> tuple[bool, int]:
    need = military_service.army_needed(db, npc, target, MARGIN)
    return int(npc.soldiers * COMMIT_SHARE) >= need, need


def _answer(db: Session, world: World, npc: Kingdom, human: Kingdom, kind: str, body: str) -> None:
    diplomacy_service.send_message_for(db, npc, human.id, ANSWERS[kind], f"{body}\n\n— {npc.ruler_name}", "cold", False)


def npc_turn(db: Session, world: World, npc: Kingdom) -> bool:
    """Run a warlord's ultimatums against every human. Returns True if it attacked (its move for the turn)."""
    for human in [k for k in queries.world_kingdoms(db, world.id) if not k.is_npc and k.id != npc.id]:
        if queries.active_war(db, npc.id, human.id) or queries.active_alliance(db, npc.id, human.id):
            continue
        demand, answer = _latest(db, npc.id, human.id)
        if demand and not answer:
            amount = tribute_for(demand.turn)
            paid = tribute_paid(db, human.id, npc.id, demand.turn)
            if paid >= amount:
                _answer(db, world, npc, human, "paid",
                        f"Your gold has reached Cinderhold. Drakoria's banners stay furled, for now.")
                continue
            if world.turn < demand.turn + ULTIMATUM_DEADLINE_TURNS:
                continue
            strong, need = can_threaten(db, npc, human)
            if not strong:
                _answer(db, world, npc, human, "deterred",
                        f"Your walls have grown tall and your spears many. Drakoria will not waste its legions "
                        f"on stone. Keep your gold, {human.name}.")
                story_service.record(db, world, "ULTIMATUM_DEFIED", f"{human.name} Defies Drakoria",
                                     f"{human.name} refused Drakoria's demand for {amount:,} gold, and its defences "
                                     f"were too strong for Queen Varka to answer with steel.",
                                     actors=[human.name, npc.name], consequences=["ULTIMATUM_DEFIED"], importance=2)
                continue
            _answer(db, world, npc, human, "march", f"You were warned. The legions march on {human.name}.")
            story_service.record(db, world, "ULTIMATUM_IGNORED", f"Drakoria Answers {human.name}'s Silence",
                                 f"{human.name} sent no tribute to Cinderhold. Queen Varka's legions are on the march.",
                                 actors=[npc.name, human.name], consequences=["WAR_DECLARED"], importance=3)
            try:
                with db.begin_nested():
                    military_service.battle_for(db, npc, human, min(int(npc.soldiers * COMMIT_SHARE), need))
                return True
            except GameError:
                continue
        # No open demand: issue a new one when strong enough and the last one is old news.
        if world.turn < max(ULTIMATUM_FIRST_TURN, world.beginner_protection_turns + 1):
            continue
        if answer and world.turn - answer.turn < ULTIMATUM_COOLDOWN_TURNS:
            continue
        strong, _ = can_threaten(db, npc, human)
        if not strong:
            continue
        amount = tribute_for(world.turn)
        deadline = world.turn + ULTIMATUM_DEADLINE_TURNS
        diplomacy_service.send_message_for(
            db, npc, human.id, DEMAND_SUBJECT,
            f"{human.name} grows fat while Drakoria's legions sharpen their blades. Send {amount:,} gold as tribute "
            f"before turn {deadline}, or our banners will darken your fields.\n\n— {npc.ruler_name}", "cold", False)
        notify(db, world, human.id, "ULTIMATUM",
               f"Drakoria demands {amount:,} gold by turn {deadline}. Pay it as a gift, or make your defences too "
               f"strong to attack.", "kingdom", npc.id)
        story_service.record(db, world, "ULTIMATUM", f"Drakoria Threatens {human.name}",
                             f"Queen Varka demands {amount:,} gold in tribute from {human.name}, or war.",
                             actors=[npc.name, human.name], consequences=["ULTIMATUM"], importance=2)
    return False


def demands_for(db: Session, human: Kingdom) -> list[dict]:
    """Open ultimatums against this ruler, with everything needed to decide what to do."""
    world = db.get(World, human.world_id)
    out = []
    for npc in [k for k in queries.world_kingdoms(db, world.id) if k.is_npc]:
        demand, answer = _latest(db, npc.id, human.id)
        if not demand or answer or queries.active_war(db, npc.id, human.id):
            continue
        amount = tribute_for(demand.turn)
        paid = tribute_paid(db, human.id, npc.id, demand.turn)
        defense, *_ = military_service.defense_breakdown(db, human, exclude_id=npc.id)
        need = military_service.army_needed(db, npc, human, MARGIN)
        turns_left = max(0, demand.turn + ULTIMATUM_DEADLINE_TURNS - world.turn)
        # Judge safety against the army they will have at the deadline, not today's: they keep recruiting.
        at_deadline = npc.soldiers + WARLORD_RECRUITS_PER_TURN * turns_left
        strength = military_service.attack_strength(db, npc)
        can_send = int(at_deadline * COMMIT_SHARE)
        # Defence you need for them to back down, at the deadline.
        defense_needed = int(can_send * strength / MARGIN) + 1
        out.append({"from_id": npc.id, "from": npc.name, "ruler": npc.ruler_name, "amount": amount, "paid": paid,
                    "owed": max(0, amount - paid), "deadline_turn": demand.turn + ULTIMATUM_DEADLINE_TURNS,
                    "turns_left": turns_left,
                    "their_army": int(round(at_deadline, -1)), "your_defense": int(defense),
                    "defense_needed": defense_needed, "safe": can_send < need})
    return out
