# Technology Stack: v1.3 Contact Discovery

**Project:** Reconnect — v1.3 Contact Discovery milestone
**Researched:** 2026-03-14
**Confidence:** HIGH — findings based on direct codebase inspection, installed package verification, and web-verified library details

---

## Context: What Already Exists (Do Not Re-Research)

The v1.3 stack additions are incremental on top of a validated existing stack.

| Layer | Technology | Verified Version |
|-------|------------|-----------------|
| Python pipeline | Python 3.11+, Click, SQLModel, SQLAlchemy, OpenAI | SQLModel 0.0.31, OpenAI 2.15.0, Click 8.3.1 |
| Database (local) | SQLite via SQLAlchemy | - |
| Database (cloud) | Supabase PostgreSQL + PostgREST | - |
| PWA | Vanilla JS, Supabase JS Client v2 (CDN) | - |
| LLM | OpenAI gpt-4o-mini | - |
| Edge Functions | Deno + TypeScript on Supabase | - |
| Sync | Bidirectional SQLite to Supabase via psycopg2 | psycopg2-binary 2.9+ |
| Enrichment | RapidAPI (fresh-linkedin-profile-data) + Hunter.io | requests 2.31+ |

---

## Search Approach Decision: Client-Side with Fuse.js

**Recommendation: Fuse.js 7.1.0 loaded via CDN for client-side fuzzy search.**

This is the correct choice for this codebase. The analysis below explains why, and why alternatives were rejected.

### Why Client-Side Search Is Correct Here

The PWA already fetches the full `connections` table from PostgREST for the queue view (all fields, joined). The data volume for a personal networking tool is bounded — a power-user LinkedIn network is 3,000–5,000 contacts maximum. Fuse.js handles 5,000 records in under 100ms for a single query on modern hardware.

Client-side search avoids:
- Round-trip latency per keystroke to Supabase
- PostgREST limitations on cross-field OR queries (confirmed: multi-column ilike requires raw PostgREST syntax and cannot combine fields across nested JSON)
- Any per-query API cost

The existing architecture decision (noted in PROJECT.md "Key Decisions") already established client-side filtering as the pattern: industry filter, signal filter, and sort are all client-side. Search extends this exact pattern.

### Search Library: Fuse.js 7.1.0

**Version:** 7.1.0 (current as of research date, confirmed via npm)
**CDN:** `https://cdn.jsdelivr.net/npm/fuse.js@7.1.0/dist/fuse.mjs` (ES module build)
**Size:** ~23KB minified (lightweight, no build tooling required)
**Zero dependencies**

Fuse.js provides:
- Weighted multi-field fuzzy search (name, role, company, location, education, tags, notes)
- Configurable threshold for match sensitivity (0.0 = perfect match, 1.0 = match anything)
- Score-ranked results (most relevant first)
- Works directly from CDN — no npm, no bundler, no build step (matches existing Vanilla JS + CDN pattern)

**Fuse.js configuration for this use case:**

```javascript
const fuse = new Fuse(contacts, {
  keys: [
    { name: 'name',            weight: 0.35 },
    { name: 'current_role',    weight: 0.25 },
    { name: 'current_company', weight: 0.20 },
    { name: 'location',        weight: 0.10 },
    // Education school extracted into a flat field before indexing
    { name: '_education',      weight: 0.10 },
  ],
  threshold: 0.4,       // Tolerates typos and partial matches
  minMatchCharLength: 2,
  includeScore: true,
  ignoreLocation: true, // Don't penalize matches at end of string
});
```

The `_education` field is a flattened string derived at data-load time from `raw_enrichment.data.educations[].school` — no runtime JSON traversal during search.

**Usage pattern (matching existing vanilla JS style):**

```javascript
// Load once when browse view initializes — reuse across keystrokes
async function loadContactsForSearch() {
  const { data } = await db.from('connections')
    .select('id, name, current_role, current_company, location, raw_enrichment, latest_signal, reconnect_score, user_priority')
    .neq('user_priority', 'never');

  // Flatten education into a searchable string before indexing
  return (data || []).map(c => ({
    ...c,
    _education: extractEducationString(c.raw_enrichment),
  }));
}

function extractEducationString(raw) {
  const enrichment = raw?.data || raw || {};
  const educations = enrichment.educations || enrichment.education || [];
  return educations.map(e => e.school || '').filter(Boolean).join(' ');
}
```

**Supabase PostgREST row limit:** Default 1,000 rows. For contacts > 1,000, use `.range(0, 4999)` with pagination or increase the PostgREST `max_rows` setting in Supabase Dashboard → API Settings. For a personal tool with < 5,000 contacts, setting `max_rows` to 5000 is safe and appropriate.

---

## Alternatives Considered and Rejected

