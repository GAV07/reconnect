# Phase 12: Enrichment Audit and Schema Extraction - Research

**Researched:** 2026-03-16
**Domain:** SQLite/SQLModel schema migration, field extraction from JSON, Click CLI, Supabase ALTER TABLE migration
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Field extraction rules:**
- `enriched_school`: All schools from `educations` array concatenated (comma-separated). Maximizes searchability for Phase 14
- `education_text`: School names only (no degrees/fields). E.g., "Stanford University, UC Berkeley". Kept simple for full-text search
- `enriched_seniority`: Reuse existing `_classify_seniority()` from `dashboard_service.py`
- `enriched_headline`: Copy from `raw_enrichment` headline field
- `enriched_industry`: Extract from `company_industry` (RapidAPI) or `companyIndustry` (Apify) — dual-key pattern already used in `dashboard_service.py`
- `enriched_city` / `enriched_country`: Extract from `city` and `country` fields in raw_enrichment

**Data normalization:**
- Light cleanup across all extracted fields: trim whitespace and title-case normalization only
- No semantic mapping or category reduction
- Same rule for all text fields

**Backfill execution:**
- Both `reconnect contacts backfill` CLI command AND a pipeline step that fills gaps on each run
- CLI output: Summary only at completion (e.g., "Backfilled 1,203 contacts: 987 with industry, 654 with education...")
- Idempotent: Only fills columns that are currently NULL

### Claude's Discretion

- `enriched_industry` transformation: Whether to simplify verbose API values or store as-is. Optimize for Phase 13 browse filter usability
- Headline cleanup: Whether to strip emojis or store verbatim. Optimize for display and search
- Cloud sync approach: Whether backfill writes to SQLite only (letting push_to_cloud sync) or dual-writes to both. Should fit existing sync architecture patterns
- Migration scope: Whether Phase 12 migration includes the tsvector generated column for Phase 14 or keeps it separate. Consider migration complexity vs phase isolation
- CLI stats output format: Design the `reconnect contacts stats --enrichment` output format

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENRICH-01 | User can run a CLI command to see enrichment coverage statistics across key fields (education, industry, skills, location) | Click `contacts stats --enrichment` subcommand pattern follows existing `contacts import` / `contacts score` pattern in `src/cli.py` |
| ENRICH-02 | Pipeline extracts education text from raw_enrichment educations array into a searchable flat column | `educations` array structure confirmed in `_get_mock_profile_data()`. Concatenation of `school` key values; stored as `education_text` TEXT column |
| ENRICH-03 | Pipeline extracts industry, headline, city, country, school, seniority from raw_enrichment into dedicated columns at enrichment time | Extraction point is `update_connection_from_profile()` in `rapidapi_linkedin.py`. All raw keys confirmed: `company_industry`/`companyIndustry`, `headline`, `city`, `country`, `educations[].school`, and `job_title`/`headline` for seniority |
| ENRICH-04 | Existing contacts are backfilled with extracted fields from their current raw_enrichment data without API calls | Backfill iterates connections where `enriched_at IS NOT NULL` and any new column IS NULL; calls the same extraction logic without API calls |
</phase_requirements>

---

## Summary

Phase 12 is a schema extension + data extraction phase. The goal is to promote 7 specific enrichment sub-fields out of the `raw_enrichment` JSON blob into queryable first-class TEXT columns on the `connections` table, both in SQLite (via SQLModel field additions) and Supabase (via SQL migration). No new external API calls occur; all data already exists in `raw_enrichment` for contacts that have been enriched.

The work falls into four distinct buckets: (1) schema changes to `Connection` model and a Supabase migration, (2) extraction logic called at enrichment time (inside `update_connection_from_profile()`), (3) a one-time-safe backfill that iterates existing enriched contacts and fills NULL columns, and (4) a CLI `stats` command that queries coverage percentages across the new columns.

The entire implementation is well-bounded. Every integration point is already identified in `CONTEXT.md`. The extraction patterns are proven in `dashboard_service.py` (`compute_industry_distribution()`, `_classify_seniority()`). The migration style is established in the prior SQL files. The main judgment calls for Claude are: whether to simplify verbose industry values (recommendation: yes, map to short canonical form for usability), whether to strip emojis from headlines (recommendation: yes, strip — they cause display inconsistency), and whether backfill writes SQLite-only or dual-writes (recommendation: SQLite-only, let push_to_cloud handle sync — consistent with all other pipeline steps).

