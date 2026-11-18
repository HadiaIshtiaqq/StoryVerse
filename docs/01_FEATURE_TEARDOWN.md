# STORYVERSE: Rise of Kingdoms — Feature Teardown & Adaptation Plan

> Companion to the official spec (*Universe King.pdf*). Where this doc and the spec disagree, **the spec wins**.
> Every feature in Part B is tagged **[MVP]**, **[Stretch]** or **[Post]** against spec §10 — see Part D.

How we studied the reference games: by watching how they play (UI, loops, player-facing rules), not by decompiling them.
Rule: we borrow **mechanics and interaction patterns**, never names, art, UI skins, text or code.
Every feature below has been redesigned for a **4-player, hands-first VR kingdom game**.

Stack reference: Unity XR + Meta XR SDK (client) → Photon Fusion (presence/sync) → FastAPI gateway →
Kingdom / Economy / Diplomacy / Military / Story engines → PostgreSQL (+ Transaction History, World Chronicle).

---

## Part A — What each reference does well (observed patterns)

### A1. Grand-strategy diplomacy screen (screenshot 1 & 2)
| Observed pattern | Why it works |
|---|---|
| **Itemised acceptance reasons** (e.g. rank difference +15, trust +14, opinion +2, culture −5, distance −10) | Player sees *why* the AI says yes/no → decisions feel fair and learnable |
| **Threshold rule** ("need at least 1 more positive than negative") | Simple, transparent pass/fail |
| **Filters** (diplomatic range, age range) + sortable target list | Keeps huge option spaces manageable |
| **Ruler stat triad** (3 numbers: admin / diplomacy / military style) | Characters matter mechanically |
| **Top resource bar with per-tick deltas** (+1.58, +0.20…) | Constant feedback on economy direction |
| **Ongoing government actions with % progress** (stabilising, assimilating, increasing control) | Long-running goals that persist across sessions |
| **Annexation progress meter** (88/95.99) | Peaceful expansion as a visible race |
| **Mission trees** (infrastructure / politics / expansion) | Guided goals for new players |
| **Eras** ("Age of …") | World-wide pacing and unlocks |
| **World event feed** (alliances broken, births, techs researched) | The world feels alive even when you aren't acting |

### A2. Living settlement art (screenshots 3 & 4)
Organic, unplanned growth: castle on high ground, town clustered on the river, a bridge as a chokepoint, docks, farmland ring, pasture, smoke from homes, riders on the road, a watchtower at the forest edge.
**Lesson:** settlements should *grow themselves* around placed anchors (keep, church, market, dock), not be grid-stamped.