### Alternative 1: PostgreSQL Full-Text Search via PostgREST `.textSearch()`

**What it offers:** Supabase supports `tsvector` generated columns with GIN indexes, enabling `.textSearch('fts_column', 'query')` via the JS client.

**Why rejected for v1.3:**

1. **Schema migration required** — A generated `tsvector` column must concatenate the searchable fields. Fields in `raw_enrichment` (education, about, skills) are JSONB — extracting them into a `tsvector` requires a migration that either uses a trigger or a generated column expression. This adds non-trivial schema complexity.

2. **Cannot search JSONB fields directly** — The most valuable search fields (school, about, industry from enrichment) live inside `raw_enrichment JSONB`. PostgreSQL FTS on a generated column can't include dynamic JSONB paths without a custom SQL function and trigger.

3. **Adds round-trip latency per keystroke** — A server-side query on every keypress feels sluggish compared to in-memory Fuse.js. Debouncing at 300ms helps but doesn't eliminate it.

4. **Overkill for data volume** — PostgreSQL FTS is designed for millions of documents. For < 5,000 contacts, the infrastructure cost is not justified.

**When to revisit:** If the tool ever becomes multi-user (multiple LinkedIn networks in one DB), PostgreSQL FTS becomes the right answer. Not for this milestone.

**PostgREST multi-column ilike — also considered and rejected:**

```javascript
// This is the PostgREST syntax for OR across columns
.or('name.ilike.%term%,current_role.ilike.%term%,current_company.ilike.%term%')
```

This only covers structured columns. `raw_enrichment` JSON fields cannot be included. Also has no fuzzy matching — typos return zero results. Not appropriate for "Sales leader, University of Miami"-style queries.

### Alternative 2: Semantic Embeddings + pgvector

**What it offers:** Generate a text embedding for each contact (name + role + company + bio), store in pgvector on Supabase (free tier supports pgvector), and query with cosine similarity.

**Cost analysis:**

| Operation | Model | Cost |
|-----------|-------|------|
| Generate embeddings for 5,000 contacts (initial) | text-embedding-3-small | ~$0.002 total ($0.02/1M tokens × ~100 tokens × 5000) |
| Re-embed on enrichment update | text-embedding-3-small | ~$0.000002 per contact |
| Search queries (pgvector similarity) | None — pure SQL | $0.00 per query |

Embedding cost is negligible. **The reason to reject is not cost — it's complexity and mismatch with the use case.**

"Sales leader, University of Miami" is a structured attribute query, not a semantic concept search. The user knows what they're looking for — they want fuzzy matching on known fields. Embeddings excel at "who in my network works on AI infrastructure?" (conceptual). They're worse than Fuse.js for "find John Smith at Google" (attribute lookup with typo tolerance).

Embeddings also require:
- Pipeline step to generate/update embeddings on enrichment
- pgvector extension enabled on Supabase (free tier supported but requires manual enablement)
- New Edge Function or RPC for similarity search (PostgREST cannot call vector operators directly)
- Complex re-indexing when contact data changes

For this milestone, Fuse.js delivers better results with zero infrastructure additions.

**When to revisit:** If "AI contact search" (free-form conceptual queries like "who knows about X?") is scoped as a future feature, embeddings become the right answer. That feature is already noted as a Potential v1.3+ item in PROJECT.md.

---

## Enrichment Completeness: What the Current Stack Covers

### Fields Already Captured by RapidAPI (fresh-linkedin-profile-data)

The mock data in `rapidapi_linkedin.py` reflects the actual API schema. Fields returned include:

| Category | Fields Available | Currently Denormalized? |
|----------|-----------------|------------------------|
| Identity | full_name, first_name, last_name, headline | name (yes), role (yes via job_title) |
| Professional | job_title, company, company_industry | current_role (yes), current_company (yes) |
| Location | location, city, state, country | location (yes) |
| About | about | Stored in raw_enrichment only |
| Experience | experiences[] with title, company, date_range, description | raw_enrichment only |
| Education | educations[] with school, degree, field_of_study | raw_enrichment only — NOT denormalized |
| Skills | skills[] | raw_enrichment only |

**Critical gap for v1.3 search:** Education (`educations[].school`) is stored in `raw_enrichment` JSONB but never promoted to a queryable column. For the "University of Miami" search query in the milestone brief, either:
1. Fuse.js must index it from flattened `raw_enrichment` (recommended — no schema change)
2. Or a new `education_school` TEXT column must be added

Option 1 (Fuse.js flat-field approach) handles this without migration.

### What Hunter.io Adds

Hunter's `enrich_from_email` returns `person.seniority` and `person.role` (category, not title). These are stored in `raw_enrichment` under the `hunter_email` key. Hunter does **not** return education data.

