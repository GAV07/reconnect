# Phase 13: Contacts Browse Page - Research

**Researched:** 2026-03-17
**Domain:** Vanilla JS PWA + PostgREST (Supabase JS v2) — browse/filter/paginate contacts
**Confidence:** HIGH

## Summary

Phase 13 adds a dedicated Contacts tab to the PWA. Users browse all non-archived contacts with role, industry, and location filters backed by server-side PostgREST queries. All implementation patterns are established in the existing codebase (`queue.js`, `contact.js`, `app.js`) — this phase is an extension, not a greenfield build.

The technical domain is well-understood: Supabase JS v2's `.from().select().ilike().eq().range()` chain covers all filtering and pagination needs. The enriched columns (`enriched_industry`, `enriched_headline`, `enriched_city`) were added by the Phase 12 migration and are indexed for filter performance. No new libraries are needed — this phase ships pure vanilla JS + CSS following existing PWA conventions.

The primary architectural decision this research informs is how to populate filter dropdowns (separate up-front queries vs. extracting from first data page) and how to handle the role autocomplete (debounce timing, min-char threshold). Both are left to Claude's discretion per CONTEXT.md.

**Primary recommendation:** Use separate up-front queries for filter dropdown values (one query each for distinct industries and cities on page load) so filters are populated immediately before the user scrolls. Use 300ms debounce + 2-character minimum for role autocomplete suggestions to balance responsiveness and request count.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Contact card layout**
- Compact row format: Name · Role · Company on first line; industry chip + city + score on second line. Fits ~8-10 cards per screen
- Show reconnect_score as a badge on each card — helps prioritize while browsing
- Show signal badge when a contact has one assigned (Warm Lead, Nurture, etc.) — provides triage context
- Tap navigates to profile: Tap anywhere on the card → existing contact profile page (contact.js via `#/contact/{id}`)

**Filter design**
- Role/title filter: Free-text input with autocomplete suggestions populated from distinct values. Filters contacts whose role/headline contains the typed text (case-insensitive `ilike`)
- Industry filter: Standard `<select>` dropdown populated from distinct `enriched_industry` values in the database
- Location filter: Standard `<select>` dropdown populated from distinct `enriched_city` values. City only — no country dropdown
- Filter combination: AND logic — all active filters must match. A visible "Clear filters" button appears when any filter is active
- Filter layout: Role text input on top, Industry and Location dropdowns below side-by-side

**Navigation placement**
- 4-tab bottom nav: Queue | Contacts | Dashboard | Settings — Contacts is the 2nd tab
- Icon: People/group silhouette (two-person icon) — standard contacts icon
- Label: "Contacts"
- Route: `#/contacts` — new hash route in `app.js` router

**Pagination UX**
- Load More button: Explicit button at bottom of list — user controls when to fetch the next page
- Page size: 50 contacts per request
- Total count: Display "Showing X of Y contacts" — gives context for list size and filter narrowing
- Default sort: Score high-to-low (reconnect_score descending) — best contacts surface first
- Server-side pagination: PostgREST `.range(offset, offset + 49)` — no single request fetches more than 50 rows