### A3. Lord creation screen (screenshot 5)
Name + portrait pick + **heraldry editor** (shield divisions, background patterns, charges/symbols, primary/secondary colours, instance count, scale, save/load presets).
**Lesson:** identity creation up front = attachment. Heraldry then appears everywhere (banners, seals, armies, map).
*(The sports-team logo in that screenshot is someone's trademark; our presets must be original charges.)*

### A4. Character letter event (screenshot 6)
Ruler-to-ruler letter, portrait, opinion number (+58), wax seal, 3 choices of different tone (accept / vain / decline).
**Lesson:** diplomacy delivered as **personal correspondence** with personality-flavoured choices.

### A5. VR references
| Reference | Core pattern to study | Adapted as |
|---|---|---|
| VR medieval settlement builder (Meta Store, single-player) | Grab-and-place buildings, villager assignment, defend the walls | Hand placement + villager "pinch-assign" |
| VR village builder with **multi-scale view** | Aerial ↔ table ↔ street-level scale shifts | **Three-Scale View** (below) |
| Hands-first mixed-reality tabletop strategy | Gameplay that *needs* hands (not a controller pretending) | Gesture vocabulary where each gesture is a verb |
| Co-op VR tabletop dungeon game | Shared table, avatars around it, pass/point/ping, turn handoffs | **The Round Table** shared space |

### A6. Mobile grand-strategy negotiation screen (screenshot 7)
| Observed pattern | Why it works | Weakness we fix |
|---|---|---|
| **Relation bar −100…+100** with coloured bands (hostile / neutral / peaceful / friendly) and a marker at the current value (32 = "Peaceful") | One number tells you where you stand | No explanation of *why* it's 32 |
| **Treaty icons placed on the bar** (war, peace, passage, alliance) | Shows which treaties unlock at which relation level | Locked actions don't say what's needed |
| **Attitude trend arrow** | Shows whether relations are improving or getting worse | — |
| **"Current agreement"** slots (peace + military passage) | Active treaties visible at a glance | — |
| **3 gift tiers** that scale with treasury (≈1×, 2×, 3×), with gold + a second resource | Simple, readable bribery | Preview shows "Diplomacy +0", so you can't see what you're buying |
| **Side ledgers per ruler**: at war / at peace / passage / allied, listed by emblem | The whole political web on one screen | Busy for VR; needs to be spatial |
| **4 big verbs**: Ally · Terminate Passage · Declare War · Negotiate | Few, high-impact choices | — |

---

## Part B — Adapted features for Universe King

### B1. The Betrothal Scales (Royal Marriage → VR)
Your court sits at a table with a **physical balance scale**. Each acceptance reason becomes a **weighted token** that drops onto the "Yes" or "No" pan. You can see exactly why it tips.

- Pick candidates by grabbing **portrait cards** from your Family Tree board; you can wave filters away ("in range", "of age").
- Tokens: Rank gap, Trust, Opinion, Culture, Faith, Border distance, Existing alliance, Rivalry, Dowry offered.
- **Hand interaction:** you can add a dowry by putting gold coins on the pan. Gold is the only token a player can move live.
- Rule: accepted when `sum(positive) − |sum(negative)| ≥ threshold` (the threshold depends on the AI ruler's personality).
- Effects: dynastic claim, opinion boost, alliance chance, heir inheritance chain, and a World Chronicle entry.

**Diplomacy Engine** — `POST /diplomacy/marriage/evaluate`
```python
def evaluate_marriage(proposer, target, a, b, dowry=0):
    reasons = []
    if proposer.rank != target.rank:      reasons.append(("Different Rank", 15 if proposer.rank > target.rank else -10))
    reasons.append(("Trust",   trust(target, proposer) * 0.5))
    reasons.append(("Opinion", opinion(target.ruler, proposer.ruler) * 0.1))
    if a.culture != b.culture:            reasons.append(("Different Culture", -5))
    if a.faith != b.faith:                reasons.append(("Different Faith", -15))
    reasons.append(("Border Distance",    -min(20, border_distance(proposer, target) / 50)))
    if dowry:                             reasons.append(("Dowry", min(25, dowry / 10)))
    pos = sum(v for _, v in reasons if v > 0); neg = sum(v for _, v in reasons if v < 0)
    threshold = target.ruler.personality.marriage_threshold   # e.g. 1 for open, 10 for proud
    return {"accepted": pos + neg >= threshold, "positive": pos, "negative": neg, "reasons": reasons}
```
The response returns the full `reasons` list, and the client spawns one token per reason.

### B2. Sealed Letters (Correspondence events → VR)
- Letters arrive by a **raven/courier** that lands on your desk. Unroll the scroll with two hands.
- To answer: pick a tone quill (Warm / Proud / Cold) and **press your signet ring** into wax to send. The ring is your heraldry from B3.
- Letter chains build **Opinion** and **Trust**. These are separate numbers: Opinion is personal, Trust is between states.
- Players can write to players too. The Story Engine supplies template text, and the player can add a short dictated line (speech-to-text, run through a moderation filter).
- **Story Engine** — `POST /story/letters`; every sealed letter → Chronicle entry ("Queen Isolde of Sylvara wrote to Drakoria…").

### B3. Heraldry Forge (Lord creation → VR)
- At a workbench you **paint a shield**: pinch to pick a division, dip a brush in a colour pot, stamp charges with a carved stamp, and spread instances with two hands.
- Data: `{division, field_pattern, tinctures[2], charge_id, charge_count, charge_scale}` stored as JSON on the kingdom.
- The heraldry is rendered procedurally (shader + charge atlas), so the same JSON drives banners, wax seals, shields, map markers and sails.
- Ships with **original** charges: sunburst, wyvern, oak-crown, star-anchor, twin keys, tower, stag, comet.

### B4. Three-Scale View (multi-scale VR builder)
| Scale | Gesture to enter | Used for |
|---|---|---|
| **Realm Map** (table-sized world) | Pull both hands apart above the table | Diplomacy, armies, trade routes, annexation |
| **Holdfast** (settlement as a diorama) | Pinch a city and pull it toward you | Building placement, production chains, villagers |
| **Street** (life-size) | Look at a spot, then palm-down "drop in" | Festivals, court audiences, defending walls, roleplay |

Photon Fusion syncs the authoritative state at the Realm and Holdfast scales. The Street scale is local cosmetic simulation, which keeps it cheap.

### B5. Organic Settlement Growth
- Players place **anchors** (Keep, Market, Chapel, Dock, Mill, Barracks). Houses, fields and paths grow procedurally around them, guided by influence fields (water, slope, roads, safety from the keep).
- Rivers + bridges become chokepoints for military pathing, and docks unlock river trade.
- Visible life: chimney smoke = employed homes, livestock count = food surplus, and empty market stalls = shortage. **The economy can be read from the scene without opening a UI.**

### B6. Production Chains (Economy Engine)
```
Field → Grain → Mill → Flour → Bakery → Bread ─┐
Pasture → Wool → Weaver → Cloth ──────────────├→ Market (prices per player market)
Forest → Logs → Sawmill → Planks → Builder ───┘
Mine → Ore → Smelter → Iron → Smithy → Tools / Weapons → Military Engine
```
- Villagers are assigned by **pinching a villager and dropping them on a building**.
- Economy ticks run on the server and push to clients over Fusion. The resource bar is a **floating ledger on your wrist** that shows deltas (+1.58/tick).
- Every trade and tax is written to **Transaction History** (an append-only ledger table).

### B7. Royal Decrees (ongoing government actions)
Long-running actions with % progress: *Stabilise Realm, Assimilate Province, Tighten Control, Annex Vassal, Build Road Network*.
- VR: decree scrolls hang on a **Decree Board**. To start one, stamp it with your seal. Progress shows as candle wax burning down.
- The progress is stored in the database, so it keeps advancing while players are offline (with a rate cap for fairness).

### B8. Peaceful Annexation Race
Vassals/minor realms have an **Allegiance meter**. Several players can compete for the same minor realm through marriages, letters, gifts and trade. The first to reach the threshold annexes it, and the others get a "Snubbed" opinion penalty plus a casus belli option.

### B9. Quest Boards (Mission trees)
There are 3 trees per kingdom (Infrastructure / Statecraft / Expansion), and each kingdom also has its **own unique tree** (see Characters doc). The boards are physical: you pull a quest card off and pin it to your active slots (max 3).

### B10. Eras
The world moves through *Age of Founding → Age of Banners → Age of Charters → Age of Stars*. Era changes are server-wide events. They unlock new building tiers and decrees, and they trigger an Era cinematic in which all 4 players are pulled into the Street scale together.

### B11. The Round Table (shared co-op/competitive space)
- A neutral **hall** with a large round map-table. All 4 player avatars stand around it. They can point (ray from index finger), ping, hand objects to one another, and shake hands to seal treaties. A handshake is a **two-player gesture** that Fusion validates.
- Treaties are physical parchments that both players sign. The server stores them, and the Chronicle records them.
- Turn/tick handoff: **real-time with pause votes**. Every player has an hourglass, and when 3 of 4 flip theirs, the game pauses.

### B12. Hands-essential gesture vocabulary
| Gesture | Verb |
|---|---|
| Pinch + drag | Place / assign |
| Two-hand pull apart / together | Change scale |
| Palm up, open | Open wrist ledger |
| Fist on table | Declare / confirm (army orders) |
| Stamp (ring hand down) | Seal decree or letter |
| Handshake (two players) | Sign treaty |
| Point + hold | Ping for other players |
Controllers are supported as a fallback, but every gesture is designed for hands first.

### B13. World Feed → Herald's Chronicle
The bottom-right event feed becomes a **herald NPC** and a **living tapestry** on the hall wall. Every Chronicle entry adds a stitched panel to the tapestry, and players can walk along it to re-read their history. Data comes from the `world_chronicle` table.

### B14. Standing Gauge, Gifts & Treaty Seals (negotiation screen → VR) **[MVP]**
This makes the spec's alliance, trade and loan systems easy to read. Every kingdom pair has a **Standing** score (−100…+100). The server computes it only from **real, validated actions**, so it also feeds the Living History Engine.

**Bands and what they unlock**
| Score | Band | Unlocks / consequences |
|---|---|---|
| −100…−50 | Hostile | War declaration is cheap; trade offers auto-flagged |
| −49…−1 | Cold | Trade allowed; loans capped at 50% of credit limit |
| 0…39 | Peaceful | Trade, loans, **military passage** (≥ 20) |
| 40…69 | Friendly | **Alliance proposals** allowed; full credit limit |
| 70…100 | Trusted | Alliance trade bonus; mutual-defence option |

Declaring war on a Friendly or Trusted kingdom, or breaking an alliance, is a **Betrayal**. The attacker loses prestige, every other kingdom's standing toward it drops by −15, and the Story Engine writes a "Betrayal" chronicle event (matching the example in spec §2.4 H).

**What moves the score** (deterministic, applied per world turn with caps):
| Action | Δ Standing |
|---|---|
| Completed trade | +3 (max +9/turn per pair) |
| Loan repaid on time | +8 |
| Loan defaulted | −25 |
| Gift | see formula below; preview shown **before** confirm |
| Alliance formed / broken | +10 / −50 |
| War declared | −60 |
| No interaction | decays 1 point/turn toward 0 |

```python
BANDS = [(70, "TRUSTED"), (40, "FRIENDLY"), (0, "PEACEFUL"), (-49, "COLD"), (-100, "HOSTILE")]

def band(score: int) -> str:
    return next(name for floor, name in BANDS if score >= floor)

def gift_gain(gift_gold: int, receiver_gold: int) -> int:
    # diminishing returns: a gift matters relative to the receiver's wealth
    return round(20 * gift_gold / (gift_gold + 0.2 * max(receiver_gold, 1)))

def gift_tiers(giver_gold: int) -> list[int]:
    return [round(giver_gold * p) for p in (0.05, 0.10, 0.15)]
```

**VR presentation (Diplomatic Desk, spec §4.7)**
- **Standing Gauge:** a brass dial with a needle on the desk, coloured band zones, and a small arrow showing the trend. Pinch the needle to see the last 5 reasons ("+8 loan repaid, turn 12").
- **Gifts:** three coin chests of increasing size sit on an envoy's tray. Each chest floats its exact effect ("+6 Standing"). Push a chest across the desk to send it, then hold your palm on the seal for 1 second to confirm. This dwell follows the spec's safeguard for actions that are hard to undo.
- **Treaty Seals:** four wax seals: *Ally · Grant/Revoke Passage · Declare War · Negotiate (trade/loan)*. A locked seal is cracked and grey, with its reason engraved on it ("Requires Friendly, 40").
- **Political web:** the side ledgers of the 2D screen become **ribbons on the world map table**: blue for allied, tan for peace, dashed for passage, red for war. It's readable at a glance from any seat at the Round Table.

**API and data** (extends spec §3.5 and §3.4)
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/relations/{kingdom_id}` | Standing to every other kingdom, with band, trend, unlocked actions and locked reasons |
| POST | `/gifts` | Send a gift (idempotency key; atomic transfer + ledger row + standing event) |
| POST | `/passage` / `/passage/{id}/revoke` | Military passage treaty |

```sql
CREATE TABLE relations (
  kingdom_a UUID REFERENCES kingdoms(kingdom_id),
  kingdom_b UUID REFERENCES kingdoms(kingdom_id),
  score INT NOT NULL DEFAULT 0 CHECK (score BETWEEN -100 AND 100),
  updated_turn INT NOT NULL,
  PRIMARY KEY (kingdom_a, kingdom_b),
  CHECK (kingdom_a < kingdom_b)            -- one symmetric row per pair (MVP)
);
CREATE TABLE relation_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kingdom_a UUID, kingdom_b UUID, delta INT, reason TEXT,
  source_transaction UUID REFERENCES transactions(transaction_id),
  turn INT, created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## Part C — Mapping to your architecture

| Feature | Client (Unity XR) | Network (Fusion) | Backend engine | Tables |
|---|---|---|---|---|
| Betrothal Scales | Scale prefab, physics tokens | RPC propose / result | Diplomacy | `marriages`, `characters`, `opinions` |
| Sealed Letters | Scroll, quill, wax seal | RPC send | Story + Diplomacy | `letters`, `opinions`, `world_chronicle` |
| Heraldry Forge | Paint/stamp tools, shader | Networked property on kingdom | Kingdom Manager | `kingdoms.heraldry` JSONB |
| Three-Scale View | Scale rig, LOD | Area-of-interest per scale | — | — |
| Settlement Growth | Procedural placer | Anchor placement is authoritative | Kingdom Manager | `buildings`, `provinces` |
| Production Chains | Villager AI, wrist ledger | Tick snapshots | Economy | `stockpiles`, `transactions` |
| Decrees | Decree board | Networked progress | Kingdom Manager | `decrees` |
| Annexation | Allegiance banners | — | Diplomacy | `allegiance` |
| Military | Army miniatures, fist-to-order | State authority | Military | `armies`, `battles` |
| Chronicle | Tapestry, herald | Event broadcast | Story | `world_chronicle` |

**Authority rule:** FastAPI + Postgres are the source of truth for persistent state (economy, diplomacy, characters). Photon Fusion (Shared or Host mode) carries presence, hands, held objects and fast-changing visuals. A client never computes outcomes. It sends intents and renders results.

---

## Part D — Scope against the spec (§10 Hackathon MVP)

The spec's four pillars are **hands-first construction, a 4-player shared world, real economic transactions and the Living History Engine**. Each borrowed feature is kept only where it strengthens one of these pillars.

| Feature | Tag | How it serves the spec / what's cut for MVP |
|---|---|---|
| B14 Standing Gauge, Gifts, Treaty Seals | **MVP** | Makes alliances, loans and war legible; small backend cost |
| B2 Sealed Letters | **MVP-lite** | The 3D letter object *is* FR-08 private messaging (spec §4.7). Signet-ring stamping → Stretch |
| B11 Round Table hall | **MVP-lite** | The WorldLobby scene + diplomatic desk. Handshake treaty gesture → Stretch |
| B4 Three-Scale View | **MVP** | Already spec §4.5. MVP = World + Kingdom scale; Village/Street scale → Stretch |
| B12 Gesture vocabulary | **MVP** | Merge with spec §4.4; spec gestures take priority, stamp/fist are additions |
| B13 Chronicle tapestry | **MVP-lite** | MVP = chronicle wall panel; stitched tapestry art → Stretch |
| B3 Heraldry Forge | Stretch | MVP uses 4 preset emblems (spec kingdom `emblem` field) |
| B7 Decrees, B9 Quest boards | Stretch | Good for onboarding after the core loop works |
| B6 Production chains | Post | Spec §2.4 C uses direct production `R + P − C`; chains come later |
| B5 Organic settlement growth | Post | Spec §2.4 B says curated prefabs for MVP |
| B1 Betrothal Scales | Post | Needs a character/dynasty system that isn't in the spec |
| B8 Annexation race | Post | Needs NPC kingdoms (FR-17). NPC *rulers* are now Critical (see 03_JUDGING_ALIGNMENT §2.1), but minor realms stay Post |
| MR tabletop, anchors, gaze | **MVP** | Added for judging criteria. See 03_JUDGING_ALIGNMENT §1 |
| B10 Eras | Post | World-pacing layer for the persistent version |

**Build order, mapped to spec §9 phases**
1. **Phase 1:** Round Table lobby, 4 avatars, hand presence (Fusion), backend + DB
2. **Phase 2:** World/Kingdom scale, prefab placement with pinch, resource ledger, production per turn
3. **Phase 3:** Trades, loans, alliances, **Standing Gauge + gifts (B14)**, letters (B2-lite), transaction history
4. **Phase 4:** Prestige/leaderboard, betrayal and other chronicle rules, battle resolution, chronicle wall
5. **Phase 5:** Polish, then Stretch items in this order: Heraldry → Village scale → Decrees → signet/handshake rituals

**Demo hook (spec §10.1, 3:30–4:20):** the Standing needle swings from Friendly into Hostile live when Drakoria betrays Valoria, the seals crack, and the herald reads out the new chronicle entry. That single moment shows all four pillars together.