**Primary recommendation:** Add 7 SQLModel fields to `Connection`, write a Supabase migration with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, extend `update_connection_from_profile()` with extraction, add `extract_enrichment_fields()` as a shared helper, add `backfill_enrichment_fields()` function, wire both into the CLI and pipeline, update `CONNECTION_SYNC_FIELDS`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLModel | (existing) | ORM + field definitions on `Connection` | Already the project ORM — all models defined here |
| SQLite (via SQLAlchemy) | (existing) | Local database engine | Project's local store — schema auto-created from SQLModel |
| Click | (existing) | CLI commands | All CLI already uses Click — contacts group exists |
| psycopg2 / Supabase migration SQL | (existing) | Apply Supabase column additions | Prior migrations use raw SQL `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` pattern |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlmodel.func` + `select` | (existing) | Coverage count queries | Used in `dashboard_service.py` for similar aggregation |
| `get_enrichment_data()` helper | in-project | Unwrap `data` envelope from raw_enrichment | Use in ALL extraction logic — handles both nested and flat formats |
| `_classify_seniority()` | in `dashboard_service.py` | Map role title → seniority tier | Import directly; do not duplicate the logic |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLite-only backfill + push_to_cloud sync | Dual-write to SQLite + Supabase directly | Dual-write is more complex; existing push_to_cloud with CONNECTION_SYNC_FIELDS is the established pattern; SQLite-first is correct |
| Minimal migration (7 columns only) | Include Phase 14 `fts` tsvector in same migration | Migration isolation is cleaner; tsvector generated column requires PostgreSQL-specific syntax and Phase 14 context — keep separate |

**Installation:** No new dependencies required.

---

## Architecture Patterns

### Recommended Project Structure

New file: `src/pipeline/enrichment_extractor.py`

```
src/
├── pipeline/
│   ├── daily_pipeline.py        # Add Step 11: gap-fill enrichment fields
│   └── enrichment_extractor.py  # NEW: extract_enrichment_fields(), backfill_enrichment_fields()
├── ingestion/
│   └── rapidapi_linkedin.py     # Extend update_connection_from_profile() to call extract_enrichment_fields()
├── sync/
│   └── push.py                  # Add 7 new fields to CONNECTION_SYNC_FIELDS
├── database/
│   └── models.py                # Add 7 Optional[str] fields to Connection
└── cli.py                       # Add contacts stats --enrichment, contacts backfill
supabase/migrations/
└── 20260316000000_enrichment_columns.sql  # NEW migration
```

### Pattern 1: SQLModel Field Addition

**What:** Add `Optional[str]` fields to the `Connection` model. SQLModel auto-creates columns on `init_db()` for SQLite via `SQLModel.metadata.create_all()`.
**When to use:** Any time a new column is needed in the local SQLite database.
**Example:**
```python
# Source: src/database/models.py — follows existing field pattern
class Connection(SQLModel, table=True):
    # ... existing fields ...
    enriched_industry: Optional[str] = Field(default=None, index=True)
    enriched_headline: Optional[str] = Field(default=None, sa_column=Column(Text))
    enriched_city: Optional[str] = Field(default=None, index=True)
    enriched_country: Optional[str] = Field(default=None, index=True)
    enriched_school: Optional[str] = Field(default=None, sa_column=Column(Text))
    enriched_seniority: Optional[str] = Field(default=None, index=True)
    education_text: Optional[str] = Field(default=None, sa_column=Column(Text))
```

**Note:** Fields with short values (city, country, industry, seniority) can use default `index=True` for PostgREST filter performance. Fields with long text (headline, school, education_text) need `sa_column=Column(Text)` to avoid VARCHAR length limits.

### Pattern 2: Supabase Migration SQL

**What:** Add columns to the live Supabase `connections` table via a SQL migration file.
**When to use:** Any schema change needed in Supabase PostgreSQL that cannot be done via SQLModel (which only controls SQLite).
**Example:**
```sql
-- Source: pattern from supabase/migrations/20260305000000_pwa_overhaul.sql
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_industry TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_headline TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_city TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_country TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_school TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_seniority TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS education_text TEXT;

