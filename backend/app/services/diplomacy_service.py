"""Diplomacy Engine: alliances, betrayal, private letters, and the relations view (Standing Gauge)."""

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.errors import GameError, conflict, forbidden, not_found
from app.game.rules import (ALLIANCE_MIN_STANDING, BETRAYAL_PRESTIGE_PENALTY, PASSAGE_GOLD_PER_TURN, PASSAGE_MIN_STANDING,
                            PASSAGE_STANDING_ON_CLOSE, PASSAGE_STANDING_ON_GRANT, STANDING_DELTAS, band)
from app.models import Alliance, Kingdom, Loan, Message, Passage, Player, StoryEvent, World
from app.services import npc_brain, queries, standing_service, story_service
from app.services.common import emit, get_kingdom, notify, require_owned_kingdom, require_same_world
from app.services.economy_service import credit_limit

MAX_ALLIANCE_TURNS = 20
TONES = ("warm", "proud", "cold")


# =============================== ALLIANCES ===================================================
def serialize_alliance(a: Alliance) -> dict:
    return {"id": a.id, "world_id": a.world_id, "kingdom_a": a.kingdom_a, "kingdom_b": a.kingdom_b,
            "proposer_id": a.proposer_id, "duration_turns": a.duration_turns, "mutual_defense": a.mutual_defense,
            "trade_benefits": a.trade_benefits, "status": a.status, "created_turn": a.created_turn,
            "expires_turn": a.expires_turn, "ended_by": a.ended_by, "decision": a.decision_reasons}


def _check_alliance_allowed(db: Session, me: Kingdom, target: Kingdom) -> None:
    if queries.active_war(db, me.id, target.id):
        raise GameError(f"You are at war with {target.name}", code="at_war")
    if queries.active_alliance(db, me.id, target.id):
        raise conflict(f"You are already allied with {target.name}")
    s = standing_service.score(db, me.world_id, me.id, target.id)
    if s < ALLIANCE_MIN_STANDING:
        raise GameError(f"An alliance requires Friendly standing ({ALLIANCE_MIN_STANDING}); yours with {target.name} is {s}",
                        code="standing_too_low", details={"standing": s, "required": ALLIANCE_MIN_STANDING})


def propose_alliance(db: Session, player: Player, kingdom_id: str, target_id: str, duration_turns: int,
                     mutual_defense: bool) -> Alliance:
    me = require_owned_kingdom(db, player, kingdom_id)
    return propose_alliance_for(db, me, target_id, duration_turns, mutual_defense)


def propose_alliance_for(db: Session, me: Kingdom, target_id: str, duration_turns: int = 10,
                         mutual_defense: bool = True) -> Alliance:
    target = get_kingdom(db, target_id)
    require_same_world(me, target)
    if not 1 <= duration_turns <= MAX_ALLIANCE_TURNS:
        raise GameError(f"Alliance duration must be 1–{MAX_ALLIANCE_TURNS} turns")
    _check_alliance_allowed(db, me, target)
    if queries.pending_alliance(db, me.id, target.id):
        raise conflict(f"An alliance proposal with {target.name} is already waiting for an answer")
    world = db.get(World, me.world_id)
    alliance = Alliance(world_id=world.id, kingdom_a=me.id, kingdom_b=target.id, proposer_id=me.id,
                        duration_turns=duration_turns, mutual_defense=mutual_defense, status="PENDING",
                        created_turn=world.turn)
    db.add(alliance)
    db.flush()
    if target.is_npc:
        decision = npc_brain.decide_alliance(db, target, me, alliance)
        alliance.decision_reasons = decision
        if decision["accept"]:
            _activate(db, world, alliance)
        else:
            alliance.status = "REJECTED"
            notify(db, world, me.id, "ALLIANCE_REJECTED", f"{target.name} refused your alliance. {decision['summary']}",
                   "alliance", alliance.id)
    else:
        notify(db, world, target.id, "ALLIANCE_PROPOSED",
               f"{me.name} proposes a {duration_turns}-turn alliance{' with mutual defence' if mutual_defense else ''}.",
               "alliance", alliance.id)
    return alliance


