# Phase 14: Search Bar - Research

**Researched:** 2026-03-18
**Domain:** PostgreSQL Full-Text Search + PostgREST + Vanilla JS PWA filter extension
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Search replaces role input**: The search bar takes the role/title text input's position in the filter bar. It searches across ALL fields (name, role, company, location, school) instead of just enriched_headline.
- **AND logic with existing filters**: Search combines with industry and city dropdown filters using AND logic. e.g. searching "Miami" with Industry:Technology returns contacts matching both.
- **Independent clearing**: Clearing the search bar keeps active dropdown filters. Clearing filters keeps search text. "Clear all" button resets everything.
- **ilike fallback if tsvector fails**: If the tsvector migration doesn't work on Supabase, fall back to chained `.or()` with ilike on each searchable column. No Fuse.js — stays server-side.
- **Score sort always**: Keep `reconnect_score` descending regardless of whether search is active. No relevance-based sorting.
- **No term highlighting**: Same card rendering as browse mode. No bold/highlight on matched terms.
- **Search-specific count banner**: When searching: `12 contacts match "Sales Miami"`. When browsing: `Showing X of Y contacts`.
- **Paginated search results**: Same Load More behavior with 50-per-page pagination, consistent with browse mode.
- **Placeholder**: "Search contacts..."
- **Search icon**: Magnifying glass icon on the left side of the input, visually distinct from dropdown filters.
- **Debounce**: 300ms (matches existing Phase 13 role filter pattern).
- **No-results message**: "No contacts match '[query]'. Try different keywords or clear your search." with actionable guidance.
- **Minimum query length**: Claude's discretion (existing role filter uses 2-char minimum).

### Claude's Discretion
- Search icon implementation (SVG inline, CSS pseudo-element, or Unicode)
- tsvector column definition (which fields, weighting strategy)
- Exact PostgREST textSearch syntax and parameter passing
- Loading state while search query is in-flight
- Whether the role autocomplete datalist is removed or repurposed
- Input clear button (X icon) styling

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SEARCH-01 | User can search contacts via a search bar that matches across name, role, company, location, and school simultaneously | tsvector generated column on `connections` table concatenates `name`, `current_role`, `current_company`, `enriched_city`, `enriched_school`; PostgREST `.textSearch('fts', query, {type:'plain'})` queries it; ilike `.or()` fallback if migration fails |
| SEARCH-02 | Search results update with debounced input and display a result count | 300ms debounce via `setTimeout` (reuse `_roleDebounceTimer` pattern); `count:'exact'` already in `renderContacts()`; `buildCountBanner()` extended for search-specific text |
</phase_requirements>

---

## Summary

Phase 14 extends the existing Phase 13 Contacts page with a PostgreSQL-backed full-text search bar. The work splits into two tracks: a Supabase SQL migration that adds a `fts` tsvector generated column with GIN index to the `connections` table, and JavaScript changes to `contacts.js` that replace the role filter input with a search bar.

The tsvector approach is the right primary path: PostgreSQL's `GENERATED ALWAYS AS ... STORED` syntax creates an automatically maintained tsvector column from concatenated text fields. A GIN index makes searches fast. PostgREST's `.textSearch()` method with `type: 'plain'` safely handles raw user input (multi-word queries work without needing `&` operators). The ilike `.or()` fallback is a fully capable server-side alternative that handles partial substring matching if the tsvector migration encounters issues.

The JavaScript changes are straightforward modifications to existing patterns. `contactFilters` gains a `searchQuery` field replacing `roleQuery`. The debounce pattern, query builder, count banner, and empty-state logic all have clear extension points already in place. No new page, no new route, no new dependencies required.