-- Indexes for PostgREST filter performance (Phase 13 browse)
CREATE INDEX IF NOT EXISTS idx_connections_enriched_industry ON connections(enriched_industry);
CREATE INDEX IF NOT EXISTS idx_connections_enriched_city ON connections(enriched_city);
CREATE INDEX IF NOT EXISTS idx_connections_enriched_country ON connections(enriched_country);
CREATE INDEX IF NOT EXISTS idx_connections_enriched_seniority ON connections(enriched_seniority);
```

**Important:** The `fts` tsvector generated column is a Phase 14 concern — do NOT include it in this migration.

### Pattern 3: Field Extraction Helper

**What:** A dedicated `extract_enrichment_fields()` function that takes a `Connection` and the unwrapped enrichment dict, applies light cleanup, and sets the 7 new fields.
**When to use:** Called from both `update_connection_from_profile()` (at enrichment time) and `backfill_enrichment_fields()` (for existing records).
**Example:**
```python
# Source: pattern established in dashboard_service.py compute_industry_distribution()
# and rapidapi_linkedin.py update_connection_from_profile()

def extract_enrichment_fields(connection: Connection, data: dict) -> None:
    """Extract and set 7 enrichment columns from the unwrapped raw_enrichment dict.

    Modifies connection in-place. Caller is responsible for session.add() and commit().
    Does NOT make any API calls. Only sets fields that have a value — caller controls
    whether to skip if already populated (backfill) or always overwrite (enrichment time).

    Args:
        connection: Connection model instance to update
        data: Unwrapped enrichment dict (already passed through get_enrichment_data())
    """
    from src.services.dashboard_service import _classify_seniority

    # enriched_industry — dual-key pattern (RapidAPI vs Apify)
    industry = data.get("company_industry") or data.get("companyIndustry")
    if industry:
        connection.enriched_industry = _normalize_industry(industry.strip())

    # enriched_headline — verbatim, stripped of leading/trailing whitespace
    headline = data.get("headline")
    if headline:
        connection.enriched_headline = _clean_headline(headline.strip())

    # enriched_city / enriched_country
    city = data.get("city")
    if city:
        connection.enriched_city = city.strip().title()

    country = data.get("country")
    if country:
        connection.enriched_country = country.strip().title()

    # enriched_school and education_text — from educations array
    educations = data.get("educations") or []
    schools = [
        edu.get("school", "").strip()
        for edu in educations
        if edu.get("school", "").strip()
    ]
    if schools:
        connection.enriched_school = ", ".join(schools)
        connection.education_text = ", ".join(schools)  # same for now (school names only)

    # enriched_seniority — from current_role or job_title
    role = connection.current_role or data.get("job_title") or data.get("headline") or ""
    if role:
        connection.enriched_seniority = _classify_seniority(role)
```

### Pattern 4: Idempotent Backfill Function

**What:** Iterate all contacts with `enriched_at IS NOT NULL` where any of the 7 new columns is NULL, and call `extract_enrichment_fields()` for each.
**When to use:** Both as a one-time CLI run and as a recurring pipeline step (gap-fill).
**Example:**
```python
# Source: pattern from push.py batch query pattern
def backfill_enrichment_fields(session: Session = None) -> dict:
    """Backfill 7 enrichment columns for contacts that have raw_enrichment but NULL extracted fields.

    Idempotent: only fills NULL columns. Does NOT make API calls.

    Returns:
        {"processed": N, "industry": N, "education": N, "city": N, ...}
    """
    from sqlalchemy import or_
    from src.database.models import Connection, get_enrichment_data

    stats = {"processed": 0, "industry": 0, "headline": 0,
             "city": 0, "country": 0, "school": 0, "seniority": 0}

    with get_session() as session:
        # Only contacts that have been enriched but have at least one NULL new column
        candidates = session.exec(
            select(Connection)
            .where(Connection.enriched_at.isnot(None))
            .where(
                or_(
                    Connection.enriched_industry.is_(None),
                    Connection.enriched_headline.is_(None),
                    Connection.enriched_city.is_(None),
                    Connection.enriched_country.is_(None),
                    Connection.enriched_school.is_(None),
                    Connection.enriched_seniority.is_(None),
                    Connection.education_text.is_(None),
                )
            )
        ).all()

        for conn in candidates:
            data = get_enrichment_data(conn)
            before = {
                "industry": conn.enriched_industry,
                "headline": conn.enriched_headline,
                "city": conn.enriched_city,
                "country": conn.enriched_country,
                "school": conn.enriched_school,
                "seniority": conn.enriched_seniority,
            }
            extract_enrichment_fields(conn, data)
            # Track what was filled
            if conn.enriched_industry and not before["industry"]:
                stats["industry"] += 1
            # ... etc.
            stats["processed"] += 1
            session.add(conn)

        session.commit()

    return stats