def respond_alliance(db: Session, player: Player, alliance_id: str, accept: bool) -> Alliance:
    alliance = db.get(Alliance, alliance_id)
    if alliance is None:
        raise not_found("Alliance")
    responder_id = alliance.kingdom_b if alliance.proposer_id == alliance.kingdom_a else alliance.kingdom_a
    responder = require_owned_kingdom(db, player, responder_id)
    if alliance.status != "PENDING":
        raise conflict(f"This proposal is already {alliance.status.lower()}")
    world = db.get(World, alliance.world_id)
    if accept:
        _check_alliance_allowed(db, responder, get_kingdom(db, alliance.proposer_id))
        _activate(db, world, alliance)
    else:
        alliance.status = "REJECTED"
        notify(db, world, alliance.proposer_id, "ALLIANCE_REJECTED", f"{responder.name} refused your alliance.",
               "alliance", alliance.id)
    return alliance


def _activate(db: Session, world: World, alliance: Alliance) -> None:
    a, b = db.get(Kingdom, alliance.kingdom_a), db.get(Kingdom, alliance.kingdom_b)
    alliance.status, alliance.expires_turn = "ACTIVE", world.turn + alliance.duration_turns
    standing_service.change(db, world, a, b, STANDING_DELTAS["alliance_formed"], "Alliance formed")
    story_service.record(db, world, "ALLIANCE_FORMED", f"The Pact of {a.name} and {b.name}",
                         f"{a.name} and {b.name} swore a {'mutual-defence ' if alliance.mutual_defense else ''}"
                         f"alliance for {alliance.duration_turns} turns.",
                         actors=[a.name, b.name], consequences=["ALLIANCE_FORMED"], importance=2)
    for k in (a, b):
        notify(db, world, k.id, "ALLIANCE_ACTIVE", f"The alliance of {a.name} and {b.name} is sealed.", "alliance", alliance.id)


def terminate_alliance(db: Session, player: Player, alliance_id: str, kingdom_id: str) -> StoryEvent:
    alliance = db.get(Alliance, alliance_id)
    if alliance is None:
        raise not_found("Alliance")
    me = require_owned_kingdom(db, player, kingdom_id)
    if me.id not in (alliance.kingdom_a, alliance.kingdom_b):
        raise forbidden("Your kingdom is not part of this alliance")
    if alliance.status != "ACTIVE":
        raise conflict(f"This alliance is {alliance.status.lower()}")
    return break_alliance(db, db.get(World, me.world_id), alliance, me, attacking=False)


def break_alliance(db: Session, world: World, alliance: Alliance, breaker: Kingdom, attacking: bool) -> StoryEvent:
    """Breaking an active alliance is a Betrayal (feature B14): prestige loss, standing crash, chronicle event."""
    victim = db.get(Kingdom, alliance.kingdom_b if alliance.kingdom_a == breaker.id else alliance.kingdom_a)
    alliance.status, alliance.ended_by = "TERMINATED", breaker.id
    breaker.betrayals += 1
    breaker.prestige_penalty += BETRAYAL_PRESTIGE_PENALTY
    standing_service.change(db, world, breaker, victim, STANDING_DELTAS["alliance_broken"], "Alliance broken")

    lines = [f"{breaker.name} broke its alliance with {victim.name}"
             + (f" and launched an attack on its {story_service.compass_side(victim, breaker)} territory." if attacking else ".")]
    if queries.trades_between(db, breaker.id, victim.id) > 0:
        lines.append("Trade relations have deteriorated.")
    for other in queries.world_kingdoms(db, world.id):
        if other.id in (breaker.id, victim.id):
            continue
        standing_service.change(db, world, breaker, other, STANDING_DELTAS["betrayal_world_penalty"],
                                f"{breaker.name} betrayed {victim.name}")
        if queries.active_alliance(db, other.id, victim.id) or queries.active_alliance(db, other.id, breaker.id):
            lines.append(f"{other.name} is now reconsidering its military commitments.")
        elif db.execute(select(Loan).where(Loan.lender_id == other.id, Loan.borrower_id == breaker.id,
                                           Loan.status == "ACTIVE")).scalars().first():
            lines.append(f"{other.name} fears for the gold it lent to {breaker.name}.")
    event = story_service.record(
        db, world, "ALLIANCE_BROKEN", f"THE BETRAYAL OF {victim.name.upper()}", " ".join(lines),
        actors=[breaker.name, victim.name],
        consequences=["ALLIANCE_TERMINATED", "RELATIONSHIP_CHANGED", "DIPLOMATIC_TENSION"] + (["WAR_DECLARED"] if attacking else []),
        importance=3)
    notify(db, world, victim.id, "BETRAYED", f"{breaker.name} has broken your alliance!", "alliance", alliance.id)
    return event