### Claude's Discretion
- Filter value fetching strategy: Claude decides whether to fetch distinct filter values via separate queries on page load, or extract them from the first data page. Should optimize for UX (filters populated before scrolling) vs request count
- Autocomplete implementation: Claude decides the debounce timing and minimum character threshold for role suggestions. Should feel responsive without excessive queries
- Empty state design: Claude designs the empty state for no results (filters too narrow) and no contacts (fresh install). Should match existing PWA empty state patterns
- Loading skeleton: Claude decides whether to show skeleton rows or a spinner during initial load and pagination. Should match existing patterns in queue.js
- Count query approach: Claude decides whether to use PostgREST `count=exact` header or a separate count query. Should consider performance with large datasets
- Active filter indicator: Claude decides how "Clear filters" is presented (button, link, or X badges on active filters)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BROWSE-01 | User can view a paginated list of all non-archived contacts in the PWA via a Contacts page | PostgREST `.range()` + `.neq('user_priority', 'never')` + new `contacts.js` module + `#/contacts` route |
| BROWSE-02 | User can filter contacts by role/title | PostgREST `.ilike('enriched_headline', '%value%')` — enriched_headline is the correct column per Phase 12 |
| BROWSE-03 | User can filter contacts by industry | PostgREST `.eq('enriched_industry', value)` — column is indexed via Phase 12 migration |
| BROWSE-04 | User can filter contacts by location | PostgREST `.eq('enriched_city', value)` — column is indexed via Phase 12 migration |
| BROWSE-05 | Contacts page uses server-side pagination and explicit field selection (no raw_enrichment in payload) | Explicit BROWSE_SELECT field list + `.range(offset, offset+49)` + `count: 'exact'` option |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @supabase/supabase-js | 2.x (CDN, already loaded) | PostgREST queries — filter, range, count | Already in use; `db` global available in all JS modules |
| Vanilla JS (ES5/ES6) | N/A | Module logic | Existing codebase pattern — no bundler, no framework |
| CSS custom properties | N/A | Styling | Established in app.css with full token set |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| None | — | — | No new dependencies needed |

**No new packages to install.** The Supabase client is already loaded via CDN in `index.html`:
```html
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js"></script>
```

## Architecture Patterns

### Recommended Project Structure

New and modified files for this phase:

```
pwa/
├── index.html          — add Contacts nav tab + <script src="js/contacts.js">
├── js/
│   ├── app.js          — add '/contacts' to routes + case 'contacts' in render()
│   └── contacts.js     — NEW: browse page module
└── css/
    └── app.css         — add contact-row, contacts-filter-bar, load-more styles
```

### Pattern 1: Module-level Filter State (from queue.js)

**What:** A module-level plain object tracks active filter values. Functions that change filters call the re-render function with the container element.

**When to use:** Any filter that triggers a new server-side query.

**Example (from queue.js, adapt for contacts.js):**
```javascript
// contacts.js — filter state object
const contactFilters = {
  roleQuery: '',         // ilike value, empty = no filter
  industryFilter: null,  // null = all
  cityFilter: null,      // null = all
  offset: 0,             // pagination cursor
  totalCount: 0,         // total matching rows
};

function setContactRoleFilter(value) {
  contactFilters.roleQuery = value || '';
  contactFilters.offset = 0;  // reset pagination when filter changes
  const content = document.getElementById('app-content');
  if (content) renderContacts(content);
}
```

### Pattern 2: Explicit Field Selection — BROWSE_SELECT Constant

**What:** A named constant lists exactly which columns to fetch. Never use `select('*')` for browse — it includes `raw_enrichment` (can be hundreds of KB per row).

**When to use:** ALL contacts page queries.

**Example:**
```javascript
// contacts.js — never select('*') on connections table
const BROWSE_SELECT = 'id,full_name,name,current_role,current_company,enriched_industry,enriched_city,enriched_headline,reconnect_score,latest_signal,linkedin_url,user_priority';
```

Note: `full_name` vs `name` — check migration. The `connections` table uses `name` in models.py but `full_name` may appear in some migrations. Verify against actual column name before shipping.

### Pattern 3: PostgREST Query with count=exact + range

**What:** Supabase JS v2 `select()` accepts a second options object. Pass `{ count: 'exact' }` to get the total filtered count in the same request. Chain `.range(offset, offset + 49)` to limit the result page.

**When to use:** Initial load and every "Load More" press.

**Example (verified pattern from Supabase JS v2 docs):**
```javascript
// Source: https://supabase.com/docs/reference/javascript/select
const { data, count, error } = await db
  .from('connections')
  .select(BROWSE_SELECT, { count: 'exact' })
  .neq('user_priority', 'never')        // exclude archived
  .ilike('enriched_headline', `%${roleQuery}%`)   // role filter (when active)
  .eq('enriched_industry', industryFilter)         // industry filter (when active)
  .eq('enriched_city', cityFilter)                 // city filter (when active)
  .order('reconnect_score', { ascending: false })
  .range(offset, offset + 49);

// data = array of up to 50 rows
// count = total matching rows (for "Showing X of Y")
```

