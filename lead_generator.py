"""
Marketing Hero — daily lead generator for Five Talents Marketing.

Farms British Columbia trades businesses that *might* sit in the $3–9M revenue
band. Runs from Windows Task Scheduler (see run_daily.bat) and appends to a
rolling JSON store that the dashboard reads.

Sources used (in order of preference):
  1. Google Places Text Search — if config.GOOGLE_PLACES_API_KEY is set
  2. OpenStreetMap Overpass API — always available, no key required

Honest scope: free sources do NOT expose revenue. The "fit score" ranks each
lead by proxies (website present, multi-location hints, review count, trade
category, urban metro). The user manually confirms revenue using the
generated research links (LinkedIn / Google / OpenCorporates).

Usage:
    python lead_generator.py              # normal daily run
    python lead_generator.py --dry-run    # show what would be added, don't write
    python lead_generator.py --reset      # wipe existing leads.json and start over
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import config

HERE = Path(__file__).resolve().parent
LEADS_JSON = HERE / config.LEADS_JSON_PATH
LEADS_JS = HERE / config.LEADS_JS_PATH
RUN_LOG = HERE / config.RUN_LOG_PATH


# ---------------------------------------------------------------------------
# LEAD MODEL
# ---------------------------------------------------------------------------

def make_lead_id(name: str, city: str) -> str:
    key = f"{name.strip().lower()}|{city.strip().lower()}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def empty_lead() -> dict:
    return {
        "id": "",
        "name": "",
        "trade": "",
        "city": "",
        "region": "",            # BC | AB | WA — short region key
        "province": "",          # province / state — written from TARGET_REGIONS
        "country": "",
        "address": "",
        "website": "",
        "phone": "",
        "email": "",
        "osm_id": "",
        "place_id": "",
        "apollo_id": "",
        "source": "",            # osm | google_places | apollo
        "discovered_at": "",
        "last_seen_at": "",
        "raw_tags": {},
        "fit_score": 0,
        "score_breakdown": {},
        "research_urls": {},
        # Website-quality signal — see config.WEBSITE_NEEDS_HELP_WEIGHTS
        "website_quality": "",       # MISSING | DEAD | SOCIAL_ONLY | FREE_TIER | WEAK | HAS_DOMAIN | OK
        "website_probed_at": "",     # ISO timestamp of last HTTP probe
        "status": "new",         # new | contacted | qualified | closed | dead
        "notes": "",
    }


# ---------------------------------------------------------------------------
# HTTP UTILITY
# ---------------------------------------------------------------------------

def http_get(url: str, timeout: int = 60, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": "MarketingHero/1.0 (Eunoia Consulting)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_post(url: str, data: bytes, timeout: int = 60, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers or {
            "User-Agent": "MarketingHero/1.0 (Eunoia Consulting)",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_post_with_retry(url: str, data: bytes, timeout: int = 60,
                          max_retries: int = 4) -> bytes:
    """POST with exponential backoff on 429/503/504 — Overpass rate-limits free users."""
    delay = 6
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            return http_post(url, data, timeout=timeout)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 503, 504):
                log(f"  . Overpass {e.code}, backing off {delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except Exception as e:
            last_err = e
            time.sleep(delay)
            delay *= 2
    if last_err:
        raise last_err
    raise RuntimeError("http_post_with_retry exhausted without raising")


# ---------------------------------------------------------------------------
# OVERPASS (OSM) SOURCE
# ---------------------------------------------------------------------------

def build_overpass_query(category: dict, region: dict) -> str | None:
    """Build an Overpass QL query for a trade category inside one region."""
    parts = []
    for craft in category.get("osm_craft", []):
        parts.append(f'node["craft"="{craft}"](area.region);')
        parts.append(f'way["craft"="{craft}"](area.region);')
    for shop in category.get("osm_shop", []):
        parts.append(f'node["shop"="{shop}"](area.region);')
        parts.append(f'way["shop"="{shop}"](area.region);')
    for entry in category.get("osm_tags", []):
        # entry is [key, value] or [key, None] for wildcard
        key = entry[0]
        value = entry[1] if len(entry) > 1 else None
        if value is None:
            parts.append(f'node["{key}"](area.region);')
            parts.append(f'way["{key}"](area.region);')
        else:
            parts.append(f'node["{key}"="{value}"](area.region);')
            parts.append(f'way["{key}"="{value}"](area.region);')
    if not parts:
        return None
    body = "\n    ".join(parts)
    iso = region["iso_code"]
    admin = region.get("admin_level", 4)
    query = f"""
