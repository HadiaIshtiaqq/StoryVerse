# STORYVERSE — Judging Alignment (Meta VR Start Developer Competition 2026)

Track: **Gaming**. The four criteria are **equally weighted** (25% each).
This doc checks the current spec + feature docs against each criterion. It lists the gaps and the concrete changes that close them.

---

## 0. The three biggest risks (fix these first)

| # | Risk | Why it costs points | Fix |
|---|---|---|---|
| 1 | **The game needs 4 humans; a judge plays alone** | A judge who enters an empty world can't trade, ally or betray anyone. Experience Design collapses | Raise **FR-17 NPC kingdoms from Low → Critical**. Every empty seat is filled by an NPC ruler (§2). Add a **"Judge / Solo Court" world preset** |
| 2 | **Fully virtual scene: no passthrough, MRUK or anchors** | Innovation and Technical criteria explicitly reward spatial depth, passthrough, scene understanding and persistent anchors | Make the **player's real table the Realm Map** (§1). That gives meaningful passthrough, as the criteria ask for |
| 3 | **No gaze interaction** | The criteria name gaze (ISDK v207+) as a defining feature | **Gaze + pinch** targeting across the map, letters and seals (§1.3) |

---

## 1. Innovation & Creativity → "your kingdom lives on your desk"

### 1.1 Mixed-reality tabletop (core change)
- At launch, MRUK reads the room. The **largest detected table or desk** becomes the Realm Map surface: the continent unfolds across your real table like a war map.
- **Walls host content:** the World Chronicle tapestry hangs on the nearest wall. Each kingdom's banner and Standing Gauge hang on a wall *in the direction of that kingdom on the map*.
- **Remote players' avatars sit around your real table** (Fusion presence). It's like the shared-tabletop co-op pattern, but anchored to your room.
- **Kingdom Scale:** pinch-pull a kingdom off the table and it grows to fill the table. **Village Scale** is an optional fully virtual step-in (passthrough off), so immersion is a deliberate choice.
- This is *purposeful* passthrough: with passthrough off, there is no table, no walls and no layout. The room changes the experience, which is what the criteria ask for.

### 1.2 Persistent anchors → repeat usage
- Save a **spatial anchor** for the map's position on the table. When you return, your kingdom is exactly where you left it on your desk.
- Pair this with the persistent world (spec §6.4): **"While you were away" ritual.** On re-entry, ravens land on your table with the letters, trade offers and loan payments that arrived, and the Herald reads out the new chronicle entries. This gives the habit-forming loop the criteria reward.

### 1.3 Hands + gaze vocabulary (merge with spec §4.4)
| Input | Action |
|---|---|
| **Gaze** at a kingdom / letter / seal | Soft highlight + name label (no commitment) |
| **Gaze + pinch** | Select at a distance: target a kingdom across the table, pick a seal, open a letter |
| Direct pinch-drag | Place / move buildings (near-field) |
| Two-hand spread / pinch | Change scale |
| Palm up | Wrist ledger (resources) |
| Palm hold 1s on seal | Confirm actions that can't be undone (war, gift, loan) |

Gaze shortens the most common action, "which kingdom do I mean?", from reach-and-point to a look.

---

## 2. Experience Design → solo-playable, seated, onboarded

### 2.1 NPC rulers (now Critical)
The four rulers in `02_CHARACTERS_AND_KINGDOMS.md` become the NPC brains. Each NPC uses the **itemised-reasons pattern** (feature B1) so the judge always sees *why* it said yes or no:

```
Alliance with Drakoria — Queen Varka REFUSES (needs +1 more than against)
  For:     Standing +14 (Friendly)   · You share a rival (Valoria) +10
  Against: You owe her 2,200 gold −15 · She values strength: your army is weaker −12
```

```python
def npc_decide(npc, proposal, ctx) -> dict:
    reasons = []
    reasons.append(("Standing", ctx.standing(npc, proposal.sender) * 0.5))
    reasons += npc.personality.evaluate(proposal, ctx)      # e.g. Varka: military ratio, Aldric: interest rate
    if ctx.has_overdue_loan(proposal.sender, npc):          reasons.append(("Overdue loan", -20))
    pos = sum(v for _, v in reasons if v > 0); neg = sum(v for _, v in reasons if v < 0)
    return {"accept": pos + neg >= npc.personality.threshold, "reasons": reasons}
```
- NPCs also *act* on each world turn. They make one move each: a trade offer, a loan request, or (for Varka) a war threat. A solo judge gets story beats without waiting.
- **Seats are hot-swappable:** a human joining replaces an NPC seat, and the NPC hands its kingdom over.

### 2.2 Seated by default
- Everything is reachable while seated: the map sits on the table and walls are only for reading. No locomotion is needed for the MVP loop.
- Fallback for rooms with no table: spawn a virtual pedestal table at seated elbow height, in front of the user (§3.3).

### 2.3 Onboarding (first 3 minutes)
1. **0:00:** Passthrough. The Herald's raven lands on your table: "Your Majesty, place your realm." Pinch the scroll and drop it on your table, and the map unfolds. *(Teaches pinch + placement)*
2. **0:30:** "Look at Sylvara." The gaze highlight pulses. Pinch to open her letter: a trade offer, 100 food for 80 iron. *(Teaches gaze + pinch, trade)*
3. **1:15:** Build a Farm: pinch it from the building tray and drop it on your kingdom. *(Teaches near-field build)*
4. **2:00:** Palm up to see the wrist ledger move. *(Teaches resources)*
5. **2:30:** Drakoria asks for a loan. The tutorial ends with your first real decision.

