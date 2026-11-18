# STORYVERSE: Rise of Kingdoms

*Build your kingdom. Forge alliances. Betray enemies. Rewrite history.*

A hands-first, mixed-reality multiplayer kingdom strategy game for Meta Quest, built for the
Meta VR Start Developer Competition 2026 (Gaming track). Four rulers share one persistent world.
Every trade, loan, alliance and betrayal is validated by the server and written into a living World Chronicle.

```
Universe King/
├── backend/            FastAPI + SQLAlchemy game server (authoritative economy, diplomacy, war, story)
│   ├── app/
│   │   ├── api/        HTTP routes + WebSocket
│   │   ├── services/   Kingdom, Economy, Diplomacy, Military, Story, NPC, Turn, Prestige engines
│   │   ├── game/       rules.py: every balancing constant in one file
│   │   └── static/sim/ Desktop simulator (browser client)
│   └── tests/          43 tests: spec TC-01…TC-20, security, idempotency, NPCs, WebSockets, turn ready-check, input hardening
├── unity/Assets/Scripts/   Quest client scripts (Meta XR SDK, MRUK, Fusion 2)
├── docs/               Design: feature teardown, kingdoms & characters, judging alignment
└── docker-compose.yml  PostgreSQL + API
```

## Run the backend (2 minutes)

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt      # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --reload --host 0.0.0.0
```

- **Simulator:** http://localhost:8000/sim/. Register, create a *Solo Court* world, and play against three NPC rulers.
  For four humans, open four browser tabs (each tab is a separate ruler) and pick a different kingdom in each.
- **API docs:** http://localhost:8000/docs
- **Tests:** `.venv/Scripts/python -m pytest`

With no `DATABASE_URL` set, the backend uses a local SQLite file (`storyverse.db`).
For PostgreSQL, start Docker Desktop and run:

```bash
docker compose up --build        # API on :8000, Postgres on the compose network
```

> **Locked-down Windows machines:** if Application Control blocks SQLAlchemy's compiled speedups
> (`DLL load failed ... _collections_cy`), reinstall it as pure Python:
> `set DISABLE_SQLALCHEMY_CEXT=1 && .venv\Scripts\python -m pip install --force-reinstall --no-binary sqlalchemy sqlalchemy`

## Look and characters
An original "Royal Court" art direction: castle stone, candlelight, gold filigree and parchment. Every piece is drawn by
[tools/art/make_art.py](tools/art/make_art.py): portraits and gold medallions of the four rulers (King Aldric Solmane,
Queen Varka Embermane, Queen Isolde Fernhallow, High King Cassian Valor), their heraldic crests, and 26 resource, action
and building icons. [tools/art/render_png.mjs](tools/art/render_png.mjs) turns them into PNGs for Unity.
The browser simulator and the VR scene share them. Screenshots are in [docs/screenshots/](docs/screenshots/).

- **Simulator:** resource ribbon, ruler medallion, building cards with a detail popup, crests on the map, and a
  **Negotiation** screen: both rulers face to face, an attitude banner over the −100…100 standing scale, gift chests
  that show their exact effect, and pennant actions.
- **VR:** crest banners on every castle, the target ruler's medallion on the Diplomatic Desk, the sender's portrait on the
  Envoy's Scroll, the leading ruler above the Hall of Crowns, and icons on the building cards.

### Court features (from the reference pictures, all original)
| Feature | Server | Simulator | VR |
|---|---|---|---|
| **Royal Council**: 12 advisers from the design doc read the live realm and give counsel | `GET /kingdoms/{id}/council` | Council tab, plus the top advice on Courts | Council board (urgent counsel is spoken by the Herald) |
| **Royal Decrees**: objectives with progress and rewards, claimed once, written to the ledger and chronicle | `GET /kingdoms/{id}/decrees`, `POST /decrees/{key}/claim` | Panel over the map | Decree scroll with a claim seal |
| **Military passage**: open your roads (Peaceful+), +15 gold/turn tolls for both, war closes them | `POST /passages`, `POST /passages/{id}/close` | Grant/Terminate pennant, roads on the map | Passage seal, dotted gold roads |
| **Gift chests of gold + iron**, preview equals result | `/gifts/tiers` returns `iron` | Two-resource chests | Chest labels show both |
| **Settlement buildings**: Houses (+3 people/turn), Tavern, Mansions (welfare prestige), Blacksmith, Granary (halves famine) | catalog with `category` + `lore` | Category bar, lore, Available / Your holdings with upgrade | Modelled with chimney smoke |
| **Negotiation screen**: treaty thresholds on the scale, both rulers' diplomatic web, rank and crown badges | from relations + treaty web | ✓ | Desk seals with lock reasons |
| **Council chamber**: stained-glass windows, candlelight, stone walls | | Windows and candle glow | Flickering candles on the table; stone chamber with rose window in the PC preview (passthrough room on Quest) |
| **Living realm**: island, river, mountains, forests, sheep, walled castles | | Map hover info panel | Diorama on the table |

## What the server does

| Pillar (spec §13) | Implementation |
|---|---|
| Real economic transactions | Trades, loans (`P × (1 + r/100)`, auto-installments, default after grace), gifts. Row-locked atomic transfers, a ledger line for every movement, **Idempotency-Key** on every value-moving POST |
| Four-player shared world | 4 seats per world; empty seats are **NPC rulers** with personalities and *itemised reasons* for every decision |
| Living History Engine | Deterministic chronicle templates: *"THE BETRAYAL OF VALORIA — Drakoria broke its alliance with Valoria and launched an attack on its eastern territory. Trade relations have deteriorated. Aurelia is now reconsidering its military commitments."* |
| Diplomacy you can read | **Standing** −100…100 with bands (Hostile…Trusted) that unlock alliances, credit and passage. Every change has a stored reason. Betrayal crashes it world-wide |
| Persistence | Turn engine: production → upkeep → loans → trade expiry → alliance expiry → standing decay → NPC moves → prestige & crowns. *"While you were away"* endpoint |
| Fair turns | Solo worlds advance on demand. In a shared world, **End Turn** is a ready vote: the turn advances when every human ruler is ready, so nobody can fast-forward another player's loan deadlines. The world's creator can `force=true` past an AFK player |

The **authority model** follows spec §3.3: clients send intents and the server decides results. Photon Fusion only carries
presence (heads, hands, pointing). It never touches gold.

### API summary
`/auth/register|login|me` · `/worlds` (create/list), `/worlds/join`, `/worlds/{id}` `/map` `/turn` `/chronicle` ·
`/kingdoms/{id}` `/resources` `/buildings` `/ledger` `/notifications` `/since` `/dashboard` ·
`/buildings` `/buildings/catalog` `/buildings/{id}/upgrade` · `/trades` (+ accept/reject/cancel) ·
`/loans` (+ accept/reject/repay) · `/alliances` (+ respond/terminate) · `/messages` (+ read) ·
`/relations/{kingdom_id}` · `/gifts/tiers` `/gifts` · `/soldiers/recruit` · `/wars` (+ peace) · `/battles` ·
`/leaderboard/{world_id}` · WebSocket `/ws/worlds/{world_id}?token=…`

## Unity client
See [unity/README.md](unity/README.md) for package setup, scene wiring and Quest build settings.

### Run the test suite against PostgreSQL
```bash
docker compose exec db psql -U storyverse -c "CREATE DATABASE storyverse_test"
docker compose run --rm -v "$(pwd)/backend/tests:/srv/tests" --user root \
  -e TEST_DATABASE_URL=postgresql+psycopg://storyverse:storyverse@db:5432/storyverse_test \
  api sh -c "pip install -q httpx pytest && python -m pytest tests"
