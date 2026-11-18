"""Game balance constants. These are initial balancing values (spec §2.4), not final economics.

Everything a designer may want to tune lives here, so gameplay code reads from one place.
"""

RESOURCES = ("gold", "food", "wood", "stone", "iron")

# Rough exchange value of one unit of each resource, in gold. Used by NPC trade
# evaluation and the anti-collusion check.
BASE_PRICES = {"gold": 1.0, "food": 2.0, "wood": 2.0, "stone": 3.0, "iron": 4.0}

STARTING_RESOURCES = {"gold": 5000, "food": 500, "wood": 400, "stone": 300, "iron": 200}
STARTING_POPULATION = 100
STARTING_SOLDIERS = 20

MAX_BUILDING_LEVEL = 3
MIN_BUILDING_SPACING = 0.03  # map units (map is 1 x 1)
MAX_BUILD_RADIUS = 0.22      # buildings must be within this distance of the kingdom seat

BUILDINGS: dict[str, dict] = {
    "farm":        {"label": "Farm",        "cost": {"wood": 100},                "production": {"food": 40},               "maintenance": {"gold": 2},  "function": "Produces food"},
    "lumber_mill": {"label": "Lumber Mill", "cost": {"wood": 120},                "production": {"wood": 35},               "maintenance": {"gold": 2},  "function": "Produces wood"},
    "mine":        {"label": "Mine",        "cost": {"wood": 100, "gold": 50},    "production": {"stone": 20, "iron": 15},  "maintenance": {"gold": 4},  "function": "Produces stone and iron"},
    "gold_mine":   {"label": "Gold Mine",   "cost": {"wood": 200, "stone": 100},  "production": {"gold": 60},               "maintenance": {"food": 5},  "function": "Produces gold"},
    "market":      {"label": "Market",      "cost": {"wood": 150, "stone": 100},  "production": {"gold": 15},               "maintenance": {},           "function": "Enables trade"},
    "bank":        {"label": "Bank",        "cost": {"wood": 250, "stone": 200},  "production": {"gold": 10},               "maintenance": {"gold": 3},  "function": "Enables lending"},
    "barracks":    {"label": "Barracks",    "cost": {"wood": 200, "iron": 100},   "production": {},                         "maintenance": {"gold": 5},  "function": "Trains soldiers"},
    "watchtower":  {"label": "Watchtower",  "cost": {"wood": 100, "stone": 100},  "production": {},                         "maintenance": {"gold": 1},  "function": "Improves defense"},
    "academy":     {"label": "Academy",     "cost": {"wood": 200, "stone": 150},  "production": {},                         "maintenance": {"gold": 4},  "function": "Research and prestige"},
    "hospital":    {"label": "Hospital",    "cost": {"wood": 150, "stone": 100},  "production": {},                         "maintenance": {"gold": 3},  "function": "Improves welfare"},
    # Settlement buildings (the town around the castle)
    "houses":      {"label": "Houses",      "cost": {"wood": 80, "stone": 20},    "production": {},                         "maintenance": {},           "function": "Grow the population (+3 people per turn per level)", "category": "housing"},
    "tavern":      {"label": "Tavern",      "cost": {"wood": 120, "stone": 40},   "production": {"gold": 12},               "maintenance": {"food": 6},  "function": "Earns gold and draws settlers (+2 people per turn per level)", "category": "housing"},
    "mansions":    {"label": "Mansions",    "cost": {"wood": 200, "stone": 200, "gold": 100}, "production": {"gold": 25},   "maintenance": {"food": 5},  "function": "Taxes the nobility and raises welfare prestige", "category": "housing"},
    "blacksmith":  {"label": "Blacksmith",  "cost": {"wood": 120, "stone": 80},   "production": {"iron": 12},               "maintenance": {"gold": 3},  "function": "Forges iron for arms and tools", "category": "military"},
    "granary":     {"label": "Granary",     "cost": {"wood": 150, "stone": 50},   "production": {"food": 10},               "maintenance": {},           "function": "Stores grain: famine losses are halved per granary", "category": "economy"},
}
BUILDING_CATEGORIES = {   # the catalog's tabs; anything not listed falls under "economy"
    "economy": ("farm", "lumber_mill", "mine", "gold_mine", "market", "bank", "granary"),
    "military": ("barracks", "watchtower", "blacksmith"),
    "civic": ("academy", "hospital"),
    "housing": ("houses", "tavern", "mansions"),
}
BUILDING_LORE = {
    "farm": "Golden fields and patient oxen. Every loaf in the realm begins here.",
    "lumber_mill": "The great saw sings from dawn to dusk, turning old forest into new kingdom.",
    "mine": "Lamplit tunnels yield grey stone for walls and dark ore for the forge.",
    "gold_mine": "Deep in the hills a thin yellow vein: the reason crowns are coveted.",
    "market": "Stalls of spice, wool and gossip. Where coin changes hands, so do alliances.",
    "bank": "Ledgers, vaults and quiet men who lend to kings at a price.",
    "barracks": "Drill yards and bunk halls where farmers learn to be soldiers.",
    "watchtower": "A fire is kept ready at the top; no army reaches the walls unseen.",
    "academy": "Scholars argue over maps and stars, and the realm grows wiser for it.",
    "hospital": "Herbs, clean linen and steady hands. A cared-for people is a loyal one.",
    "houses": "Timber-framed homes with smoking chimneys: the realm's families take root.",
    "tavern": "Ale, song and rumour. Travellers stay a night and settlers stay for good.",
    "mansions": "Stone halls for the noble houses, whose taxes and favour flow to the crown.",
    "blacksmith": "Hammer on anvil all day long: spearheads, plough blades and horseshoes.",
    "granary": "Thick walls and dry floors keep the harvest safe through siege and winter.",
}
HOUSING_GROWTH = {"houses": 3, "tavern": 2}   # extra people per turn per building level
MANSION_WELFARE_PRESTIGE = 20                  # raw welfare points per mansion level