**Important:** Only chain filter methods when the filter is active. Build the query conditionally:
```javascript
let query = db.from('connections').select(BROWSE_SELECT, { count: 'exact' })
  .neq('user_priority', 'never')
  .order('reconnect_score', { ascending: false })
  .range(contactFilters.offset, contactFilters.offset + 49);

if (contactFilters.roleQuery) {
  query = query.ilike('enriched_headline', `%${contactFilters.roleQuery}%`);
}
if (contactFilters.industryFilter) {
  query = query.eq('enriched_industry', contactFilters.industryFilter);
}
if (contactFilters.cityFilter) {
  query = query.eq('enriched_city', contactFilters.cityFilter);
}
```

### Pattern 4: Filter Dropdown Value Fetching Strategy

**What:** Fetch distinct `enriched_industry` and `enriched_city` values in separate queries on page load, before (or alongside) the first data query.

**Recommendation:** Use separate up-front queries. Rationale: with 50-contact pages, the first data page may not contain all industry/city values present in the full dataset. Showing incomplete filter options would confuse users. Two extra lightweight queries (distinct values only, no data payload) are acceptable.

```javascript
async function fetchFilterOptions() {
  // Fetch distinct industries
  const { data: industries } = await db
    .from('connections')
    .select('enriched_industry')
    .neq('user_priority', 'never')
    .not('enriched_industry', 'is', null)
    .order('enriched_industry');

  // Fetch distinct cities
  const { data: cities } = await db
    .from('connections')
    .select('enriched_city')
    .neq('user_priority', 'never')
    .not('enriched_city', 'is', null)
    .order('enriched_city');

  return {
    industries: [...new Set((industries || []).map(r => r.enriched_industry).filter(Boolean))],
    cities: [...new Set((cities || []).map(r => r.enriched_city).filter(Boolean))],
  };
}
```

Note: PostgREST does not natively support `SELECT DISTINCT` — the JS client returns all rows, so `new Set()` deduplication on the client is required. For a database with hundreds of contacts, this is cheap.

### Pattern 5: Role Autocomplete with Debounce

**What:** Role filter is a text input that suggests matching `enriched_headline` values. Suggestions appear after 2 characters with 300ms debounce.

**Recommendation:** 300ms debounce, 2-character minimum. This matches mobile typing behavior and avoids a query on every keystroke.

```javascript
let _roleDebounceTimer = null;

function onRoleInputChange(value) {
  clearTimeout(_roleDebounceTimer);
  if (value.length < 2) {
    // Clear suggestions, but don't fire a filter query
    hideSuggestions();
    if (!value) {
      // Empty input: clear the role filter and re-render
      contactFilters.roleQuery = '';
      contactFilters.offset = 0;
      renderContacts(document.getElementById('app-content'));
    }
    return;
  }
  _roleDebounceTimer = setTimeout(async () => {
    // Fetch suggestions for autocomplete datalist
    const { data } = await db
      .from('connections')
      .select('enriched_headline')
      .not('enriched_headline', 'is', null)
      .ilike('enriched_headline', `%${value}%`)
      .limit(10);
    showSuggestions((data || []).map(r => r.enriched_headline).filter(Boolean));
  }, 300);
}
```

Use an HTML `<datalist>` element tied to the text input for suggestions — zero JS UI complexity, works on mobile browsers.

### Pattern 6: Load More + Accumulating Results

**What:** "Load More" appends the next page to the existing list (does not replace it). Offset advances by 50 on each press.

**Example:**
```javascript
let _contactRows = [];  // accumulated rows across pages

async function loadMoreContacts() {
  contactFilters.offset += 50;
  const { data, error } = await buildAndExecuteQuery(); // re-use query builder, no count needed
  if (data) {
    _contactRows = _contactRows.concat(data);
    renderContactList(_contactRows, /* append=true */);
  }
}
```

