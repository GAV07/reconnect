# Architecture Patterns

**Domain:** Personal networking tool — contact search/discovery + enrichment extraction (v1.3)
**Researched:** 2026-03-14
**Confidence:** HIGH (derived from direct codebase inspection + verified PostgREST/PostgreSQL documentation)

---

## System Overview (Current State, post-v1.2)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         LOCAL MACHINE (macOS)                            │
├──────────────────────────────────────────────────────────────────────────┤
│  LaunchAgent (8AM) → reconnect pipeline run (Click CLI)                  │
│  daily_pipeline.py (10 steps):                                            │
│    Step 2: enrich → rapidapi_linkedin.py → raw_enrichment JSON            │
│    Step 7: data completeness → data_completeness_score + missing_fields   │
│    Step 9: enrichment_planner → plan_enrichment() budget allocation       │
│                                                                           │
│  SQLite (source of truth)                                                 │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ connections (raw_enrichment: JSON, data_completeness_score: float)│   │
│  │ connections (current_role, current_company, location: TEXT cols)  │   │
│  │ outreach_queue, contact_signals, contact_notes + more             │   │
│  └───────────────────────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────────────┤
│                    SYNC (bidirectional, daily)                            │
│  push.py → Supabase PostgreSQL ← pull.py                                 │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                         SUPABASE (Cloud)                                  │
├──────────────────────────────────────────────────────────────────────────┤
│  PostgreSQL (mirror of local, raw_enrichment as JSONB)                   │
│                                                                           │
│  PostgREST API ◄──── PWA (anon key)                                      │
│  Supports: ilike, or(), textSearch(), eq(), order(), select()            │
│  Cannot: filter on JSONB path, filter on embedded resource fields        │
│                                                                           │
│  Edge Functions: action (email tokens), draft (OpenAI)                   │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                         PWA (Netlify — Vanilla JS)                        │
├──────────────────────────────────────────────────────────────────────────┤
│  Current pages: queue.js, contact.js, dashboard.js, preferences.js       │
│  All reads/writes via PostgREST (supabase-js client)                     │
│  Client-side filtering: signal, industry (from raw_enrichment JSON)      │
│  New v1.3: contacts.js (browse/search page)                              │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## The Core Problem: raw_enrichment is a JSON Blob

The current architecture stores all enrichment API results in `connections.raw_enrichment` as a single JSON column. This is the root cause of all search/filter limitations:

```javascript
// Current pattern in queue.js — reading from JSONB in browser:
const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
const industry = enrichment.company_industry || enrichment.companyIndustry || '';
```

**Why this prevents server-side search:**

PostgREST cannot filter on JSONB path expressions. The `ilike`, `eq`, and `textSearch` operators work only on first-class PostgreSQL columns, not on JSONB subfield paths. A query like "where raw_enrichment->>'company_industry' ilike '%tech%'" is not expressible through the PostgREST REST API — it requires raw SQL.

**The consequence is that all current filtering is client-side:** the PWA fetches all records and filters in JavaScript. This works at current scale (~few hundred synced contacts) but breaks as the browse/search use case requires showing all contacts (not just queue items).

---

## v1.3 Solution: Extract JSON Fields to Real Columns

The correct solution is to extract the fields needed for search and filtering from `raw_enrichment` into first-class `TEXT` columns on `connections`. Once they are real columns, PostgREST can filter, sort, and search them natively.

### Fields to Extract

Based on the RapidAPI response shape (confirmed in `rapidapi_linkedin.py` mock data and `update_connection_from_profile()`):

| Extracted Column | Source in raw_enrichment | Purpose |
|-----------------|--------------------------|---------|
| `enriched_industry` | `data.company_industry` or `data.companyIndustry` | Industry filter in browse/search |
| `enriched_headline` | `data.headline` | Full-text search inclusion |
| `enriched_location_city` | `data.city` | Location filter |
| `enriched_location_country` | `data.country` | Location filter |
| `enriched_school` | `data.educations[0].school` | Education search ("University of Miami") |
| `enriched_seniority` | derived from `data.job_title` or `data.headline` | Seniority filter |
| `enriched_follower_count` | `data.follower_count` | Influence/reach sorting |

