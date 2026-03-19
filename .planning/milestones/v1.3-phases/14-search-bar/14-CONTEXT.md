# Phase 14: Search Bar - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a full-text search bar to the existing Contacts page that matches across name, role, company, location, and school simultaneously. Debounced input with result count. Search replaces the existing role/title filter input. Requires a new Supabase migration for the tsvector generated column (deferred from Phase 12). No new pages, no new navigation — extends the Phase 13 Contacts page.

</domain>

<decisions>
## Implementation Decisions

### Search + filter interaction
- **Search replaces role input**: The search bar takes the role/title text input's position in the filter bar. It searches across ALL fields (name, role, company, location, school) instead of just enriched_headline
- **AND logic with existing filters**: Search combines with industry and city dropdown filters using AND logic. e.g. searching "Miami" with Industry:Technology returns contacts matching both
- **Independent clearing**: Clearing the search bar keeps active dropdown filters. Clearing filters keeps search text. "Clear all" button resets everything
- **ilike fallback if tsvector fails**: If the tsvector migration doesn't work on Supabase, fall back to chained `.or()` with ilike on each searchable column. No Fuse.js — stays server-side

### Result display behavior
- **Score sort always**: Keep `reconnect_score` descending regardless of whether search is active. No relevance-based sorting
- **No term highlighting**: Same card rendering as browse mode. No bold/highlight on matched terms
- **Search-specific count banner**: When searching: `12 contacts match "Sales Miami"`. When browsing: `Showing X of Y contacts`
- **Paginated search results**: Same Load More behavior with 50-per-page pagination, consistent with browse mode

### Search feedback UX
- **Placeholder**: "Search contacts..."
- **Search icon**: Magnifying glass icon on the left side of the input, visually distinct from dropdown filters
- **Debounce**: 300ms (matches existing Phase 13 role filter pattern)
- **No-results message**: "No contacts match '[query]'. Try different keywords or clear your search." with actionable guidance
- **Minimum query length**: Claude's discretion (existing role filter uses 2-char minimum)

### Claude's Discretion
- Search icon implementation (SVG inline, CSS pseudo-element, or Unicode)
- tsvector column definition (which fields, weighting strategy)
- Exact PostgREST textSearch syntax and parameter passing
- Loading state while search query is in-flight
- Whether the role autocomplete datalist is removed or repurposed
- Input clear button (X icon) styling

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Contacts page (Phase 13 — the page being modified)
- `pwa/js/contacts.js` — Current browse module: filter bar, pagination, card rendering, debounce pattern
- `pwa/css/app.css` — `.contacts-filter-bar`, `.filter-group-full`, `.contacts-count-banner` styles
- `pwa/index.html` — Script loading order, nav tabs

### Database schema
- `supabase/migrations/20260316000000_enrichment_columns.sql` — Phase 12 enrichment columns (note: "fts tsvector generated column is deferred to Phase 14 migration")
- `src/database/models.py` — Connection model with enriched fields

### PostgREST patterns
- `pwa/js/contacts.js` — `.select()`, `.ilike()`, `.eq()`, `.or()`, `.range()`, `.order()` patterns
- `pwa/js/queue.js` — Additional PostgREST query patterns, SIGNAL_ACTIONS constant

### Prior phase context
- `.planning/phases/13-contacts-browse-page/13-CONTEXT.md` — Filter design decisions, pagination UX, count approach

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `contactFilters` state object in `contacts.js`: Already tracks `roleQuery`, `industryFilter`, `cityFilter`, `offset`, `totalCount` — extend with `searchQuery`
- `onContactRoleInput()` debounce pattern: 300ms timer with 2-char minimum, autocomplete suggestions — replace/adapt for search
- `buildFilterBarHtml()`: Generates the filter bar HTML — modify to swap role input for search bar
- `buildCountBanner()`: "Showing X of Y contacts" — extend for search-specific format
- `clearContactFilters()`: Resets all filter state — extend to include search

### Established Patterns
- **Filter state → re-render**: Changing any filter calls `renderContacts(content)` which rebuilds the full query with all active filters
- **PostgREST query building**: Conditional `.ilike()` / `.eq()` chaining in `renderContacts()` and `loadMoreContacts()` — extend with `.textSearch()` or `.or()` for search
- **Debounce with `setTimeout`**: `_roleDebounceTimer` pattern — reuse for search debounce

### Integration Points
- `contacts.js:renderContacts()` — Add search parameter to the PostgREST query
- `contacts.js:buildFilterBarHtml()` — Replace role input with search bar
- `contacts.js:loadMoreContacts()` — Include search parameter in pagination queries
- `contacts.js:contactFilters` — Add searchQuery field, remove roleQuery
- `supabase/migrations/` — New migration for tsvector generated column + GIN index
- `pwa/css/app.css` — Search icon styling, input padding for icon

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches that fit the existing vanilla JS PWA patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 14-search-bar*
*Context gathered: 2026-03-18*