### Pattern 7: Router Integration (from app.js)

**What:** Add `/contacts` to the `routes` object and a `case 'contacts'` in the `render()` switch.

```javascript
// In app.js routes object:
const routes = {
  '/queue':     { module: 'queue',     title: 'Queue' },
  '/contacts':  { module: 'contacts',  title: 'Contacts' },  // ADD THIS
  '/contact':   { module: 'contact',   title: 'Contact' },
  '/dashboard': { module: 'dashboard', title: 'Dashboard' },
  '/preferences': { module: 'preferences', title: 'Settings' },
};

// In render() switch:
case 'contacts':
  await renderContacts(content);
  break;
```

### Pattern 8: 4-Tab Bottom Nav

**What:** Current nav has 3 tabs (Queue, Dashboard, Settings). Add Contacts as 2nd tab. The nav active-state logic in `app.js` uses `href` attribute matching — new tab needs `href="#/contacts"`.

**Current nav structure in index.html (3 tabs):**
```html
<nav class="bottom-nav">
  <a href="#/queue" class="active"> ... Queue</a>
  <a href="#/dashboard"> ... Dashboard</a>
  <a href="#/preferences"> ... Settings</a>
</nav>
```

**Updated 4-tab structure:**
```html
<nav class="bottom-nav">
  <a href="#/queue"> ... Queue</a>
  <a href="#/contacts"> ... Contacts</a>  <!-- INSERT HERE -->
  <a href="#/dashboard"> ... Dashboard</a>
  <a href="#/preferences"> ... Settings</a>
</nav>
```

**People icon SVG (two-person silhouette, matching existing icon style):**
```html
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
  <circle cx="9" cy="7" r="4"/>
  <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
  <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
</svg>
```

### Pattern 9: Contact Row Card Layout

**What:** Compact 2-line row. Line 1: Name + score badge (flex row). Line 2: Industry chip + city + signal badge.

```javascript
function renderContactRow(conn) {
  const name = escapeHtml(conn.name || conn.full_name || 'Unknown');
  const role = escapeHtml(conn.current_role || '');
  const company = escapeHtml(conn.current_company || '');
  const roleLine = company ? `${role} @ ${company}` : role;
  const score = Math.round(conn.reconnect_score || 0);
  const industry = escapeHtml(conn.enriched_industry || '');
  const city = escapeHtml(conn.enriched_city || '');
  const signal = conn.latest_signal;
  const signalInfo = signal && SIGNAL_ACTIONS[signal] ? SIGNAL_ACTIONS[signal] : null;

  const industryChip = industry
    ? `<span class="industry-chip">${industry}</span>`
    : '';
  const citySpan = city
    ? `<span class="contact-row-city">${city}</span>`
    : '';
  const signalBadge = signalInfo
    ? `<span class="signal-badge" style="background:${signalInfo.bg};color:${signalInfo.color};">${escapeHtml(signalInfo.label)}</span>`
    : '';

  return `
    <div class="contact-row" onclick="navigate('#/contact/${conn.id}')">
      <div class="contact-row-header">
        <div>
          <div class="contact-row-name">${name}</div>
          <div class="contact-row-role">${roleLine}</div>
        </div>
        <div class="score-badge">${score}</div>
      </div>
      <div class="contact-row-meta">
        ${industryChip}${citySpan}${signalBadge}
      </div>
    </div>`;
}
```

### Anti-Patterns to Avoid

