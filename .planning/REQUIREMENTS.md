# Requirements: Reconnect

**Defined:** 2026-03-14
**Core Value:** When I get my morning email, I can quickly decide who to reconnect with, take action right there, and dig deeper into anyone who interests me — all without friction.

## v1.3 Requirements

Requirements for v1.3 Contact Discovery. Each maps to roadmap phases.

### Enrichment

- [x] **ENRICH-01**: User can run a CLI command to see enrichment coverage statistics across key fields (education, industry, skills, location)
- [x] **ENRICH-02**: Pipeline extracts education text from raw_enrichment educations array into a searchable flat column
- [x] **ENRICH-03**: Pipeline extracts industry, headline, city, country, school, seniority from raw_enrichment into dedicated columns at enrichment time
- [x] **ENRICH-04**: Existing contacts are backfilled with extracted fields from their current raw_enrichment data without API calls

### Browse

- [x] **BROWSE-01**: User can view a paginated list of all non-archived contacts in the PWA via a Contacts page
- [x] **BROWSE-02**: User can filter contacts by role/title
- [x] **BROWSE-03**: User can filter contacts by industry
- [x] **BROWSE-04**: User can filter contacts by location
- [x] **BROWSE-05**: Contacts page uses server-side pagination and explicit field selection (no raw_enrichment in payload)

### Search

- [x] **SEARCH-01**: User can search contacts via a search bar that matches across name, role, company, location, and school simultaneously
- [x] **SEARCH-02**: Search results update with debounced input and display a result count

## Future Requirements

Deferred to v1.4+. Tracked but not in current roadmap.

### Enrichment Planner

- **EPLNR-01**: Enrichment planner guards against re-enriching permanently unfetchable contacts
- **EPLNR-02**: Enrichment planner allocates explicit budget percentages per tier
- **EPLNR-03**: Pipeline logs RapidAPI rate-limit headers for empirical budget measurement

### Browse Differentiators

- **BDIFF-01**: User can filter contacts by seniority level (VP/Director/Manager/Senior)
- **BDIFF-02**: User can filter contacts by signal on contacts page
- **BDIFF-03**: User can filter contacts by data completeness score
- **BDIFF-04**: Contacts page shows result count summary

### Advanced Search

- **ASRCH-01**: Search bar works alongside structured filters in a single combined query
- **ASRCH-02**: Skills filter (contingent on >50% skills coverage from diagnostic)
- **ASRCH-03**: Graduation year / cohort filter (contingent on >60% education coverage)
- **ASRCH-04**: Saved searches / smart lists

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| AI/semantic search (pgvector + embeddings) | Attribute queries don't need semantic understanding; cost and complexity not justified at this scale |
| Server-side raw_enrichment JSONB filtering | PostgREST cannot filter JSONB with ilike/eq — confirmed limitation |
| Per-keystroke PostgREST queries | Round-trip latency makes search feel broken on mobile |
| LLM-based query parsing | ~$0.01/search, adds latency, breaks offline mode |
| New enrichment providers | RapidAPI already returns education, skills, industry — gap is extraction not acquisition |
| select('*') for browse view | 15 MB+ payload on mobile, approaches Supabase free-tier egress limit |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENRICH-01 | Phase 12 | Complete |
| ENRICH-02 | Phase 12 | Complete |
| ENRICH-03 | Phase 12 | Complete |
| ENRICH-04 | Phase 12 | Complete |
| BROWSE-01 | Phase 13 | Complete |
| BROWSE-02 | Phase 13 | Complete |
| BROWSE-03 | Phase 13 | Complete |
| BROWSE-04 | Phase 13 | Complete |
| BROWSE-05 | Phase 13 | Complete |
| SEARCH-01 | Phase 14 | Complete |
| SEARCH-02 | Phase 14 | Complete |

**Coverage:**
- v1.3 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0

---
*Requirements defined: 2026-03-14*
*Last updated: 2026-03-14 — traceability updated after roadmap creation*
