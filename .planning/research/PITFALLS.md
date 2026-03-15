# Domain Pitfalls: v1.3 Contact Discovery

**Domain:** Adding contact search/discovery, enrichment completeness, and browse/filter capabilities to existing personal CRM (Reconnect v1.3)
**Researched:** 2026-03-14
**Confidence:** HIGH for architecture-specific pitfalls (codebase reviewed, PostgREST/PostgreSQL docs verified); MEDIUM for enrichment API cost traps (pricing confirmed from multiple sources, specific free-tier limits for RapidAPI not published publicly); HIGH for migration patterns (official PostgreSQL generated column docs verified)

---

## Critical Pitfalls

Mistakes that cause rewrites, silent data corruption, or hard-to-reverse behavioral regressions.

---

### Pitfall 1: Extracting JSON Fields Into Generated Columns Breaks SQLite Local DB

**What goes wrong:**
The v1.3 goal of making `raw_enrichment` searchable (education, industry, location, skills) naturally points toward PostgreSQL generated columns:

```sql
-- Supabase side — works fine
ALTER TABLE connections ADD COLUMN industry_extracted TEXT
  GENERATED ALWAYS AS (
    COALESCE(raw_enrichment->>'company_industry', raw_enrichment->'data'->>'company_industry')
  ) STORED;
```

The problem: `SQLModel` definitions in `models.py` drive **both** the local SQLite schema and Supabase PostgreSQL. Generated column syntax is PostgreSQL-only — `GENERATED ALWAYS AS (...) STORED` is not valid SQLite DDL. If the generated column is added to `models.py`, the local database breaks on the next `init_db()` call.

The v1.2 signal foundation already encountered this: `idx_outreach_queue_active_unique` is PostgreSQL-only and was explicitly kept out of `models.py` (see comment in `20260311000000_signal_foundation.sql` line 59). The same pattern must apply to any generated columns.

**Why it happens:**
The SQLModel/SQLAlchemy ORM is used for both the local SQLite schema and the cloud PostgreSQL schema. Any column definition in `models.py` must be valid for both database engines. PostgreSQL features like generated columns and partial indexes do not exist in SQLite.

**Consequences:**
- `init_db()` raises `OperationalError: near "GENERATED": syntax error` on first pipeline run after migration
- SQLite local database is left in a half-migrated state
- Rollback requires dropping the column from `models.py` and re-running migrations

**Prevention:**
Keep all generated columns and PostgreSQL-only indexes exclusively in Supabase migration SQL files — never in `models.py`. The generated column exists only in Supabase. Local filtering of `raw_enrichment` for search continues client-side in JavaScript or via Python SQLAlchemy JSON queries.

Maintain this pattern:
```
models.py        → both SQLite + PostgreSQL schema (portable columns only)
supabase/migrations/*.sql → PostgreSQL-only features (generated columns, partial indexes, GIN indexes)
```

**Warning signs:**
- `OperationalError` or `DatabaseError` mentioning `GENERATED` or `STORED` keyword during pipeline startup
- Local SQLite database missing expected columns after pipeline run
- `models.py` diff contains `sa_column=Column(...)` with `server_default` pointing to a function expression

**Phase to address:** Data extraction / enrichment completeness phase — generated column migrations must be Supabase-only from the start.

---

### Pitfall 2: PostgREST Cannot Filter JSONB Fields Directly — Wrong Architecture for Server-Side Search

**What goes wrong:**
The current industry filter already works client-side because PostgREST cannot filter nested JSON without generated columns:

```javascript
// From queue.js line 86 — correct, but fragile pattern
const industry = (enrichment.raw_enrichment?.data || enrichment.raw_enrichment || {}).company_industry;
```

For v1.3 search ("Sales leader, University of Miami"), the temptation is to send the query to PostgREST using ilike on the JSONB column:

```javascript
// WRONG — this will fail with "operator does not exist: jsonb ~~ unknown"
db.from('connections').select('*').ilike('raw_enrichment->company_industry', '%SaaS%')
```

PostgREST's ilike filter maps to the SQL `~~` operator. The `~~` operator does not exist for `jsonb` type. The filter silently returns 0 rows or throws an error depending on PostgREST version, rather than returning an informative message.

Even if PostgREST supported this, filtering on unindexed JSONB fields requires a full sequential scan of the `connections` table — at 5,000+ contacts with multi-KB `raw_enrichment` blobs, this will be slow.

**Why it happens:**
PostgREST translates HTTP query parameters directly to SQL operators. The `jsonb` type has its own operators (`@>`, `#>>`) that are not aliased to the standard text operators PostgREST uses for `ilike`/`like`/`eq`. The workaround (cast to text: `raw_enrichment::text ilike '%...'`) works in raw SQL but PostgREST does not accept inline casts in filter parameters.