Note: `current_role`, `current_company`, and `location` are **already** extracted (done in `update_connection_from_profile()`). These are already searchable via PostgREST. The gap is the richer fields above that currently live only in the JSON blob.

### Why Not Index the JSONB Directly?

A GIN index on `raw_enrichment` enables fast lookup for exact key-value matches (`@>` operator) but does not enable PostgREST's `ilike` or `textSearch` — those operators only work on regular columns. Generated columns from JSONB expressions (`GENERATED ALWAYS AS (raw_enrichment->>'company_industry') STORED`) are a cleaner path and allow standard B-tree or GIN indexes alongside PostgREST's native filter operators.

---

## Search Strategy: Hybrid (Not Purely Client-Side or Server-Side)

### Decision

Use **server-side filtering via PostgREST** for structured fields (industry, location, seniority) and **PostgreSQL full-text search via a `tsvector` generated column** for free-text queries ("Sales leader, University of Miami"). The PWA sends one parameterized PostgREST query; no client-side filtering is required for the search/browse page.

The existing client-side filtering in `queue.js` is preserved as-is — it works for the queue's smaller result set and is battle-tested.

### Why Not Pure Client-Side?

The queue page works client-side because it fetches only outreach_queue items (typically tens to low hundreds). A contact browse page would need to fetch all synced connections — potentially thousands of rows — before filtering. This is wasteful on mobile and grows worse over time.

### Why Not Pure Full-Text Search?

Full-text search via `tsvector` works well for open-ended queries but does not support structured filters like "show only Executives in Miami." The hybrid approach sends `textSearch` for the free-text query while stacking `eq` / `ilike` filters for structured facets. PostgREST supports chaining these in a single request.

### PostgREST Capabilities (Verified)

| PostgREST Feature | v1.3 Use Case | API Call |
|-------------------|---------------|----------|
| `ilike` | Case-insensitive industry/location partial match | `.ilike('enriched_industry', '%tech%')` |
| `.or()` with `ilike` | Multi-field keyword search across name, role, company | `.or('name.ilike.%query%,current_role.ilike.%query%,current_company.ilike.%query%')` |
| `textSearch` | Full-text search on `fts` tsvector column | `.textSearch('fts', 'sales miami', { type: 'websearch' })` |
| `eq` | Exact-match filters (signal, status) | `.eq('latest_signal', 'WARM_LEAD')` |
| `order` | Sort by score, name | `.order('reconnect_score', { ascending: false })` |
| `range` (limit/offset) | Pagination | `.range(0, 49)` |

**Limitation confirmed:** PostgREST cannot filter on `raw_enrichment` JSONB path expressions. Filtering requires extracted columns.

---

## Data Flow: Search Query

### Flow Diagram

```
User types "Sales leader, University of Miami" in search bar
                    │
                    ▼
contacts.js: parseSearchQuery(input) →
  {
    freeText: "Sales leader University of Miami",  // goes to tsvector
    industry: null,                                // no explicit industry filter
    location: null,                                // no explicit location filter
  }
                    │
                    ▼
buildSearchQuery(db, params) →
  db.from('connections')
    .select('id, name, current_role, current_company, location,
             enriched_industry, enriched_school, enriched_headline,
             reconnect_score, latest_signal, data_completeness_score')
    .textSearch('fts', 'Sales leader University Miami', { type: 'websearch' })
    .not('user_priority', 'eq', 'never')          // hide ARCHIVE
    .order('reconnect_score', { ascending: false })
    .range(0, 49)                                  // page 1 of 50
                    │
                    ▼
PostgREST → PostgreSQL:
  SELECT ... FROM connections
  WHERE fts @@ websearch_to_tsquery('Sales leader University Miami')
    AND user_priority IS DISTINCT FROM 'never'
  ORDER BY reconnect_score DESC
  LIMIT 50 OFFSET 0
                    │
                    ▼
PWA renders result cards (no client-side filter needed)
  Click on card → navigate('#/contact/{id}') (existing contact.js)
```

### Flow for Structured Filters