```
`TEST_DATABASE_URL` is wiped by the tests. Never point it at the real game database.

## Status
| Part | Verified | How |
|---|---|---|
| Backend on SQLite | ✅ 45/45 tests | `pytest` |
| Backend on **PostgreSQL 16 (Docker)** | ✅ 45/45 tests | suite run inside the API container, including the row-locked turn ready-check |
| Security hardening | ✅ | finite and bounded coordinates and rates; bounded login input; constant-time login (no username enumeration); WebSocket limited to the world's rulers; session tokens redacted from access logs |
| Concurrency on PostgreSQL | ✅ | 8 simultaneous accepts of one trade → 1 succeeds; 8 parallel same-key gifts → charged once; 10 parallel gifts draining a treasury → stops at exactly 0 |
| Spec §10.1 demo flow | ✅ | 4 players: build, trade, 2,000 @10% loan, alliance, private letter, betrayal battle, chronicle, crowns |
| Desktop simulator | ✅ | Headless Chrome: register, create world, build by clicking the map, NPC trade with reasons, gift tiers, 3 turns, chronicle, WebSocket live, 0 console errors |
| **Unity client end-to-end (Windows build, headless)** | ✅ `Storyverse.exe -batchmode -nographics -smoketest` | Finds the server by LAN discovery (even with a stale IP in the build), resumes its world, renders map and seats and Hall of Crowns, End Turn advances, an NPC proposal reaches the Envoy's Scroll, accepting it moves gold on the server |
| LAN discovery | ✅ | Server answers UDP 47800 `STORYVERSE?` with its address on the asker's network; headsets re-find a laptop whose Wi-Fi IP changed |
| **Unity project, real editor** | ✅ batch-mode import + compile, exit 0, 0 errors | Unity 6000.0.85f2 with the real Meta XR SDK 209.0.0 (Core, MRUK, Interaction), OpenXR 1.19.0; `Assembly-CSharp.dll` contains all game scripts, 0 warnings from them |
| **Unity client scripts (offline check)** | ✅ compile, 0 errors / 0 warnings | All 29 scripts were built with C# 9 against Unity 6000.0.85f2's real `UnityEngine` DLLs, uGUI + TextMeshPro compiled from the editor's own source, and Newtonsoft 13. Meta XR and MRUK calls were **checked against the real v209 SDK source**, which found and fixed an OpenXR hand-bone bug in `PinchDetector`. Fusion 2 signatures are still unchecked, because the SDK needs a Photon login; the Fusion code sits behind the `STORYVERSE_FUSION` define. A planted typo is caught, so the check works. Still needed: Unity sign-in, the Android module, and testing on the headset |
