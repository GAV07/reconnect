# Phase 13: Contacts Browse Page - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a Contacts page to the PWA where users can browse all non-archived contacts with role, industry, and location filters. Server-side pagination via PostgREST `.range()`, explicit field selection (no `raw_enrichment` in payload). No full-text search (Phase 14).

</domain>

<decisions>
## Implementation Decisions

### Contact card layout
- **Compact row format**: Name · Role · Company on first line; industry chip + city + score on second line. Fits ~8-10 cards per screen
- **Show reconnect_score** as a badge on each card — helps prioritize while browsing
- **Show signal badge** when a contact has one assigned (Warm Lead, Nurture, etc.) — provides triage context
- **Tap navigates to profile**: Tap anywhere on the card → existing contact profile page (`contact.js` via `#/contact/{id}`)

### Filter design
- **Role/title filter**: Free-text input with autocomplete suggestions populated from distinct values. Filters contacts whose role/headline contains the typed text (case-insensitive `ilike`)
- **Industry filter**: Standard `<select>` dropdown populated from distinct `enriched_industry` values in the database
- **Location filter**: Standard `<select>` dropdown populated from distinct `enriched_city` values. City only — no country dropdown
- **Filter combination**: AND logic — all active filters must match. A visible "Clear filters" button appears when any filter is active
- **Filter layout**: Role text input on top, Industry and Location dropdowns below side-by-side

### Navigation placement
- **4-tab bottom nav**: Queue | **Contacts** | Dashboard | Settings — Contacts is the 2nd tab
- **Icon**: People/group silhouette (two-person icon) — standard contacts icon
- **Label**: "Contacts"
- **Route**: `#/contacts` — new hash route in `app.js` router

### Pagination UX
- **Load More button**: Explicit button at bottom of list — user controls when to fetch the next page
- **Page size**: 50 contacts per request
- **Total count**: Display "Showing X of Y contacts" — gives context for list size and filter narrowing
- **Default sort**: Score high-to-low (`reconnect_score` descending) — best contacts surface first
- **Server-side pagination**: PostgREST `.range(offset, offset + 49)` — no single request fetches more than 50 rows

### Claude's Discretion
- **Filter value fetching strategy**: Claude decides whether to fetch distinct filter values via separate queries on page load, or extract them from the first data page. Should optimize for UX (filters populated before scrolling) vs request count
- **Autocomplete implementation**: Claude decides the debounce timing and minimum character threshold for role suggestions. Should feel responsive without excessive queries
- **Empty state design**: Claude designs the empty state for no results (filters too narrow) and no contacts (fresh install). Should match existing PWA empty state patterns
- **Loading skeleton**: Claude decides whether to show skeleton rows or a spinner during initial load and pagination. Should match existing patterns in queue.js
- **Count query approach**: Claude decides whether to use PostgREST `count=exact` header or a separate count query. Should consider performance with large datasets
- **Active filter indicator**: Claude decides how "Clear filters" is presented (button, link, or X badges on active filters)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches that fit the existing PWA patterns established in queue.js and contact.js.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `queue.js` filter pattern: Signal/industry/sort filters with client-side filtering — established UI pattern for filter dropdowns and state management
- `SIGNAL_ACTIONS` constant in `queue.js`: Signal label/color/bg definitions — reuse for signal badges on browse cards
- `contact.js` profile page: Already renders full contact detail — browse cards navigate here via `#/contact/{id}`
- `app.js` router: Hash-based routing with `routes` object and `getRoute()` — add `/contacts` route here
- `app.css`: Mobile-first styles, card patterns, chip styles, bottom nav — extend for browse page
- Phase 12 enriched columns: `enriched_industry`, `enriched_headline`, `enriched_city`, `enriched_country`, `enriched_school`, `enriched_seniority`, `education_text` — filter and display targets

### Established Patterns
- **Bottom nav**: SVG icons with labels in `index.html` `<nav class="bottom-nav">` — add 4th tab here
- **Script loading**: Module JS files loaded via `<script>` tags in `index.html` — add `contacts.js`
- **Supabase queries**: `db.from('table').select('fields').eq()/.ilike()/.range()` pattern used throughout
- **Filter state**: Module-level object (like `queueFilters`) tracks active filters, re-render on change
- **Empty states**: `<div class="empty-state"><div class="icon">...</div><p>...</p></div>` pattern

### Integration Points
- `pwa/index.html` — add Contacts nav tab + `<script src="js/contacts.js">`
- `pwa/js/app.js` — add `/contacts` to `routes` object, wire `renderContacts()` in `render()` switch
- `pwa/js/contacts.js` — new file: browse page module (fetch, filter, paginate, render)
- `pwa/css/app.css` — add contact row styles, filter bar styles
- PostgREST queries on `connections` table — server-side filtering on enriched columns + `.range()` pagination

### Key PostgREST Patterns for This Phase
- **Field selection**: `.select('id,full_name,current_role,current_company,enriched_industry,enriched_city,enriched_headline,reconnect_score,latest_signal,linkedin_url')`
- **Exclude archived**: `.neq('user_priority', 'never')` or similar
- **Industry filter**: `.eq('enriched_industry', value)`
- **Location filter**: `.eq('enriched_city', value)`
- **Role filter**: `.ilike('enriched_headline', '%value%')` or `.ilike('current_role', '%value%')`
- **Pagination**: `.range(0, 49)` for first page, `.range(50, 99)` for second, etc.
- **Sort**: `.order('reconnect_score', { ascending: false })`
- **Count**: `{ count: 'exact', head: false }` option on `.select()`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 13-contacts-browse-page*
*Context gathered: 2026-03-17*
