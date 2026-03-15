# Feature Landscape

**Domain:** Personal networking CRM — v1.3 Contact Discovery milestone
**Researched:** 2026-03-14
**Confidence:** HIGH (codebase direct analysis + PostgREST docs verified + CRM ecosystem patterns)

---

## Context: What Already Exists (Not In Scope)

These features are fully built and working in v1.0–v1.2. This document covers only v1.3 scope.

**v1.0–v1.2 already built:**
- Queue with signal filter, industry filter, sort by score
- Contact profile with AI rationale, conversation starters, notes, signal history
- 7 intent signals with cadence re-queuing, tone adaptation
- Email digest with signal-aligned vocabulary
- Pipeline: import → enrich → score → queue → digest
- RapidAPI (fresh-linkedin-profile-data) + Hunter enrichment providers
- Data completeness scoring (`data_completeness_score`, `missing_data_fields` on Connection)
- `raw_enrichment` stores full profile JSON including `educations[]`, `experiences[]`, `skills[]`

**v1.3 scope (everything below):**
- Flexible search bar to find contacts by name, role, company, school, industry, location
- Browse/filter page for contacts beyond the outreach queue
- Enrichment field completeness for segmentation (education, skills, location properly indexed)
- Denormalized education and skills columns for reliable filtering without JSON parsing

---

## Litmus Test: "Find Sales/Marketing people who are University of Miami alum in my network"

This use case requires:
1. **Education data in enrichment** — RapidAPI `fresh-linkedin-profile-data` returns `educations[]` array with `school`, `degree`, `field_of_study`. Coverage is HIGH for contacts who include education on LinkedIn. No new API provider needed.
2. **School name searchable** — Currently buried in `raw_enrichment.educations[]`. Not queryable via PostgREST without a generated column or client-side JSON parsing. This is the core gap.
3. **Role/function filter** — `current_role` is already a denormalized indexed column. Text contains "Sales" or "Marketing" is filterable with `ilike`.
4. **Result browsing** — Contacts page (does not exist) showing all connections, not just the queue.

---

## Table Stakes

Features users expect. Missing = product feels incomplete or the milestone goal is unachievable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Search bar on contacts page | The milestone's stated goal. Without it, v1.3 has no deliverable | MEDIUM | Client-side search over fetched contacts works well for single-user datasets (<5K contacts). PostgREST `ilike` on name/company/role for server-side pre-filter; education search requires denormalized field (see below) |
| Contacts browse page (all contacts, not queue) | Queue shows a curated subset. You can't currently browse your full network in the PWA. The UMiami use case requires browsing all contacts | MEDIUM | New PWA route `/contacts`. Fetches from `connections` table directly (not `outreach_queue`). Needs pagination or virtual scroll for large datasets |
| Denormalized `school` column on connections | Education is in `raw_enrichment.educations[0].school` — not queryable. Filtering by university requires extracting this to a flat column during enrichment | LOW | Pipeline step: after enrichment, extract `educations[0].school` → `connections.school`. One `ALTER TABLE` migration. Single source of truth — no new enrichment API needed |
| Role/function filter on contacts page | "Sales/Marketing" filter is the stated use case. `current_role` already exists and is indexed | LOW | Client-side `ilike` on `current_role`. Works today — just needs the contacts browse page to exist |
| Industry filter on contacts page | Already implemented on queue page. Contacts page needs same filter | LOW | Reuse existing industry extraction logic from `queue.js`. Copy pattern, apply to contacts page |
| Location filter on contacts page | `location` is already a denormalized indexed column. "Miami" or "Florida" filters are directly searchable | LOW | `ilike` on `connections.location`. No new data work needed |
| Enrichment coverage verification | Education coverage currently unknown. Must confirm what % of contacts have `educations[]` data before committing to education search as a feature | LOW | Diagnostic: query `raw_enrichment` for `educations` presence across enriched contacts. Run via CLI (`reconnect contacts stats`) |

---

## Differentiators