Hunter is useful for:
- Email finding (existing, pipeline-driven)
- Seniority classification ("manager", "director", "vp", "c_level") — useful for filter chips in the browse UI

### Data Completeness: What Needs to Change

The existing `compute_completeness()` in `data_analyzer.py` already measures 10 fields. For v1.3, add education as a completeness dimension:

```python
# Add to FIELD_WEIGHTS in data_analyzer.py
("education", 5, "enrichment"),  # School name from educations[]
```

And add to `_check_field()`:

```python
if field_name == "education":
    educations = enrichment.get("educations") or enrichment.get("education") or []
    return len(educations) > 0 and bool(educations[0].get("school"))
```

This surfaces "no education data" in `missing_data_fields` — making the completeness dashboard more useful for the browse/discovery use case.

---

## PWA Additions for Search and Browse UI

### New Route: `/browse`

Add a contacts browse view as a new route in `app.js`:

```javascript
const routes = {
  '/queue':      { module: 'queue',      title: 'Queue' },
  '/contact':    { module: 'contact',    title: 'Contact' },
  '/dashboard':  { module: 'dashboard',  title: 'Dashboard' },
  '/preferences':{ module: 'preferences',title: 'Preferences' },
  '/browse':     { module: 'browse',     title: 'Browse' },  // NEW v1.3
};
```

New file: `pwa/js/browse.js` — responsible for:
1. Fetching all contacts (non-ARCHIVE) from PostgREST once on load
2. Building Fuse.js index from the results
3. Rendering search input + filter chips
4. Rendering contact cards on search or filter change (client-side only)

### Fuse.js CDN Integration

Add to `pwa/index.html` alongside existing Supabase CDN import:

```html
<!-- Fuse.js — lightweight fuzzy search (client-side, no backend needed) -->
<script type="module">
  import Fuse from 'https://cdn.jsdelivr.net/npm/fuse.js@7.1.0/dist/fuse.mjs';
  window.Fuse = Fuse;
</script>
```

Note: The ESM build from jsDelivr is the right choice. It works with the `type="module"` pattern. Do not use the UMD build — it conflicts with existing module usage.

### Browse UI Filter State

Browse filters operate independently from queue filters. Keep state in a module-scoped object in `browse.js` (same pattern as `queueFilters` in `queue.js`):

```javascript
const browseState = {
  query: '',
  signalFilter: null,     // null = all signals
  industryFilter: null,   // null = all industries
  hasEmailFilter: false,  // Only show contacts with email
  sortBy: 'score',        // 'score' | 'name' | 'recent'
  fuseInstance: null,     // Initialized after data load
  allContacts: [],        // Full dataset for re-search
};
```

### No New Edge Functions

Search is entirely client-side. No Edge Function is needed. Browse filter interactions do not require server-side secrets. The existing PostgREST `select` with the anon key is sufficient.

---

## Database Schema Changes

### No New Tables Required

Fuse.js operates on data already returned by the existing `connections` select. No new columns are strictly necessary for the core search feature.

### Optional: Promote Education to Denormalized Column

If education filtering via PostgREST becomes desirable in a future milestone (e.g., "show contacts from Ivy League schools" as a dashboard metric), add:

```sql
-- Optional — not required for v1.3 Fuse.js approach
ALTER TABLE connections ADD COLUMN IF NOT EXISTS education_school TEXT;
```

Populated by extending `update_connection_from_profile()` in `rapidapi_linkedin.py`:

```python
educations = data.get("educations") or data.get("education") or []
if educations:
    connection.education_school = educations[0].get("school", "")
```

**Decision for v1.3:** Defer this column. Fuse.js handles it via `_education` flattening. Add the column only if a later milestone needs server-side education filtering.

### PostgREST `max_rows` Configuration

The existing `max_rows` in Supabase API settings is 1,000. For a browse view that loads all contacts, increase to 5,000 in Supabase Dashboard → Project Settings → API → Max Rows. This is a configuration change, not a code change.

---

## Recommended Stack Additions Summary

| Addition | Type | Why |
|----------|------|-----|
| Fuse.js 7.1.0 | CDN import in `index.html` | Client-side fuzzy search, zero dependencies, matches existing CDN pattern |
| `pwa/js/browse.js` | New PWA module | Contacts browse + search view, Fuse.js integration |
| `/browse` route in `app.js` | 1-line change | Navigate to browse view |
| Education in `FIELD_WEIGHTS` | `data_analyzer.py` extension | Makes education a completeness dimension |
| `max_rows = 5000` | Supabase Dashboard config | Allows full contact list fetch for client-side search |