**Consequences:**
- Search returns 0 results even when matching contacts exist
- Developers add a workaround (cast to text) in raw SQL then discover PostgREST cannot express it
- The fix requires adding a Supabase RPC (stored procedure) or generated columns, which adds migration complexity mid-phase

**Prevention:**
For v1.3, use one of these two architectures — not ad-hoc JSONB filtering:

**Option A (recommended for v1.3): Client-side search on full fetch**
Fetch all connections with `SELECT *` (within PostgREST 1000-row limit), filter client-side in JavaScript. Works for the current dataset size. Fast — no round-trip for each filter change. Requires pagination awareness.

**Option B: PostgreSQL full-text search via tsvector generated column + GIN index (Supabase-only migration)**
```sql
-- In supabase migration only — NOT in models.py
ALTER TABLE connections ADD COLUMN IF NOT EXISTS search_vector tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english',
      COALESCE(name, '') || ' ' ||
      COALESCE(current_role, '') || ' ' ||
      COALESCE(current_company, '') || ' ' ||
      COALESCE(location, '') || ' ' ||
      COALESCE(raw_enrichment->>'company_industry', '') || ' ' ||
      COALESCE(raw_enrichment->'data'->>'company_industry', '') || ' ' ||
      COALESCE(raw_enrichment->>'about', '') || ' ' ||
      COALESCE(raw_enrichment->'data'->>'about', '')
    )
  ) STORED;
CREATE INDEX IF NOT EXISTS idx_connections_search_vector ON connections USING GIN(search_vector);
```

PostgREST supports `.textSearch('search_vector', query)` which maps to the `@@` operator — this works correctly. The Supabase JS client exposes this as `.textSearch(column, query)`. Education data from `raw_enrichment->'data'->'educations'` must be pre-extracted into a separate denormalized text column or concatenated into the `search_vector` expression using a database trigger (not GENERATED ALWAYS, since the generated column expression cannot call functions that access aggregate JSON array data).

**Warning signs:**
- Search returns 0 results for queries that should match (test against known contacts)
- PostgREST returns HTTP 400 with "operator does not exist: jsonb"
- Developer shifts to `db.rpc('search_connections', {query})` without documenting the Supabase-only migration required

**Phase to address:** Search implementation phase — architecture decision must be made before any PWA code is written.

---

### Pitfall 3: Fetching All Connections Hits PostgREST 1000-Row Hard Limit

**What goes wrong:**
Client-side search requires fetching all connections from PostgREST. The default Supabase project configuration sets `db-max-rows = 1000`. If the connections table exceeds 1000 rows (which it will as LinkedIn contacts accumulate), `GET /rest/v1/connections` silently returns only the first 1000 rows. A search for a contact in row 1001+ will appear to return no results, with no error message indicating truncation.

The current queue fetch works fine because `outreach_queue` typically has 5-20 rows. But a "browse all contacts" view or global search must handle the full connections table.

**Why it happens:**
PostgREST adds a hard LIMIT equal to `db-max-rows` to every query. Unlike a SQL LIMIT clause, this does not produce an error when hit — the response simply stops at 1000 rows. The Supabase JS client does not raise an exception when the row limit is reached; it returns the partial dataset with a count hint in response headers.

**Consequences:**
- Search silently misses contacts beyond row 1000
- A user searching for a specific person gets "no results" even though the contact exists
- Problem only appears after sufficient LinkedIn imports — may not be caught in testing with small dataset

**Prevention:**
Use PostgREST pagination with explicit `range` headers or `select` with `limit`/`offset` for the browse view. For client-side search, fetch in pages of 500 and merge results before filtering:

```javascript
async function fetchAllConnections() {
  const PAGE_SIZE = 500;
  let allConnections = [];
  let from = 0;
  let hasMore = true;

  while (hasMore) {
    const { data, error } = await db
      .from('connections')
      .select('id, name, current_role, current_company, location, raw_enrichment, latest_signal, reconnect_score')
      .range(from, from + PAGE_SIZE - 1);

    if (error || !data) break;
    allConnections = allConnections.concat(data);
    hasMore = data.length === PAGE_SIZE;
    from += PAGE_SIZE;
  }
  return allConnections;
}
```

Only select the fields needed for search display (not `activity_log`, `score_reasoning`, or other large text columns) to keep payload size manageable.

**Warning signs:**
- Search returns results for contacts with names A-M but not N-Z (alphabetical truncation suggesting default ordering)
- Total contact count in browse view does not match what's shown in dashboard stats
- Adding the `Prefer: count=exact` header reveals `Content-Range: 0-999/1247` (1247 total, 1000 returned)

**Phase to address:** Browse/search phase — pagination must be built before the first client-side search implementation ships.

---

### Pitfall 4: Re-Enriching Already-Enriched Contacts Burns API Budget Without New Data