```
User selects: Industry = "Technology", Location = "Miami"
                    │
                    ▼
contacts.js buildSearchQuery():
  let query = db.from('connections').select(CONTACT_COLS)
  if (filters.industry)  query = query.ilike('enriched_industry', `%${filters.industry}%`)
  if (filters.location)  query = query.ilike('location', `%${filters.location}%`)
  if (filters.signal)    query = query.eq('latest_signal', filters.signal)
  query = query.order(...).range(...)
                    │
                    ▼
PostgREST → PostgreSQL (server-side filter, uses B-tree indexes on extracted columns)
```

---

## New vs Modified Components

### New: Extracted Columns Migration (Phase 1 — Must Come First)

Nothing can be searched until the columns exist. This is the hard dependency.

**Migration file:** `supabase/migrations/20260314000000_enrichment_extraction.sql`

```sql
-- Extracted enrichment fields for searchable columns
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_industry TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_headline TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_location_city TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_location_country TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_school TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_seniority TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_follower_count INTEGER;

-- Backfill from existing raw_enrichment JSONB
UPDATE connections SET
  enriched_industry = COALESCE(
    raw_enrichment->'data'->>'company_industry',
    raw_enrichment->>'company_industry',
    raw_enrichment->'data'->>'companyIndustry',
    raw_enrichment->>'companyIndustry'
  ),
  enriched_headline = COALESCE(
    raw_enrichment->'data'->>'headline',
    raw_enrichment->>'headline'
  ),
  enriched_location_city = COALESCE(
    raw_enrichment->'data'->>'city',
    raw_enrichment->>'city'
  ),
  enriched_location_country = COALESCE(
    raw_enrichment->'data'->>'country',
    raw_enrichment->>'country'
  ),
  enriched_school = COALESCE(
    raw_enrichment->'data'->'educations'->0->>'school',
    raw_enrichment->'educations'->0->>'school'
  ),
  enriched_follower_count = (COALESCE(
    raw_enrichment->'data'->>'follower_count',
    raw_enrichment->>'follower_count'
  ))::INTEGER
WHERE raw_enrichment IS NOT NULL;

-- Seniority derived from job_title or headline
UPDATE connections SET
  enriched_seniority = CASE
    WHEN current_role ILIKE '%VP%' OR current_role ILIKE '%Vice President%' THEN 'VP'
    WHEN current_role ILIKE '%Director%' THEN 'Director'
    WHEN current_role ILIKE '%Chief%' OR current_role ILIKE '% C%O%' THEN 'C-Suite'
    WHEN current_role ILIKE '%Manager%' THEN 'Manager'
    WHEN current_role ILIKE '%Senior%' OR current_role ILIKE '% Sr.%' THEN 'Senior'
    ELSE NULL
  END
WHERE current_role IS NOT NULL;

-- Full-text search vector column
-- Covers: name, current_role, company, industry, headline, school, location, notes
ALTER TABLE connections ADD COLUMN IF NOT EXISTS fts tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english',
      COALESCE(name, '') || ' ' ||
      COALESCE(current_role, '') || ' ' ||
      COALESCE(current_company, '') || ' ' ||
      COALESCE(enriched_industry, '') || ' ' ||
      COALESCE(enriched_headline, '') || ' ' ||
      COALESCE(enriched_school, '') || ' ' ||
      COALESCE(location, '') || ' ' ||
      COALESCE(notes, '')
    )
  ) STORED;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_connections_industry ON connections(enriched_industry);
CREATE INDEX IF NOT EXISTS idx_connections_seniority ON connections(enriched_seniority);
CREATE INDEX IF NOT EXISTS idx_connections_school ON connections(enriched_school);
CREATE INDEX IF NOT EXISTS idx_connections_fts ON connections USING GIN(fts);
```

**Important:** The `fts` column is `GENERATED ALWAYS AS ... STORED`. PostgreSQL automatically keeps it in sync whenever any source column changes. No trigger needed. The column auto-updates when `name`, `current_role`, `enriched_industry`, etc. are updated — which happens every time the pipeline pushes enriched data.

### New: Python Enrichment Extraction in Pipeline (Phase 1 — Same Migration Window)