**Primary recommendation:** Add the tsvector migration first and validate it on Supabase before writing any JS. If the migration succeeds, use `.textSearch('fts', query, {type:'plain'})`. If it fails, the `.or()` with ilike pattern covers all requirements without compromise.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@supabase/supabase-js` | 2.x (CDN, already loaded) | PostgREST client; `.textSearch()` and `.or()` methods | Already in use; no new dependency |
| PostgreSQL `tsvector` | Native (Supabase PostgreSQL 15+) | Full-text search index column | Standard PostgreSQL; no extension required |
| PostgreSQL GIN index | Native | Fast `@@` operator queries on tsvector | Required for acceptable query speed at scale |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `websearch_to_tsquery` (SQL only) | Native PG | Parses user input naturally (handles typos, partial words) | If switching to SQL-level direct queries |
| `plain` type in `.textSearch()` | supabase-js 2.x | Accepts raw user text without operator escaping | Use for `.textSearch()` calls from PWA |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tsvector generated column | ilike `.or()` on each column | ilike handles substrings (e.g. "Uni" matches "University"); tsvector handles full tokens only (stemmed). Locked: ilike is the fallback, tsvector is primary. |
| `type: 'plain'` textSearch | `type: 'websearch'` | websearch supports OR logic in query string; plain treats all words as AND. Plain is correct for this use case. |
| Single concatenated `to_tsvector` | `setweight()` per field | Weighted search ranks name matches higher than school. For v1.3, simple concatenation (equal weight) is sufficient; no relevance sort needed anyway. |

**Installation:** No new packages. supabase-js already loaded via CDN in `pwa/index.html`.

---

## Architecture Patterns

### Recommended Project Structure

Files being modified:

```
supabase/
└── migrations/
    └── 20260318000000_fts_column.sql     # NEW: tsvector generated column + GIN index

pwa/
├── js/
│   └── contacts.js                        # MODIFIED: search bar replaces role filter
└── css/
    └── app.css                            # MODIFIED: search icon + input padding
```

### Pattern 1: tsvector Generated Column

**What:** PostgreSQL stores a precomputed tsvector alongside the row. Updated automatically on any write to source columns. Queried via `@@` operator.

**When to use:** Primary path. Covers SEARCH-01 for multi-field simultaneous search.

**Migration SQL:**
```sql
-- Source: https://supabase.com/docs/guides/database/full-text-search
-- Source: https://www.postgresql.org/docs/current/textsearch-tables.html

ALTER TABLE connections
  ADD COLUMN IF NOT EXISTS fts tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english',
      coalesce(name, '') || ' ' ||
      coalesce(current_role, '') || ' ' ||
      coalesce(current_company, '') || ' ' ||
      coalesce(enriched_city, '') || ' ' ||
      coalesce(enriched_school, '')
    )
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_connections_fts ON connections USING GIN (fts);
```

**Notes:**
- `education_text` (the full education blob) is intentionally excluded — it creates very noisy matches. `enriched_school` (short name like "University of Miami") is correct.
- The `fts` column is NOT added to `BROWSE_SELECT` — it is never returned to the PWA, only filtered on.
- No RLS needed for the fts column itself since the `connections` table RLS already applies.

### Pattern 2: PostgREST textSearch Query

**What:** `.textSearch('fts', query, {type:'plain'})` maps to `fts @@ plainto_tsquery('english', query)` in SQL.

**When to use:** When tsvector migration is confirmed applied.

**Example:**
```javascript
// Source: https://supabase.com/docs/reference/javascript/textsearch
// type: 'plain' accepts raw user input — no operator escaping needed
if (contactFilters.searchQuery) {
  query = query.textSearch('fts', contactFilters.searchQuery, {
    type: 'plain',
    config: 'english'
  });
}
```

**Multi-word behavior:** `type: 'plain'` converts "Sales Miami" into `plainto_tsquery('sales & miami')` — AND logic, matching SEARCH-01's "combined query returns contacts matching all terms" success criterion.

### Pattern 3: ilike OR Fallback

**What:** Chain `.or()` with ilike conditions across all searchable columns. Handles substring matches (`"Uni"` matches `"University"`).

**When to use:** If tsvector migration fails on Supabase. Locked as fallback in CONTEXT.md.

**Example:**
```javascript
// Source: https://github.com/supabase/supabase/discussions/6778
// Each term split from input, OR across columns
if (contactFilters.searchQuery) {
  var term = contactFilters.searchQuery;
  var pattern = '%' + term + '%';
  query = query.or(
    'name.ilike.' + pattern + ',' +
    'current_role.ilike.' + pattern + ',' +
    'current_company.ilike.' + pattern + ',' +
    'enriched_city.ilike.' + pattern + ',' +
    'enriched_school.ilike.' + pattern
  );
}
```

**Limitation:** ilike doesn't handle multi-word split across columns (e.g. "Sales Miami" won't find contacts where "Sales" is in role and "Miami" is in city). For multi-word input, split on spaces and chain multiple `.or()` calls — each word ORed across all columns, then ANDed with each other. This matches the "combined query returns contacts matching all terms across fields" success criterion.

**Multi-word ilike pattern:**
```javascript
// Split "Sales Miami" → apply: (name|role|company|city|school ilike %Sales%)
//                                AND (name|role|company|city|school ilike %Miami%)
var terms = contactFilters.searchQuery.trim().split(/\s+/);
terms.forEach(function(term) {
  var p = '%' + term + '%';
  query = query.or(
    'name.ilike.' + p + ',' +
    'current_role.ilike.' + p + ',' +
    'current_company.ilike.' + p + ',' +
    'enriched_city.ilike.' + p + ',' +
    'enriched_school.ilike.' + p
  );
});
```

### Pattern 4: State Extension

**What:** Replace `roleQuery` with `searchQuery` in `contactFilters`. Remove datalist autocomplete.

**When to use:** Always — this is the required state migration from Phase 13.

```javascript
const contactFilters = {
  searchQuery: '',           // replaces roleQuery
  industryFilter: null,
  cityFilter: null,
  offset: 0,
  totalCount: 0,
};
```

### Pattern 5: Count Banner with Search Context

**What:** `buildCountBanner()` returns different text when search is active.

```javascript
function buildCountBanner(showing, total) {
  if (total === 0) return '';
  if (contactFilters.searchQuery) {
    return '<div class="contacts-count-banner">' + total + ' contacts match "' + escapeHtml(contactFilters.searchQuery) + '"</div>';
  }
  return '<div class="contacts-count-banner">Showing ' + showing + ' of ' + total + ' contacts</div>';
}
```

### Pattern 6: Search Bar HTML

**What:** Replace the role filter group in `buildFilterBarHtml()` with a search bar wrapper that positions an icon.

```javascript
// Search bar group replaces the ROLE / TITLE filter-group-full block
'<div class="filter-group filter-group-full search-bar-wrapper">' +
  '<label ...>SEARCH</label>' +
  '<div class="search-input-wrap">' +
    '<span class="search-icon">&#128269;</span>' +  // or inline SVG
    '<input type="search" class="filter-input search-input"' +
      ' placeholder="Search contacts..."' +
      ' value="' + escapeHtml(contactFilters.searchQuery) + '"' +
      ' oninput="onContactSearchInput(this.value)"' +
    '/>' +
  '</div>' +