- **`select('*')` on connections table:** Pulls in `raw_enrichment` (JSONB, potentially hundreds of KB per contact). With 500+ contacts, this approaches Supabase free-tier egress limits. Always use the explicit `BROWSE_SELECT` constant.
- **Client-side filtering after full fetch:** The queue.js pattern fetches all rows and filters in JS — acceptable for the queue (usually <50 items) but wrong for browse (potentially 500+ contacts). ALL filters must be server-side PostgREST filters.
- **Re-fetching filter options on every filter change:** Distinct industries/cities rarely change. Fetch them once on page load and cache in module-level variables.
- **Resetting `_contactRows` on every filter change but forgetting to reset `offset`:** Always reset `offset = 0` when any filter value changes.
- **Not guarding null enriched columns in ilike:** If `enriched_headline` is NULL for a contact, `.ilike('enriched_headline', '%value%')` will correctly exclude that row (SQL ILIKE on NULL returns NULL, not matched). This is the desired behavior — contacts without a headline don't appear in role-filtered results. No special handling needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Total count for "Showing X of Y" | Separate COUNT query | `select(BROWSE_SELECT, { count: 'exact' })` | One round-trip; PostgREST returns count in response headers, Supabase JS surfaces it as `count` |
| Case-insensitive role filter | JS string.toLowerCase() | `.ilike('enriched_headline', '%value%')` | Server-side; uses indexed column; works across all contacts, not just current page |
| Autocomplete deduplication | Complex data structure | `new Set()` + HTML `<datalist>` | `<datalist>` is native browser UI, zero JS complexity |
| Distinct dropdown values | Manual DISTINCT SQL | Fetch column + `new Set()` client-side | PostgREST doesn't expose DISTINCT directly; JS Set is sufficient for hundreds of values |

**Key insight:** This phase has no hard problems. Every pattern is solved by existing Supabase JS v2 primitives that are already in use in the codebase. The risk is in scope creep (adding features beyond the locked decisions) and payload bloat (forgetting to exclude `raw_enrichment`).

## Common Pitfalls

### Pitfall 1: active nav state for /contacts/* routes

**What goes wrong:** The `#/contact/{id}` route (singular) highlights the Queue tab in the current `app.js` active-state logic. Adding a `/contacts` (plural) tab requires the active-state logic to also keep Contacts highlighted when viewing a contact profile that was opened from the Contacts page.

**Why it happens:** The current logic uses `currentPath.startsWith('#/contact')` to keep Queue active. This will also match `/contacts`, unintentionally highlighting the wrong tab.

**How to avoid:** Update the active-state logic in `app.js` to distinguish between `/contact/{id}` (opened from queue) and contact profiles opened from `/contacts`. One approach: use `sessionStorage` to track "came from contacts" and reflect that in nav highlighting. Simpler approach: accept that tapping a contact from the Contacts page briefly highlights Queue — the user returns to Contacts via the tab, not the back button. Verify acceptable UX with the existing behavior.

**Warning signs:** Queue tab lights up when browsing contacts from the Contacts tab.

### Pitfall 2: user_priority='never' exclusion

**What goes wrong:** "Non-archived" contacts are those where `user_priority != 'never'`. Using `.neq('user_priority', 'never')` in PostgREST will NOT include contacts where `user_priority IS NULL` — PostgREST's `.neq()` follows SQL semantics where NULL != 'never' returns NULL (not TRUE).

**Why it happens:** SQL three-valued logic. `.neq('user_priority', 'never')` generates `user_priority != 'never'` which excludes NULLs.

**How to avoid:** Test with the actual Supabase JS v2 client. In practice, `neq` in postgrest-js does include NULLs because it generates `user_priority=neq.never` which PostgREST handles as "not equal, including nulls". Verify this behavior against the actual database — if NULLs are excluded, use `.or('user_priority.neq.never,user_priority.is.null')` instead.

**Warning signs:** Contacts without an assigned priority (the majority) disappear from the browse list.

### Pitfall 3: enrichment_columns migration not applied to Supabase

**What goes wrong:** `enriched_industry`, `enriched_city`, `enriched_headline` columns don't exist in the live Supabase PostgreSQL database yet. Phase 13 queries against them will return empty data or errors.

**Why it happens:** The migration file `20260316000000_enrichment_columns.sql` is in the repo but must be applied manually to the Supabase project (noted as a blocker in STATE.md).