**What goes wrong:**
The v1.3 enrichment completeness phase will identify contacts with incomplete `raw_enrichment` (missing education, skills, industry). The enrichment planner (`enrichment_planner.py`) currently runs Tier 4 re-enrichment for contacts where `enriched_at > 90 days`. But contacts enriched within 90 days may also have missing education/skills data — they were enriched but the RapidAPI response simply did not include those fields (the contact has no public LinkedIn education listed, or the API returned a partial profile).

If the completeness analyzer marks these contacts as "missing education" and the enrichment planner adds them to the budget, the pipeline will call RapidAPI again for the same contact. The second API call returns the same partial data. The contact is charged against the daily budget (default: 30 contacts/day), the API cost is incurred, and the data completeness score does not change.

The existing code in `update_connection_from_profile()` has no guard to detect "this API response is no better than what we already have" — it overwrites `raw_enrichment` unconditionally.

**Why it happens:**
The enrichment planner uses `enriched_at` as a proxy for data quality. An old `enriched_at` means "stale data, re-enrich." But "data the API cannot provide" (e.g., a contact who never filled in their education on LinkedIn) will never improve regardless of how many times it is fetched. The API cannot invent data that does not exist on the public LinkedIn profile.

**Consequences:**
- Daily API budget consumed by re-fetching contacts with permanently incomplete profiles
- Higher-priority unenriched contacts are never reached because budget is exhausted by re-enrichment loops
- At RapidAPI's metered overage rate (~$0.0065/request on the Ultra plan), 30 wasted calls/day = ~$0.20/day = ~$6/month in unnecessary API cost

**Prevention:**
Before adding a contact to the enrichment plan for completeness reasons, check whether their missing fields are "API-provided" or "LinkedIn-optional":

```python
# In enrichment_planner.py — add enrichment guard
PERMANENTLY_OPTIONAL_FIELDS = {"educations", "school", "degree"}

def _is_worth_re_enriching(connection: Connection, missing_fields: list[str]) -> bool:
    """Return False if all missing fields are ones the API cannot reliably provide."""
    api_improvable = set(missing_fields) - PERMANENTLY_OPTIONAL_FIELDS
    if not api_improvable:
        return False
    # Also skip if re-enriched in last 30 days with same missing fields
    if connection.enriched_at and (datetime.utcnow() - connection.enriched_at).days < 30:
        return False
    return True
```

Track "enrichment attempt count" on contacts where re-enrichment did not improve completeness. After 2 failed attempts, mark those specific fields as "unfetchable" in `missing_data_fields` with a flag like `{"field": "education", "unfetchable": true}` to prevent future scheduling.

**Warning signs:**
- Pipeline logs show the same contact IDs being enriched on consecutive days
- `data_completeness_score` for re-enriched contacts does not increase after pipeline run
- Daily budget exhausted by `re_enrichment` tier contacts while `priority_contacts` still show 0

**Phase to address:** Enrichment completeness phase — guard logic must be added before any re-enrichment budget is allocated based on completeness scores.

---

### Pitfall 5: Education Search Requires Array Traversal That Neither PostgREST Nor Client-Side JSON Handles Well

**What goes wrong:**
Education data from RapidAPI is stored as an array of objects in `raw_enrichment`:

```json
{
  "educations": [
    { "school": "University of Miami", "degree": "MBA", "field_of_study": "Marketing", "end_year": 2018 },
    { "school": "Florida State University", "degree": "B.S.", "field_of_study": "Business", "end_year": 2015 }
  ]
}
```

A search for "University of Miami" must find this contact. But the education data is a nested array — not a flat field. Three failure modes emerge:

1. **PostgREST filter**: `raw_enrichment @> '{"educations": [{"school": "University of Miami"}]}'` — the JSONB containment operator works in raw SQL but requires an exact subset match. If the stored school name is "Univ. of Miami" or "UM Business School", the match fails. Fuzzy matching on nested JSONB arrays via PostgREST is not supported.

2. **Client-side filter**: `JSON.stringify(raw_enrichment).includes('University of Miami')` — works, but catches partial matches inside unrelated field values (e.g., a contact whose `about` mentions "I studied in Miami").

3. **Generated column approach**: You cannot use `GENERATED ALWAYS AS` to aggregate values from a JSONB array into a text column because the generated column expression cannot call functions that involve set-returning functions or aggregates over array elements. A trigger or a denormalized `education_text` column (written by the enrichment pipeline) is required instead.

**Why it happens:**
The RapidAPI response design stores multi-valued attributes (education, experience) as arrays. This is the correct data model for the source data, but it creates an impedance mismatch for search — search needs flat text, the storage model is hierarchical.

**Consequences:**
- Education-based search silently returns 0 results even for exact matches
- Workarounds (stringify + includes) produce false positives and cannot rank by relevance
- Adding a trigger later to maintain a denormalized column is a non-trivial Supabase migration that requires re-running the enrichment pipeline to backfill existing rows