The migration backfills existing data. For new enrichments, `update_connection_from_profile()` in `rapidapi_linkedin.py` must be extended to write the extracted columns at enrichment time, so they stay in sync in SQLite (which feeds push.py to Supabase).

**Modified:** `src/ingestion/rapidapi_linkedin.py`

```python
# In update_connection_from_profile() — add after existing field extraction:

# Extract searchable columns from enrichment data
if data.get("company_industry"):
    connection.enriched_industry = data["company_industry"]
elif data.get("companyIndustry"):
    connection.enriched_industry = data["companyIndustry"]

if data.get("headline"):
    connection.enriched_headline = data["headline"][:255]

if data.get("city"):
    connection.enriched_location_city = data["city"]

if data.get("country"):
    connection.enriched_location_country = data["country"]

if data.get("educations") and len(data["educations"]) > 0:
    connection.enriched_school = data["educations"][0].get("school", "")

if data.get("follower_count"):
    connection.enriched_follower_count = int(data["follower_count"])

# Derive seniority from current_role
if connection.current_role:
    connection.enriched_seniority = _derive_seniority(connection.current_role)
```

**New:** `src/database/models.py` — add extracted fields to `Connection` model:

```python
# Extracted enrichment fields (populated by rapidapi_linkedin.py, searchable via PostgREST)
enriched_industry: Optional[str] = Field(default=None, index=True)
enriched_headline: Optional[str] = Field(default=None, sa_column=Column(Text))
enriched_location_city: Optional[str] = Field(default=None, index=True)
enriched_location_country: Optional[str] = Field(default=None, index=True)
enriched_school: Optional[str] = Field(default=None, index=True)
enriched_seniority: Optional[str] = Field(default=None, index=True)
enriched_follower_count: Optional[int] = Field(default=None)
# Note: 'fts' tsvector column is GENERATED in PostgreSQL — not mapped in SQLModel
# It exists only in Supabase PostgreSQL, not in local SQLite (SQLite has no tsvector)
```

**Critical note on `fts`:** The `fts` tsvector column is a PostgreSQL-only feature. Do not add it to the SQLModel definition (it would break SQLite). The `fts` column lives in Supabase PostgreSQL only. The PWA calls `textSearch('fts', ...)` against Supabase; the Python pipeline never reads or writes `fts` directly.

### New: `pwa/js/contacts.js` — Browse/Search Page

A new page module following the same pattern as `queue.js` and `contact.js`.

**Component responsibility:** Fetch contacts from `connections` directly (not via `outreach_queue` join), support free-text search and structured filters, paginate results, navigate to `contact.js` on selection.

```javascript
// Key PostgREST query pattern:
async function searchContacts(searchText, filters = {}, page = 0) {
  const PAGE_SIZE = 50;
  let query = db
    .from('connections')
    .select(`
      id, name, current_role, current_company, location,
      enriched_industry, enriched_headline, enriched_school,
      enriched_seniority, reconnect_score, latest_signal,
      data_completeness_score, enriched_at
    `)
    .not('user_priority', 'eq', 'never')   // exclude ARCHIVE contacts
    .order('reconnect_score', { ascending: false, nullsFirst: false })
    .range(page * PAGE_SIZE, (page + 1) * PAGE_SIZE - 1);

  // Full-text search — uses GIN index on fts column
  if (searchText && searchText.trim()) {
    query = query.textSearch('fts', searchText.trim(), { type: 'websearch' });
  }

  // Structured filters — use extracted columns (not raw_enrichment)
  if (filters.industry) {
    query = query.ilike('enriched_industry', `%${filters.industry}%`);
  }
  if (filters.location) {
    // Search across location (city+state+country) and city field
    query = query.or(
      `location.ilike.%${filters.location}%,enriched_location_city.ilike.%${filters.location}%`
    );
  }
  if (filters.seniority) {
    query = query.eq('enriched_seniority', filters.seniority);
  }
  if (filters.signal) {
    query = query.eq('latest_signal', filters.signal);
  }
  if (filters.hasEmail) {
    query = query.not('email', 'is', null);
  }

  return await query;
}
```