```

### Pattern 5: Click CLI Stats Command

**What:** `reconnect contacts stats --enrichment` prints coverage percentages.
**When to use:** Developer/user diagnostics. Follows existing `queue stats` pattern.
**Example:**
```python
# Source: pattern from src/cli.py queue_stats command
@contacts.command("stats")
@click.option("--enrichment", "show_enrichment", is_flag=True, help="Show enrichment field coverage")
def contacts_stats(show_enrichment):
    """Show contact statistics."""
    from src.pipeline.enrichment_extractor import get_enrichment_coverage

    if show_enrichment:
        stats = get_enrichment_coverage()
        total = stats["total_enriched"]
        print(f"\n[Enrichment Coverage] ({total} enriched contacts)")
        print(f"  Industry:   {stats['industry_pct']:.1f}%  ({stats['industry_count']}/{total})")
        print(f"  Education:  {stats['education_pct']:.1f}%  ({stats['education_count']}/{total})")
        print(f"  Headline:   {stats['headline_pct']:.1f}%  ({stats['headline_count']}/{total})")
        print(f"  City:       {stats['city_pct']:.1f}%  ({stats['city_count']}/{total})")
        print(f"  Seniority:  {stats['seniority_pct']:.1f}%  ({stats['seniority_count']}/{total})")
