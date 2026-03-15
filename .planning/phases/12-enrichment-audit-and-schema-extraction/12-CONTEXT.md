# Phase 12: Enrichment Audit and Schema Extraction - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract 7 enrichment fields from `raw_enrichment` JSON into queryable first-class columns on `connections` (both SQLite and Supabase), build a CLI coverage stats command, backfill all existing contacts, and ensure the pipeline writes these columns on every future enrichment run. No new API calls. No browse/search UI (Phases 13-14).

</domain>

<decisions>
## Implementation Decisions

### Field extraction rules
- **enriched_school**: All schools from `educations` array concatenated (comma-separated). Maximizes searchability for Phase 14
- **education_text**: School names only (no degrees/fields). E.g., "Stanford University, UC Berkeley". Kept simple for full-text search
- **enriched_seniority**: Reuse existing `_classify_seniority()` from `dashboard_service.py`, which maps role titles to tiers (executive/senior/mid/entry). Consistent with dashboard charts
- **enriched_headline**: Copy from `raw_enrichment` headline field
- **enriched_industry**: Extract from `company_industry` (RapidAPI) or `companyIndustry` (Apify) — dual-key pattern already used in `dashboard_service.py`
- **enriched_city** / **enriched_country**: Extract from `city` and `country` fields in raw_enrichment

### Data normalization
- **Light cleanup across all extracted fields**: Trim whitespace and title-case normalization. No semantic mapping or category reduction
- **Same rule for all text fields**: Location, school names, and other text fields all get the same light cleanup treatment for consistency
- **No industry normalization into canonical categories** — store the API value with light cleanup only

### Backfill execution
- **Both CLI command and pipeline step**: `reconnect contacts backfill` for manual initial run, plus a pipeline step that fills gaps on each run
- **CLI output**: Summary only at completion (e.g., "Backfilled 1,203 contacts: 987 with industry, 654 with education..."). No per-contact progress bar
- **Idempotent**: Safe to re-run — only fills columns that are currently NULL

### Claude's Discretion
- **enriched_industry transformation**: Claude decides whether to simplify verbose API industry values (e.g., "Information Technology & Services" -> "Technology") or store as-is. Should optimize for Phase 13 browse filter usability
- **Headline cleanup**: Claude decides whether to strip emojis or store verbatim. Should optimize for display and search
- **Cloud sync approach**: Claude decides whether backfill writes to SQLite only (letting push_to_cloud sync) or dual-writes to both. Should fit existing sync architecture patterns
- **Migration scope**: Claude decides whether Phase 12 migration includes the tsvector generated column for Phase 14 or keeps it separate. Should consider migration complexity vs phase isolation
- **CLI stats output format**: Claude designs the `reconnect contacts stats --enrichment` output format

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches that fit the existing CLI and pipeline patterns.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_enrichment_data()` in `models.py`: Already unwraps the `data` key from raw_enrichment — handles both nested and flat formats
- `_classify_seniority()` in `dashboard_service.py`: Classifies role titles into 4 tiers (executive/senior/mid/entry) — reuse directly for `enriched_seniority`
- `compute_industry_distribution()` in `dashboard_service.py`: Uses dual-key extraction (`company_industry` / `companyIndustry`) — same pattern for `enriched_industry`
- Click CLI in `cli.py`: Existing `contacts` command group with `import` subcommand — add `stats` and `backfill` subcommands here
- `_get_mock_profile_data()` in `rapidapi_linkedin.py`: Shows exact RapidAPI response shape including `educations` array structure

### Established Patterns
- **Enrichment field extraction** in `rapidapi_linkedin.py:update_connection_from_profile()`: Extracts `current_role`, `current_company`, `location` from raw data — extend this function with 7 new field extractions
- **Supabase migrations**: SQL files in `supabase/migrations/` with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` pattern (see `20260305000000_pwa_overhaul.sql`)
- **CONNECTION_SYNC_FIELDS** in `push.py`: Explicit field list for cloud sync — must add 7 new columns here
- **Pipeline steps** in `daily_pipeline.py`: Numbered steps with results dict — add backfill-gap-fill as a step

### Integration Points
- `src/ingestion/rapidapi_linkedin.py:update_connection_from_profile()` — write new columns at enrichment time
- `src/sync/push.py:CONNECTION_SYNC_FIELDS` — add 7 new fields for cloud sync
- `src/database/models.py:Connection` — add 7 new SQLModel fields
- `src/cli.py` — add `contacts stats` and `contacts backfill` subcommands
- `src/pipeline/daily_pipeline.py` — add gap-fill pipeline step
- `supabase/migrations/` — new migration for Supabase column additions

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-enrichment-audit-and-schema-extraction*
*Context gathered: 2026-03-15*