**Route addition in `app.js`:**

```javascript
const routes = {
  '/queue':    { module: 'queue',    title: 'Queue' },
  '/contacts': { module: 'contacts', title: 'Contacts' },  // NEW
  '/contact':  { module: 'contact',  title: 'Contact' },
  '/dashboard':{ module: 'dashboard',title: 'Dashboard' },
  '/preferences':{ module: 'preferences', title: 'Preferences' },
};
```

**Navigation addition in `index.html`:** Add a "Contacts" tab to the bottom nav alongside Queue, Dashboard, Preferences.

### Modified: `push.py` — Sync Extracted Columns

The `CONNECTION_SYNC_FIELDS` list in `push.py` must include the new extracted columns so they are pushed to Supabase:

```python
CONNECTION_SYNC_FIELDS = [
    # ... existing fields ...
    # v1.3 enrichment extraction
    "enriched_industry",
    "enriched_headline",
    "enriched_location_city",
    "enriched_location_country",
    "enriched_school",
    "enriched_seniority",
    "enriched_follower_count",
]
```

**Note:** `fts` is not in this list — it is a generated column in PostgreSQL and auto-computes from the other columns after push. Do not attempt to write `fts`.

### Modified: Enrichment Completeness Pipeline Step

The existing `data_completeness_score` and `missing_data_fields` fields (added in PWA Overhaul migration) need their computation updated to account for the newly tracked fields. This is in the pipeline step that runs `_compute_data_completeness()` (likely in `daily_pipeline.py` or `feedback_processor.py`).

**The completeness score should track:** name, email, linkedin_url, current_role, current_company, location, enriched_industry, enriched_school, enriched_seniority. Missing fields in `missing_data_fields` JSON array should name these extracted columns, not raw_enrichment subkeys.

---

## Migration Strategy

### Phase Order (Non-Negotiable Dependencies)

```
Phase 1: Schema + Extraction
  ├── SQL migration: add extracted columns + fts + backfill + indexes
  ├── models.py: add Connection fields (no fts — SQLite only)
  ├── rapidapi_linkedin.py: write extracted columns on enrichment
  ├── push.py: include extracted columns in sync
  └── Backfill script (one-time): run extraction across all existing SQLite connections
              │
              ▼
Phase 2: Browse/Search PWA Page
  ├── contacts.js: new page module with textSearch + ilike queries
  ├── app.js: add /contacts route
  └── index.html: add Contacts nav tab
              │
              ▼
Phase 3: Enrichment Completeness Improvements
  ├── Update completeness scoring to reference extracted columns
  ├── Update missing_data_fields to reference extracted column names
  └── Enrich contacts with missing fields per enrichment_planner.py budget
```

Phase 2 cannot be built before Phase 1 because the columns it queries do not exist yet. The `fts` column does not exist to be searched. The `textSearch('fts', ...)` call will fail with a PostgREST error if the column is absent.

### Backfill Script

After applying the SQL migration, existing SQLite records need their extracted columns populated from their existing `raw_enrichment` JSON. The SQL `UPDATE` in the migration handles the Supabase side. A CLI command or pipeline step must do the same for SQLite:

```python
# src/pipeline/daily_pipeline.py or a standalone reconnect CLI command
def backfill_enrichment_extractions():
    """One-time: populate extracted columns from raw_enrichment for all connections."""
    with get_session() as session:
        connections = session.exec(
            select(Connection)
            .where(Connection.raw_enrichment.isnot(None))
            .where(Connection.enriched_industry.is_(None))
        ).all()
        for conn in connections:
            data = get_enrichment_data(conn)  # uses existing unwrap helper
            _apply_extraction(conn, data)
            session.add(conn)
        session.commit()
```

This runs once. After it runs, ongoing enrichments write extracted columns via the updated `update_connection_from_profile()`.

---

## Component Boundaries