Features that make contact discovery meaningfully better than a flat contact list.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multi-field free-text search bar | Single input that searches name, company, role, and school simultaneously. "University of Miami Sales" finds contacts matching any combination — no need to pick a field first. This matches how users actually think | MEDIUM | Client-side: after fetching contacts, filter across `name + current_role + current_company + school` with a single lowercased substring match. No PostgREST full-text-search complexity needed at this data scale |
| Skills filter | "Find people with Python or ML skills" — skills live in `raw_enrichment.skills[]`. Useful for technical network mapping | MEDIUM | Requires denormalized `skills_text` column (comma-joined skills string) extracted at enrichment time, or client-side JSON parse of `raw_enrichment` skills array. Skills text column preferred for reliable filtering |
| Graduated-year filter / cohort search | "UMiami class of 2012–2016" narrows alumni to people from a specific era — stronger reconnection hook (shared professors, events) | MEDIUM | `educations[0].end_year` extraction into a `graduation_year` column. Filterable as a numeric range. Depends on enrichment coverage |
| Data completeness filter | "Show me contacts missing education data" — enables targeted enrichment runs. The `data_completeness_score` column already exists | LOW | Filter on `data_completeness_score < 60` or `missing_data_fields contains "education"`. No new data work; just expose in contacts page filter UI |
| Contact count / result summary | "12 contacts match: Sales/Marketing + University of Miami" — gives immediate sense of network segment size. Useful for deciding whether a segment is worth pursuing | LOW | Count of filtered results shown in page header. Trivial to implement once contacts page exists |
| Signal filter on contacts page | "Show all WARM_LEAD contacts" — currently only available as a queue filter on queue page, not on the full contact list | LOW | `connections.latest_signal` is already synced. Simple dropdown filter on contacts page |

---

## Anti-Features

Features to explicitly NOT build in v1.3.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Server-side full-text search with tsvector | PostgREST supports `fts` operator on text columns and can auto-convert JSON to tsvector, but setup complexity (generated tsvector column, GIN index, tsquery parsing) is not justified for a single-user dataset with <5K contacts | Client-side substring filter over fetched data. Instant, zero infrastructure, trivially maintainable. Revisit if dataset exceeds 20K contacts |
| Education data from a new enrichment provider (Clearbit, Apollo, etc.) | LinkedIn profile data from RapidAPI already includes `educations[]`. Adding a second enrichment provider adds API cost, new auth tokens, data normalization complexity, and potential conflicts | Extract education from existing `raw_enrichment.educations[]`. Fill gaps via re-enrichment of contacts who were enriched before education extraction was added to the pipeline |
| Saved search / smart lists | "Save this search as 'UMiami Sales'" — Clay and folk offer this, but building a saved search system (persistence, naming, edit, delete) adds ~3x the complexity of search itself | Tags/notes already allow manual segmentation. Saved searches are v1.4+ if the use case proves persistent |
| Bulk tagging from search results | "Select all UMiami contacts and tag them" — bulk operations require checkbox selection UI, selection state management, and batch PostgREST writes | Single-contact signal assignment from contacts page is sufficient. Bulk is a power-user edge case |
| AI-powered semantic search ("who in my network knows about X?") | Appealing but requires embedding generation, vector storage (Supabase pgvector or external), and LLM query rewriting — substantial infrastructure for a search feature that starts with very few queries per day | Substring/field search covers 90% of real use cases. Semantic search is explicitly listed in PROJECT.md as v1.3+ potential feature |
| Infinite scroll / virtualized list for all contacts | Technically correct for large datasets, but adds JavaScript complexity (Intersection Observer, scroll position management) | Pagination with simple prev/next is sufficient. Load 50 contacts per page. Stack can handle this easily |

---

## Feature Dependencies

