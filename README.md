# Marketing Hero — Five Talents Lead Generator + Profit Dashboard

Daily lead-farming pipeline for Five Talents Marketing targeting British Columbia trades businesses in the **$3M–$9M revenue band**, plus an interactive profit dashboard that models how leads translate into revenue.

## What it does

**`lead_generator.py`** — runs daily, queries OpenStreetMap (and optionally Google Places) for BC trades businesses, scores each one on a 0–100 fit score, dedupes against the existing store, and writes to `data/leads.json` + `data/leads.js`.

**`dashboard.html`** — standalone HTML file. Open in any browser. Sliders on the left drive the economic model (close rate, deal size, service mix, delivery cost, overhead). KPI tiles and charts on the right update live. The lead pipeline table at the bottom reads straight from the generated data with search, filter, and sort.

## One-time setup

1. **Confirm Python is on PATH** (already verified: Python 3.14.3).
2. **First run**:
   ```
   cd "marketing_hero"
   python lead_generator.py --dry-run
   ```
   `--dry-run` prints the top candidates without writing. If it looks sane, run without the flag.
3. **Open the dashboard**: double-click `dashboard.html`. No web server needed — the generator writes `data/leads.js` which the HTML loads via `<script>` tag.

## Daily automation (Windows Task Scheduler)

1. Open Task Scheduler → **Create Basic Task**.
2. Name: `Marketing Hero Daily`.
3. Trigger: **Daily**, pick a time (e.g. 7:00 AM).
4. Action: **Start a program**.
5. Program/script: browse to `marketing_hero\run_daily.bat`.
6. Start in: the `marketing_hero` directory itself.
7. Finish. Right-click the task → **Run** to test once.

Every run appends to `data/run_log.txt` so you can see what happened.

## Data sources (honest scope)

Free sources do **not** expose revenue. The `fit_score` ranks leads by proxies that correlate with the $3–9M band:

- Has a live website (+15)
- Has phone / email on file (+5 each)
- Multi-location or regional service area mentioned in tags (+20)
- 5+ years since `start_date` tag (+10)
- "Commercial", "industrial", "multi-family" keywords (+10)
- High-revenue trade category: HVAC, electrical, roofing, plumbing, GC (+10)
- Located in an urban metro — Vancouver, Surrey, Burnaby, Richmond, Victoria, Coquitlam, Langley (+15)
- ≥50 Google reviews (Places only) (+10)

Each lead also gets research URLs so **you** can confirm revenue manually in one click:

- Google search
- Google Maps
- LinkedIn company search
- OpenCorporates (BC jurisdiction)
- BC Registry

**When you're ready to upgrade**, paste a Google Places API key into `config.py` (`GOOGLE_PLACES_API_KEY`) or set the env var `MARKETING_HERO_PLACES_KEY`. The generator will automatically pull richer data (ratings, review counts, place IDs) alongside OSM. For even better revenue data, a paid enrichment layer (Apollo, ZoomInfo, Dun & Bradstreet) can be bolted on by adding a function that hits their API after `score_lead()` in `lead_generator.py`.

## Tuning

Everything tunable lives in `config.py`:

- `TARGET_REVENUE_MIN/MAX` — the band you care about (affects reporting only)
- `BC_TARGET_AREAS` — which BC cities to farm; edit the list to match your outreach geography
- `TRADE_CATEGORIES` — which trades to include; add/remove entries freely
- `MAX_NEW_LEADS_PER_RUN` — daily quota (default 40)
- `MAX_TOTAL_LEADS` — cap on total leads on file before pruning (default 2000)
- `SCORE_WEIGHTS` — shift the scoring priorities
- `MIN_FIT_SCORE` — leads below this score are rejected (default 25)

## Dashboard model

The dashboard blends a **weighted-mix deal size** (from the Service Mix sliders, which use exact Five Talents tier prices from the April 2026 proposal) with a **manual override** at 70/30 — you can anchor to a number you have in mind without fighting the mix.

The 12-month revenue chart rolls forward monthly cohorts: each month's new-client cohort adds MRR for the contract length, then drops off. Setup fees are recognized in the month of signing. Gross profit = annual revenue × (1 − delivery cost %); net = gross − overhead × 12.

The "break-even leads/day" KPI solves for the lead volume where annual net profit = 0, using the current funnel and economics.

## Files

```
marketing_hero/
├── config.py              # tune everything here
├── lead_generator.py      # daily scraper + scorer
├── dashboard.html         # open in browser
├── run_daily.bat          # Task Scheduler entry point
├── README.md              # this file
└── data/
    ├── leads.json         # canonical store
    ├── leads.js           # script-tag version the dashboard reads
    └── run_log.txt        # appended each run
```

## Service catalogue reference (hard-coded in dashboard.html)

These values come from `Five_Talents_New_Services_Proposal.pdf` (April 2026):

| Service      | Monthly (target) | Setup / project |
|--------------|------------------|-----------------|
| Compounding  | $2,000           | —               |
| Dominion CMO | $7,500           | —               |
| Order COO    | $9,000           | —               |
| Multiplier AI| $1,500           | $12,000         |
| Cornerstone  | $300 (care plan) | $14,000         |
| Herald SEO   | $3,500           | —               |

If pricing changes, update the `SERVICES` array at the top of the `<script>` block in `dashboard.html`.