**How to avoid:** Before implementing Phase 13, apply the migration via Supabase Dashboard SQL editor or `supabase db push`. Add a smoke test that queries `enriched_industry` and asserts no error.

**Warning signs:** Filter dropdowns show empty options; all contacts appear unfiltered regardless of filter selection.

### Pitfall 4: count='exact' performance on large datasets

**What goes wrong:** `count: 'exact'` issues a `SELECT COUNT(*)` on the filtered result set. On a table with thousands of rows and no WHERE clause (initial load with no filters), this is a full table scan.

**Why it happens:** Exact count requires scanning all matching rows.

**How to avoid:** For this project scale (hundreds, not millions of contacts), exact count is fine. If performance becomes an issue later, switch to `count: 'estimated'` (uses PostgreSQL statistics, fast but approximate). The indexes on `enriched_industry` and `enriched_city` ensure filtered counts are fast.

**Warning signs:** Initial page load is slow (>1 second on mobile) when no filters are active.

### Pitfall 5: Navigation active state breaks with 4-tab nav

**What goes wrong:** The existing `app.js` active state logic was written for 3 tabs. The line `href === '#/queue'` in the active-state update will need to correctly map `/contact/{id}` to whichever tab the user came from.

**Current logic (app.js line 65):**
```javascript
a.classList.toggle('active', href === currentPath || (currentPath.startsWith('#/contact') && href === '#/queue'));
```

**How to avoid:** When adding the 4th tab, update this logic. The simplest fix: keep the existing `/contact` → Queue mapping since contact profiles are primarily accessed from the Queue flow. Contacts-page-opened contacts will briefly show no active tab (acceptable) or can use sessionStorage to track origin.

## Code Examples

Verified patterns from existing codebase and Supabase JS v2 docs:

### Complete contacts.js Module Skeleton

```javascript
/* contacts.js — Contacts browse page */

const BROWSE_SELECT = [
  'id', 'name', 'current_role', 'current_company',
  'enriched_industry', 'enriched_city', 'enriched_headline',
  'reconnect_score', 'latest_signal', 'user_priority'
].join(',');

const contactFilters = {
  roleQuery: '',
  industryFilter: null,
  cityFilter: null,
  offset: 0,
  totalCount: 0,
};

let _contactRows = [];
let _filterOptions = { industries: [], cities: [] };
let _roleDebounceTimer = null;

async function renderContacts(container) {
  if (!db) {
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Supabase not configured.</p></div>';
    return;
  }

  // On first load (offset=0), fetch filter options and show spinner
  if (contactFilters.offset === 0) {
    container.innerHTML = '<div class="loading"><div class="spinner"></div> Loading...</div>';
    _contactRows = [];
    if (_filterOptions.industries.length === 0) {
      _filterOptions = await fetchFilterOptions();
    }
  }

  let query = db
    .from('connections')
    .select(BROWSE_SELECT, { count: 'exact' })
    .neq('user_priority', 'never')
    .order('reconnect_score', { ascending: false })
    .range(contactFilters.offset, contactFilters.offset + 49);

  if (contactFilters.roleQuery) {
    query = query.ilike('enriched_headline', `%${contactFilters.roleQuery}%`);
  }
  if (contactFilters.industryFilter) {
    query = query.eq('enriched_industry', contactFilters.industryFilter);
  }
  if (contactFilters.cityFilter) {
    query = query.eq('enriched_city', contactFilters.cityFilter);
  }

  const { data, count, error } = await query;

  if (error) {
    console.error('Contacts fetch error:', error);
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Failed to load contacts.</p></div>';
    return;
  }

  contactFilters.totalCount = count || 0;
  if (contactFilters.offset === 0) {
    _contactRows = data || [];
  } else {
    _contactRows = _contactRows.concat(data || []);
  }

  renderContactsHtml(container);
}
```

### PostgREST Distinct Values Fetch