**Prevention:**
In the enrichment pipeline (`update_connection_from_profile()`), extract education data into a flat denormalized column at write time:

```python
# In rapidapi_linkedin.py — add extraction after line 163
education_parts = []
for edu in (data.get("educations") or data.get("education") or []):
    parts = [edu.get("school"), edu.get("degree"), edu.get("field_of_study")]
    education_parts.append(" ".join(p for p in parts if p))
if education_parts:
    connection.education_text = " | ".join(education_parts)
```

Add `education_text TEXT` as a regular nullable column to `models.py` (works in both SQLite and PostgreSQL). This column is included in the Supabase `search_vector` generated column and can be indexed independently. Backfill existing contacts by re-running the extraction over their existing `raw_enrichment` data without calling the API.

**Warning signs:**
- Education-based search returns 0 results for contacts that have education in their raw_enrichment
- Search for "MBA" finds 0 contacts even though many contacts have MBA entries in their educations array
- SQL query `SELECT raw_enrichment->'educations'->0->>'school' FROM connections` returns data but search finds nothing

**Phase to address:** Data extraction phase — denormalized columns must be extracted before search UI is built. Backfill is a one-time pipeline step over existing raw_enrichment data.

---

## Moderate Pitfalls

---

### Pitfall 6: Client-Side Fuzzy Search Must Avoid Per-Keystroke Re-Renders on Mobile

**What goes wrong:**
A search input that fires a filter on every `keyup` event works fine in testing on desktop with 50 contacts. With 1,000+ contacts fetched and held in memory, filtering on every keystroke triggers expensive DOM operations. Each filter pass iterates the full contacts array, rebuilds the result list, and repaints the DOM. On a mid-range Android phone, this produces visible input lag — the typing experience feels broken.

The existing queue.js `renderQueue()` function already has the "full re-render resets scroll position" problem identified in v1.2 PITFALLS.md (Pitfall 9). The browse/search view will be a new view with the same problem at larger scale.

**Why it happens:**
Client-side JavaScript filtering is synchronous and blocks the main thread during DOM operations. For arrays of 1,000+ objects each with multi-KB JSON enrichment data, the filter loop itself is fast, but the DOM reconstruction for even 50 result cards at once causes paint jank.

**Prevention:**
1. **Debounce search input**: 200ms debounce on the search handler — fire filter only after typing stops.
2. **Limit rendered results**: Show top 50 results with "Load more" pagination — do not render all matches at once.
3. **Keep enrichment JSON out of the DOM**: For the search results view, only render the extracted flat fields (`name`, `current_role`, `current_company`, `location`, `education_text`, `latest_signal`, `reconnect_score`). Do not serialize `raw_enrichment` into data attributes on card elements.
4. **Use document fragments**: Build the result list in a `DocumentFragment` before inserting into the DOM — single reflow instead of N reflows for N cards.

**Warning signs:**
- Typing in the search box produces visible lag (>100ms between keypress and visible result change)
- Profiler shows layout thrashing during search input events
- Memory usage spikes when opening the browse view (all raw_enrichment JSON loaded into JS heap)

**Phase to address:** Search UI phase — debounce and result limiting must be in the initial implementation, not added as a fix after.

---

### Pitfall 7: Enrichment Completeness Score Counts "API Can't Provide" Fields as Gaps, Skewing Prioritization

**What goes wrong:**
The current `data_completeness_score` in `data_analyzer.py` awards points for `education`, `about_summary`, and `skills`. Some contacts have no LinkedIn education listed (they never filled it in), no about section, and no skills — the API returns empty arrays for all three. These contacts score 0/25 for those fields permanently.

The completeness score is intended to prioritize which contacts to re-enrich. But permanently-empty contacts will always appear at the top of the "needs enrichment" list, consuming budget that should go to contacts where enrichment would actually improve the data.

At v1.3's focus on enrichment completeness for search, this creates a search problem: the browse view may offer a "completeness" sort that surfaces the wrong contacts. A user expects "low completeness" to mean "needs more data" — but many low-completeness contacts are already at their maximum achievable data level.

**Why it happens:**
The completeness analyzer has no concept of "field attempted but unavailable" vs "field not yet attempted." It measures presence/absence, not potential. The distinction requires tracking enrichment attempt outcomes, not just field values.

**Prevention:**
Add an `enrichment_ceiling` concept — track which fields have been attempted and returned empty vs. never attempted:

```python
# In missing_data_fields (JSON column on Connection), distinguish states:
# {"field": "education_text", "status": "missing"}    — not yet enriched
# {"field": "education_text", "status": "unfetchable"} — enriched, API returned nothing
# {"field": "education_text", "status": "present"}     — has data
```

Completeness score should penalize `"missing"` fields (fixable) but not `"unfetchable"` fields (permanent). The enrichment planner should skip contacts where all missing fields are marked `"unfetchable"`.