def expire_alliances(db: Session, world: World) -> None:
    for alliance in db.execute(select(Alliance).where(Alliance.world_id == world.id, Alliance.status == "ACTIVE",
                                                      Alliance.expires_turn <= world.turn)).scalars().all():
        alliance.status = "EXPIRED"
        a, b = db.get(Kingdom, alliance.kingdom_a), db.get(Kingdom, alliance.kingdom_b)
        story_service.record(db, world, "ALLIANCE_EXPIRED", f"The Pact of {a.name} and {b.name} Lapses",
                             f"The alliance between {a.name} and {b.name} has run its course.", actors=[a.name, b.name])
        for k in (a, b):
            notify(db, world, k.id, "ALLIANCE_EXPIRED", f"Your alliance of {a.name} and {b.name} has expired.",
                   "alliance", alliance.id)


def alliances_in_world(db: Session, world_id: str) -> list[Alliance]:
    return list(db.execute(select(Alliance).where(Alliance.world_id == world_id).order_by(Alliance.created_at.desc())).scalars())


# =============================== LETTERS =====================================================
def serialize_message(m: Message) -> dict:
    return {"id": m.id, "sender_kingdom_id": m.sender_kingdom_id, "recipient_kingdom_id": m.recipient_kingdom_id,
            "subject": m.subject, "body": m.body, "tone": m.tone, "read": m.read, "turn": m.turn,
            "created_at": m.created_at.isoformat() if m.created_at else None}


def send_message(db: Session, player: Player, kingdom_id: str, recipient_id: str, subject: str, body: str,
                 tone: str) -> Message:
    me = require_owned_kingdom(db, player, kingdom_id)
    return send_message_for(db, me, recipient_id, subject, body, tone)


def send_message_for(db: Session, me: Kingdom, recipient_id: str, subject: str, body: str, tone: str,
                     allow_npc_reply: bool = True) -> Message:
    recipient = get_kingdom(db, recipient_id)
    require_same_world(me, recipient)
    if tone not in TONES:
        raise GameError(f"Tone must be one of {', '.join(TONES)}")
    subject, body = subject.strip(), body.strip()
    if not subject or not body:
        raise GameError("A letter needs a subject and a body")
    if len(subject) > 120 or len(body) > 2000:
        raise GameError("Letters are limited to 120-character subjects and 2,000-character bodies")
    world = db.get(World, me.world_id)
    msg = Message(world_id=world.id, sender_kingdom_id=me.id, recipient_kingdom_id=recipient.id, subject=subject,
                  body=body, tone=tone, turn=world.turn)
    db.add(msg)
    db.flush()
    # Private delivery: only the recipient's sockets receive the letter (spec §6.2).
    emit(db, {"type": "letter", "world_id": world.id, "private_to": recipient.id, "message": serialize_message(msg)})
    notify(db, world, recipient.id, "LETTER_RECEIVED", f"A sealed letter has arrived from {me.name}.", "message", msg.id)
    if recipient.is_npc and allow_npc_reply:
        reply = npc_letter_reply(db, recipient, me, tone)
        send_message_for(db, recipient, me.id, f"Re: {subject}"[:120], reply, "warm" if "friend" in reply else "proud",
                         allow_npc_reply=False)
    return msg


def npc_letter_reply(db: Session, npc: Kingdom, writer: Kingdom, tone: str) -> str:
    s = standing_service.score(db, npc.world_id, npc.id, writer.id)
    style = npc_brain.personality(npc)["style"]
    opener = {
        "merchant": "The counting-houses of Aurelia have read your letter.",
        "warlord": "Your letter reached Cinderhold.",
        "steward": "The wind through Thornwood carried your words to us.",
        "broker": "Valoria's harbour-masters delivered your letter with care.",
    }[style]
    if tone == "cold" or s < 0:
        body = f"{writer.name} would do well to remember who it addresses. We do not forget a slight."
    elif s >= 40:
        body = f"{writer.name} has been a friend to us, and friends are remembered when the ledgers are closed."
    else:
        body = f"We will watch what {writer.name} does, not only what it writes."
    return f"{opener} {body}\n\n— {npc.ruler_name}"