'</div>'
```

### Pattern 7: Debounce (reuse existing)

**What:** `_roleDebounceTimer` variable can be renamed `_searchDebounceTimer` or reused as-is. 300ms matches CONTEXT.md decision.

```javascript
// Rename _roleDebounceTimer → _searchDebounceTimer (or reuse same var)
let _searchDebounceTimer = null;

function onContactSearchInput(value) {
  clearTimeout(_searchDebounceTimer);
  if (!value || value.length < 2) {
    if (!value) {
      contactFilters.searchQuery = '';
      contactFilters.offset = 0;
      // re-render immediately when cleared
      var content = document.getElementById('app-content');
      if (content) renderContacts(content);
    }
    return;
  }
  _searchDebounceTimer = setTimeout(function() {
    contactFilters.searchQuery = value;
    contactFilters.offset = 0;
    var content = document.getElementById('app-content');
    if (content) renderContacts(content);
  }, 300);
}
```

### Anti-Patterns to Avoid

- **Adding `fts` to BROWSE_SELECT**: The fts column is a search-only column; returning it wastes bandwidth and exposes internal data. Never add it to the select list.
- **Using `type: 'websearch'`** for the primary query: websearch type allows OR logic from user input (e.g. "Sales OR Miami") which violates the AND-logic success criterion. Use `type: 'plain'`.
- **Per-keystroke queries**: The out-of-scope table in REQUIREMENTS.md explicitly lists this. Always debounce.
- **Fuse.js or client-side filtering**: Locked out by CONTEXT.md. All search is server-side.
- **Removing roleQuery tests without adding searchQuery tests**: The Phase 13 test `test_contact_filters_shape` checks for `roleQuery`. Phase 14 replaces it with `searchQuery` — the test must be updated.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Stemming / tokenization | Custom text normalization | PostgreSQL `to_tsvector('english', ...)` | Handles stemming (searches → search), stopwords, multiple languages |
| Search index maintenance | Trigger-based tsvector updates | `GENERATED ALWAYS AS ... STORED` | Automatically updated on INSERT/UPDATE, no trigger code |
| Multi-word query parsing | Manual `&` injection | `type: 'plain'` in `.textSearch()` (maps to `plainto_tsquery`) | Safe for raw user input; handles punctuation, extra spaces |
| Substring matching fallback | Custom SQL function | `.or()` with `ilike` | Already in Supabase JS client |

**Key insight:** PostgreSQL's native FTS handles all edge cases in text normalization. The only hand-rolled part is the tsvector column definition (which fields to include) — everything else is standard SQL and PostgREST.

---

## Common Pitfalls

### Pitfall 1: tsvector Does Not Match Substrings

**What goes wrong:** User types "Uni" expecting to match "University of Miami" — but FTS only matches full tokens. `plainto_tsquery('uni')` does not match `to_tsvector('university')`.

**Why it happens:** PostgreSQL FTS is designed for full-word matching (with stemming). It is not a LIKE-style substring search.

**How to avoid:** The ilike fallback handles substrings correctly. For Phase 14 success criteria, the test cases use full words ("University of Miami", "Sales Miami") — full-word FTS handles these. If short prefix search becomes important, that is a v1.4 concern (Fuse.js or pg_trgm). For now, 2-char minimum + FTS is acceptable.

**Warning signs:** Users report "University" not matching when they type "Univ". This is expected behavior for FTS; document it or add prefix-matching with `:*` tsquery syntax.

### Pitfall 2: tsvector Column in BROWSE_SELECT

**What goes wrong:** Adding `fts` to `BROWSE_SELECT` returns large tsvector blobs in every response, inflating payload size.

**Why it happens:** Developer copies column list without thinking.

**How to avoid:** `fts` is filter-only. Never add it to `BROWSE_SELECT`. The column is invisible to the PWA.

### Pitfall 3: Multi-Word ilike Needs Per-Term Looping

**What goes wrong:** `query.or('name.ilike.%Sales Miami%')` — the whole phrase must appear literally. "Sales" in role + "Miami" in city would not match.

**Why it happens:** ilike with a full phrase requires the phrase to appear in a single column.

**How to avoid:** Split the query on whitespace and apply a separate `.or()` call for each term. Each `.or()` call is ANDed with the others by PostgREST — matching the "all terms" success criterion.

### Pitfall 4: `clearContactFilters()` Must Reset `searchQuery`, Not `roleQuery`

**What goes wrong:** `clearContactFilters()` still resets `roleQuery` after the rename, so the search bar value never clears.

**Why it happens:** Copy-paste from Phase 13 code without updating the state field name.

**How to avoid:** Update `clearContactFilters()` to set `searchQuery: ''` and remove `roleQuery`. Also update `hasActiveFilter` check in `renderContactsPage()` and `buildFilterBarHtml()`.

### Pitfall 5: Phase 13 Tests Will Break on `roleQuery` Removal

**What goes wrong:** `test_role_filter_exists()` and `test_contact_filters_shape()` in `tests/test_phase13_contacts.py` check for `roleQuery`, `role-suggestions`, `ilike` in specific Phase 13 contexts. Replacing them will fail these tests.

**Why it happens:** Phase 13 tests encode Phase 13 implementation details.

**How to avoid:** Write a new `tests/test_phase14_search.py` that checks for `searchQuery` and the new patterns. Update or remove the specific Phase 13 assertions that are no longer accurate (e.g., `roleQuery` → `searchQuery`, `role-suggestions` datalist removed). The test update is a first-class deliverable of this phase.

### Pitfall 6: Migration Must Run Before PWA Uses textSearch

**What goes wrong:** Calling `.textSearch('fts', ...)` on a table where the `fts` column does not exist returns a PostgREST 400 error.

**Why it happens:** Migration is applied separately from code deployment on Supabase.

**How to avoid:** Apply migration via Supabase dashboard SQL editor or `supabase db push` before deploying the updated `contacts.js`. Verify with: `SELECT fts FROM connections LIMIT 1;`

---

## Code Examples

Verified patterns from official sources:

### tsvector Migration (PRIMARY PATH)
```sql
-- Source: https://www.postgresql.org/docs/current/textsearch-tables.html
-- Source: https://supabase.com/docs/guides/database/full-text-search
ALTER TABLE connections
  ADD COLUMN IF NOT EXISTS fts tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english',
      coalesce(name, '') || ' ' ||
      coalesce(current_role, '') || ' ' ||
      coalesce(current_company, '') || ' ' ||
      coalesce(enriched_city, '') || ' ' ||
      coalesce(enriched_school, '')
    )
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_connections_fts ON connections USING GIN (fts);
```

### PostgREST textSearch Query
```javascript
// Source: https://supabase.com/docs/reference/javascript/textsearch
// type:'plain' = plainto_tsquery — safe for raw user input, AND logic per word
if (contactFilters.searchQuery) {
  query = query.textSearch('fts', contactFilters.searchQuery, {
    type: 'plain',
    config: 'english'
  });
}
```

### ilike OR Fallback (multi-word)
```javascript
// Source: https://github.com/supabase/supabase/discussions/6778
// Each term ORed across all searchable columns, terms ANDed together
if (contactFilters.searchQuery) {
  var terms = contactFilters.searchQuery.trim().split(/\s+/);
  terms.forEach(function(term) {
    var p = '%' + term + '%';
    query = query.or(
      'name.ilike.' + p + ',' +
      'current_role.ilike.' + p + ',' +
      'current_company.ilike.' + p + ',' +
      'enriched_city.ilike.' + p + ',' +
      'enriched_school.ilike.' + p
    );
  });
}
```

### Search Icon (SVG inline — recommended)
```html
<!-- Inline SVG: no external dependency, scales with CSS, standard magnifying glass -->
<svg class="search-icon-svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="8.5" cy="8.5" r="5.5"/>
  <line x1="13" y1="13" x2="18" y2="18"/>