**Warning signs:**
- Completeness sort shows same 50 contacts at the bottom every day despite repeated enrichment runs
- `plan_enrichment()` repeatedly selects the same contacts for `re_enrichment` tier
- After enrichment run, `data_completeness_score` for re-enriched contacts is unchanged

**Phase to address:** Enrichment completeness phase — the completeness model must distinguish "missing" from "unfetchable" before completeness-based sorting is exposed in the browse UI.

---

### Pitfall 8: Search That Mixes Structured Filters and Free-Text Needs a Clear Precedence Model

**What goes wrong:**
The query "Sales leader, University of Miami" could be interpreted as:
- Free-text search across all fields for "Sales leader" AND "University of Miami"
- A structured filter: role contains "Sales" AND education contains "University of Miami"
- A boolean AND of two separate name searches

If the search interprets this as a single free-text query using `String.prototype.includes()` or tsvector FTS, and the contact's `current_role` is "VP of Sales" (not "Sales leader"), the match fails even though the contact is clearly a "sales leader."

The v1.3 feature description mentions: "flexible search bar to find contacts by criteria ('Sales leader, University of Miami')". This implies natural-language query parsing — which is either an LLM call (expensive) or a client-side heuristic parser (cheap but requires explicit design).

**Why it happens:**
"Flexible search" without a defined query model produces inconsistent results that users cannot predict. When search fails to find an expected contact, users lose trust in the feature entirely — a worse outcome than a more limited but predictable search.

**Prevention:**
Define a simple, explicit query model before implementing search:

| Input pattern | Interpretation | Example |
|--------------|----------------|---------|
| `"John Smith"` | Name exact/fuzzy match | Searches `name` field |
| `"@Google"` | Company filter | Prefix `@` means company |
| `"#Sales"` | Role/industry filter | Prefix `#` means role or industry |
| `"Miami"` | Location filter | Single word, no prefix: location or name |
| `"Sales leader, University of Miami"` | Comma-split AND: each term searched in role AND education_text | Comma = multi-field AND |

Document this model in the search placeholder text. Users who understand the model trust the results. Use a pure client-side tokenizer (split on commas, match each token across relevant fields) — no LLM call needed.

**Warning signs:**
- Search for a known contact by role returns "no results" even though the contact exists
- Users report search "works sometimes" — indicating undefined behavior in query parsing
- Attempts to add LLM-based query parsing creep into the codebase to "fix" search quality

**Phase to address:** Search design phase — query model must be documented and approved before UI implementation begins.

---

### Pitfall 9: RapidAPI Daily Budget Consumed by Enrichment-for-Search Before Queue Enrichment Gets Its Share

**What goes wrong:**
The enrichment planner allocates a `daily_enrich_budget` (config default: 30 contacts/day) across four tiers. The v1.3 enrichment completeness phase will add a fifth concern: contacts that have `raw_enrichment` but are missing education/skills needed for search. These contacts compete with the existing four tiers for the same 30-call budget.

If enrichment completeness is prioritized over Tier 1 (user-priority contacts missing all data) or Tier 2 (high-score contacts needing email), the queue quality degrades. High-score contacts that could be reached out to via email are not enriched; contacts with partial data get a second enrichment pass for search purposes.

At the RapidAPI Ultra plan rate ($200/month for 100,000 requests, ~$0.002/call), 30 calls/day = ~$1.80/month in API cost. The free tier has a hard request cap that is not published publicly — research found only that a "Basic plan for testing" exists with an unspecified limit. Running out of free-tier requests mid-day causes `fetch_linkedin_profile()` to return `None` for all subsequent contacts that day.

**Why it happens:**
The enrichment planner was designed for a single concern: filling in missing core data (company, role, email). The v1.3 completeness-for-search goal introduces a competing concern that uses the same budget. Without explicit budget allocation between concerns, the planner will fill whichever tier has the most candidates — which may be completeness, not queue quality.

**Prevention:**
Make budget allocation explicit in the enrichment plan:

```python
# Proposed budget allocation for v1.3
BUDGET_ALLOCATION = {
    "priority_contacts": 0.30,       # 30% — user-priority, no enrichment
    "email_finding": 0.25,            # 25% — high score, no email
    "activity_refresh": 0.20,         # 20% — missing activity hooks
    "completeness_for_search": 0.15,  # 15% — NEW: has enrichment, missing search fields
    "re_enrichment": 0.10,            # 10% — stale data (>90 days)
}
```

Add a daily budget cap check at the start of each pipeline run:

```python
# Early warning before enrichment step runs
if plan["allocated"] >= settings.daily_enrich_budget:
    logger.warning("Enrichment budget fully allocated — completeness tier may get 0 calls today")
```

Monitor RapidAPI quota usage by checking the response headers (`X-RateLimit-Requests-Remaining`) on each call. Log remaining quota. Alert (via pipeline stats) when remaining quota drops below 20% of daily budget.