def letters(db: Session, player: Player, kingdom_id: str, box: str) -> list[Message]:
    me = require_owned_kingdom(db, player, kingdom_id)
    col = Message.recipient_kingdom_id if box == "inbox" else Message.sender_kingdom_id
    return list(db.execute(select(Message).where(col == me.id).order_by(Message.created_at.desc()).limit(100)).scalars())


def mark_read(db: Session, player: Player, message_id: str) -> Message:
    msg = db.get(Message, message_id)
    if msg is None:
        raise not_found("Letter")
    require_owned_kingdom(db, player, msg.recipient_kingdom_id)
    msg.read = True
    return msg


# =============================== STANDING GAUGE VIEW =========================================
def relations_view(db: Session, player: Player, kingdom_id: str) -> list[dict]:
    me = require_owned_kingdom(db, player, kingdom_id)
    world = db.get(World, me.world_id)
    out = []
    for other in queries.world_kingdoms(db, me.world_id):
        if other.id == me.id:
            continue
        rel = standing_service.get_relation(db, world.id, me.id, other.id)
        war = queries.active_war(db, me.id, other.id)
        alliance = queries.active_alliance(db, me.id, other.id)
        pending = queries.pending_alliance(db, me.id, other.id)
        s, b = rel.score, band(rel.score)
        limit = credit_limit(db, me, other)

        def gate(ok: bool, reason: str) -> dict:
            return {"allowed": ok, "reason": None if ok else reason}

        actions = {
            "trade": gate(not war, "Not while at war"),
            "gift": gate(True, ""),
            "loan": gate(not war and b != "HOSTILE", "Requires better than Hostile standing" if not war else "Not while at war"),
            "alliance": gate(not war and not alliance and not pending and s >= ALLIANCE_MIN_STANDING,
                             "Not while at war" if war else "Already allied" if alliance else
                             "A proposal is already pending" if pending else
                             f"Requires Friendly ({ALLIANCE_MIN_STANDING})"),
            "declare_war": gate(not war and world.turn > world.beginner_protection_turns,
                                "Already at war" if war else f"Beginner protection until turn {world.beginner_protection_turns + 1}"),
            "peace": gate(bool(war), "Not at war"),
            "passage": gate(not war and s >= PASSAGE_MIN_STANDING and not _active_passage(db, me.id, other.id),
                            "Not while at war" if war else "Your roads are already open to them"
                            if _active_passage(db, me.id, other.id) else "Requires Peaceful standing"),
        }
        if alliance and actions["declare_war"]["allowed"]:
            actions["declare_war"]["warning"] = "This would break your alliance: a Betrayal"
        out.append({
            "kingdom_id": other.id, "name": other.name, "title": other.title, "ruler_name": other.ruler_name,
            "is_npc": other.is_npc, "emblem_key": other.emblem_key, "color": other.color,
            "standing": s, "band": b, "trend": rel.last_delta,
            "recent_reasons": standing_service.recent_reasons(db, world.id, me.id, other.id),
            "alliance": serialize_alliance(alliance) if alliance else None,
            "pending_alliance": serialize_alliance(pending) if pending else None,
            "war_id": war.id if war else None, "credit_limit_from_them": limit, "actions": actions,
            "passage_granted": _serialize_opt(_active_passage(db, me.id, other.id)),
            "passage_received": _serialize_opt(_active_passage(db, other.id, me.id)),
        })
    return out


def public_treaty_web(db: Session, world_id: str) -> dict:
    """The political web (ribbons on the map table): alliances and wars are public knowledge."""
    from app.models import War

    alliances = db.execute(select(Alliance).where(Alliance.world_id == world_id, Alliance.status == "ACTIVE")).scalars()
    wars = db.execute(select(War).where(War.world_id == world_id, War.status.in_(("ACTIVE", "PEACE_PROPOSED")))).scalars()
    passages = db.execute(select(Passage).where(Passage.world_id == world_id, Passage.status == "ACTIVE")).scalars()
    return {"alliances": [{"id": a.id, "a": a.kingdom_a, "b": a.kingdom_b, "expires_turn": a.expires_turn} for a in alliances],
            "wars": [{"id": w.id, "attacker": w.attacker_id, "defender": w.defender_id, "betrayal": w.betrayal} for w in wars],
            "passages": [{"id": p.id, "grantor": p.grantor_id, "grantee": p.grantee_id} for p in passages]}