```javascript
// Source: Supabase JS v2 + project pattern
async function fetchFilterOptions() {
  const [indResult, cityResult] = await Promise.all([
    db.from('connections').select('enriched_industry').neq('user_priority', 'never').not('enriched_industry', 'is', null),
    db.from('connections').select('enriched_city').neq('user_priority', 'never').not('enriched_city', 'is', null),
  ]);

  const industries = [...new Set(
    (indResult.data || []).map(r => r.enriched_industry).filter(Boolean)
  )].sort();

  const cities = [...new Set(
    (cityResult.data || []).map(r => r.enriched_city).filter(Boolean)
  )].sort();

  return { industries, cities };
}
```

### Filter Bar HTML

```javascript
function buildFilterBarHtml() {
  const hasActiveFilter = contactFilters.roleQuery || contactFilters.industryFilter || contactFilters.cityFilter;
  const clearBtn = hasActiveFilter
    ? `<button class="btn btn-sm" onclick="clearContactFilters()" style="align-self:flex-end;">Clear filters</button>`
    : '';

  const industryOptions = _filterOptions.industries.map(ind =>
    `<option value="${escapeHtml(ind)}" ${contactFilters.industryFilter === ind ? 'selected' : ''}>${escapeHtml(ind)}</option>`
  ).join('');

  const cityOptions = _filterOptions.cities.map(city =>
    `<option value="${escapeHtml(city)}" ${contactFilters.cityFilter === city ? 'selected' : ''}>${escapeHtml(city)}</option>`
  ).join('');

  return `
    <div class="contacts-filter-bar">
      <div class="filter-group filter-group-full">
        <label>Role / Title</label>
        <input type="text" class="filter-input"
          placeholder="e.g. Product Manager"
          value="${escapeHtml(contactFilters.roleQuery)}"
          oninput="onContactRoleInput(this.value)"
          list="role-suggestions"
        />
        <datalist id="role-suggestions"></datalist>
      </div>
      <div class="contacts-filter-row">
        <div class="filter-group">
          <label>Industry</label>
          <select onchange="setContactIndustryFilter(this.value)">
            <option value="">All</option>
            ${industryOptions}
          </select>
        </div>
        <div class="filter-group">
          <label>Location</label>
          <select onchange="setContactCityFilter(this.value)">
            <option value="">All</option>
            ${cityOptions}
          </select>
        </div>
        ${clearBtn}
      </div>
    </div>`;
}
```

### Empty State Pattern (from queue.js)

```javascript
// No contacts at all (fresh install / all archived)
'<div class="empty-state"><div class="icon">&#128101;</div><p>No contacts yet. Import your LinkedIn connections to get started.</p></div>'

// Filters too narrow (no results for current filter combination)
'<div class="empty-state"><div class="icon">&#128269;</div><p>No contacts match these filters. Try adjusting or clearing your filters.</p></div>'
```

### Showing X of Y Count Banner

```javascript
function buildCountBanner(showing, total) {
  if (total === 0) return '';
  return `<div class="contacts-count-banner">Showing ${showing} of ${total} contacts</div>`;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Client-side filter on full fetch (queue.js) | Server-side PostgREST filter + range (contacts.js) | Phase 13 | Required — browse has 10x more rows than queue |
| `raw_enrichment` JSONB for industry/city | Dedicated `enriched_industry`, `enriched_city` columns | Phase 12 | Enables indexed server-side filter |
| 3-tab bottom nav | 4-tab bottom nav | Phase 13 | Contacts tab added as 2nd tab |

**Deprecated/outdated in this context:**
- `raw_enrichment` field: Never include in browse payload — Phase 12 extracted the needed fields to dedicated columns.
- Client-side filtering: Only appropriate when entire dataset is fetched (queue, <50 items). Browse must use server-side filtering.

## Open Questions

1. **Column name: `name` vs `full_name`**
   - What we know: `src/database/models.py` uses `name`. Some migrations may use `full_name`. The `contact.js` render function uses `conn.name`.
   - What's unclear: Whether Supabase's live `connections` table has `name` or `full_name` or both.
   - Recommendation: Use `name` (matches models.py and contact.js). Include it in BROWSE_SELECT. If `full_name` also exists, include both with `name || full_name` fallback in render.

2. **neq() behavior with NULL user_priority**
   - What we know: Most contacts have `user_priority = NULL` (no priority set). PostgREST `.neq('user_priority', 'never')` should include NULLs based on PostgREST's `neq` semantics.
   - What's unclear: Whether the live Supabase PostgREST version handles this as expected.
   - Recommendation: The first plan task (smoke test) should assert that contacts with NULL `user_priority` appear in browse results.

3. **enrichment_columns migration status on Supabase**
   - What we know: `20260316000000_enrichment_columns.sql` is in the repo but its application to the live Supabase project is listed as a blocker in STATE.md.
   - What's unclear: Whether it has been applied since STATE.md was last written.
   - Recommendation: Plan task 1 should verify migration status and apply if needed before any contacts.js implementation.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, `tests/` directory) |
| Config file | none — pytest auto-discovers `tests/test_*.py` |
| Quick run command | `python -m pytest tests/test_phase13_contacts.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