```

### Pattern 6: CONNECTION_SYNC_FIELDS Update

**What:** Add 7 new field names to the `CONNECTION_SYNC_FIELDS` list in `push.py`.
**When to use:** Required so push_to_cloud() includes the new columns when syncing to Supabase.
**Example:**
```python
# Source: src/sync/push.py — add to the existing list
CONNECTION_SYNC_FIELDS = [
    # ... existing fields ...
    # Enrichment extracted columns (Phase 12)
    "enriched_industry", "enriched_headline", "enriched_city",
    "enriched_country", "enriched_school", "enriched_seniority",
    "education_text",
]
```

### Anti-Patterns to Avoid

- **Duplicating `_classify_seniority()` logic:** Import from `dashboard_service.py` directly. The keyword lists are the source of truth and duplicating causes drift.
- **Calling `get_enrichment_data()` manually without the helper:** Always use the project's existing `get_enrichment_data(conn)` helper — it handles both nested `{"data": {...}}` and flat formats.
- **Adding the `fts` tsvector column in this migration:** That is Phase 14's job. Including it now adds PostgreSQL-only syntax and Phase 14 complexity before Phase 13 is even planned.
- **Making API calls in backfill:** The backfill must work entirely from existing `raw_enrichment` data. Any code path that could trigger `update_connection_from_profile()` is wrong in the backfill context.
- **Altering `Connection.__table_args__` composite indexes for TEXT columns:** The existing composite index covers name/company/role. New `enriched_` columns get their own single-column `index=True` declarations, not composite index additions.
- **Using SQLModel field without `sa_column=Column(Text)` for long strings:** Headline and school lists can exceed SQLite/PostgreSQL default VARCHAR. Use `sa_column=Column(Text)` for these.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Seniority classification | Custom keyword logic | `_classify_seniority()` from `dashboard_service.py` | Already battle-tested with 4 tiers; duplicating causes keyword list drift |
| raw_enrichment unwrapping | Manual `if "data" in raw` logic | `get_enrichment_data(conn)` from `models.py` | Handles both nested RapidAPI format and legacy flat format |
| Industry dual-key lookup | Custom field alias resolution | `data.get("company_industry") or data.get("companyIndustry")` pattern | Dual-key pattern established in `dashboard_service.py`; copy it exactly |
| Coverage stats queries | SQLAlchemy raw SQL | `sqlmodel.func.count()` with `.where(Column.isnot(None))` | Established pattern in `dashboard_service.py` compute functions |

**Key insight:** All the hard parts (seniority classification, dual-key extraction, raw_enrichment unwrapping) are already solved in `dashboard_service.py`. Phase 12 is predominantly wiring these existing pieces into new columns.

---

## Common Pitfalls

### Pitfall 1: SQLite ALTER TABLE Not Supported at Runtime

**What goes wrong:** SQLite does not support `ALTER TABLE ADD COLUMN` at the SQLAlchemy model layer when `create_all()` is called on an existing database. `SQLModel.metadata.create_all()` only creates tables that don't exist — it does NOT add new columns to existing tables.
**Why it happens:** SQLite's `create_all` is idempotent for whole tables, not columns. An existing `connections` table will not get new columns via `create_all()`.
**How to avoid:** For SQLite, use Alembic OR issue raw `ALTER TABLE connections ADD COLUMN IF NOT EXISTS ...` via SQLite-compatible SQL on startup. The simpler approach for this project: use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in a migration helper that runs on init, similar to how the project currently applies Supabase migrations. Alternatively: since `IF NOT EXISTS` is supported in SQLite 3.37+, add the columns via a startup migration function.
**Warning signs:** Column missing from SQLite after `init_db()`. Check with `PRAGMA table_info(connections)`.

**The correct approach for this project:** Use a Python migration helper that issues the `ALTER TABLE` statements directly against the SQLite engine. Pattern already used for Supabase (raw SQL via psycopg2). Apply same approach for SQLite:

```python
# In src/database/engine.py or a new src/database/migrations.py
def apply_column_migrations(engine):
    """Add new columns to existing tables if missing (SQLite safe)."""
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE connections ADD COLUMN enriched_industry TEXT",
            "ALTER TABLE connections ADD COLUMN enriched_headline TEXT",
            # ...etc
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # Column already exists — safe to ignore
```

### Pitfall 2: `enriched_school` vs `education_text` Distinction

**What goes wrong:** The two fields sound identical but serve different Phase 14 purposes. `enriched_school` = all school names comma-separated (searchability). `education_text` = also school names only, no degree/field (full-text search input). At Phase 12 time they have the same value, but a planner could be tempted to make them identical by reference rather than by copy.
**Why it happens:** Seems like de-duplication but they are actually different semantic columns.
**How to avoid:** Set both independently, even if the value is the same function of the same input. Do not make one a reference to the other.

### Pitfall 3: Industry Normalization Decision

**What goes wrong:** The raw API returns verbose values like "Information Technology & Services", "Computer Software", "Internet". Without normalization, Phase 13 browse filters will show 20+ near-duplicate industry values and the filter will be useless.
**Why it happens:** RapidAPI industry values are LinkedIn's raw taxonomy — verbose and inconsistent.
**How to avoid:** Apply a light normalization map for the most common LinkedIn industry values into shorter canonical labels (e.g., "Information Technology & Services" → "Technology", "Computer Software" → "Technology", "Financial Services" → "Finance"). Store the normalized value. This is the "Claude's Discretion" item from CONTEXT.md.
**Recommended normalization approach:** Map top 15 LinkedIn industry strings to ~8 canonical categories. Anything not in the map: store as-is with title-case cleanup. This gives browse filters clean buckets without over-engineering.

### Pitfall 4: Headline Emoji Handling

**What goes wrong:** LinkedIn headlines commonly contain emojis (e.g., "🚀 Founder | Building the future"). Storing these verbatim causes display issues in some email clients and search tokenization problems.
**Why it happens:** RapidAPI returns the raw LinkedIn headline string.
**How to avoid:** Strip emoji characters before storing. Python's `str.encode('ascii', 'ignore').decode('ascii')` is too aggressive (loses accented characters). Use the `re` module to strip Unicode emoji blocks:

```python
import re
EMOJI_PATTERN = re.compile(
    "[\U00010000-\U0010ffff"
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "]+",
    flags=re.UNICODE
)
def _clean_headline(text: str) -> str:
    cleaned = EMOJI_PATTERN.sub("", text).strip()
    # Collapse multiple spaces after emoji removal
    return re.sub(r"\s{2,}", " ", cleaned)