# --- Royal Decrees: objectives with rewards (claimed once per kingdom) -------------------
# kind: buildings (count of type), level (any building at level >= n), resource, population, trades,
#       band (reach that band with any court), battles_won, alliances
DECREES = [
    {"key": "sow_fields", "title": "Sow the Fields", "goal": "Have 2 Farms", "kind": "buildings", "target": "farm", "need": 2, "reward": {"wood": 150}},
    {"key": "timber", "title": "Timber for the Crown", "goal": "Have 2 Lumber Mills", "kind": "buildings", "target": "lumber_mill", "need": 2, "reward": {"gold": 150}},
    {"key": "homes", "title": "Hearth and Home", "goal": "Have 3 Houses", "kind": "buildings", "target": "houses", "need": 3, "reward": {"food": 200}},
    {"key": "masons", "title": "The Masons' Guild", "goal": "Upgrade any building to rank 2", "kind": "level", "need": 2, "reward": {"stone": 150}},
    {"key": "markets", "title": "Open the Markets", "goal": "Complete 2 trades", "kind": "trades", "need": 2, "reward": {"gold": 250}},
    {"key": "friend", "title": "A Friend at Court", "goal": "Reach Friendly standing with a court", "kind": "band", "target": "FRIENDLY", "need": 1, "reward": {"iron": 80}},
    {"key": "growth", "title": "A Growing Realm", "goal": "Reach 150 people", "kind": "population", "need": 150, "reward": {"gold": 200}},
    {"key": "watch", "title": "Raise the Watch", "goal": "Build a Watchtower", "kind": "buildings", "target": "watchtower", "need": 1, "reward": {"stone": 100}},
    {"key": "treasury", "title": "A Treasury of Kings", "goal": "Hold 8,000 gold", "kind": "resource", "target": "gold", "need": 8000, "reward": {"iron": 120}},
    {"key": "pact", "title": "Bound by Oath", "goal": "Form an alliance", "kind": "alliances", "need": 1, "reward": {"gold": 300}},
    {"key": "victory", "title": "Victory in the Field", "goal": "Win a battle", "kind": "battles_won", "need": 1, "reward": {"gold": 300}},
]
DECREES_SHOWN = 3   # like a quest log: the next three open decrees

# --- Royal Market: the crown's own exchange (needs a Market) -----------------------------
# Gold buys materials at a premium and materials sell back at a loss, so gold always has a use but
# trading with other courts stays the better deal. Each market level lets you move this many units a turn.
MARKET_BUY_MARKUP = 2.0             # buy price = BASE_PRICES x markup (wood costs 4 gold)
MARKET_SELL_RATE = 0.5              # sell price = BASE_PRICES x rate (wood sells for 1 gold)
MARKET_UNITS_PER_LEVEL = 150        # units bought + sold per turn, per market level