</svg>
```

### CSS for Search Input with Icon
```css
/* Search bar wrapper — positions icon inside input */
.search-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.search-icon-svg {
  position: absolute;
  left: 8px;
  width: 16px;
  height: 16px;
  color: var(--text-muted);
  pointer-events: none;
}
.search-input {
  padding-left: 30px;  /* room for icon */
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Trigger-based tsvector maintenance | `GENERATED ALWAYS AS ... STORED` tsvector column | PostgreSQL 12+ | No trigger code needed; generated columns handle updates automatically |
| Manual `to_tsquery` operator syntax | `plainto_tsquery` / `websearch_to_tsquery` | PostgreSQL 9.6+ | Safe for raw user input without escaping |
| Fuse.js client-side search | Server-side FTS via PostgREST | Project decision (CONTEXT.md) | Correct for large datasets; no client payload overhead |

**Deprecated/outdated:**
- `type: null` (default) in `.textSearch()`: Requires tsquery operator syntax in user input (`'eggs' & 'ham'`). Not suitable for a user-facing search bar. Use `type: 'plain'` instead.
- Role autocomplete datalist (`role-suggestions`): Replaced by open-ended search bar. Remove the `<datalist>` element and autocomplete query.

---

## Open Questions

1. **Has the enrichment_columns migration (20260316000000) been applied to production Supabase?**
   - What we know: STATE.md records "RESOLVED: supabase/migrations/20260316000000_enrichment_columns.sql was applied before Phase 13 human verification"
   - What's unclear: Whether `enriched_school` column is populated with meaningful data (governs search recall quality)
   - Recommendation: Validate with `SELECT count(*) FROM connections WHERE enriched_school IS NOT NULL;` before testing school searches. This does not block implementation.

2. **Minimum query length: 1 char or 2 chars?**
   - What we know: Phase 13 role filter uses 2-char minimum to avoid noise. CONTEXT.md delegates this to Claude's discretion.
   - Recommendation: Use **2-char minimum**, consistent with existing pattern. Single characters yield too many results to be useful and increase query frequency.

3. **Loading state during search query in-flight**
   - What we know: CONTEXT.md lists this as Claude's discretion. Current browse page shows full `<div class="loading">` spinner on first load only.
   - Recommendation: Do not show a full-page spinner on search. Debounce absorbs the latency. If desired, a subtle `opacity: 0.5` on the results list during the async call is sufficient without a new spinner component.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (detected: `tests/` directory, `conftest.py`, multiple test files) |
| Config file | `pytest.ini` or implicit (no explicit config file detected) |
| Quick run command | `python -m pytest tests/test_phase14_search.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEARCH-01 | `contacts.js` has `searchQuery` in `contactFilters` state | unit (static analysis) | `python -m pytest tests/test_phase14_search.py::test_search_query_state -x` | ❌ Wave 0 |
| SEARCH-01 | `contacts.js` queries `fts` column via `.textSearch()` | unit (static analysis) | `python -m pytest tests/test_phase14_search.py::test_textsearch_call -x` | ❌ Wave 0 |
| SEARCH-01 | `contacts.js` has ilike OR fallback pattern | unit (static analysis) | `python -m pytest tests/test_phase14_search.py::test_ilike_fallback_pattern -x` | ❌ Wave 0 |
| SEARCH-01 | Migration SQL contains `fts tsvector GENERATED ALWAYS AS` | unit (static analysis) | `python -m pytest tests/test_phase14_search.py::test_migration_has_fts_column -x` | ❌ Wave 0 |
| SEARCH-01 | Migration SQL contains GIN index on `fts` | unit (static analysis) | `python -m pytest tests/test_phase14_search.py::test_migration_has_gin_index -x` | ❌ Wave 0 |
| SEARCH-02 | `contacts.js` has `searchQuery` debounce with 300ms timer | unit (static analysis) | `python -m pytest tests/test_phase14_search.py::test_search_debounce_pattern -x` | ❌ Wave 0 |
| SEARCH-02 | `buildCountBanner` has search-specific format `contacts match` | unit (static analysis) | `python -m pytest tests/test_phase14_search.py::test_count_banner_search_format -x` | ❌ Wave 0 |
| SEARCH-01/02 | Search bar HTML uses `Search contacts...` placeholder | unit (static analysis) | `python -m pytest tests/test_phase14_search.py::test_search_placeholder -x` | ❌ Wave 0 |
| SEARCH-01/02 | `clearContactFilters()` resets `searchQuery` (not `roleQuery`) | unit (static analysis) | `python -m pytest tests/test_phase14_search.py::test_clear_filters_resets_search -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_phase14_search.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase14_search.py` — covers SEARCH-01, SEARCH-02 via PWA static file analysis
- [ ] Update `tests/test_phase13_contacts.py` — `test_role_filter_exists()` and `test_contact_filters_shape()` will fail after `roleQuery` removal; need to adjust assertions or remove outdated ones

*(No new framework install needed — pytest already in use)*

---

## Sources

### Primary (HIGH confidence)
- [Supabase Full Text Search Guide](https://supabase.com/docs/guides/database/full-text-search) — tsvector generated column syntax, GIN index, textSearch PostgREST method
- [Supabase JS textSearch Reference](https://supabase.com/docs/reference/javascript/textsearch) — method signature, `type` parameter values (plain/phrase/websearch), code examples
- [PostgreSQL textsearch-tables docs](https://www.postgresql.org/docs/current/textsearch-tables.html) — `GENERATED ALWAYS AS ... STORED` syntax, GIN index creation
- [PostgreSQL generated columns docs](https://www.postgresql.org/docs/current/ddl-generated-columns.html) — generated column constraints and rules
- `pwa/js/contacts.js` — Existing debounce, filter state, query builder, count banner patterns (project source)
- `tests/test_phase13_contacts.py` — Existing test pattern (Python static file analysis) used for Phase 14 test design

### Secondary (MEDIUM confidence)
- [Supabase Discussion #6778: Search on multiple columns with ilike](https://github.com/supabase/supabase/discussions/6778) — `.or()` syntax for multi-column ilike, verified against official PostgREST filter docs

### Tertiary (LOW confidence)
- None — all critical claims verified against official sources

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use; tsvector/GIN verified in PostgreSQL and Supabase official docs
- Architecture: HIGH — migration SQL pattern verified in official docs; JS patterns derived directly from existing Phase 13 code
- Pitfalls: HIGH — FTS substring limitation is well-documented; test breakage identified from direct code inspection
- Validation architecture: HIGH — test framework detected in repo; test patterns match existing phase test style

**Research date:** 2026-03-18
**Valid until:** 2026-06-18 (stable domain — PostgreSQL FTS API is not fast-moving)
