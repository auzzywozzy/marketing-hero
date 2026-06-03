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

# Target regions. The agent farms each region against the full category list.
#
# Each entry:
#   key            — short slug used in logs and lead.region
#   iso_code       — ISO 3166-2 (Overpass admin area filter)
#   admin_level    — OSM admin_level for the area=> .region binding
#                     (province for CA, state for US — both are 4)
#   country        — country name written onto each lead
#   province       — province / state written onto each lead
#   target_areas   — list of city names accepted as `addr:city`
#   places_metros  — metros to query via Google Places (cost-capped subset)
#   places_suffix  — appended to Places query (e.g. "British Columbia")
#   apollo_locations — strings handed to Apollo's person_locations filter
#   research       — region-specific registry URLs for the "Research" row
#                    in the dashboard
TARGET_REGIONS = [
    {
        "key": "BC",
        "iso_code": "CA-BC",
        "admin_level": 4,
        "country": "Canada",
        "province": "BC",
        "target_areas": [
            "Vancouver", "Surrey", "Burnaby", "Richmond", "Coquitlam", "Langley",
            "Abbotsford", "Kelowna", "Victoria", "Saanich", "Nanaimo", "Kamloops",
            "Chilliwack", "Prince George", "Delta", "Maple Ridge", "New Westminster",
            "North Vancouver", "West Vancouver", "Port Coquitlam", "Vernon",
            "Penticton", "Courtenay", "Campbell River", "Squamish", "Whistler",
        ],
        "places_metros": ["Vancouver", "Surrey", "Burnaby", "Victoria", "Richmond"],
        "places_suffix": "British Columbia",
        "apollo_locations": [
            "British Columbia", "Greater Vancouver Metropolitan Area",
            "Greater Victoria Metropolitan Area", "Kelowna", "Kamloops",
        ],
        "research": {
            "registry": "https://www.bcregistry.gov.bc.ca/search?q={q}",
            "opencorporates": "https://opencorporates.com/companies?q={q}&jurisdiction_code=ca_bc",
        },
    },
    {
        "key": "AB",
        "iso_code": "CA-AB",
        "admin_level": 4,
        "country": "Canada",
        "province": "AB",
        "target_areas": [
            "Calgary", "Edmonton", "Red Deer", "Lethbridge", "Medicine Hat",
            "Grande Prairie", "Airdrie", "St. Albert", "Spruce Grove", "Leduc",
            "Fort McMurray", "Okotoks", "Sherwood Park", "Camrose", "Cochrane",
            "Lloydminster", "Beaumont", "Stony Plain", "Sylvan Lake", "Brooks",
            "Wetaskiwin", "Chestermere",
        ],
        "places_metros": ["Calgary", "Edmonton", "Red Deer", "Lethbridge", "Sherwood Park"],
        "places_suffix": "Alberta",
        "apollo_locations": [
            "Alberta", "Greater Calgary Metropolitan Area",
            "Greater Edmonton Metropolitan Area", "Red Deer",
        ],
        "research": {
            # Alberta Corporate Registry search lives behind a paywall; the
            # public "corporate registration system" landing page is the best
            # zero-cost stub we can deep-link to. OpenCorporates fills the gap.
            "registry": "https://cores.reg.gov.ab.ca/cores/public/searchcorporation.aspx?q={q}",
            "opencorporates": "https://opencorporates.com/companies?q={q}&jurisdiction_code=ca_ab",
        },
    },
    {
        "key": "WA",
        "iso_code": "US-WA",
        "admin_level": 4,  # state in OSM is admin_level=4
        "country": "United States",
        "province": "WA",
        "target_areas": [
            "Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue", "Kent",
            "Everett", "Renton", "Yakima", "Federal Way", "Spokane Valley",
            "Bellingham", "Kennewick", "Auburn", "Pasco", "Marysville", "Redmond",
            "Lakewood", "Shoreline", "Richland", "Kirkland", "Burien",
            "Sammamish", "Olympia", "Lacey", "Edmonds", "Bremerton", "Puyallup",
            "Lynnwood", "Bothell", "Issaquah", "Wenatchee",
        ],
        "places_metros": ["Seattle", "Spokane", "Tacoma", "Bellevue", "Vancouver"],
        "places_suffix": "Washington",
        "apollo_locations": [
            "Washington, United States", "Greater Seattle Area",
            "Spokane, Washington", "Tacoma, Washington",
        ],
        "research": {
            "registry": "https://ccfs.sos.wa.gov/#/BusinessSearch/BusinessInformation?q={q}",
            "opencorporates": "https://opencorporates.com/companies?q={q}&jurisdiction_code=us_wa",
        },
    },
]

# Back-compat — older code expected a single flat BC list. Auto-derived from
# TARGET_REGIONS so nothing else has to change.
BC_TARGET_AREAS = TARGET_REGIONS[0]["target_areas"]