```

### Pitfall 5: `push_to_cloud` Won't Sync Backfilled Contacts Without `updated_at` Change

**What goes wrong:** The backfill query in `push_to_cloud()` filters by `Connection.updated_at > last_push_at`. If the backfill sets the 7 new columns but does NOT update `updated_at`, those contacts won't be picked up by the incremental sync.
**Why it happens:** The backfill touches enrichment columns but the last push timestamp predates the backfill run.
**How to avoid:** The backfill function MUST set `connection.updated_at = datetime.utcnow()` when any column is changed. This ensures push_to_cloud picks them up on the next sync.

### Pitfall 6: `Connection.__table_args__` Redefinition

**What goes wrong:** The existing `Connection.__table_args__` is set after the class definition. Adding indexes for new columns by redefining it will overwrite the existing tuple.
**Why it happens:** SQLModel/SQLAlchemy uses `__table_args__` as a class-level tuple; redefining it replaces the existing indexes.
**How to avoid:** When adding `enriched_industry`, `enriched_city`, etc. as `Field(default=None, index=True)`, SQLModel generates the single-column indexes automatically. Do NOT touch `Connection.__table_args__` — the existing composite indexes are correct as-is.

---

## Code Examples

### Raw Enrichment Data Shape (RapidAPI)

```python
# Source: src/ingestion/rapidapi_linkedin.py _get_mock_profile_data()
# The "data" key is always unwrapped by get_enrichment_data() before extraction
{
    "headline": "Senior Product Manager | AI Enthusiast",
    "job_title": "Senior Product Manager",
    "company": "Acme Corp",
    "company_industry": "Technology",
    "city": "San Francisco",
    "state": "California",
    "country": "United States",
    "educations": [
        {
            "school": "Stanford University",
            "degree": "MBA",
            "field_of_study": "Business Administration",
            "date_range": "2017 - 2019",
            "start_year": 2017,
            "end_year": 2019,
        },
    ],
}
```

### Coverage Stats Query Pattern

```python
# Source: modeled on src/services/dashboard_service.py compute_data_quality()
from sqlmodel import func, select, Session
from src.database.models import Connection

def get_enrichment_coverage() -> dict:
    with get_session() as session:
        total_enriched = session.exec(
            select(func.count(Connection.id))
            .where(Connection.enriched_at.isnot(None))
        ).one()

        if total_enriched == 0:
            return {"total_enriched": 0}

        def pct_col(col):
            count = session.exec(
                select(func.count(Connection.id))
                .where(Connection.enriched_at.isnot(None))
                .where(col.isnot(None))
            ).one()
            return count, round(count / total_enriched * 100, 1)

        industry_count, industry_pct = pct_col(Connection.enriched_industry)
        education_count, education_pct = pct_col(Connection.education_text)
        headline_count, headline_pct = pct_col(Connection.enriched_headline)
        city_count, city_pct = pct_col(Connection.enriched_city)
        seniority_count, seniority_pct = pct_col(Connection.enriched_seniority)

    return {
        "total_enriched": total_enriched,
        "industry_count": industry_count, "industry_pct": industry_pct,
        "education_count": education_count, "education_pct": education_pct,
        "headline_count": headline_count, "headline_pct": headline_pct,
        "city_count": city_count, "city_pct": city_pct,
        "seniority_count": seniority_count, "seniority_pct": seniority_pct,
    }
```

### Adding a Pipeline Step (Gap-Fill)

```python
# Source: pattern from src/pipeline/daily_pipeline.py steps 7-9
# Add after step 10 (dashboard_snapshot) or before sync

try:
    from src.pipeline.enrichment_extractor import backfill_enrichment_fields

    gap_fill_result = backfill_enrichment_fields()
    results["enrichment_gap_fill"] = gap_fill_result
    steps_completed.append("enrichment_gap_fill")