[out:json][timeout:{config.OVERPASS_TIMEOUT_SEC}];
area["ISO3166-2"="{iso}"][admin_level={admin}]->.region;
(
    {body}
);
out center tags 300;
""".strip()
    return query


def fetch_overpass(category: dict, region: dict) -> list[dict]:
    query = build_overpass_query(category, region)
    if not query:
        return []
    try:
        data = http_post_with_retry(
            config.OVERPASS_URL,
            data=f"data={urllib.parse.quote(query)}".encode("utf-8"),
            timeout=config.OVERPASS_TIMEOUT_SEC,
        )
        payload = json.loads(data)
    except Exception as e:
        log(f"  ! Overpass error for {category['label']} [{region['key']}]: {e}")
        return []

    target_areas_lower = {a.lower() for a in region["target_areas"]}
    leads = []
    for elem in payload.get("elements", []):
        tags = elem.get("tags", {}) or {}
        name = tags.get("name") or tags.get("operator") or ""
        if not name:
            continue
        city = (
            tags.get("addr:city")
            or tags.get("addr:place")
            or tags.get("is_in:city")
            or ""
        ).strip()
        # Skip anything not in a configured target area for THIS region.
        if not city:
            continue
        if city.lower() not in target_areas_lower:
            continue

        lead = empty_lead()
        lead["id"] = make_lead_id(name, city)
        lead["name"] = name.strip()
        lead["trade"] = category["label"]
        lead["city"] = city
        lead["region"] = region["key"]
        lead["province"] = region["province"]
        lead["country"] = region["country"]
        lead["address"] = _compose_address(tags)
        lead["website"] = tags.get("website", "") or tags.get("contact:website", "")
        lead["phone"] = tags.get("phone", "") or tags.get("contact:phone", "")
        lead["email"] = tags.get("email", "") or tags.get("contact:email", "")
        lead["osm_id"] = f'{elem.get("type", "node")}/{elem.get("id", "")}'
        lead["source"] = "osm"
        lead["raw_tags"] = tags
        leads.append(lead)
    return leads


def _compose_address(tags: dict) -> str:
    parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
        tags.get("addr:city", ""),
        tags.get("addr:postcode", ""),
    ]
    return ", ".join(p for p in parts if p).strip(", ")


# ---------------------------------------------------------------------------
# GOOGLE PLACES SOURCE (optional)
# ---------------------------------------------------------------------------

def places_key() -> str:
    return (
        config.GOOGLE_PLACES_API_KEY
        or os.environ.get("MARKETING_HERO_PLACES_KEY", "")
    )


def fetch_places(category: dict, city: str, region: dict) -> list[dict]:
    key = places_key()
    if not key:
        return []
    q = f'{category["places_query"]} in {city}, {region["places_suffix"]}'
    # Google's `region=` bias is an ISO 3166-1 country code (ca / us).
    region_bias = "us" if region["country"] == "United States" else "ca"
    url = (
        config.PLACES_TEXT_SEARCH_URL
        + "?query=" + urllib.parse.quote(q)
        + "&region=" + region_bias + "&key=" + key
    )
    try:
        data = http_get(url)
        payload = json.loads(data)
    except Exception as e:
        log(f"  ! Places error for {category['label']} in {city} [{region['key']}]: {e}")
        return []

    leads = []
    for r in payload.get("results", []):
        name = r.get("name", "").strip()
        if not name:
            continue
        lead = empty_lead()
        lead["id"] = make_lead_id(name, city)
        lead["name"] = name
        lead["trade"] = category["label"]
        lead["city"] = city
        lead["region"] = region["key"]
        lead["province"] = region["province"]
        lead["country"] = region["country"]
        lead["address"] = r.get("formatted_address", "")
        lead["place_id"] = r.get("place_id", "")
        lead["source"] = "google_places"
        lead["raw_tags"] = {
            "rating": r.get("rating"),
            "user_ratings_total": r.get("user_ratings_total"),
            "types": r.get("types", []),
        }
        leads.append(lead)
    return leads


# ---------------------------------------------------------------------------
# APOLLO SOURCE (optional — opt-in via MARKETING_HERO_APOLLO_KEY)
# ---------------------------------------------------------------------------

def apollo_key() -> str:
    return (
        getattr(config, "APOLLO_API_KEY", "")
        or os.environ.get("MARKETING_HERO_APOLLO_KEY", "")
    )


def fetch_apollo_companies(region: dict, page: int) -> tuple[list[dict], int]:
    """Run one Apollo /mixed_companies/api_search call for a region.

    Returns (leads, total_pages_estimate). total_pages_estimate is best-effort
    and used to short-circuit pagination when Apollo runs out of matches.
    """
    key = apollo_key()
    if not key:
        return [], 0

    url = config.APOLLO_API_BASE_URL + config.APOLLO_ORG_SEARCH_PATH
    body = {
        "page": page,
        "per_page": config.APOLLO_PAGE_SIZE,
        "organization_locations": region["apollo_locations"],
        "organization_num_employees_ranges": list(config.APOLLO_EMPLOYEE_RANGES),
        # `organization_industries` is the only Apollo filter that actually
        # constrains by taxonomy. q_organization_keyword_tags is a loose
        # text search that returns recruiting / design / publishing noise.
        "organization_industries": list(config.APOLLO_INDUSTRY_KEYWORDS),
    }
    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "X-Api-Key": key,
        "User-Agent": "MarketingHero/1.0 (Eunoia Consulting)",
    }

    try:
        raw = http_post(url, data=json.dumps(body).encode("utf-8"),
                        timeout=30, headers=headers)
        payload = json.loads(raw)
    except urllib.error.HTTPError as e:
        log(f"  ! Apollo HTTP {e.code} [{region['key']} p{page}]: {e.read()[:200].decode('utf-8', 'replace')}")
        return [], 0
    except Exception as e:
        log(f"  ! Apollo error [{region['key']} p{page}]: {e}")
        return [], 0

    # Apollo's response keys have shifted over time — orgs may live under
    # "organizations", "accounts", or "companies". Check in order.
    orgs = []
    for k in ("organizations", "accounts", "companies"):
        v = payload.get(k)
        if isinstance(v, list) and v:
            orgs = v
            break
    total_entries = payload.get("total_entries")
    if total_entries is None and isinstance(payload.get("pagination"), dict):
        total_entries = payload["pagination"].get("total_entries")
    pages_estimate = 0
    if isinstance(total_entries, (int, float)):
        pages_estimate = int(-(-int(total_entries) // config.APOLLO_PAGE_SIZE))

    target_areas_lower = {a.lower() for a in region["target_areas"]}
    leads = []
    for o in orgs:
        if not isinstance(o, dict):
            continue
        name = (o.get("name") or "").strip()
        if not name:
            continue
        # Apollo gives city / state on the org record.
        city = (o.get("city") or o.get("primary_city") or "").strip()
        state = (o.get("state") or o.get("primary_state") or "").strip()
        country = (o.get("country") or o.get("primary_country") or "").strip()
        # Keep only orgs in the configured target_areas — guards against
        # Apollo's loose location matching (e.g. "Vancouver" returning WA hits
        # when querying for BC, etc.).
        if city.lower() not in target_areas_lower:
            continue
        # Compose address from whatever Apollo returned. Apollo's `street_address`
        # field carries the street; postal_code is sometimes populated.
        addr_bits = [
            (o.get("street_address") or "").strip(),
            city,
            state,
            (o.get("postal_code") or "").strip(),
        ]
        address = ", ".join(b for b in addr_bits if b)

        # Trade label inferred from Apollo's industry keywords array. We
        # fall back to "Apollo · Unclassified" when nothing maps.
        trade_label = _map_apollo_industry(o)

        lead = empty_lead()
        lead["id"] = make_lead_id(name, city)
        lead["name"] = name
        lead["trade"] = trade_label
        lead["city"] = city
        lead["region"] = region["key"]
        lead["province"] = region["province"]
        lead["country"] = region["country"]
        lead["address"] = address
        lead["website"] = (o.get("website_url") or "").strip()
        lead["phone"] = (o.get("phone") or o.get("sanitized_phone") or "").strip()
        lead["apollo_id"] = (o.get("id") or "").strip() if isinstance(o.get("id"), str) else str(o.get("id") or "")
        lead["source"] = "apollo"
        lead["raw_tags"] = {
            "industry": o.get("industry"),
            "keywords": (o.get("keywords") or [])[:8],
            "estimated_num_employees": o.get("estimated_num_employees"),
            "annual_revenue_printed": o.get("annual_revenue_printed"),
            "linkedin_url": o.get("linkedin_url"),
            "founded_year": o.get("founded_year"),
        }
        leads.append(lead)
    return leads, pages_estimate


# Apollo-industry → trade-label map. Anything not matched gets a generic
# "Apollo · …" bucket so we don't accidentally collapse unrelated orgs into
# the wrong OSM category.
_APOLLO_INDUSTRY_MAP = [
    ("plumb",            "Plumbing"),
    ("hvac",             "HVAC / Heating"),
    ("heating",          "HVAC / Heating"),
    ("electric",         "Electrical"),
    ("roof",             "Roofing"),
    ("concrete",         "Concrete / Masonry"),
    ("mason",            "Concrete / Masonry"),
    ("excav",            "Excavation / Earthworks"),
    ("demolition",       "Demolition / Site Prep"),
    ("landscap",         "Landscaping"),
    ("cabinet",          "Cabinet / Millwork"),
    ("millwork",         "Cabinet / Millwork"),
    ("metal fab",        "Metal Fabrication / Welding"),
    ("welding",          "Metal Fabrication / Welding"),
    ("printing",         "Printing / Signs"),
    ("sign",             "Printing / Signs"),
    ("brewery",          "Brewery / Distillery / Winery"),
    ("distillery",       "Brewery / Distillery / Winery"),
    ("winery",           "Brewery / Distillery / Winery"),
    ("sawmill",          "Sawmill / Wood Products"),
    ("manufactur",       "Manufacturing / Factory"),
    ("fabricat",         "Manufacturing / Factory"),
    ("construction",     "General Contracting"),
    ("contractor",       "General Contracting"),
    ("building materials","Trade Supply / Hardware"),
    ("glass",            "Glass / Glazing"),
    ("insulation",       "Insulation / Scaffolding"),
    ("scaffold",         "Insulation / Scaffolding"),
    ("flooring",         "Flooring / Tile"),
    ("tile",             "Flooring / Tile"),
    ("paint",            "Painting"),
    ("drywall",          "Drywall / Plastering"),
    ("plaster",          "Drywall / Plastering"),
    ("window",           "Windows / Doors"),
    ("door",             "Windows / Doors"),
    ("fence",            "Fencing / Decking"),
    ("decking",          "Fencing / Decking"),
    ("solar",            "Solar"),
    ("pool",             "Pool / Spa"),
]


def _map_apollo_industry(org: dict) -> str:
    haystack = " ".join(
        str(x).lower() for x in [
            org.get("industry") or "",
            " ".join(org.get("keywords") or []),
            " ".join(org.get("industries") or []),
        ]
    )
    for needle, label in _APOLLO_INDUSTRY_MAP:
        if needle in haystack:
            return label
    return "Apollo · Unclassified"


# ---------------------------------------------------------------------------
# ENRICHMENT — research URLs the user can click to verify revenue band
# ---------------------------------------------------------------------------

def add_research_urls(lead: dict, region: dict | None = None) -> None:
    region = region or _region_for_lead(lead)
    name_enc = urllib.parse.quote(lead["name"])
    q = f'"{lead["name"]}" {lead["city"]} {lead.get("province", "")}'.strip()
    enc = urllib.parse.quote(q)
    research = {
        "google": f"https://www.google.com/search?q={enc}",
        "google_maps": f"https://www.google.com/maps/search/{urllib.parse.quote(lead['name'] + ' ' + lead['city'])}",
        "linkedin": f"https://www.linkedin.com/search/results/companies/?keywords={name_enc}",
    }
    if region:
        for label, template in region.get("research", {}).items():
            research[label] = template.format(q=name_enc)
    else:
        research["opencorporates"] = f"https://opencorporates.com/companies?q={name_enc}"
    lead["research_urls"] = research


def _region_for_lead(lead: dict) -> dict | None:
    key = lead.get("region")
    if not key:
        return None
    for r in config.TARGET_REGIONS:
        if r["key"] == key:
            return r
    return None


# ---------------------------------------------------------------------------
# WEBSITE QUALITY — URL classifier + optional HTTP probe
# ---------------------------------------------------------------------------

def _hostname(url: str) -> str:
    """Best-effort lowercase hostname extraction without requiring scheme."""
    if not url:
        return ""
    u = url.strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "http://" + u
    try:
        host = urllib.parse.urlparse(u).hostname or ""
    except Exception:
        host = ""
    return host.lower().lstrip(".").removeprefix("www.")


def classify_website_url(url: str) -> str:
    """Classify a lead's website by URL pattern alone (no network call).

    Returns one of: MISSING | SOCIAL_ONLY | FREE_TIER | HAS_DOMAIN
    """
    if not url or not str(url).strip():
        return "MISSING"
    host = _hostname(url)
    if not host:
        return "MISSING"
    for d in getattr(config, "SOCIAL_ONLY_DOMAINS", []):
        if host == d or host.endswith("." + d):
            return "SOCIAL_ONLY"
    for d in getattr(config, "FREE_TIER_DOMAINS", []):
        if host == d or host.endswith("." + d):
            return "FREE_TIER"
    return "HAS_DOMAIN"


def probe_website(url: str, timeout: int | None = None) -> str:
    """HTTP-probe a website to refine its quality grade.

    Returns one of: MISSING | DEAD | SOCIAL_ONLY | FREE_TIER | WEAK | OK

    Falls through to URL classification for anything we don't need to fetch
    (missing / social-only / free-tier already settle the score). For real
    domains we GET the homepage, look for: SSL, viewport meta, <title>,
    <h1>, and meta description. >=4/5 signals = OK; otherwise WEAK; any
    transport / 4xx / 5xx failure = DEAD.
    """
    base = classify_website_url(url)
    if base != "HAS_DOMAIN":
        return base
    if timeout is None:
        timeout = getattr(config, "WEBSITE_PROBE_TIMEOUT", 8)

    target = url.strip()
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    try:
        req = urllib.request.Request(
            target,
            headers={
                "User-Agent": "Mozilla/5.0 (MarketingHero website probe; +https://eunoiaconsulting.net)",
                "Accept": "text/html",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl() or target
            body_bytes = resp.read(40_000)  # first 40KB is enough for <head>
        body = body_bytes.decode("utf-8", errors="ignore").lower()
        has_ssl = final_url.startswith("https://")
        has_viewport = 'name="viewport"' in body or "name='viewport'" in body
        has_title = "<title" in body
        has_desc = 'name="description"' in body or "name='description'" in body
        has_h1 = "<h1" in body
        signals = sum([has_ssl, has_viewport, has_title, has_desc, has_h1])
        return "OK" if signals >= 4 else "WEAK"
    except urllib.error.HTTPError as e:
        if e.code and e.code >= 400:
            return "DEAD"
        return "WEAK"
    except Exception:
        return "DEAD"


def website_probe_enabled() -> bool:
    return os.environ.get("MARKETING_HERO_PROBE_WEBSITES", "").strip() in ("1", "true", "yes", "on")


def _needs_reprobe(lead: dict) -> bool:
    stamp = lead.get("website_probed_at") or ""
    if not stamp:
        return True
    try:
        last = dt.datetime.fromisoformat(stamp)
    except Exception:
        return True
    days = (dt.datetime.now() - last).days
    return days >= getattr(config, "PROBE_REFRESH_DAYS", 14)


def assess_website(lead: dict) -> str:
    """Compute the lead's website_quality grade. Uses URL-pattern only by
    default; if MARKETING_HERO_PROBE_WEBSITES=1, additionally HTTP-probes
    HAS_DOMAIN leads to refine to OK / WEAK / DEAD."""
    url = lead.get("website", "")
    grade = classify_website_url(url)
    if grade == "HAS_DOMAIN" and website_probe_enabled():
        grade = probe_website(url)
        lead["website_probed_at"] = dt.datetime.now().isoformat(timespec="seconds")
    return grade


# ---------------------------------------------------------------------------
# SCORING
# ---------------------------------------------------------------------------

MULTI_LOCATION_PATTERNS = [
    r"\b(locations?|branches?)\b",
    r"serving\s+(the\s+)?(lower mainland|greater vancouver|vancouver island|interior|okanagan)",
    r"\b(throughout|across)\s+(bc|british columbia)\b",
]

COMMERCIAL_PATTERNS = [
    r"\bcommercial\b",
    r"\bindustrial\b",
    r"\bmulti[- ]?family\b",
    r"\bstrata\b",
]


def score_lead(lead: dict) -> None:
    breakdown = {}
    raw = lead.get("raw_tags") or {}
    score = 0

    if lead["website"]:
        score += config.SCORE_WEIGHTS["has_website"]
        breakdown["has_website"] = config.SCORE_WEIGHTS["has_website"]
    if lead["phone"]:
        score += config.SCORE_WEIGHTS["has_phone"]
        breakdown["has_phone"] = config.SCORE_WEIGHTS["has_phone"]
    if lead["email"]:
        score += config.SCORE_WEIGHTS["has_email"]
        breakdown["has_email"] = config.SCORE_WEIGHTS["has_email"]

    description_bag = " ".join([
        lead["name"].lower(),
        str(raw.get("description", "")).lower(),
        str(raw.get("note", "")).lower(),
        str(raw.get("service", "")).lower(),
    ])

    if any(re.search(p, description_bag) for p in MULTI_LOCATION_PATTERNS):
        score += config.SCORE_WEIGHTS["multi_location_hint"]
        breakdown["multi_location_hint"] = config.SCORE_WEIGHTS["multi_location_hint"]

    if any(re.search(p, description_bag) for p in COMMERCIAL_PATTERNS):
        score += config.SCORE_WEIGHTS["commercial_indicator"]
        breakdown["commercial_indicator"] = config.SCORE_WEIGHTS["commercial_indicator"]

    start_date = raw.get("start_date", "")
    if start_date and re.match(r"^\d{4}", str(start_date)):
        try:
            year = int(str(start_date)[:4])
            if dt.date.today().year - year >= 5:
                score += config.SCORE_WEIGHTS["established_years"]
                breakdown["established_years"] = config.SCORE_WEIGHTS["established_years"]
        except Exception:
            pass

    # Priority-trade boost (the 9 single-scope trades for the SEO outreach
    # play). Back-compat: read PRIORITY_TRADES if defined, else fall back to
    # BIG_TRADE_CATEGORIES.
    priority_set = getattr(config, "PRIORITY_TRADES", config.BIG_TRADE_CATEGORIES)
    priority_wt = config.SCORE_WEIGHTS.get(
        "priority_trade",
        config.SCORE_WEIGHTS.get("big_trade_category", 10),
    )
    if lead["trade"] in priority_set:
        score += priority_wt
        breakdown["priority_trade"] = priority_wt

    if lead["city"] in config.URBAN_METROS:
        score += config.SCORE_WEIGHTS["urban_metro"]
        breakdown["urban_metro"] = config.SCORE_WEIGHTS["urban_metro"]

    # Google Places review count proxy
    reviews = raw.get("user_ratings_total")
    if isinstance(reviews, (int, float)) and reviews >= 50:
        score += config.SCORE_WEIGHTS["review_count_proxy"]
        breakdown["review_count_proxy"] = config.SCORE_WEIGHTS["review_count_proxy"]

    # Website-needs-help — central to the SEO-audit + redesign outreach play.
    # assess_website() classifies the URL and (if MARKETING_HERO_PROBE_WEBSITES
    # is set) HTTP-probes HAS_DOMAIN leads to refine OK / WEAK / DEAD.
    grade = lead.get("website_quality")
    if not grade or grade not in config.WEBSITE_NEEDS_HELP_WEIGHTS:
        grade = assess_website(lead)
        lead["website_quality"] = grade
    elif website_probe_enabled() and grade == "HAS_DOMAIN" and _needs_reprobe(lead):
        # Periodic re-probe of HAS_DOMAIN leads — sites can break or upgrade.
        grade = probe_website(lead.get("website", ""))
        lead["website_quality"] = grade
        lead["website_probed_at"] = dt.datetime.now().isoformat(timespec="seconds")
    wt = config.WEBSITE_NEEDS_HELP_WEIGHTS.get(grade, 0)
    if wt:
        score += wt
        breakdown[f"website_{grade.lower()}"] = wt

    lead["fit_score"] = min(score, 100)
    lead["score_breakdown"] = breakdown


# ---------------------------------------------------------------------------
# STORE
# ---------------------------------------------------------------------------

def load_store() -> dict:
    if not LEADS_JSON.exists():
        return {"generated_at": "", "leads": []}
    try:
        return json.loads(LEADS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {"generated_at": "", "leads": []}


def save_store(store: dict) -> None:
    LEADS_JSON.parent.mkdir(parents=True, exist_ok=True)
    LEADS_JSON.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
    # Also write a JS file so the dashboard can load data via <script> tag
    # (file:// browsers block fetch() of local JSON).
    js = "window.MARKETING_HERO_DATA = " + json.dumps(store, ensure_ascii=False) + ";"
    LEADS_JS.parent.mkdir(parents=True, exist_ok=True)
    LEADS_JS.write_text(js, encoding="utf-8")


def merge_leads(store: dict, new_leads: list[dict]) -> tuple[int, int]:
    """Merge new leads into the store. Returns (added, updated)."""
    existing = {l["id"]: l for l in store["leads"]}
    added = 0
    updated = 0
    now = dt.datetime.now().isoformat(timespec="seconds")

    for lead in new_leads:
        if lead["fit_score"] < config.MIN_FIT_SCORE:
            continue
        if lead["id"] in existing:
            # Refresh last_seen_at and update any newly populated fields.
            e = existing[lead["id"]]
            e["last_seen_at"] = now
            for k in ("website", "phone", "email", "address"):
                if not e.get(k) and lead.get(k):
                    e[k] = lead[k]
            if lead["fit_score"] > e.get("fit_score", 0):
                e["fit_score"] = lead["fit_score"]
                e["score_breakdown"] = lead["score_breakdown"]
            updated += 1
        else:
            lead["discovered_at"] = now
            lead["last_seen_at"] = now
            existing[lead["id"]] = lead
            added += 1
            if added >= config.MAX_NEW_LEADS_PER_RUN:
                break

    store["leads"] = list(existing.values())

    # Prune if over cap — lowest score + oldest first.
    if config.MAX_TOTAL_LEADS and len(store["leads"]) > config.MAX_TOTAL_LEADS:
        store["leads"].sort(key=lambda l: (-l.get("fit_score", 0), l.get("discovered_at", "")))
        store["leads"] = store["leads"][: config.MAX_TOTAL_LEADS]

    return added, updated


# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    line = f"[{stamp}] {msg}"
    # Windows console may be cp1252 and choke on non-ASCII. Re-encode safely.
    try:
        print(line)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(line.encode(enc, errors="replace").decode(enc, errors="replace"))
    try:
        RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with RUN_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def run(dry_run: bool = False, reset: bool = False) -> int:
    if reset and LEADS_JSON.exists():
        LEADS_JSON.unlink()
        log("Reset: deleted existing leads.json")

    store = load_store()
    log(f"Loaded store: {len(store['leads'])} existing leads")

    use_places = bool(places_key())
    use_apollo = bool(apollo_key())
    sources = ["OSM"]
    if use_places: sources.append("Google Places")
    if use_apollo: sources.append("Apollo")
    log(f"Sources active: {' + '.join(sources)}")

    regions = config.TARGET_REGIONS
    log(f"Regions: {', '.join(r['key'] for r in regions)} "
        f"({sum(len(r['target_areas']) for r in regions)} target cities)")
    log(f"Categories: {len(config.TRADE_CATEGORIES)}")

    places_big_only = getattr(config, "PLACES_BIG_CATEGORIES_ONLY", True)
    places_max = getattr(config, "PLACES_MAX_CALLS_PER_RUN", 80)
    places_calls = 0

    if use_places:
        eligible_cats = [
            c["label"] for c in config.TRADE_CATEGORIES
            if (not places_big_only) or c["label"] in config.BIG_TRADE_CATEGORIES
        ]
        total_metros = sum(len(r["places_metros"]) for r in regions)
        estimated = len(eligible_cats) * total_metros
        log(f"Places scope: {len(eligible_cats)} cats × {total_metros} metros "
            f"(across {len(regions)} regions) = {estimated} calls (cap {places_max})")

    candidates: list[dict] = []

    # ---- OSM + Google Places: iterate (category × region) ----
    for category in config.TRADE_CATEGORIES:
        log(f"Category: {category['label']}")
        for region in regions:
            osm_leads = fetch_overpass(category, region)
            log(f"  OSM [{region['key']}]: {len(osm_leads)} raw hits")
            candidates.extend(osm_leads)
            time.sleep(4.0)  # be polite to Overpass

            # Google Places — scoped to stay under the free credit
            if use_places and (not places_big_only or category["label"] in config.BIG_TRADE_CATEGORIES):
                # Multi-query support: high-volume trades define places_queries[]
                # as a list of phrasings — each surfaces different Google Places
                # results. Categories without it fall back to a single
                # places_query string.
                place_queries = category.get("places_queries") or [category.get("places_query", "")]
                place_queries = [q for q in place_queries if q]
                for city in region["places_metros"]:
                    for q_idx, q_str in enumerate(place_queries):
                        if places_calls >= places_max:
                            log(f"  Places cap reached ({places_max}) — skipping remainder")
                            break
                        # Hand the active query into fetch_places by temporarily
                        # rewriting category.places_query (the function reads it).
                        original_q = category.get("places_query")
                        category["places_query"] = q_str
                        try:
                            places_leads = fetch_places(category, city, region)
                        finally:
                            category["places_query"] = original_q
                        places_calls += 1
                        if places_leads:
                            tag = f"q{q_idx+1}" if len(place_queries) > 1 else ""
                            log(f"  Places [{region['key']} · {city}{(' ·' + tag) if tag else ''}]: {len(places_leads)} hits")
                        candidates.extend(places_leads)
                        time.sleep(0.2)
                    if places_calls >= places_max:
                        break

    if use_places:
        log(f"Places calls this run: {places_calls}")

    # ---- Apollo organization search: iterate region × pages ----
    if use_apollo:
        apollo_max = getattr(config, "APOLLO_MAX_CALLS_PER_RUN", 12)
        apollo_calls = 0
        pages_per_region = getattr(config, "APOLLO_MAX_PAGES_PER_REGION", 3)
        for region in regions:
            log(f"Apollo: region {region['key']}")
            for page in range(1, pages_per_region + 1):
                if apollo_calls >= apollo_max:
                    log(f"  Apollo cap reached ({apollo_max}) — skipping remainder")
                    break
                apollo_leads, est_pages = fetch_apollo_companies(region, page)
                apollo_calls += 1
                log(f"  Apollo [{region['key']} p{page}]: {len(apollo_leads)} hits "
                    f"(est pool {est_pages * config.APOLLO_PAGE_SIZE if est_pages else '?'})")
                candidates.extend(apollo_leads)
                if est_pages and page >= est_pages:
                    log(f"  Apollo [{region['key']}]: reached est page count, stopping")
                    break
                time.sleep(1.0)
            if apollo_calls >= apollo_max:
                break
        log(f"Apollo calls this run: {apollo_calls}")

    log(f"Total raw candidates: {len(candidates)}")

    # Score everyone and add research URLs
    for lead in candidates:
        score_lead(lead)
        add_research_urls(lead)

    # Sort by score so the best candidates get picked first (quota cap)
    candidates.sort(key=lambda l: -l["fit_score"])

    if dry_run:
        log("Dry-run: top 10 candidates this run:")
        for lead in candidates[:10]:
            log(f"  [{lead['fit_score']:3d}] {lead['name']} — {lead['trade']} — {lead['city']}")
        return 0

    added, updated = merge_leads(store, candidates)
    store["generated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    save_store(store)

    log(f"Run complete. Added: {added}, Updated: {updated}, Total on file: {len(store['leads'])}")
    return 0


def cli() -> int:
    p = argparse.ArgumentParser(description="Marketing Hero — daily lead generator")
    p.add_argument("--dry-run", action="store_true", help="Show candidates without writing")
    p.add_argument("--reset", action="store_true", help="Wipe existing leads.json first")
    args = p.parse_args()
    try:
        return run(dry_run=args.dry_run, reset=args.reset)
    except KeyboardInterrupt:
        log("Interrupted")
        return 130
    except Exception as e:
        log(f"FATAL: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(cli())
