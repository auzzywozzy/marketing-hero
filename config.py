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
# ICP refocus 2026-06-03: BC + Alberta for the single-scope-trade + bad-website
# hunt that feeds the SEO-audit → website-redesign outreach play. Washington
# is retired (Seattle metro orgs trended too large + cross-border friction).
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
            "registry": "https://cores.reg.gov.ab.ca/cores/public/searchcorporation.aspx?q={q}",
            "opencorporates": "https://opencorporates.com/companies?q={q}&jurisdiction_code=ca_ab",
        },
    },
]

# Empty list — Washington was retired 2026-06-03. Kept as a constant so any
# code that still references PAUSED_REGIONS doesn't crash.
PAUSED_REGIONS = []

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
    # High-volume trades (Electrical, HVAC, Roofing) get places_queries[] —
    # multiple Google Places searches per metro per run. Each phrasing
    # surfaces different businesses on Google's index, expanding the pool
    # without burning Apollo credits.
    {
        "label": "Plumbing",
        "osm_craft": ["plumber"],
        "osm_shop": [],
        "places_query": "plumber",
        "places_queries": [
            "plumber",
            "plumbing contractor",
            "commercial plumbing services",
        ],
    },
    {
        "label": "HVAC / Heating",
        "osm_craft": ["hvac", "heating_engineer"],
        "osm_shop": [],
        "places_query": "hvac heating cooling contractor",
        "places_queries": [
            "hvac contractor",
            "heating and cooling company",
            "furnace and air conditioning installation",
            "commercial hvac services",
        ],
    },
    {
        "label": "Electrical",
        "osm_craft": ["electrician"],
        "osm_shop": [],
        "places_query": "electrician electrical contractor",
        "places_queries": [
            "electrician",
            "electrical contractor",
            "commercial electrical services",
            "industrial electrical contractor",
        ],
    },
    {
        "label": "Roofing",
        "osm_craft": ["roofer"],
        "osm_shop": [],
        "places_query": "roofing contractor",
        "places_queries": [
            "roofer",
            "roofing contractor",
            "commercial roofing company",
            "flat roof installation",
        ],
    },
    {
        "label": "General Contracting",
        "osm_craft": ["builder"],
        "osm_shop": ["trade"],
        "places_query": "general contractor construction",
    },
    {
        "label": "Carpentry",
        "osm_craft": ["carpenter"],
        "osm_shop": [],
        "places_query": "carpenter framing finish carpentry contractor",
    },
    {
        "label": "Prefabrication",
        "osm_craft": [],
        "osm_shop": [],
        "osm_tags": [
            ["building", "prefabricated"],
            ["industrial", "prefab"],
            ["man_made", "prefab"],
        ],
        "places_query": "prefabricated modular construction panelized builder",
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
    # Retired 2026-06-24 — not single-scope trades, polluted the dataset
    # with non-ICP companies. Categories removed:
    #   Manufacturing / Factory   — too broad (food-processing, shipyard, etc.)
    #   Sawmill / Wood Products   — industrial extraction, not service trade
    #   Brewery / Distillery / Winery — beverage producers, not trades
    #   Printing / Signs          — print shops, not construction
    #   Trade Supply / Hardware   — wholesalers/retailers, not contractors
    # Auto Body / Collision Repair retired 2026-06-02 — OSM auto_repair tags
    # pulled in too many small independent shops that fall well below the
    # $3M revenue band and don't fit the trades/ops ICP.
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
# Bumped from 220 → 350 after enabling multi-query Places for the high-
# volume trades (Plumbing, HVAC, Electrical, Roofing) — each now runs
# 3–4 query variations per metro per region, which expands the call
# count meaningfully. New budget: ~200/day = ~6000/mo ≈ $190 (just
# inside the $200 Google free credit).
PLACES_MAX_CALLS_PER_RUN = 350

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
    # "automotive" retired with the Auto Body category — Apollo's automotive
    # taxonomy pulled in dealerships, parts retailers, and other non-ICP orgs.
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
    # Profile-completeness signals (still useful — operating businesses)
    "has_website":          5,   # was 15 — bad/missing websites are now the TARGET
    "has_phone":            5,
    "has_email":            5,
    "multi_location_hint": 15,   # was 20
    "established_years":   10,
    "commercial_indicator":10,
    # Trade + geography — bumped to favour priority trades in BC metros
    "priority_trade":      20,   # was big_trade_category(10) — see PRIORITY_TRADES
    "urban_metro":         10,   # was 15
    "review_count_proxy":   5,   # was 10
    # NEW — website needs help (the SEO-audit + redesign outreach play)
    # Weight applied via WEBSITE_NEEDS_HELP_WEIGHTS by quality grade.
}

