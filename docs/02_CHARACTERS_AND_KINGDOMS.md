# STORYVERSE — Kingdoms & Characters (original)

Aligned to spec §4.2. Specialisations are **starting bonuses, not permanent classes**.
**MVP use:** each kingdom needs its emblem, ruler name and portrait (on the Diplomatic Desk and the Standing Gauge) and its starting bonus. Heirs, advisors and traits are **Stretch/Post** flavour for the Story Engine.

Every character has the **stat triad**: **Statecraft** (economy), **Envoy** (diplomacy) and **Martial** (war). Each also has 2–3 traits. Personality values only drive **NPC** behaviour (FR-17). Human players decide for themselves.

---

## Aurelia — The Golden Kingdom (economic)
**Emblem:** gold sunburst on azure · **Seat:** Solmere, a river-port capital
**Starting bonus:** +10% gold production; Bank costs −20% · **Natural crown:** Golden Crown
**Signature:** the world's lender. Loans are its weapon.

| Character | Role | Statecraft / Envoy / Martial | Traits |
|---|---|---|---|
| **King Aldric Solmane** | Ruler, 46 | 62 / 55 / 31 | Shrewd, Pious, Gout-ridden |
| **Queen Maren Solmane** | Consort | 40 / 68 / 12 | Gracious, Letter-writer |
| **Princess Elowen** | Heir, 17 | 30 / 44 / 18 | Curious, Stubborn |
| **Master Caius Vell** | Treasurer | 64 / 40 / 10 | Scholar, Ledger-keeper (+5% loan interest cap) |

## Drakoria — The Iron Kingdom (military)
**Emblem:** black wyvern on red · **Seat:** Cinderhold, a volcanic fortress on jagged cliffs
**Starting bonus:** +15% iron; Barracks and Watchtower build faster · **Natural crown:** Iron Crown
**Signature:** strong and always short of gold, so it is Aurelia's natural borrower (spec demo beat 4).

| Character | Role | S / E / M | Traits |
|---|---|---|---|
| **Queen Varka Embermane** | Ruler, 39 | 38 / 30 / 74 | Ruthless, Brilliant tactician |
| **Prince Torvald** | Heir, 21 | 25 / 20 / 58 | Hot-headed, Duelist |
| **Marshal Hrothgar Ashborn** | General | 20 / 15 / 70 | Veteran, One-eyed |
| **Silka the Smelter** | Guildmistress | 55 / 35 / 20 | Inventive (+iron output) |

## Sylvara — The Emerald Kingdom (environmental)
**Emblem:** silver stag under an oak-crown on green · **Seat:** Thornwood, a forest-canopy city
**Starting bonus:** +15% food and wood; Farms cost −20% · **Natural crown:** People's Crown
**Signature:** feeds the continent. Food-for-iron trade is its lever (spec example: "Sylvara offers 100 food for 80 iron").

| Character | Role | S / E / M | Traits |
|---|---|---|---|
| **Queen Isolde Fernhallow** | Ruler, 52 | 45 / 72 / 30 | Wise, Secretive |
| **Lord Wren Fernhallow** | Spymaster, brother | 35 / 60 / 25 | Cunning (hook for FR-16 espionage) |
| **Elder Mossa** | Herbalist adviser | 50 / 45 / 5 | Healer (+welfare, Hospital bonus) |
| **Princess Lirael** | Heir, 15 | 22 / 38 / 14 | Gentle, Gifted archer |

## Valoria — The Maritime Kingdom (trade & diplomacy)
**Emblem:** white star-anchor on purple · **Seat:** Highspire, a cliff citadel above the harbour
**Starting bonus:** Market costs −20%; +1 trade offer slot; standing gains +10% · **Natural crown:** Diplomat's Crown
**Signature:** the broker. It profits from everyone's trade, which makes it the betrayal target in demo beat 6.

| Character | Role | S / E / M | Traits |
|---|---|---|---|
| **High King Cassian Valor** | Ruler, 60 | 55 / 50 / 55 | Just, Aging, Honourable |
| **Dame Seraphine Valor** | Heir, Knight-Commander | 40 / 35 / 66 | Brave, Zealous |
| **Admiral Oren Tidewell** | Fleet & shipping | 30 / 25 / 60 | Seafarer |
| **Harbormistress Ibbe** | Trade envoy | 60 / 58 / 10 | Incorruptible |

---

## Neutral characters
- **The Herald (Old Penn)** reads new World Chronicle entries aloud in the Round Table hall. He is the voice of the Living History Engine. **[MVP-lite: voice line + text]**
- **Ravenkeeper Nyla** delivers private letters and guides the tutorial. **[Stretch]**
- **NPC minor realms** (Lordship of Greymarsh, County of Brindle, Free City of Saltreach) fill empty seats when fewer than 4 humans play (FR-17). **[Post]**

## Data (fits spec §3.4 UUID style)
```sql
CREATE TABLE characters (
  character_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kingdom_id   UUID REFERENCES kingdoms(kingdom_id),
  name TEXT NOT NULL, role TEXT NOT NULL, age INT,
  statecraft INT, envoy INT, martial INT,
  traits TEXT[] DEFAULT '{}',
  is_ruler BOOLEAN DEFAULT FALSE,
  portrait_key TEXT                       -- Unity Addressables key
);
-- kingdoms gains: specialization TEXT, emblem_key TEXT, starting_bonus JSONB
```
Seed values for the four rulers go in `backend/app/database/seed.py`. All other characters are optional seed data.