```
[Contacts Browse Page — new PWA route /contacts]
    └──required by──> [Search bar on contacts page]
    └──required by──> [Role/industry/location/signal filters on contacts page]
    └──required by──> [Data completeness filter]
    └──depends on──> [connections table readable via PostgREST anon role]

[Denormalized `school` column]
    └──required by──> [Education / alumni filter]
    └──required by──> [University of Miami litmus test]
    └──depends on──> [RapidAPI enrichment having run — educations[] present in raw_enrichment]
    └──requires──> [DB migration: ALTER TABLE connections ADD COLUMN school TEXT]
    └──requires──> [Pipeline step: extract educations[0].school after enrich]

[Denormalized `skills_text` column]  ← optional differentiator
    └──required by──> [Skills filter]
    └──depends on──> [RapidAPI enrichment having run — skills[] present in raw_enrichment]
    └──requires──> [DB migration: ALTER TABLE connections ADD COLUMN skills_text TEXT]
    └──requires──> [Pipeline step: extract + join skills after enrich]

[Multi-field search bar]
    └──depends on──> [Contacts browse page]
    └──enhanced by──> [Denormalized school column] (education searchable)
    └──enhanced by──> [Denormalized skills_text column] (skills searchable)

[Enrichment coverage verification]
    └──prerequisite for──> [Deciding whether education filter is feasible]
    └──independent of other features]
    └──run first — shapes scope of remaining work]
```

### Dependency Summary

- **Contacts browse page must be built first.** All search and filter features are moot without a page that shows your full contact list. This is the foundational deliverable.
- **`school` column extraction is the critical path for the stated use case.** Without it, the UMiami alumni search cannot work reliably. It is a pipeline + DB migration task, not a UI task.
- **Enrichment coverage check gates everything.** If only 20% of contacts have `educations[]` data, education search is a low-value feature. If 70%+ do, it is high-value. Run the diagnostic before committing to education filtering.
- **Skills text is optional.** If the coverage diagnostic shows skills are also sparsely populated, defer skills filter to v1.4.
- **Signal and location filters are free** — data already exists, just needs the contacts page to render them.

---

## Field Coverage Analysis: What RapidAPI Returns

RapidAPI `fresh-linkedin-profile-data` (`enrich-lead` endpoint) returns these fields relevant to contact discovery:

| Field | Location in raw_enrichment | Coverage (estimated) | Already Denormalized? |
|-------|---------------------------|---------------------|----------------------|
| `job_title` | `data.job_title` | HIGH — most professionals have a title | Yes → `current_role` |
| `company` | `data.company` | HIGH | Yes → `current_company` |
| `company_industry` | `data.company_industry` | HIGH | No — in raw_enrichment JSON |
| `location` | `data.location` | HIGH | Yes → `location` |
| `headline` | `data.headline` | HIGH | No — in raw_enrichment JSON |
| `educations[]` | `data.educations[].school` | MEDIUM — depends on user filling it in on LinkedIn | No — needs extraction |
| `educations[].degree` | `data.educations[].degree` | MEDIUM | No — needs extraction |
| `educations[].end_year` | `data.educations[].end_year` | LOW-MEDIUM — often omitted | No |
| `skills[]` | `data.skills[]` | MEDIUM — opt-in skill endorsements | No — needs extraction |
| `experiences[]` | `data.experiences[]` | HIGH — most have work history | No — parsed for scoring |
| `about` | `data.about` | MEDIUM | No — in raw_enrichment JSON |

Note: Education fields are LinkedIn-user-populated, not derived. Coverage depends entirely on whether contacts chose to fill in their education on LinkedIn. For a professional network of someone who graduated from a known university, education coverage is typically 50–75% among connections from college-era relationships, lower for purely professional connections.

---

## MVP Definition

### Build First (required for milestone coherence)

1. **Enrichment coverage diagnostic** — before writing any search UI, query production data to understand what % of enriched contacts have `educations[]`, `skills[]`, and location. This shapes which filters are worth building. Run as a CLI command: `reconnect contacts stats --enrichment`.

2. **Contacts browse page** — new PWA route `/contacts`. Fetch all connections from Supabase (not outreach_queue). Show name, role, company, location, signal badge, score. Simple list with load-more pagination (50/page). Filter controls on same page.

3. **Search bar** — client-side substring match across `name`, `current_role`, `current_company`, `location`. Applied after fetching current page. Instant, no server round-trip.

4. **Role and industry filters** — dropdowns, same pattern as queue page. Industry extracted client-side from `raw_enrichment`. Role uses `ilike` on `current_role`.

5. **School column extraction** — DB migration adds `school TEXT` to connections. Pipeline step (post-enrich) extracts `raw_enrichment.educations[0].school` and writes to `connections.school`. Existing enriched contacts get backfilled via `reconnect contacts backfill-school` CLI command.

### Add After Core (same milestone, once core works)