# Trade categories. Each entry maps a human label to OpenStreetMap tags and
# Google Places text-search query fragments.
#
# OSM tag fields (all optional):
#   osm_craft  — list of craft=* values  (e.g. "plumber")
#   osm_shop   — list of shop=* values   (e.g. "trade")
#   osm_tags   — list of [key, value] pairs for other tag schemas.
#                value can be None to match any value for that key (wildcard).
#                Examples: ["industrial", "factory"], ["man_made", "works"], ["office", "company"]
TRADE_CATEGORIES = [
    # --- Core trades (contractors / installers) ---
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
        "label": "Landscaping",
        "osm_craft": ["gardener"],
        "osm_shop": [],
        "osm_tags": [["landuse", "plant_nursery"]],
        "places_query": "landscaping contractor lawn maintenance",
    },
    {
        "label": "Excavation / Earthworks",
        "osm_craft": ["earthworks"],
        "osm_shop": [],
        "osm_tags": [
            ["industrial", "excavation"],
            ["industrial", "earthworks"],
            ["industrial", "quarry"],
        ],
        "places_query": "excavation earthworks site preparation contractor",
    },
    {
        "label": "Demolition / Site Prep",
        "osm_craft": ["demolition"],
        "osm_shop": [],
        "places_query": "demolition site prep contractor",
    },
    {
        "label": "Painting",
        "osm_craft": ["painter"],
        "osm_shop": [],
        "places_query": "painting contractor",
    },
    {
        "label": "Flooring / Tile",
        "osm_craft": ["floorer", "tiler", "parquet_layer", "carpet_layer"],
        "osm_shop": [],
        "places_query": "flooring tile contractor installer",
    },
    {
        "label": "Drywall / Plastering",
        "osm_craft": ["plasterer"],
        "osm_shop": [],
        "places_query": "drywall plaster contractor",
    },
    {
        "label": "Concrete / Masonry",
        "osm_craft": ["stonemason", "bricklayer", "concrete", "paver"],
        "osm_shop": [],
        "places_query": "concrete masonry contractor",
    },
    {
        "label": "Windows / Doors",
        "osm_craft": ["window_construction", "door_construction"],
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
        "osm_craft": ["fence_maker"],
        "osm_shop": [],
        "places_query": "fencing decking contractor",
    },
    {
        "label": "Solar",
        "osm_craft": ["photovoltaic"],
        "osm_shop": [],
        "places_query": "solar installer contractor",
    },
    {
        "label": "Pool / Spa",
        "osm_craft": [],
        "osm_shop": [],
        "places_query": "pool spa contractor installer",
    },
    # --- Specialty trades ---
    {
        "label": "Glass / Glazing",
        "osm_craft": ["glaziery"],
        "osm_shop": [],
        "places_query": "glass glazing contractor",
    },
    {
        "label": "Insulation / Scaffolding",
        "osm_craft": ["insulation", "scaffolder"],
        "osm_shop": [],
        "places_query": "insulation scaffolding contractor",
    },
    {
        "label": "Metal Fabrication / Welding",
        "osm_craft": ["blacksmith", "metal_construction", "welder", "tinsmith"],
        "osm_shop": [],
        "places_query": "metal fabrication welding shop",
    },
    {
        "label": "Cabinet / Millwork",
        "osm_craft": ["cabinet_maker", "joiner", "turner"],
        "osm_shop": [],
        "places_query": "cabinet maker millwork joinery",
    },
    # --- Manufacturing / industrial ---
    {
        "label": "Manufacturing / Factory",
        "osm_craft": [],
        "osm_shop": [],
        "osm_tags": [
            ["industrial", "factory"],
            ["industrial", "machine_shop"],
            ["industrial", "metal_production"],
            ["industrial", "food_processing"],
            ["industrial", "sawmill"],
            ["industrial", "shipyard"],
            ["industrial", "wire_drawing"],
            ["man_made", "works"],
        ],
        "places_query": "manufacturing factory",
    },
    {
        "label": "Sawmill / Wood Products",
        "osm_craft": ["sawmill"],
        "osm_shop": [],
        "places_query": "sawmill lumber wood products manufacturer",
    },
    {
        "label": "Brewery / Distillery / Winery",
        "osm_craft": ["brewery", "distillery", "winery"],
        "osm_shop": [],
        "places_query": "brewery distillery winery",
    },
    {
        "label": "Printing / Signs",
        "osm_craft": ["printer", "signmaker", "engraver"],
        "osm_shop": [],
        "places_query": "commercial printing sign shop",
    },
    # --- Trade supply / wholesale ---
    {
        "label": "Trade Supply / Hardware",
        "osm_craft": [],
        "osm_shop": ["doityourself", "hardware", "paint", "fireplace", "bathroom_furnishing", "kitchen", "tiles"],
        "places_query": "building supply hardware trade wholesale",
    },
    # --- Auto / collision ---
    {
        "label": "Auto Body / Collision Repair",
        "osm_craft": ["car_body_repair", "car_painter"],
        "osm_shop": ["car_repair"],
        "osm_tags": [["amenity", "car_repair"]],
        "places_query": "auto body collision repair shop",
    },
]

# ---------------------------------------------------------------------------
# DATA SOURCES
# ---------------------------------------------------------------------------

# OpenStreetMap Overpass API — free, no key, but spotty coverage for small biz.
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT_SEC = 90