**Warning signs:**
- Pipeline logs show `re_enrichment` tier consuming 25+ of 30 daily budget slots while `priority_contacts` tier gets 0
- `fetch_linkedin_profile()` returns `None` after the 10th contact in a single pipeline run (free tier exhausted)
- Queue quality metrics (% of queue items with email available) stops improving despite daily enrichment runs

**Phase to address:** Enrichment completeness phase — budget allocation must be refactored before adding the new completeness tier to the planner.

---

### Pitfall 10: Browse View Fetch Includes `raw_enrichment` JSON Blob — Payload Too Large for Free Tier

**What goes wrong:**
The current `CONNECTION_SYNC_FIELDS` in `push.py` includes `raw_enrichment`. The RapidAPI response for a single contact can be 15-30 KB of JSON (experiences, skills, posts, followers, company details). For 500 contacts, this is 7.5-15 MB of JSON fetched from Supabase PostgREST on every browse view load.

On the Supabase free tier with 500 MB storage, 500 contacts × 20 KB average = 10 MB just for `raw_enrichment` data. This is within storage limits, but the network payload for a full browse fetch is problematic:
- Mobile connections: 15 MB fetch = 3-8 seconds on LTE, unacceptable for a browsing experience
- Supabase free tier egress: 5 GB/month included. A user opening the browse view 10 times/day × 15 MB × 30 days = 4.5 GB — nearly the entire monthly egress allowance for one feature

**Why it happens:**
The current `select('*')` pattern in the PWA fetches all columns. This was fine for the queue (5-20 rows) and the contact profile (1 row, detail view). A browse-all-contacts view is structurally different — it fetches hundreds of rows but does not need the full data for each row.

**Prevention:**
Never use `select('*')` for the browse/search view. Define explicit field lists for each view type:

```javascript
// Browse view — display fields only (no raw blobs)
const BROWSE_SELECT = 'id, name, current_role, current_company, location, reconnect_score, latest_signal, data_completeness_score, enriched_at, education_text';

// Search view — same as browse plus computed text for client-side matching
const SEARCH_SELECT = BROWSE_SELECT + ', education_text, tags, notes';

// Contact profile — full detail (1 row only)
const PROFILE_SELECT = '*, contact_signals(*), contact_notes(*)';
```

Add the `education_text` denormalized column (Pitfall 5) to the browse select list — this removes the need to fetch `raw_enrichment` just to display education data.

**Warning signs:**
- Browse view takes >2 seconds to load on a mobile connection
- Supabase dashboard shows unusually high "Database Egress" in the metrics panel
- Chrome DevTools network panel shows the connections fetch response is >1 MB

**Phase to address:** Browse UI phase — field selection must be scoped before the fetch is implemented, not added as optimization after launch.

---

## Minor Pitfalls

---

### Pitfall 11: Search Index (tsvector) Not Updated When Pipeline Re-Enriches Contacts

**What goes wrong:**
If Option B (tsvector generated column) is used for search, the generated column automatically updates when `raw_enrichment` is updated via a direct SQL UPDATE. However, the pipeline's `update_connection_from_profile()` writes to the local SQLite database, not directly to Supabase PostgreSQL. The sync push (`push.py`) then upserts the row to Supabase.

The upsert via `psycopg2` updates `raw_enrichment` — which triggers the generated column recomputation in PostgreSQL. This is correct. However, if `education_text` is a regular column written by the pipeline (Pitfall 5 prevention), and the upsert does not include `education_text` in `CONNECTION_SYNC_FIELDS`, the search index will be stale.

**Prevention:**
Add `education_text` (and any other search-relevant denormalized columns) to `CONNECTION_SYNC_FIELDS` in `push.py` before the v1.3 milestone ships. Use the existing field coverage pattern — the push sync explicitly lists every field it syncs.

**Warning signs:**
- Re-enriched contacts do not appear in education-based search even after pipeline run and sync
- Supabase `connections` table shows NULL for `education_text` on recently enriched contacts

---

### Pitfall 12: Enrichment API Key Rotation Leaves Old Enrichment Data with No Version Tag

**What goes wrong:**
If the RapidAPI key is rotated (e.g., billing failure, plan downgrade, key compromise), previously enriched contacts have no record of which API key or plan was used to fetch their data. If a new plan returns different data shapes (e.g., field name changes from `company_industry` to `industry`), the existing `raw_enrichment` blobs have a different schema than new enrichments. The `get_enrichment_data()` helper handles `data` envelope vs flat format, but cannot handle field name changes without updates to every consumer.

**Prevention:**
The existing `_source: "rapidapi"` and `_fetched_at` fields in `raw_enrichment` (added by `fetch_linkedin_profile()`) already provide basic provenance. Add `_api_version` or `_schema_version` to help detect schema drift in future:

```python
profile_data["_schema_version"] = "rapidapi-v2"  # increment when field names change
```