| Component | Responsibility | Reads | Writes |
|-----------|---------------|-------|--------|
| `rapidapi_linkedin.py` | Enrichment + extraction | RapidAPI response | `raw_enrichment` + 7 extracted columns + `current_role/company/location` |
| `models.py` (Connection) | Schema definition | — | SQLite schema (extracted columns only, not fts) |
| `push.py` | Sync to Supabase | SQLite Connection rows | Supabase `connections` table (including extracted columns) |
| `20260314_migration.sql` | Supabase schema + backfill | Existing `raw_enrichment` JSONB | New extracted columns + `fts` generated column |
| `contacts.js` | Browse/search PWA page | PostgREST (extracted columns + fts) | None (read-only browse; contact edits go through contact.js) |
| `app.js` | Router | — | Routes table |
| `contact.js` | Contact profile page | PostgREST (full `connections` row + `contact_notes` + `contact_signals`) | `connections.notes`, `contact_notes` INSERT |
| `queue.js` | Queue triage | PostgREST `outreach_queue + connections` | `contact_signals`, `outreach_queue`, `connections` |

---

## Architectural Patterns

### Pattern 1: Extraction at Write Time, Not Query Time

**What:** Extract JSONB fields to real columns when enrichment data is written, not when it is queried.

**When:** Every time `update_connection_from_profile()` runs in the pipeline.

**Why:** Query-time extraction (using `raw_enrichment->>'company_industry'` in WHERE clauses) bypasses PostgREST's filter operators. Write-time extraction means the data is in standard columns that PostgREST can filter natively with no special handling.

**The pattern in practice:**
```python
# In update_connection_from_profile() — write both raw and extracted:
connection.raw_enrichment = data          # preserve full API response
connection.enriched_industry = data.get("company_industry")  # extracted column
```

Raw enrichment is preserved for detail views (contact.js already reads it for career path, about sections, etc.). Extracted columns handle search/filter.

### Pattern 2: PostgreSQL Generated Column for Full-Text Index

**What:** Define `fts` as `GENERATED ALWAYS AS (...) STORED` in PostgreSQL. PostgreSQL auto-maintains it.

**When to use:** Any field that needs full-text search across multiple source columns.

**Why not a trigger:** Generated columns are declarative, transactional, and zero-maintenance. Triggers require a separate function definition, are more error-prone, and are harder to reason about.

**Example from migration:**
```sql
ALTER TABLE connections ADD COLUMN IF NOT EXISTS fts tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english',
      COALESCE(name, '') || ' ' ||
      COALESCE(current_role, '') || ' ' ||
      COALESCE(enriched_industry, '') || ' ' ||
      COALESCE(enriched_school, '') || ' ' ||
      COALESCE(location, '')
    )
  ) STORED;
```

`fts` auto-updates whenever `name`, `current_role`, etc. are updated via push.py. No additional code.

### Pattern 3: Separate Browse Page from Queue Page

**What:** The new `contacts.js` page is distinct from `queue.js`. It fetches from `connections` directly; `queue.js` fetches from `outreach_queue` with an embedded `connections` join.

**When to use:** Any browse/search interaction that does not require queue context (queue_item_id, why_today, priority_score, draft status).

**Why not add search to queue.js:** Queue page semantics (pending/approved/sent status, queue_item_id for draft generation) are orthogonal to contact discovery semantics (find anyone in the network, regardless of queue status). Merging them creates a confusing UX and complex state management. The queue is for triage; contacts is for discovery.

### Pattern 4: Pagination at the PostgREST Layer

**What:** Use `.range(offset, limit)` in the PostgREST query, not client-side array slicing.

**When:** Any browse/search query that could return more than ~100 results.

**Why:** Client-side pagination requires fetching all matching rows first. At full network size, "show all contacts in Technology industry" could return thousands of rows.

```javascript
// Correct: server-side pagination
query = query.range(page * PAGE_SIZE, (page + 1) * PAGE_SIZE - 1);
// Returns count header if .select('...', { count: 'exact' }) used

// Wrong: fetch all, slice in JS
const all = await query;
const page = all.slice(page * 50, (page + 1) * 50); // wasteful
```

### Pattern 5: fts Lives in Supabase Only (Not SQLite)

**What:** The `fts` tsvector column is defined in the Supabase PostgreSQL migration but NOT in the SQLModel `Connection` class.