# --- Ultimatums: Drakoria demands tribute from weaker human rulers -------------------------
ULTIMATUM_FIRST_TURN = 4            # no threats before this turn
ULTIMATUM_DEADLINE_TURNS = 2        # pay within this many turns, or Drakoria marches
ULTIMATUM_COOLDOWN_TURNS = 5        # turns between one ultimatum's answer and the next demand
ULTIMATUM_TRIBUTE_BASE = 300        # tribute = base + per_turn x the turn it is demanded
ULTIMATUM_TRIBUTE_PER_TURN = 40

# --- Military passage (open roads between two realms) -----------------------------------
PASSAGE_MIN_STANDING = 0            # PEACEFUL or better to open your roads to someone
PASSAGE_GOLD_PER_TURN = 15          # road tolls each realm earns per open passage
PASSAGE_STANDING_ON_GRANT = 5
PASSAGE_STANDING_ON_CLOSE = -8

# --- Royal Council (docs/02_CHARACTERS_AND_KINGDOMS.md): who advises on what --------------
# (name, role, domain, portrait key). Domains: treasury, military, diplomacy, welfare, industry.
COUNCIL = {
    "Aurelia": [("Master Caius Vell", "Treasurer", "treasury", "caius"),
                ("Queen Maren Solmane", "Royal Consort", "diplomacy", "maren"),
                ("Princess Elowen", "Heir to the Throne", "welfare", "elowen")],
    "Drakoria": [("Marshal Hrothgar Ashborn", "General of the Host", "military", "hrothgar"),
                 ("Silka the Smelter", "Guildmistress", "industry", "silka"),
                 ("Prince Torvald", "Heir to the Throne", "diplomacy", "torvald")],
    "Sylvara": [("Lord Wren Fernhallow", "Spymaster", "diplomacy", "wren"),
                ("Elder Mossa", "Herbalist", "welfare", "mossa"),
                ("Princess Lirael", "Heir and Archer", "military", "lirael")],
    "Valoria": [("Harbormistress Ibbe", "Trade Envoy", "treasury", "ibbe"),
                ("Admiral Oren Tidewell", "Admiral of the Fleet", "industry", "oren"),
                ("Dame Seraphine Valor", "Knight-Commander", "military", "seraphine")],
}

# --- Gifts: a chest holds gold and, if you have it, iron ------------------------------
GIFT_IRON_SHARE = 0.25              # iron in a chest, as a fraction of its gold (by count)

# --- Kingdom seats (spec §4.2; characters doc) -------------------------------------------
KINGDOMS: list[dict] = [
    {
        "name": "Aurelia", "title": "The Golden Kingdom", "specialization": "economic",
        "ruler": "King Aldric Solmane", "emblem": "sunburst", "color": "#C6A15B", "map": (0.28, 0.32),
        "production_bonus": {"gold": 1.10}, "discounts": {"bank": 0.8},
        "starting_buildings": ["farm", "market", "bank", "gold_mine", "lumber_mill"], "soldiers": 20,
        "places": ["the Solmere Fords", "the Golden Fields", "Sunreach Bridge"],
    },
    {
        "name": "Drakoria", "title": "The Iron Kingdom", "specialization": "military",
        "ruler": "Queen Varka Embermane", "emblem": "wyvern", "color": "#813C43", "map": (0.72, 0.28),
        "production_bonus": {"iron": 1.15}, "discounts": {"barracks": 0.8, "watchtower": 0.8},
        "starting_buildings": ["farm", "mine", "barracks", "lumber_mill"], "soldiers": 60,
        "places": ["Cinderhold Pass", "the Ashen Slopes", "Emberfall Gate"],
    },
    {
        "name": "Sylvara", "title": "The Emerald Kingdom", "specialization": "environmental",
        "ruler": "Queen Isolde Fernhallow", "emblem": "stag", "color": "#3E7C5A", "map": (0.27, 0.72),
        "production_bonus": {"food": 1.15, "wood": 1.15}, "discounts": {"farm": 0.8},
        "starting_buildings": ["farm", "farm", "lumber_mill", "market"], "soldiers": 25,
        "places": ["Thornwood Edge", "the Fernhallow Glade", "Mossbridge"],
    },
    {
        "name": "Valoria", "title": "The Maritime Kingdom", "specialization": "maritime",
        "ruler": "High King Cassian Valor", "emblem": "star_anchor", "color": "#5B6FA8", "map": (0.73, 0.71),
        "production_bonus": {}, "discounts": {"market": 0.8},
        "starting_buildings": ["farm", "market", "lumber_mill"], "soldiers": 35,
        "places": ["Highspire Harbour", "the Eastern Cliffs", "Tidewell Strand"],
        "standing_gain_multiplier": 1.10,
    },
]
KINGDOM_BY_NAME = {k["name"]: k for k in KINGDOMS}