---

### Pitfall 13: "Browse All Contacts" View Has No Empty State for Unenriched Contacts

**What goes wrong:**
Contacts imported from LinkedIn CSV but not yet enriched have no `current_role`, no `location`, no `reconnect_score`, no `education_text`. A browse view that expects these fields will show blank cards — which looks like a bug, not expected behavior. Users may think the import failed.

**Prevention:**
Treat unenriched contacts as first-class browse objects. Show a "Needs enrichment" badge with `data_completeness_score` and the count of missing fields. Never show a blank card — always show name + `connection_source` + `connected_on` as a minimum.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems in the context of v1.3.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Add generated column to `models.py` instead of a migration-only SQL file | Single-source schema definition | SQLite compatibility breaks on next init_db() | Never — generated columns must stay in Supabase migration SQL |
| Filter `raw_enrichment` with `ilike` via PostgREST | No migration needed | Returns 0 results or error; no semantic filtering possible | Never — use client-side filter or tsvector |
| `select('*')` for browse view | Simple code | 15 MB+ payload on mobile; approaches Supabase free tier egress limit | Acceptable only for contact profile (single row) |
| Re-enrich contacts with low completeness without checking "unfetchable" status | Simpler enrichment planner | Wastes daily API budget; same contacts enriched repeatedly; higher-priority contacts never reached | Never — add unfetchable guard before v1.3 enrichment completeness ships |
| Per-keystroke filter without debounce | Simple event handler | Input lag on mobile with 1000+ contacts; perceived as broken | Acceptable in initial prototype; must add debounce before user testing |
| Fetch educations from raw_enrichment array client-side at render time | No migration needed | Cannot include in tsvector; education search requires stringify + includes (false positives) | Acceptable as interim for Phase 1 of v1.3; replace with denormalized column in Phase 2 |
| Use LLM to parse search queries | "Smart" search | ~$0.01/search query × daily usage = significant monthly cost; adds latency; breaks offline mode | Never for simple field matching; acceptable only if semantic search is an explicit feature |

---

## Integration Gotchas

Common mistakes when wiring the new search/discovery features into the existing stack.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Generated columns in Supabase migration | Adding generated column definition to SQLModel model class in models.py | Keep all generated columns and GIN indexes in supabase/migrations/ SQL files only; models.py stays portable |
| PostgREST + JSONB filtering | Using `.ilike('raw_enrichment->company_industry', '%SaaS%')` | Use `.textSearch('search_vector', query)` against a tsvector generated column, or filter client-side |
| Browse view data fetch | `select('*')` to fetch all contacts | Explicit field list: `id, name, current_role, current_company, location, reconnect_score, latest_signal, education_text` |
| PostgREST row limit | Assuming single fetch returns all contacts | Paginate at 500 rows, merge arrays before client-side filtering |
| Enrichment planner + completeness | Adding completeness tier without budget allocation | Define explicit percentage budget per tier; monitor remaining API quota in pipeline logs |
| Education search | Filtering on `raw_enrichment.educations` array via JS | Extract to flat `education_text` column at enrichment write time; search the flat column |
| Sync + new denormalized columns | Adding `education_text` to models.py but not to CONNECTION_SYNC_FIELDS | Every new searchable column must be added to `CONNECTION_SYNC_FIELDS` in push.py |

---

## Performance Traps

Patterns that work at current scale but break as contacts accumulate.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `select('*')` on all connections | Browse view load time >2s on mobile; high Supabase egress | Explicit column selection for browse/search views | At ~200 contacts with multi-KB raw_enrichment blobs |
| No PostgREST pagination for browse fetch | Contacts beyond row 1000 silently missing from search results | Explicit range-based pagination: `.range(from, from + 499)` | Exactly when connections table exceeds 1000 rows |
| Full array scan on raw_enrichment for education search | Education search produces false positives; `JSON.stringify(blob).includes()` is O(n×m) | Denormalized `education_text` column extracted at enrichment time | Immediately visible with >100 contacts and multi-KB enrichment blobs |
| Per-keystroke DOM rebuild of search results | Input lag on mid-range Android; >100ms between keypress and visual update | 200ms debounce + DocumentFragment bulk insert + 50-result display limit | At 500+ result cards rendered to DOM |
| Re-enrichment loop for permanently-missing fields | API budget depleted daily; higher-priority contacts never enriched | `unfetchable` status in `missing_data_fields`; budget allocation percentages | As soon as completeness-based re-enrichment is enabled |

---

## Cost Traps

Specific to enrichment APIs and AI-powered search for this budget-constrained setup.