**When this matters:** `init_db()` in `database/engine.py` uses SQLModel metadata to create tables. If `fts` were mapped in SQLModel, `init_db()` would try to create a `tsvector` column in SQLite — which does not support that type and would crash.

**The split:**
- SQLite schema (from SQLModel): extracted TEXT/INTEGER columns — yes
- Supabase PostgreSQL schema (from migration SQL): extracted columns + `fts` generated column — yes
- SQLModel Connection class: extracted columns — yes; `fts` — NO

This is intentional and clean. The push.py sync writes extracted columns; PostgreSQL auto-generates `fts` from them.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Searching raw_enrichment in the Browser

**What goes wrong:** Fetching all contacts and filtering `conn.raw_enrichment?.data?.company_industry` in JavaScript.

**Why:** At 1,000+ synced contacts, the initial payload is several MB of JSON. Mobile Safari will be slow or crash. More critically, it means the search box cannot work until all data is loaded.

**Instead:** Extract to columns, use PostgREST filters. The search is fast and returns a small result set.

### Anti-Pattern 2: Adding Search to queue.js

**What goes wrong:** Putting a global contact search bar on the queue page and having it fetch from `outreach_queue` with text matching.

**Why:** `outreach_queue` does not contain all contacts — only those the pipeline has queued. Contacts without queue items are invisible. The search box on the queue page already exists for queue-level filtering; adding contact discovery semantics there conflates two different user intents.

**Instead:** Separate `/contacts` route and `contacts.js` module. Queue page stays focused on triage.

### Anti-Pattern 3: Mapping fts in SQLModel

**What goes wrong:** Adding `fts: Optional[str]` to the `Connection` SQLModel class.

**Why:** `init_db()` creates SQLite tables from SQLModel metadata. SQLite has no `tsvector` type. Even if aliased as TEXT, the column would be null (SQLite cannot run `to_tsvector`), and push.py would try to write a null `fts` value to Supabase, overwriting the generated column.

**Instead:** `fts` column is defined only in the migration SQL. It is never touched by Python code.

### Anti-Pattern 4: Removing raw_enrichment After Extraction

**What goes wrong:** Deleting or nulling `raw_enrichment` after copying fields to extracted columns, to save space.

**Why:** `contact.js` renders rich profile data (career history, education details, about section, skills) directly from `raw_enrichment`. The extracted columns cover only the search-relevant subset. Losing raw_enrichment breaks the profile page.

**Instead:** Keep `raw_enrichment` intact. The extracted columns are additive, not a replacement.

### Anti-Pattern 5: Using LIKE Without an Index

**What goes wrong:** Running `ilike('enriched_industry', '%tech%')` without an index.

**Why:** `%prefix%` pattern (leading wildcard) cannot use B-tree indexes. PostgreSQL falls back to a sequential scan.

**Instead:** For industry and other categorical fields, favor equality matching (`eq`) or prefix matching (`ilike('enriched_industry', 'tech%')`) where possible. For the full-text cases (search bar), use the `fts` GIN index via `textSearch`. The migration creates the right indexes for each case.

---

## Build Order Rationale

```
Step 1: SQL migration (Supabase side — extracted columns + backfill + fts + indexes)
Step 2: models.py update (add extracted fields to Connection — SQLite side)
Step 3: rapidapi_linkedin.py update (write extracted columns on new enrichments)
Step 4: Backfill script (one-time — populate extracted columns in SQLite from raw_enrichment)
Step 5: push.py update (include extracted columns in CONNECTION_SYNC_FIELDS)
  ↓ Pipeline now produces searchable columns end-to-end ↓
Step 6: contacts.js (new browse/search page — queries extracted columns + fts)
Step 7: app.js route + index.html nav (wire up /contacts route)
Step 8: Completeness scoring update (track extracted column completeness)
```

Steps 1-5 must complete before Step 6 is built. The contacts page queries columns that must already exist in Supabase and contain data.

---

## Integration Points with Existing Architecture