Each step gives one sentence of instruction, then one action, with no text walls. The Village scale and wars unlock afterwards.

### 2.4 Rewarding, habit-forming purpose
- Turn-based world (spec §6.4) with a short **turn timer in active sessions** and **longer turns offline**. Every return has something new waiting.
- Five Crowns (spec §4.8) shown as **five physical crowns on a shelf on your wall**. They fill as you progress, so your goal is always visible.

---

## 3. Technical Implementation → the checklist judges look for

### 3.1 Platform feature map
| Criterion keyword | STORYVERSE implementation | Owner |
|---|---|---|
| Hand tracking | Pinch / grab / palm gestures (ISDK) | P1 |
| **Gaze (ISDK v207+)** | Gaze highlight + gaze-pinch selection | P1 |
| **Passthrough** | Default mode; Village scale fades to full VR | P1 |
| **Scene understanding (MRUK)** | Table → map surface; walls → chronicle and banners; room-free fallback | P1 |
| **Spatial anchors** | Persistent map anchor per player; (Stretch) shared anchors for co-located players | P1 |
| **FoV-aware design** | Notifications and letters appear within ~30° of gaze centre; nothing important at the periphery; wall content is optional to read | P3 |
| Multiplayer | Photon Fusion presence, server-authoritative economy (spec §3.3) | P2 |
| Performance ≥ 60 fps | Target 72; see §3.2 | All |

> Use the exact ISDK/MRUK component names and versions from the Meta docs for the SDK version you install. Lock the SDK version in Phase 1.

### 3.2 Performance budget (Quest 3/3S)
- Map: one combined mesh per kingdom; buildings are GPU-instanced; LOD0 only at Village scale.
- ≤ 150 draw calls on the table view; baked lighting; no realtime shadows in MR.
- Passthrough + MR content: avoid full-screen transparency; UI is opaque parchment.
- Profile weekly on device (OVR Metrics Tool), not in the Editor.

### 3.3 "Holds up in rooms you never tested"
| Room condition | Behaviour |
|---|---|
| No scene data / user skipped Space Setup | Prompt once; if declined → virtual pedestal table + virtual back wall |
| No table detected | Virtual pedestal at seated height |
| Table too small (< 0.6 m) | Map scales down + pinch-to-pan |
| Table cluttered / odd height | Map floats 5 cm above the detected surface; height adjustable by two-hand lift |
| No usable wall in view | Chronicle becomes a free-standing banner behind the map |
| Tracking or anchor lost | Re-anchor to the table; if the table is lost, keep the last pose and show "Re-place your realm" |

Test in at least **5 different rooms** (homes, office, small desk, coffee table, no table) before submission.

---

## 4. Polish & Presentation

- **Art direction:** the spec palette (Midnight / Emerald / Royal Gold / Parchment / Crimson) on **diorama-style low-poly** assets. Miniatures on a real table look intentional and stay performant. One art style only.
- **Sound:** spatialised sounds from the table (quill scratch, coin chest, wax seal crack, raven wings), plus a short musical theme per kingdom. Sound is a quarter of "polish".
- **Video (2–3 min), real capture only.** The criteria say not to lean on AI-generated video. The spec's reference links are AI images: use them as a **moodboard only**, never in the submission.
  1. 0:00 Hook: a real desk, the realm unfolds on it (passthrough).
  2. 0:15 One sentence on the pitch: "Your history is written by real players' decisions."
  3. 0:25 Gaze + pinch trade, hands-only building.
  4. 1:00 The loan, then the **Betrayal beat**: the Standing needle swings, seals crack, the Herald reads the chronicle.
  5. 1:45 Leave and return: the map is still on your desk, and ravens bring what happened.
  6. 2:15 Remote players' avatars around the same table; then the title.
- **Text and images:** Devpost screenshots captured on device. Each one shows a different criterion: MR table, gaze, gestures, chronicle.

---

## 5. Required spec changes (edit *Universe King.pdf*)

| Spec section | Change |
|---|---|
| 1.5 FR-17 NPC kingdoms | **Low → Critical** (solo judging) |
| 1.5 new FR-18 | Mixed-reality table placement via MRUK, with room-free fallback — **Critical** |
| 1.5 new FR-19 | Persistent spatial anchor for the map — **High** |
| 1.5 new FR-20 | Gaze + pinch selection (ISDK v207+) — **High** |
| 1.5 new FR-21 | Guided 3-minute onboarding — **High** |
| 1.6 Performance | Hard floor **60 fps** (judging minimum); target 72 |
| 2.1 Stack | Add **Meta XR Interaction SDK v207+**, **MRUK**, Spatial Anchors |
| 4.4 Gestures | Add gaze rows (§1.3) |
| 4.5 Scales | World scale = **your real table** in passthrough |
| 7.4 XR tests | Add: no-table room, small table, anchor reload, gaze accuracy at 1 m |
| 10.1 Demo | Replace with §4 video plan; record on device |
| 10 MVP table | Add NPC rulers, MR table, anchors, gaze, onboarding. To make room, **cut warfare to a single resolved battle** and move espionage out entirely |

---

## 6. Self-score before submitting (each 1–5)
| Criterion | Question to answer honestly |
|---|---|
| Innovation | Would this be meaningfully worse with passthrough off? |
| Experience | Can a stranger, seated, alone, finish onboarding and make a betrayal-level decision in 10 minutes without help? |
| Technical | 60+ fps on Quest 3S in a busy scene? Works in a room with no table? |
| Polish | Is every shot in the video real gameplay? Does every action make a sound? |