# =============================== MILITARY PASSAGE ============================================
def _active_passage(db: Session, grantor_id: str, grantee_id: str) -> Passage | None:
    return db.execute(select(Passage).where(Passage.grantor_id == grantor_id, Passage.grantee_id == grantee_id,
                                            Passage.status == "ACTIVE")).scalars().first()


def _serialize_opt(p: Passage | None) -> dict | None:
    return serialize_passage(p) if p else None


def serialize_passage(p: Passage) -> dict:
    return {"id": p.id, "grantor_id": p.grantor_id, "grantee_id": p.grantee_id, "status": p.status,
            "created_turn": p.created_turn, "closed_turn": p.closed_turn}


def grant_passage(db: Session, player: Player, kingdom_id: str, target_id: str) -> Passage:
    """Open your roads to another realm: their merchants and armies may cross; both earn road tolls."""
    me = require_owned_kingdom(db, player, kingdom_id)
    target = get_kingdom(db, target_id)
    require_same_world(me, target)
    if me.id == target.id:
        raise GameError("You cannot grant passage to yourself")
    world = db.get(World, me.world_id)
    if queries.active_war(db, me.id, target.id):
        raise forbidden("Not while at war")
    if standing_service.score(db, world.id, me.id, target.id) < PASSAGE_MIN_STANDING:
        raise forbidden("Requires Peaceful standing or better")
    if _active_passage(db, me.id, target.id):
        raise conflict(f"Your roads are already open to {target.name}")
    p = Passage(world_id=world.id, grantor_id=me.id, grantee_id=target.id, created_turn=world.turn)
    db.add(p)
    db.flush()
    standing_service.change(db, world, me, target, PASSAGE_STANDING_ON_GRANT, f"{me.name} opened its roads to us", kind="passage")
    story_service.record(db, world, "PASSAGE_GRANTED", f"The Roads of {me.name} Open",
                         f"{me.name} grants {target.name} free passage. Caravans roll across the border and the toll-houses fill.",
                         actors=[me.name, target.name], consequences=["TRADE_ROUTES_OPENED"])
    notify(db, world, target.id, "PASSAGE_GRANTED", f"{me.name} granted you military passage (+{PASSAGE_GOLD_PER_TURN} gold per turn in tolls).")
    emit(db, {"type": "treaty_changed", "world_id": world.id})
    return p


def close_passage(db: Session, player: Player, passage_id: str, kingdom_id: str) -> Passage:
    me = require_owned_kingdom(db, player, kingdom_id)
    p = db.get(Passage, passage_id)
    if p is None or p.status != "ACTIVE":
        raise not_found("Open passage")
    if p.grantor_id != me.id:
        raise forbidden("Only the realm that granted passage can close its roads")
    world = db.get(World, me.world_id)
    target = get_kingdom(db, p.grantee_id)
    p.status, p.closed_turn = "CLOSED", world.turn
    standing_service.change(db, world, me, target, PASSAGE_STANDING_ON_CLOSE, f"{me.name} closed its roads to us", kind="passage")
    story_service.record(db, world, "PASSAGE_CLOSED", f"{me.name} Closes Its Roads",
                         f"The border gates of {me.name} swing shut to {target.name}. Merchants turn back; tempers rise.",
                         actors=[me.name, target.name], consequences=["TRADE_ROUTES_CLOSED"])
    notify(db, world, target.id, "PASSAGE_CLOSED", f"{me.name} terminated your military passage.")
    emit(db, {"type": "treaty_changed", "world_id": world.id})
    return p


def close_passages_between(db: Session, world: World, a: str, b: str) -> None:
    """War closes the roads both ways, without the diplomatic penalty (the war already carries one)."""
    for p in db.execute(select(Passage).where(Passage.status == "ACTIVE", Passage.world_id == world.id,
                                              or_(and_(Passage.grantor_id == a, Passage.grantee_id == b),
                                                  and_(Passage.grantor_id == b, Passage.grantee_id == a)))).scalars():
        p.status, p.closed_turn = "CLOSED", world.turn
