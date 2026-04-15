"""
Marketing Hero — configuration.

Edit this file to change target trades, BC cities, API keys, and scoring weights.
Everything downstream (lead_generator.py, dashboard.html) reads from here.
"""

# ---------------------------------------------------------------------------
# WHO WE'RE LOOKING FOR
# ---------------------------------------------------------------------------

# Target revenue band (CAD annual) — used for reporting and fit-score narrative.
# NOTE: Free data sources do NOT expose revenue. This is a heuristic target; the
# fit score ranks leads by proxies (website, multi-location, service breadth).
TARGET_REVENUE_MIN = 3_000_000
TARGET_REVENUE_MAX = 9_000_000

# BC cities/regions to farm. Order matters — earlier cities are checked first
# when the daily quota is tight.
BC_TARGET_AREAS = [
    "Vancouver",
    "Surrey",
    "Burnaby",
    "Richmond",
    "Coquitlam",
    "Langley",
    "Abbotsford",
    "Kelowna",
    "Victoria",
    "Saanich",
    "Nanaimo",
    "Kamloops",
    "Chilliwack",
    "Prince George",
    "Delta",
    "Maple Ridge",
    "New Westminster",
    "North Vancouver",
    "West Vancouver",
    "Port Coquitlam",
    "Vernon",
    "Penticton",
    "Courtenay",
    "Campbell River",
    "Squamish",
    "Whistler",
]

# Trade categories. Each entry maps a human label to OpenStreetMap tags and
# Google Places text-search query fragments. Keep the OSM tags specific —
# "craft=*" and "shop=trade" are the two richest veins.
TRADE_CATEGORIES = [
    {
        "label": "Plumbing",
        "osm_craft": ["plumber"],
        "osm_shop": [],
        "places_query": "plumber",
    },
    {
        "label": "HVAC / Heating",
        "osm_craft": ["hvac", "heating_engineer"],
        "osm_shop": [],
        "places_query": "hvac heating cooling contractor",
    },
    {
        "label": "Electrical",
        "osm_craft": ["electrician"],
        "osm_shop": [],
        "places_query": "electrician electrical contractor",
    },
    {
        "label": "Roofing",
        "osm_craft": ["roofer"],
        "osm_shop": [],
        "places_query": "roofing contractor",
    },
    {
        "label": "General Contracting",
        "osm_craft": ["builder", "carpenter"],
        "osm_shop": ["trade"],
        "places_query": "general contractor construction",
    },
    {
        "label": "Landscaping / Excavation",
        "osm_craft": ["gardener"],
        "osm_shop": [],
        "places_query": "landscaping excavation contractor",
    },
    {
        "label": "Painting",
        "osm_craft": ["painter"],
        "osm_shop": [],
        "places_query": "painting contractor",
    },
    {
        "label": "Flooring",
        "osm_craft": ["floorer"],
        "osm_shop": [],
        "places_query": "flooring contractor installer",
    },
    {
        "label": "Drywall",
        "osm_craft": ["plasterer"],
        "osm_shop": [],
        "places_query": "drywall contractor",
    },
    {
        "label": "Concrete / Masonry",
        "osm_craft": ["stonemason", "bricklayer", "concrete"],
        "osm_shop": [],
        "places_query": "concrete masonry contractor",
    },
    {
        "label": "Windows / Doors",
        "osm_craft": ["window_construction"],
        "osm_shop": [],
        "places_query": "windows doors installer contractor",
    },
    {
        "label": "Garage Doors",
        "osm_craft": [],
        "osm_shop": [],
        "places_query": "garage door installer",
    },
    {
        "label": "Fencing / Decking",
        "osm_craft": [],
        "osm_shop": [],
        "places_query": "fencing decking contractor",
    },
    {
        "label": "Solar",
        "osm_craft": [],
        "osm_shop": [],
        "places_query": "solar installer contractor",
    },
    {
        "label": "Pool / Spa",
        "osm_craft": [],
        "osm_shop": [],
        "places_query": "pool spa contractor installer",
    },
]

# ---------------------------------------------------------------------------
# DATA SOURCES
# ---------------------------------------------------------------------------

# OpenStreetMap Overpass API — free, no key, but spotty coverage for small biz.
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT_SEC = 90

# Optional: Google Places API. Paste your key here (or set env var
# MARKETING_HERO_PLACES_KEY) to unlock richer data. Leave empty to use OSM only.
GOOGLE_PLACES_API_KEY = ""
PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# ---------------------------------------------------------------------------
# DAILY QUOTA
# ---------------------------------------------------------------------------

# Max NEW leads to add per run (prevents the JSON blob from ballooning).
MAX_NEW_LEADS_PER_RUN = 40

# Max total leads to keep on file. Oldest low-score leads get pruned when
# exceeded. Set to None for unlimited.
MAX_TOTAL_LEADS = 2000

# ---------------------------------------------------------------------------
# SCORING (fit score for the $3–9M band)
# ---------------------------------------------------------------------------

SCORE_WEIGHTS = {
    "has_website": 15,
    "has_phone": 5,
    "has_email": 5,
    "multi_location_hint": 20,  # multiple branches or service areas mentioned
    "established_years": 10,    # start_date tag present and > 5 years old
    "commercial_indicator": 10, # "commercial", "residential+commercial" keywords
    "big_trade_category": 10,   # HVAC, electrical, roofing = higher avg revenue
    "urban_metro": 15,          # Vancouver / Surrey / Victoria etc. = larger market
    "review_count_proxy": 10,   # richer data on OSM = more established biz
}

BIG_TRADE_CATEGORIES = {"HVAC / Heating", "Electrical", "Roofing", "Plumbing", "General Contracting"}
URBAN_METROS = {"Vancouver", "Surrey", "Burnaby", "Richmond", "Victoria", "Coquitlam", "Langley"}

# Minimum fit score required to include a lead in the output (0–100).
MIN_FIT_SCORE = 25

# ---------------------------------------------------------------------------
# OUTPUT PATHS (relative to this file)
# ---------------------------------------------------------------------------

LEADS_JSON_PATH = "data/leads.json"
LEADS_JS_PATH = "data/leads.js"   # dashboard reads this via <script> tag
RUN_LOG_PATH = "data/run_log.txt"