# Optional: Google Places API. Paste your key here (or set env var
# MARKETING_HERO_PLACES_KEY — recommended, keeps key out of git) to unlock
# richer data. Leave empty to use OSM only.
GOOGLE_PLACES_API_KEY = ""
PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# --- Cost control for Places ---
# Places Text Search is billed at ~$32 / 1000 requests. Google provides a
# $200/mo free credit, which covers ~6,250 calls/month (~200/day).
#
# Across 3 regions × 5 metros × ~12 big cats = 180 calls/day = ~5,400/mo,
# which still fits inside the $200 free credit with headroom. Each region
# carries its own metro list — see TARGET_REGIONS[*]["places_metros"].
PLACES_TOP_METROS = TARGET_REGIONS[0]["places_metros"]  # back-compat alias
PLACES_BIG_CATEGORIES_ONLY = True
# Safety cap — hard stop on Places calls per run, even if config drifts.
PLACES_MAX_CALLS_PER_RUN = 220

# --- Apollo.io (organization search) ---
# Apollo's /api/v1/mixed_companies/api_search returns companies matching an
# ICP filter (industry × geo × employee band). Leave the key blank to skip
# Apollo entirely; set MARKETING_HERO_APOLLO_KEY in the environment to enable.
# Cost: included in Apollo's paid plan ($49–$99/mo). Each call returns up
# to ~25 organizations; we cap calls per run below to keep the rolling
# quota sane.
APOLLO_API_KEY = ""  # prefer env var MARKETING_HERO_APOLLO_KEY
APOLLO_API_BASE_URL = "https://api.apollo.io/api/v1"
# /organizations/search is Apollo's canonical org-search endpoint. The
# mixed_companies/* paths exist too but return the same data with an extra
# "accounts" key (saved-account state). We don't need that here.
APOLLO_ORG_SEARCH_PATH = "/organizations/search"

# Apollo industry tags — these are the exact strings from Apollo's fixed
# industry taxonomy (`organization_industries` filter, NOT `q_*`). Strings
# outside this taxonomy are silently dropped. Names match Apollo's UI labels
# in lowercase.
APOLLO_INDUSTRY_KEYWORDS = [
    "construction",
    "building materials",
    "civil engineering",
    "mechanical or industrial engineering",
    "electrical/electronic manufacturing",
    "machinery",
    "facilities services",
    "glass, ceramics & concrete",
    "wholesale building materials",
    "automotive",
    "printing",
    "wine and spirits",
    "food production",
    "packaging and containers",
    # Excluded on purpose: "mining & metals" pulls gold/silver/mineral
    # extraction firms (Skeena Gold, Inca One Gold, etc.) which don't match
    # the trades / ops ICP. Re-add only if pursuing extraction-adjacent work.
]

# Employee-band brackets that approximate the $3–9M CAD revenue band — sweet
# spot is ~10–100 employees for trades/manufacturing.
APOLLO_EMPLOYEE_RANGES = ["11,20", "21,50", "51,100"]

# Cap per run — Apollo paid plans have monthly call limits; this keeps a
# daily run from burning the entire month's quota in one shot. Across 3
# regions, ~3 pages each = 9 calls/day = ~270/mo.
APOLLO_MAX_CALLS_PER_RUN = 12
APOLLO_PAGE_SIZE = 25
APOLLO_MAX_PAGES_PER_REGION = 3

# ---------------------------------------------------------------------------
# DAILY QUOTA
# ---------------------------------------------------------------------------

# Max NEW leads to add per run (prevents the JSON blob from ballooning).
# Bumped to 500 after the 3-region widening — the first widened OSM-only
# run capped out at 200 with hundreds left on the floor.
MAX_NEW_LEADS_PER_RUN = 500

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

BIG_TRADE_CATEGORIES = {
    "HVAC / Heating",
    "Electrical",
    "Roofing",
    "Plumbing",
    "General Contracting",
    "Manufacturing / Factory",
    "Metal Fabrication / Welding",
    "Sawmill / Wood Products",
    "Brewery / Distillery / Winery",
    "Cabinet / Millwork",
    "Excavation / Earthworks",
    "Demolition / Site Prep",
    "Concrete / Masonry",
    "Auto Body / Collision Repair",
}
URBAN_METROS = {
    # BC
    "Vancouver", "Surrey", "Burnaby", "Richmond", "Victoria", "Coquitlam", "Langley",
    # AB
    "Calgary", "Edmonton", "Red Deer", "Sherwood Park", "St. Albert",
    # WA
    "Seattle", "Bellevue", "Tacoma", "Spokane", "Redmond", "Kirkland",
}

# Minimum fit score required to include a lead in the output (0–100).
MIN_FIT_SCORE = 25

# ---------------------------------------------------------------------------
# OUTPUT PATHS (relative to this file)
# ---------------------------------------------------------------------------

LEADS_JSON_PATH = "data/leads.json"
LEADS_JS_PATH = "data/leads.js"   # dashboard reads this via <script> tag
RUN_LOG_PATH = "data/run_log.txt"