Phase 13 is primarily a **PWA front-end phase** (vanilla JS + CSS). Python pytest tests are not the primary vehicle for verifying PWA behavior. The test strategy is:

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BROWSE-01 | contacts.js file exists + renderContacts function defined | unit (static analysis) | `pytest tests/test_phase13_contacts.py::test_contacts_js_exists -x` | ❌ Wave 0 |
| BROWSE-01 | PWA route /contacts added to app.js routes object | unit (static analysis) | `pytest tests/test_phase13_contacts.py::test_contacts_route_registered -x` | ❌ Wave 0 |
| BROWSE-01 | 4-tab nav includes Contacts tab in index.html | unit (static analysis) | `pytest tests/test_phase13_contacts.py::test_nav_has_contacts_tab -x` | ❌ Wave 0 |
| BROWSE-02 | BROWSE_SELECT constant excludes raw_enrichment | unit (static analysis) | `pytest tests/test_phase13_contacts.py::test_browse_select_excludes_raw_enrichment -x` | ❌ Wave 0 |
| BROWSE-03/04 | contactFilters object has roleQuery/industryFilter/cityFilter | unit (static analysis) | `pytest tests/test_phase13_contacts.py::test_contact_filters_shape -x` | ❌ Wave 0 |
| BROWSE-05 | Page size constant is 50 | unit (static analysis) | `pytest tests/test_phase13_contacts.py::test_page_size_is_50 -x` | ❌ Wave 0 |

**Note:** These tests use Python `open()` + string matching to verify PWA static files contain expected patterns — a pattern this project uses for PWA phases (see `tests/test_phase3_pwa.py` which uses `open('pwa/index.html')` etc.). No browser automation is needed.

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_phase13_contacts.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase13_contacts.py` — covers BROWSE-01 through BROWSE-05 via static file analysis

## Sources

### Primary (HIGH confidence)
- Existing codebase: `pwa/js/queue.js`, `pwa/js/app.js`, `pwa/js/contact.js`, `pwa/css/app.css` — established patterns verified by direct code reading
- `supabase/migrations/20260316000000_enrichment_columns.sql` — confirmed column names and indexes
- `src/database/models.py` (via tests) — confirmed `name` field on Connection

### Secondary (MEDIUM confidence)
- [Supabase JS v2 Select Reference](https://supabase.com/docs/reference/javascript/select) — `count: 'exact'` option and `.range()` syntax confirmed
- `tests/test_phase3_pwa.py` — confirmed static-file Python test pattern for PWA phases

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing libraries already in use, no new dependencies
- Architecture: HIGH — direct extension of queue.js and app.js patterns verified by code reading
- PostgREST query patterns: HIGH — verified against Supabase JS v2 official docs
- Pitfalls: MEDIUM — neq()/NULL behavior flagged for verification; migration status flagged as known blocker

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable domain — Supabase JS v2 API is stable)