# The 9 single-scope trades that the SEO-audit → redesign outreach play
# targets. Leads in these categories get the "priority_trade" score boost.
# Carpentry + Prefabrication added 2026-06-03.
PRIORITY_TRADES = {
    "Electrical",
    "HVAC / Heating",
    "Plumbing",
    "Carpentry",
    "Prefabrication",
    "Roofing",
    "General Contracting",
    "Concrete / Masonry",
}

# Back-compat alias for any code that still imports BIG_TRADE_CATEGORIES.
BIG_TRADE_CATEGORIES = PRIORITY_TRADES
URBAN_METROS = {
    # BC (active hunt)
    "Vancouver", "Surrey", "Burnaby", "Richmond", "Victoria", "Coquitlam",
    "Langley", "Abbotsford", "Kelowna", "Saanich",
    # AB + WA kept here so existing leads still score urban-metro correctly
    # even while those regions are paused at the agent level.
    "Calgary", "Edmonton", "Red Deer", "Sherwood Park", "St. Albert",
    "Seattle", "Bellevue", "Tacoma", "Spokane", "Redmond", "Kirkland",
}

# Minimum fit score required to include a lead in the output (0–100).
MIN_FIT_SCORE = 25

# ---------------------------------------------------------------------------
# WEBSITE QUALITY SCORING — supports the "free SEO audit" outreach play
# ---------------------------------------------------------------------------
#
# Every lead gets a website_quality grade (URL-pattern classification, always
# runs). If MARKETING_HERO_PROBE_WEBSITES=1 in the environment, the agent
# additionally fetches each lead's homepage with a short timeout and refines
# the grade (DEAD, WEAK, OK based on HTML signals).
#
# Grade meaning (rank by outreach-pitch attractiveness, highest first):
#   MISSING      — no website at all; perfect "you don't have a site" pitch
#   DEAD         — URL returns 4xx/5xx or connection error
#   SOCIAL_ONLY  — Facebook / Instagram / LinkedIn URL listed as their "site"
#   FREE_TIER    — wixsite.com, wordpress.com, weebly.com, etc.
#   WEAK         — alive but missing modern signals (no viewport, no SSL,
#                  no description meta, etc.) — strong SEO-audit pitch
#   HAS_DOMAIN   — has a real domain; quality unknown until probed
#   OK           — modern site with full signals; lower outreach priority

WEBSITE_NEEDS_HELP_WEIGHTS = {
    "MISSING":     25,
    "DEAD":        22,
    "SOCIAL_ONLY": 22,
    "FREE_TIER":   18,
    "WEAK":        12,
    "HAS_DOMAIN":   5,
    "OK":           0,
}

# Domains that indicate a free / template / weak-tier website. Includes a
# couple of common builder platforms whose free tier most BC trades end up on.
FREE_TIER_DOMAINS = [
    "wixsite.com", "wix.com",
    "wordpress.com",
    "weebly.com",
    "godaddysites.com",
    "business.site",        # Google Business Profile microsites
    "jimdofree.com", "jimdosite.com",
    "webnode.com",
    "simdif.com",
    "yola.com", "yolasite.com",
    "site123.com", "site123.me",
    "strikingly.com",
    "mywebsite.com",        # Vistaprint
]

# URLs whose "website" field is actually a social profile — not a real site.
SOCIAL_ONLY_DOMAINS = [
    "facebook.com", "fb.com", "fb.me",
    "instagram.com",
    "linkedin.com",
    "x.com", "twitter.com",
    "yelp.com", "yelp.ca",
]

# Opt-in HTTP probe of each lead's website to refine the quality grade. Set
# MARKETING_HERO_PROBE_WEBSITES=1 in the environment to enable. Even with
# probing, results are cached per-lead via `website_probed_at` so re-runs
# only re-probe leads older than PROBE_REFRESH_DAYS.
WEBSITE_PROBE_TIMEOUT = 8        # seconds per HEAD/GET attempt
WEBSITE_PROBE_MAX_PER_RUN = 200  # safety cap so one run can't probe forever
PROBE_REFRESH_DAYS = 14          # re-probe a lead at most every N days

# ---------------------------------------------------------------------------
# OUTPUT PATHS (relative to this file)
# ---------------------------------------------------------------------------

LEADS_JSON_PATH = "data/leads.json"
LEADS_JS_PATH = "data/leads.js"   # dashboard reads this via <script> tag
RUN_LOG_PATH = "data/run_log.txt"