| Existing Component | What Changes | What Stays the Same |
|-------------------|--------------|---------------------|
| `rapidapi_linkedin.py::update_connection_from_profile()` | Writes 7 new extracted fields after enrichment | Writes `raw_enrichment`, `current_role`, `current_company`, `location` (unchanged) |
| `src/database/models.py::Connection` | 7 new TEXT/INTEGER fields added | All existing fields, JSON columns, indexes unchanged |
| `src/sync/push.py::CONNECTION_SYNC_FIELDS` | 7 new field names added | All existing sync logic unchanged |
| `pwa/js/app.js` | `/contacts` route added to routes table | Hash router, Supabase init, deep link bridge unchanged |
| `pwa/index.html` | Contacts nav tab added | All existing nav tabs (Queue, Dashboard, Preferences) unchanged |
| `pwa/js/queue.js` | No change (client-side industry filter preserved) | Existing signal filter, sort, card structure unchanged |
| `pwa/js/contact.js` | No change | Reads `raw_enrichment` for detail display (unchanged) |
| `supabase/migrations/` | New migration file added | All existing migrations unmodified |
| `src/pipeline/daily_pipeline.py` | Backfill step added (one-time or CLI command) | 10-step pipeline order and logic unchanged |

**Edge Functions:** No changes needed. Search is a read-only PWA operation via PostgREST. Draft generation (`draft/`) and action tokens (`action/`) are unaffected.

**PostgREST permissions:** The `anon` role already has `SELECT` on `connections` (required for the queue page's embedded `connections(*)` join). No new permission grants needed for the contacts page.

---

## Scalability Considerations

This is a single-user personal tool. The relevant concern is payload size and query latency on mobile.

| Concern | Current (queue.js) | With v1.3 (contacts.js) |
|---------|--------------------|--------------------------|
| Payload size | Small — queue items only, typically <100 | Controlled — 50 rows per page, server-side pagination |
| Filtering | Client-side (all rows fetched first) | Server-side (PostgREST with indexes) |
| Search latency | N/A | GIN index on fts — fast even at 10K rows |
| Storage overhead | raw_enrichment JSON (~1-5KB per contact) | +7 small extracted columns (~200 bytes per contact) — negligible |
| Generated column maintenance | N/A | Auto-maintained by PostgreSQL — zero overhead for single-user write volume |

The GIN index on `fts` and B-tree indexes on extracted columns handle search at any plausible personal network size (10K+ contacts) without issue.

---

## Sources

- `src/database/models.py` — Connection model field inventory, existing indexes
- `src/ingestion/rapidapi_linkedin.py` — Enrichment field extraction, raw_enrichment shape, mock data
- `src/pipeline/enrichment_planner.py` — Enrichment budget and prioritization logic
- `src/sync/push.py` — `CONNECTION_SYNC_FIELDS` list, sync patterns
- `pwa/js/queue.js` — PostgREST query patterns, client-side filter patterns, raw_enrichment access
- `pwa/js/contact.js` — raw_enrichment rendering, PostgREST read patterns
- `pwa/js/app.js` — Router structure, Supabase client init
- `supabase/migrations/20260305000000_pwa_overhaul.sql` — Migration pattern reference
- `.planning/PROJECT.md` — v1.3 requirements, constraints, existing key decisions
- [PostgREST Tables and Views — v12 docs](https://docs.postgrest.org/en/v12/references/api/tables_views.html) — ilike, textSearch, filter operators
- [Supabase JavaScript API — ilike](https://supabase.com/docs/reference/javascript/ilike) — MEDIUM confidence (docs)
- [Supabase JavaScript API — textSearch](https://supabase.com/docs/reference/javascript/textsearch) — MEDIUM confidence (docs)
- [PostgreSQL Generated Columns](https://www.postgresql.org/docs/current/ddl-generated-columns.html) — GENERATED ALWAYS AS STORED syntax
- [Supabase Full Text Search Guide](https://supabase.com/docs/guides/database/full-text-search) — tsvector + GIN index pattern
- [Search on multiple columns with ilike — Supabase Discussion #6778](https://github.com/supabase/supabase/discussions/6778) — `.or()` multi-column search pattern

All architectural claims about existing code are grounded in direct source-code inspection. Confidence: HIGH.

---

*Architecture research for: Reconnect v1.3 Contact Discovery*
*Researched: 2026-03-14*