except Exception as gf_error:
    import logging
    logging.getLogger(__name__).warning(
        "Enrichment gap-fill failed (non-fatal): %s", gf_error
    )
    results["enrichment_gap_fill"] = {"error": str(gf_error)}
```

### Supabase Migration File Pattern

```sql
-- Source: pattern from supabase/migrations/20260305000000_pwa_overhaul.sql
-- File: supabase/migrations/20260316000000_enrichment_columns.sql

-- Enrichment extracted columns (Phase 12: v1.3 Contact Discovery)
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_industry TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_headline TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_city TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_country TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_school TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_seniority TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS education_text TEXT;

-- Indexes for Phase 13 browse filters (PostgREST eq/ilike performance)
CREATE INDEX IF NOT EXISTS idx_connections_enriched_industry
    ON connections(enriched_industry);
CREATE INDEX IF NOT EXISTS idx_connections_enriched_city
    ON connections(enriched_city);
CREATE INDEX IF NOT EXISTS idx_connections_enriched_country
    ON connections(enriched_country);
CREATE INDEX IF NOT EXISTS idx_connections_enriched_seniority
    ON connections(enriched_seniority);

-- NOTE: fts tsvector generated column is deferred to Phase 14 migration
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| All enrichment data in `raw_enrichment` JSONB blob | 7 fields promoted to first-class columns | Phase 12 | PostgREST can now filter/sort on these fields; no JSONB traversal needed in browse queries |
| Industry/education only in dashboard snapshot | Available as queryable columns on connections | Phase 12 | Enables Phase 13 server-side filter queries via PostgREST without raw_enrichment |

---

## Claude's Discretion — Recommendations

### Industry Normalization: Apply a lightweight canonical map

**Recommendation:** Store a normalized short-form industry value. Rationale: Phase 13 browse will present these as filter chips. "Information Technology & Services" and "Computer Software" and "Internet" should all map to "Technology" — otherwise the filter has 20+ near-duplicate options.

Suggested normalization map (covers ~80% of LinkedIn contacts):
```python
INDUSTRY_MAP = {
    "information technology and services": "Technology",
    "information technology & services": "Technology",
    "computer software": "Technology",
    "internet": "Technology",
    "financial services": "Finance",
    "investment banking": "Finance",
    "venture capital & private equity": "Finance",
    "hospital & health care": "Healthcare",
    "medical devices": "Healthcare",
    "biotechnology": "Healthcare",
    "consulting": "Consulting",
    "management consulting": "Consulting",
    "marketing and advertising": "Marketing",
    "real estate": "Real Estate",
    "education management": "Education",
    "higher education": "Education",
    "media production": "Media",
    "entertainment": "Media",
}

def _normalize_industry(raw: str) -> str:
    normalized = INDUSTRY_MAP.get(raw.lower())
    return normalized if normalized else raw.strip().title()
```

### Headline Cleanup: Strip emojis, preserve accented characters

**Recommendation:** Strip Unicode emoji ranges using regex (see Pitfall 4 code). Store cleaned value. Rationale: Headlines display in the PWA and email digest — emojis look inconsistent across platforms and break search tokenization.

### Cloud Sync Approach: SQLite-only writes, let push_to_cloud sync

**Recommendation:** Backfill writes only to local SQLite. `updated_at` is set so push_to_cloud incremental sync picks them up. Rationale: Consistent with every other pipeline step. Dual-writing to Supabase directly from the backfill would bypass the `CONNECTION_SYNC_FIELDS` whitelist and risk pushing unwanted columns.

### Migration Scope: Phase 12 migration = 7 columns only, no tsvector

**Recommendation:** Keep the migration minimal. The `fts` tsvector generated column involves `to_tsvector('english', ...)` expression syntax, Supabase trigger setup, and GIN index creation — all Phase 14 concerns. Adding it now creates risk without benefit.

---

## Open Questions

1. **SQLite column migration strategy**
   - What we know: `SQLModel.metadata.create_all()` does not add columns to existing tables
   - What's unclear: The project has no existing Python-side SQLite migration runner for adding columns to live databases
   - Recommendation: Add a `apply_sqlite_migrations()` helper called from `init_db()` that issues `ALTER TABLE ... ADD COLUMN` statements wrapped in try/except (for idempotency). This is the minimal-disruption approach consistent with the project's existing patterns.