# Seeded starting standings make the demo story possible from turn 1.
INITIAL_STANDINGS = {
    ("Aurelia", "Valoria"): 45,
    ("Drakoria", "Valoria"): 42,
    ("Aurelia", "Sylvara"): 30,
    ("Aurelia", "Drakoria"): 15,
    ("Sylvara", "Valoria"): 20,
    ("Drakoria", "Sylvara"): -10,
}

WORLD_PRESETS = {
    # standard: competitive; beginner protection for 3 turns; a reign of 30 turns.
    "standard": {"beginner_protection_turns": 3, "turn_limit": 30},
    # solo_court: a judge/solo player against three NPC rulers; faster pacing, a 20-turn reign.
    "solo_court": {"beginner_protection_turns": 1, "turn_limit": 20},
}
CORONATION_WARNING_TURNS = 3   # "the coronation approaches" in the last turns of a reign

# --- Standing (feature B14) --------------------------------------------------------------
STANDING_BANDS = [(70, "TRUSTED"), (40, "FRIENDLY"), (0, "PEACEFUL"), (-49, "COLD"), (-100, "HOSTILE")]
ALLIANCE_MIN_STANDING = 40
STANDING_DELTAS = {
    "trade_completed": 3,
    "loan_repaid": 8,
    "loan_defaulted": -25,
    "alliance_formed": 10,
    "alliance_broken": -50,  # with the war penalty, attacking an ally always ends Hostile
    "war_declared": -60,
    "betrayal_world_penalty": -15,
    "peace_made": 15,
}
TRADE_GAIN_CAP_PER_TURN = 9
GIFT_GAIN_CAP_PER_TURN = 20
GIFT_TIER_FRACTIONS = (0.05, 0.10, 0.15)

# --- Economy ------------------------------------------------------------------------------
LOAN_LIMITS = {"min_principal": 100, "max_interest": 50.0, "min_duration": 1, "max_duration": 20}
CREDIT_BASE = 2000  # lets the spec demo loan (Drakoria borrows 2,000 @ 10%) through
CREDIT_PER_BUILDING_LEVEL = 300
DEFAULT_GRACE_TURNS = 2
TRADE_MAX_VALUE_RATIO = 5.0  # anti-collusion: lopsided human trades must use the gift seal

# --- Military -----------------------------------------------------------------------------
RECRUIT_COST = {"gold": 10, "iron": 2, "food": 1}
RECRUIT_PER_BARRACKS_LEVEL = 20
WAR_DECLARATION_COST = 200
BASE_DEFENSE = 50
WATCHTOWER_DEFENSE_PER_LEVEL = 0.25
ALLY_DEFENSE_SHARE = 0.25
PLUNDER_FRACTION = 0.15
PLUNDER_CAP = 1500

# --- Prestige (spec §4.8) -----------------------------------------------------------------
PRESTIGE_CATEGORY_CAP = 200
PRESTIGE_SCALE = 300.0
BETRAYAL_PRESTIGE_PENALTY = 50
DEFAULT_PRESTIGE_PENALTY = 30
CROWNS = {
    "economic": "Golden Crown",
    "military": "Iron Crown",
    "diplomatic": "Diplomat's Crown",
    "development": "Builder's Crown",
    "welfare": "People's Crown",
}


def band(score: int) -> str:
    return next(name for floor, name in STANDING_BANDS if score >= floor)


def building_cost(building_type: str, specialization_discounts: dict, level: int = 1) -> dict[str, int]:
    """Cost to build (level=1) or to upgrade *to* `level`."""
    base = BUILDINGS[building_type]["cost"]
    discount = specialization_discounts.get(building_type, 1.0)
    return {res: int(round(amount * level * discount)) for res, amount in base.items()}
