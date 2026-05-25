"""Shop catalogue. Static data; safe to expose to the client."""

CATALOGUE = [
    # ---- card backs ----
    {"id": "back_classic",  "category": "card_back",   "name": "Classic",  "price": 0,    "preview": "diag-gold"},
    {"id": "back_noir",     "category": "card_back",   "name": "Noir",     "price": 250,  "preview": "noir"},
    {"id": "back_ruby",     "category": "card_back",   "name": "Ruby",     "price": 500,  "preview": "ruby"},
    {"id": "back_ocean",    "category": "card_back",   "name": "Ocean",    "price": 750,  "preview": "ocean"},
    {"id": "back_aurora",   "category": "card_back",   "name": "Aurora",   "price": 1500, "preview": "aurora"},

    # ---- chip styles ----
    {"id": "chip_gold",     "category": "chip_style",  "name": "Gold",     "price": 0,    "preview": "#d4af37"},
    {"id": "chip_silver",   "category": "chip_style",  "name": "Silver",   "price": 300,  "preview": "#c0c4cc"},
    {"id": "chip_emerald",  "category": "chip_style",  "name": "Emerald",  "price": 600,  "preview": "#2fb886"},
    {"id": "chip_violet",   "category": "chip_style",  "name": "Violet",   "price": 900,  "preview": "#a78bfa"},
    {"id": "chip_crimson",  "category": "chip_style",  "name": "Crimson",  "price": 1200, "preview": "#e85a4f"},

    # ---- table felts ----
    {"id": "felt_emerald",  "category": "table_felt",  "name": "Emerald",  "price": 0,    "preview": "#143b2a"},
    {"id": "felt_midnight", "category": "table_felt",  "name": "Midnight", "price": 400,  "preview": "#10172a"},
    {"id": "felt_burgundy", "category": "table_felt",  "name": "Burgundy", "price": 700,  "preview": "#3a1320"},
    {"id": "felt_obsidian", "category": "table_felt",  "name": "Obsidian", "price": 1000, "preview": "#0d0d0f"},
]

CATALOGUE_BY_ID = {item["id"]: item for item in CATALOGUE}