2. **Skills coverage gating (Phase 14 dependency)**
   - What we know: STATE.md records "Phase 12: Education coverage unknown until `reconnect contacts stats --enrichment` runs — gates whether education filter ships in v1.3 or defers to v1.4"
   - What's unclear: The actual coverage percentage won't be known until the CLI command runs against real data
   - Recommendation: The plan should include running `reconnect contacts stats --enrichment` as the final verification step and documenting the output. Phase 13/14 planning depends on this number.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` or implicit (no `pytest.ini` detected) |
| Quick run command | `python -m pytest tests/test_phase12_enrichment.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENRICH-01 | `reconnect contacts stats --enrichment` prints coverage percentages | unit | `python -m pytest tests/test_phase12_enrichment.py::TestEnrichmentCoverage -x` | Wave 0 |
| ENRICH-02 | `education_text` column populated with school names from educations array | unit | `python -m pytest tests/test_phase12_enrichment.py::TestFieldExtraction::test_education_text_extracted -x` | Wave 0 |
| ENRICH-03 | All 7 columns written at enrichment time via `update_connection_from_profile()` | unit | `python -m pytest tests/test_phase12_enrichment.py::TestFieldExtraction -x` | Wave 0 |
| ENRICH-04 | Backfill fills NULL columns from existing raw_enrichment without API calls | unit | `python -m pytest tests/test_phase12_enrichment.py::TestBackfill -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_phase12_enrichment.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_phase12_enrichment.py` — covers ENRICH-01, ENRICH-02, ENRICH-03, ENRICH-04
- [ ] `src/pipeline/enrichment_extractor.py` — new module (extract_enrichment_fields, backfill_enrichment_fields, get_enrichment_coverage)

---

## Sources

### Primary (HIGH confidence)

- Direct code inspection: `src/database/models.py` — Connection model, existing fields, `get_enrichment_data()` helper
- Direct code inspection: `src/services/dashboard_service.py` — `_classify_seniority()`, `compute_industry_distribution()`, `get_enrichment_data()` usage pattern
- Direct code inspection: `src/ingestion/rapidapi_linkedin.py` — `update_connection_from_profile()`, `_get_mock_profile_data()` (confirms raw data shape including `educations` array)
- Direct code inspection: `src/sync/push.py` — `CONNECTION_SYNC_FIELDS` list, `_upsert_record()` pattern
- Direct code inspection: `src/cli.py` — existing `contacts` command group structure
- Direct code inspection: `src/pipeline/daily_pipeline.py` — pipeline step numbering and non-fatal try/except wrapper pattern
- Direct code inspection: `supabase/migrations/20260305000000_pwa_overhaul.sql` — `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` pattern, index creation pattern
- Direct code inspection: `supabase/migrations/20260311000000_signal_foundation.sql` — additional migration pattern confirmation
- Direct code inspection: `.planning/phases/12-enrichment-audit-and-schema-extraction/12-CONTEXT.md` — locked decisions

### Secondary (MEDIUM confidence)

- SQLite documentation (training knowledge, HIGH confidence): `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` supported in SQLite 3.37.0+ (released 2021-11-27). macOS ships SQLite 3.43+ with Python 3.11+. The try/except wrapper pattern handles older environments safely.
- Python `re` module emoji stripping (training knowledge, HIGH confidence): Unicode emoji ranges are well-defined; the pattern in Pitfall 4 is the standard approach.

### Tertiary (LOW confidence)

None — all claims in this document are grounded in direct code inspection.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — direct code inspection of every integration point
- Architecture: HIGH — all patterns confirmed from existing code; new `enrichment_extractor.py` follows established module pattern
- Pitfalls: HIGH — SQLite ALTER TABLE limitation is well-documented; other pitfalls derived from direct inspection of existing code and explicit project decisions
- Discretion recommendations: MEDIUM — judgment calls on normalization and emoji stripping are informed by Phase 13/14 requirements context

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable codebase; valid until project schema changes significantly)