6. **Education filter on contacts page** — search/filter by school name. Depends on school column being populated. Gate behind coverage diagnostic result.

7. **Location filter** — filter by location substring. `location` column already populated.

8. **Signal filter** — dropdown to filter by `latest_signal`. Works today, just needs the page.

9. **Data completeness filter** — show contacts with low completeness scores. Useful for prioritizing enrichment runs.

### Defer to v1.4

- Skills filter — only if coverage diagnostic shows skills are >50% populated
- Graduation year / cohort filter — only if education coverage is strong
- Saved searches / smart lists
- Semantic / AI search

---

## Implementation Notes

### Contacts Page Data Fetch

PostgREST query shape:
```javascript
db.from('connections')
  .select('id, name, current_role, current_company, location, school, latest_signal, reconnect_score, data_completeness_score, raw_enrichment')
  .neq('user_priority', 'never')
  .order('reconnect_score', { ascending: false })
  .range(offset, offset + 49)
```

Industry is still extracted client-side from `raw_enrichment` (no generated column needed yet — existing pattern from queue.js works).

### School Column Migration

```sql
ALTER TABLE connections ADD COLUMN IF NOT EXISTS school TEXT;
CREATE INDEX IF NOT EXISTS idx_connection_school ON connections(school);
```

Pipeline extraction (after `update_connection_from_profile()`):
```python
educations = data.get("educations") or []
if educations:
    connection.school = educations[0].get("school", "")[:200]
```

Backfill for already-enriched contacts:
```python
reconnect contacts backfill-school  # iterates enriched contacts, extracts school from raw_enrichment
```

### Multi-Field Client-Side Search

```javascript
function filterContacts(contacts, query) {
  if (!query) return contacts;
  const q = query.toLowerCase();
  return contacts.filter(c =>
    (c.name || '').toLowerCase().includes(q) ||
    (c.current_role || '').toLowerCase().includes(q) ||
    (c.current_company || '').toLowerCase().includes(q) ||
    (c.location || '').toLowerCase().includes(q) ||
    (c.school || '').toLowerCase().includes(q)
  );
}
```

This covers the UMiami + Sales litmus test: a search for "university of miami" matches `school`, and an industry filter for "Marketing" matches `current_role`.

---

## Sources

- Codebase direct analysis (HIGH confidence): `src/database/models.py`, `src/ingestion/rapidapi_linkedin.py`, `src/ingestion/hunter.py`, `src/llm/data_analyzer.py`, `pwa/js/queue.js`, `pwa/js/app.js`, `supabase/migrations/20260305000000_pwa_overhaul.sql`
- `.planning/PROJECT.md` — v1.3 goal, constraints, out-of-scope list (HIGH confidence)
- RapidAPI `fresh-linkedin-profile-data` mock response structure in `rapidapi_linkedin.py` — confirms `educations[]`, `skills[]`, `experiences[]` are returned (HIGH confidence, mock reflects actual API schema)
- PostgREST full text search docs — `ilike` and `or` filter patterns verified (MEDIUM confidence via WebSearch → Supabase docs): [Supabase Full Text Search](https://supabase.com/docs/guides/database/full-text-search), [PostgREST Tables and Views](https://docs.postgrest.org/en/stable/references/api/tables_views.html)
- Folk CRM contact field model — confirmed standard fields for personal CRM search: name, job title, company, location, education (MEDIUM confidence): [folk data model](https://help.folk.app/en/articles/9790806-folk-data-model)
- Personal CRM search UX — substring/type-to-filter pattern is standard at this data scale (MEDIUM confidence): [Search UX Best Practices](https://www.pencilandpaper.io/articles/search-ux), [LeadDelta Best Personal CRM](https://leaddelta.com/best-personal-crm-apps/)
- LinkedIn education data coverage — population-dependent, user-filled field, estimated 50–75% for college-era connections (LOW-MEDIUM confidence — no authoritative coverage stat found, estimate from LinkedIn data product descriptions): [LinkedIn Field of Study Explorer](https://engineering.linkedin.com/university/field-study-explorer-data-insights-students)

---

*Feature research for: Reconnect v1.3 Contact Discovery milestone*
*Researched: 2026-03-14*
