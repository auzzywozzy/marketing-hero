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
        "province": "BC",
        "country": "Canada",
        "address": "",
        "website": "",
        "phone": "",
        "email": "",
        "osm_id": "",
        "place_id": "",
        "source": "",
        "discovered_at": "",
        "last_seen_at": "",
        "raw_tags": {},
        "fit_score": 0,
        "score_breakdown": {},
        "research_urls": {},
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

def build_overpass_query(category: dict) -> str | None:
    """Build an Overpass QL query for a trade category inside BC."""
    parts = []
    for craft in category["osm_craft"]:
        parts.append(f'node["craft"="{craft}"](area.bc);')
        parts.append(f'way["craft"="{craft}"](area.bc);')
    for shop in category["osm_shop"]:
        parts.append(f'node["shop"="{shop}"](area.bc);')
        parts.append(f'way["shop"="{shop}"](area.bc);')
    if not parts:
        return None
    body = "\n    ".join(parts)
    query = f"""
[out:json][timeout:{config.OVERPASS_TIMEOUT_SEC}];
area["ISO3166-2"="CA-BC"][admin_level=4]->.bc;
(
    {body}
);
out center tags 300;
""".strip()
    return query


def fetch_overpass(category: dict) -> list[dict]:
    query = build_overpass_query(category)
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
        log(f"  ! Overpass error for {category['label']}: {e}")
        return []

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
        # Skip anything not in a configured BC target area.
        if city and city not in config.BC_TARGET_AREAS:
            # Loose fallback: match against lowercase compare
            low = city.lower()
            if not any(a.lower() == low for a in config.BC_TARGET_AREAS):
                continue
        if not city:
            # Try to derive from postcode or skip
            continue

        lead = empty_lead()
        lead["id"] = make_lead_id(name, city)
        lead["name"] = name.strip()
        lead["trade"] = category["label"]
        lead["city"] = city
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


def fetch_places(category: dict, city: str) -> list[dict]:
    key = places_key()
    if not key:
        return []
    q = f'{category["places_query"]} in {city}, British Columbia'
    url = (
        config.PLACES_TEXT_SEARCH_URL
        + "?query=" + urllib.parse.quote(q)
        + "&region=ca&key=" + key
    )
    try:
        data = http_get(url)
        payload = json.loads(data)
    except Exception as e:
        log(f"  ! Places error for {category['label']} in {city}: {e}")
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
# ENRICHMENT — research URLs the user can click to verify revenue band
# ---------------------------------------------------------------------------

def add_research_urls(lead: dict) -> None:
    q = f'"{lead["name"]}" {lead["city"]} BC'
    enc = urllib.parse.quote(q)
    lead["research_urls"] = {
        "google": f"https://www.google.com/search?q={enc}",
        "google_maps": f"https://www.google.com/maps/search/{urllib.parse.quote(lead['name'] + ' ' + lead['city'])}",
        "linkedin": f"https://www.linkedin.com/search/results/companies/?keywords={urllib.parse.quote(lead['name'])}",
        "opencorporates": f"https://opencorporates.com/companies?q={urllib.parse.quote(lead['name'])}&jurisdiction_code=ca_bc",
        "bc_registry": f"https://www.bcregistry.gov.bc.ca/search?q={urllib.parse.quote(lead['name'])}",
    }


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

    if lead["trade"] in config.BIG_TRADE_CATEGORIES:
        score += config.SCORE_WEIGHTS["big_trade_category"]
        breakdown["big_trade_category"] = config.SCORE_WEIGHTS["big_trade_category"]

    if lead["city"] in config.URBAN_METROS:
        score += config.SCORE_WEIGHTS["urban_metro"]
        breakdown["urban_metro"] = config.SCORE_WEIGHTS["urban_metro"]

    # Google Places review count proxy
    reviews = raw.get("user_ratings_total")
    if isinstance(reviews, (int, float)) and reviews >= 50:
        score += config.SCORE_WEIGHTS["review_count_proxy"]
        breakdown["review_count_proxy"] = config.SCORE_WEIGHTS["review_count_proxy"]

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
    log(f"Source: {'Google Places + OSM' if use_places else 'OpenStreetMap (no API key)'}")

    candidates: list[dict] = []

    for category in config.TRADE_CATEGORIES:
        log(f"Category: {category['label']}")
        # OSM first (always runs)
        osm_leads = fetch_overpass(category)
        log(f"  OSM: {len(osm_leads)} raw hits")
        candidates.extend(osm_leads)
        time.sleep(4.0)  # be polite to Overpass (free tier rate-limits hard)

        # Google Places if configured
        if use_places:
            for city in config.BC_TARGET_AREAS[:8]:  # top 8 metros per run
                places_leads = fetch_places(category, city)
                if places_leads:
                    log(f"  Places [{city}]: {len(places_leads)} hits")
                candidates.extend(places_leads)
                time.sleep(0.2)

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