**No new Python packages. No new pip installs. No new Edge Functions. No schema migrations required for v1.3.**

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PostgreSQL full-text search / tsvector | Requires schema migration for JSONB fields, adds round-trip per keystroke, overkill for < 5,000 contacts | Fuse.js client-side — same result, zero infrastructure |
| pgvector + embeddings | Mismatch for attribute lookup queries, adds pipeline complexity, requires Edge Function for RPC | Defer to "AI contact search" feature if scoped later |
| React or Vue component for search UI | Breaks CDN-only deployment model, requires build tooling | Extend `browse.js` in vanilla JS — search input + debounce is ~20 lines |
| Separate search index / IndexedDB persistence | Over-engineering for < 5,000 contacts — Fuse.js rebuild from memory is fast | Build Fuse index in memory on page load from PostgREST fetch |
| Elasticsearch / Typesense | Requires new infrastructure, paid tier, ops overhead | No justification for single-user personal tool |
| New denormalized `education_school` column | Fuse.js handles education via `raw_enrichment` flattening — no column needed | Client-side `_education` field from `raw_enrichment.educations[].school` |
| Per-keystroke PostgREST queries | Round-trip latency ruins search UX; PostgREST can't do multi-field OR with fuzzy matching | Single fetch on load + Fuse.js in-memory search |

---

## Version Compatibility

All v1.3 changes work within existing installed versions.

| Package | Current Version | v1.3 Requirement | Compatible |
|---------|----------------|-------------------|-----------|
| sqlmodel | 0.0.31 | No change | Yes |
| openai | 2.15.0 | No change | Yes |
| click | 8.3.1 | No change | Yes |
| psycopg2-binary | 2.9+ | No change | Yes |
| Supabase JS Client | v2 (CDN) | `.select()` with increased row range | Yes |
| Fuse.js | 7.1.0 (new) | ESM build via CDN | No conflict — additive only |

---

## Installation

**No new pip packages.**

Add Fuse.js to `pwa/index.html` (one line alongside existing CDN imports):

```html
<script type="module">
  import Fuse from 'https://cdn.jsdelivr.net/npm/fuse.js@7.1.0/dist/fuse.mjs';
  window.Fuse = Fuse;
</script>
```

**Supabase Dashboard config change (not code):**
Project Settings → API → Max Rows: change from 1000 to 5000.

---

## Integration Points Summary

| Feature | Python Pipeline | Supabase DB | Edge Function | PWA (JS) |
|---------|----------------|-------------|---------------|----------|
| Contact search | No change | No change | None | Fuse.js in `browse.js` |
| Browse/filter view | No change | No change | None | New `browse.js`, new route |
| Education completeness | `data_analyzer.py` add education field | No change | None | No change |
| Enrichment field coverage | Already good via RapidAPI; `_education` flattening | No change | None | Client-side flatten in `browse.js` |
| PostgREST row limit | No change | Dashboard config only | None | `.range()` or increased `max_rows` |

---

## Sources

- Direct codebase inspection: `src/ingestion/rapidapi_linkedin.py`, `src/ingestion/hunter.py`, `src/llm/data_analyzer.py`, `src/database/models.py`, `src/sync/push.py`, `pwa/js/queue.js`, `pwa/js/contact.js`, `pwa/js/app.js`
- Fuse.js version 7.1.0 confirmed via [npm](https://www.npmjs.com/package/fuse.js) — current as of 2026-03-14
- Fuse.js CDN via [jsDelivr](https://www.jsdelivr.com/package/npm/fuse.js) — ESM build at `fuse.mjs`
- Supabase PostgREST full-text search: [Official Docs](https://supabase.com/docs/guides/database/full-text-search), [JS textSearch reference](https://supabase.com/docs/reference/javascript/textsearch)
- Supabase PostgREST multi-column ilike: [Community discussion](https://github.com/orgs/supabase/discussions/6778) confirming `.or()` syntax required
- Supabase `max_rows` default (1,000) and configurability: [Community discussion](https://github.com/orgs/supabase/discussions/3765) and [Community discussion](https://github.com/orgs/supabase/discussions/1742)
- pgvector on Supabase free tier: [Official Docs](https://supabase.com/docs/guides/database/extensions/pgvector) — available on free tier with manual enablement
- OpenAI text-embedding-3-small pricing: $0.02/1M tokens — [costgoat.com](https://costgoat.com/pricing/openai-embeddings) (confirmed negligible for 5K contacts)
- Fuse.js performance: 81K-record dataset tested at ~4 seconds; 5K records expected < 100ms — [GitHub issue #282](https://github.com/krisk/Fuse/issues/282)
- Existing `CLIENT_DECISION` pattern: PROJECT.md "Key Decisions" — industry filter, signal filter, sort all client-side (confirms architecture precedent)

---

*Stack research for: Reconnect v1.3 Contact Discovery*
*Researched: 2026-03-14*