| Trap | Monthly Cost Estimate | Trigger | Prevention |
|------|-----------------------|---------|------------|
| LLM-based search query parsing (per-query OpenAI call) | ~$2-15/month at 200 searches/month @ $0.01-$0.07/call (GPT-4o-mini) | Adding "smart search" with LLM query interpretation | Client-side tokenizer with comma-split AND logic; no LLM call for search |
| Re-enriching unfetchable contacts daily | ~$6/month in RapidAPI overage at $0.0065/call × 30 calls/day | Completeness-based re-enrichment without "unfetchable" guard | Track enrichment attempt outcomes; mark permanently-empty fields as unfetchable |
| `select('*')` browse fetch consumed by egress | Approaches 5 GB free tier egress limit with 10+ daily browse sessions | Browse view fetching all columns for all contacts | Explicit narrow field selection for browse/search; never fetch `raw_enrichment` or `activity_log` in list views |
| Vector embeddings for semantic contact search | $0.10-1.00/month for pgvector on Supabase free tier (pgvector extension available) | Choosing vector search over client-side fuzzy for "AI contact search" | Reserve vector search for explicit phase; client-side fuzzy search sufficient for v1.3 |
| RapidAPI free tier exhaustion mid-day | Pipeline halts enrichment silently | Daily budget not tracking remaining API quota | Log `X-RateLimit-Requests-Remaining` from response headers; alert when <20% of plan limit remains |

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Enrichment completeness audit | Marking "unfetchable" fields as completeness gaps, triggering wasted re-enrichment | Distinguish "missing" vs "unfetchable" in missing_data_fields before completeness score drives enrichment prioritization |
| Data extraction (JSON → columns) | Adding generated column to models.py (breaks SQLite) | All generated columns and GIN indexes go in supabase/migrations/ only |
| Data extraction (education) | Expecting PostgREST to handle JSONB array filtering | Extract to flat `education_text` column in Python enrichment code; write at enrichment time |
| Search implementation | Fetching `select('*')` to enable client-side search | Define explicit field list; paginate at 500 rows |
| Browse UI | PostgREST 1000-row hard limit silently truncates results | Paginate with `.range()` and merge; test with >1000 contact dataset |
| Search UX | Per-keystroke DOM rebuild producing mobile input lag | 200ms debounce + 50-result limit + DocumentFragment pattern |
| Budget allocation | Completeness tier consuming entire enrichment budget | Explicit percentage allocation in enrichment_planner.py before completeness tier ships |

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Generated column in models.py breaks SQLite | MEDIUM | Remove column from models.py; keep only in Supabase migration SQL; re-run local SQLite init; no data loss (column was new) |
| PostgREST JSONB filter returning 0 results | LOW | Switch to client-side filter or add tsvector column via Supabase-only migration; no data migration needed |
| Browse view missing contacts beyond row 1000 | LOW | Add pagination loop to fetch; no data loss (data always existed in Supabase) |
| Enrichment budget consumed by re-enrichment loops | MEDIUM | Identify contacts being re-enriched repeatedly; mark missing fields as "unfetchable" in missing_data_fields; reset enrichment planner priority |
| Search producing false positives from stringify approach | LOW | Add `education_text` extracted column; backfill from existing raw_enrichment via one-time Python script; no API calls needed for backfill |
| Supabase egress approaching 5 GB limit | LOW | Scope select fields immediately; egress drops on next deploy; no data loss |
| LLM search query parsing added mid-phase | LOW | Revert to client-side tokenizer; LLM integration is additive, removal is a one-file change |

---

## Sources

- Existing codebase (reviewed): `src/database/models.py`, `src/ingestion/rapidapi_linkedin.py`, `src/llm/data_analyzer.py`, `src/pipeline/enrichment_planner.py`, `src/sync/push.py`, `pwa/js/queue.js`, `supabase/migrations/20260311000000_signal_foundation.sql`
- PostgREST JSONB filtering limitation (confirmed): https://github.com/PostgREST/postgrest/issues/240
- Supabase full text search with tsvector generated columns: https://supabase.com/docs/guides/database/full-text-search
- PostgreSQL generated columns (STORED syntax, SQLite incompatibility): https://www.postgresql.org/docs/current/ddl-generated-columns.html
- PostgREST pagination and max-rows limit: https://docs.postgrest.org/en/v12/references/api/pagination_count.html
- Supabase free tier limits (500 MB storage, 5 GB egress): https://uibakery.io/blog/supabase-pricing
- RapidAPI fresh-linkedin-profile-data pricing ($0.0065/call overage on Ultra plan): https://rapidapi.com/freshdata-freshdata-default/api/fresh-linkedin-profile-data/pricing
- API rate limiting and deduplication best practices: https://derrick-app.com/en/rate-limits-quotas-api-2/
- JSONB search in Supabase (community discussion): https://github.com/orgs/supabase/discussions/12677
- Previous v1.2 pitfalls (signal model migration, sync patterns): `.planning/research/PITFALLS.md` (v1.2 version)

---
*Pitfalls research for: Reconnect v1.3 Contact Discovery milestone*
*Researched: 2026-03-14*
