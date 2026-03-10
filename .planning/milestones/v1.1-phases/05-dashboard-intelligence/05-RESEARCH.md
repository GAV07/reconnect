# Phase 5: Dashboard Intelligence - Research

**Researched:** 2026-03-09
**Domain:** Vanilla JS PWA (dashboard charts, score breakdown UI), Python dashboard_service.py (new compute functions), DashboardSnapshot JSON schema extension
**Confidence:** HIGH — all findings from direct codebase inspection

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DASH-01 | User can see health score breakdown showing what drives the score with actionable insights | `dashboard_service.compute_network_health()` returns `components` dict (4 values) and top-level `score`; PWA `dashboard.js` already renders these 4 component values as metric cards but shows no per-component insight text; new `compute_health_breakdown()` function must add `insights: list[str]` to the return dict; `dashboard.js` must render each insight below the component grid |
| DASH-02 | User can see industry distribution across enriched contacts | Industry lives in `raw_enrichment` as `company_industry` (RapidAPI) or `companyIndustry` (Apify) — same dual-key extraction pattern used in `scoring.py`, `feedback_processor.py`, and `queue.js`; new `compute_industry_distribution()` function queries `connections` table, uses `get_enrichment_data()` helper, buckets by industry; PWA renders as horizontal bar chart using inline CSS bars (no external chart library) |
| DASH-03 | User can see role/seniority mix across enriched contacts | `Connection.current_role` is a top-level column (denormalized from enrichment at ingest time); seniority must be derived algorithmically from role keywords (same keyword list in `src/ui/views/dashboard.py`); `inferred_seniority` exists on `UserProfile` (not `Connection`); new `compute_role_seniority_mix()` function queries `Connection.current_role` directly; PWA renders as two side-by-side metric grids |
| DASH-04 | User can see score tier distribution across contacts | `Connection.reconnect_score` is a top-level float column; tier buckets are "High (70-100)", "Medium (40-69)", "Low (0-39)"; new `compute_score_tier_distribution()` function; PWA renders as horizontal bar chart inline CSS |
</phase_requirements>

---

## Summary

Phase 5 adds four visual intelligence sections to the existing PWA dashboard. All four requirements are additions to the `dashboard.js` file (PWA side) and `dashboard_service.py` (Python side), following patterns already established in both.

The data flow is: Python computes analytics → stores in `DashboardSnapshot.snapshot_data` JSON → synced to Supabase via `push.py` → PWA reads snapshot → renders sections. This flow already works end-to-end for existing dashboard sections. Phase 5 extends the snapshot schema with four new top-level keys: `health_breakdown`, `industry_distribution`, `role_seniority_mix`, and `score_tier_distribution`.

The key architectural decision is that all four new compute functions live in `dashboard_service.py` alongside the existing `compute_network_health()`, `compute_data_quality()`, etc. The snapshot builder `compute_dashboard_snapshot()` calls them all. No new Python files are needed.

For the PWA, all four sections use inline CSS horizontal bar charts — the same technique already used in `buildFunnelSection()` in `dashboard.js`. The project has no external charting library and there is no reason to add one: the bar pattern with `style="width:X%"` is already established, works without JavaScript bundle overhead, and fits the mobile-first CSS design system.

**Primary recommendation:** Add four compute functions to `dashboard_service.py`, extend `compute_dashboard_snapshot()` to call them, then add four `build*Section()` functions to `dashboard.js` that render the new snapshot keys. No new tables, no schema migrations, no new npm packages.

---

## Standard Stack

### Core (no changes to existing stack)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLModel + SQLAlchemy | >=0.0.14 (installed) | Query `Connection.reconnect_score`, `current_role`, `enriched_at` | Already in use; `get_enrichment_data()` helper handles dual-key JSON unwrap |
| supabase-js | CDN (already in PWA) | Read `dashboard_snapshots` table | Already used in `renderDashboard()` for existing snapshot fetch |
| Vanilla JS DOM manipulation | — | Render inline CSS bar charts | Consistent with existing `buildFunnelSection()` and `buildEnrichmentStatusSection()` patterns |

### No new packages required

All four requirements are served by the existing stack. The Streamlit dashboard (`src/ui/views/dashboard.py`) uses Plotly for charts, but the PWA does not and must not — the PWA is vanilla JS, deployed via Netlify, with no build step.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inline CSS bars | Chart.js or similar | Chart.js requires CDN load + canvas element; inline bars already used for pipeline funnel; stay consistent |
| Inline CSS bars | SVG pie charts | SVG pie is more visually rich for distribution charts but increases code complexity significantly; bar charts are sufficient for this use case |
| Adding 4 new snapshot keys | Adding new Supabase table | New table requires migration + new sync code + new PostgREST query; snapshot JSON extension is zero-migration, consistent with existing approach |

---

## Architecture Patterns

### Recommended Changes (files modified only)

```
src/services/
└── dashboard_service.py  # ADD: compute_health_breakdown(), compute_industry_distribution(),
                          #      compute_role_seniority_mix(), compute_score_tier_distribution()
                          # MODIFY: compute_dashboard_snapshot() to call the 4 new functions

pwa/js/
└── dashboard.js          # ADD: buildHealthBreakdownSection(), buildIndustryDistributionSection(),
                          #      buildRoleSenioritySection(), buildScoreTierSection()
                          # MODIFY: renderDashboard() to call the 4 new build functions
```

No new files. No migrations. No new dependencies.

### Snapshot JSON Schema Extension

The `DashboardSnapshot.snapshot_data` JSON currently has these top-level keys:

```json
{
  "network_health": { "score": 72.4, "components": { ... } },
  "opportunity_alerts": [ ... ],
  "feedback_insights": { ... },
  "data_quality": { ... },
  "computed_at": "2026-03-09T08:00:00"
}
```

Phase 5 adds:

```json
{
  "health_breakdown": {
    "score": 72.4,
    "components": {
      "data_completeness": { "value": 68.0, "weight": 0.30, "insight": "Enrich more contacts to improve data completeness" },
      "enrichment_pct":    { "value": 55.2, "weight": 0.25, "insight": "55% of contacts enriched — enrich more for better scores" },
      "email_coverage_pct":{ "value": 42.1, "weight": 0.25, "insight": "Add email addresses to unlock email outreach" },
      "activity_score":    { "value": 30.0, "weight": 0.20, "insight": "Send more messages to build activity score" }
    },
    "insights": [
      "Data completeness is your biggest opportunity — each enriched contact adds 30% weight to the score",
      "Email coverage is low (42%) — run Hunter.io to find missing emails"
    ]
  },
  "industry_distribution": [
    { "industry": "Technology", "count": 87, "pct": 42.0 },
    { "industry": "Finance", "count": 34, "pct": 16.4 },
    ...
  ],
  "role_seniority_mix": {
    "roles": [
      { "keyword": "Engineer", "count": 54 },
      { "keyword": "Manager", "count": 38 },
      ...
    ],
    "seniority": [
      { "tier": "Executive (C-suite/VP/Director)", "count": 22 },
      { "tier": "Senior (Senior/Lead/Staff)", "count": 61 },
      { "tier": "Mid-level (Manager/Analyst/Specialist)", "count": 84 },
      { "tier": "Entry/Unknown", "count": 40 }
    ]
  },
  "score_tier_distribution": [
    { "tier": "High (70-100)", "count": 28, "pct": 13.5 },
    { "tier": "Medium (40-69)", "count": 74, "pct": 35.7 },
    { "tier": "Low (0-39)", "count": 105, "pct": 50.7 }
  ]
}
```

### Pattern 1: Python Compute Function (applies to all 4 new functions)

**What:** Query Connection table, compute aggregate, return structured dict.

**When to use:** All four new `compute_*` functions follow this exact pattern.

```python
# Source: direct extension of existing dashboard_service.py patterns

def compute_industry_distribution() -> list[dict]:
    """Compute industry distribution across enriched contacts."""
    from collections import Counter

    with get_session() as session:
        enriched = session.exec(
            select(Connection)
            .where(Connection.enriched_at.isnot(None))
        ).all()

    industry_counts: Counter = Counter()
    for conn in enriched:
        enrichment = get_enrichment_data(conn)
        # Dual-key extraction — same pattern as scoring.py line 199 and feedback_processor.py line 87
        industry = (
            enrichment.get("company_industry")
            or enrichment.get("companyIndustry")
            or "Unknown"
        )
        industry_counts[industry] += 1

    total = sum(industry_counts.values()) or 1
    # Top 10, sorted descending, with percentage
    result = [
        {
            "industry": industry,
            "count": count,
            "pct": round(count / total * 100, 1),
        }
        for industry, count in industry_counts.most_common(10)
    ]
    return result
```

### Pattern 2: Seniority Derivation from Role Keywords

**What:** The `Connection.current_role` column is a top-level string. Seniority is not stored directly — it must be derived from role title keywords. `UserProfile.inferred_seniority` exists but applies to the user, not contacts.

**Seniority keyword mapping (authoritative — derived from existing Streamlit dashboard keyword list):**

```python
# Source: src/ui/views/dashboard.py lines 256-265 (role keyword extraction pattern)
# Extended for seniority tiering

EXECUTIVE_KEYWORDS = ["ceo", "cto", "coo", "cfo", "founder", "president", "owner", "partner"]
SENIOR_KEYWORDS = ["vp", "vice president", "director", "head of", "senior", "lead", "staff", "principal", "chief"]
MID_KEYWORDS = ["manager", "analyst", "specialist", "consultant", "engineer", "developer", "designer", "product"]

def _classify_seniority(role: str) -> str:
    """Classify a role title into a seniority tier."""
    role_lower = (role or "").lower()
    if any(kw in role_lower for kw in EXECUTIVE_KEYWORDS):
        return "Executive"
    if any(kw in role_lower for kw in SENIOR_KEYWORDS):
        return "Senior"
    if any(kw in role_lower for kw in MID_KEYWORDS):
        return "Mid-level"
    return "Unknown"
```

### Pattern 3: Inline CSS Bar Chart in Vanilla JS (for DASH-02, DASH-03, DASH-04)

**What:** Render distribution data as horizontal bars using inline width style — the same technique already used in `buildFunnelSection()`.

**When to use:** Any distribution rendering in `dashboard.js`. Do not add an external chart library.

```javascript
// Source: Consistent with buildFunnelSection() pattern in dashboard.js lines 3-25

function buildIndustryDistributionSection(industries) {
  if (!industries || industries.length === 0) return '';

  let html = '<div class="detail-section mt-4">';
  html += '<h3 style="font-size: 15px; font-weight: 600; color: var(--text-secondary); margin-bottom: 12px;">INDUSTRY DISTRIBUTION</h3>';

  for (const item of industries) {
    html += `
      <div class="funnel-stage">
        <div class="funnel-label" style="width: 140px; font-size: 13px;">${escapeHtml(item.industry)}</div>
        <div class="funnel-bar"><div class="funnel-fill" style="width:${item.pct}%"></div></div>
        <div class="funnel-count">${item.count} <span style="color: var(--text-muted); font-size: 12px;">${item.pct}%</span></div>
      </div>`;
  }
  html += '</div>';
  return html;
}
```

### Pattern 4: Health Score Actionable Insights (DASH-01)

**What:** Per-component insight text is generated Python-side (not in the PWA) so the text can reference actual values and thresholds. The PWA renders insight strings as-is.

```python
# Source: extends compute_network_health() in dashboard_service.py

def _generate_component_insight(component: str, value: float) -> str:
    """Return actionable insight text for a health score component."""
    if component == "data_completeness":
        if value >= 80:
            return "Data completeness is strong"
        if value >= 60:
            return f"Data completeness is {value:.0f}% — enrich more contacts to improve"
        return f"Data completeness is low ({value:.0f}%) — enriching contacts is your biggest lever"

    if component == "enrichment_pct":
        if value >= 70:
            return "Enrichment rate is strong"
        return f"Only {value:.0f}% of contacts enriched — run the pipeline to enrich more"

    if component == "email_coverage_pct":
        if value >= 60:
            return "Email coverage is healthy"
        return f"Email coverage is {value:.0f}% — run Hunter.io to find missing email addresses"

    if component == "activity_score":
        if value >= 70:
            return "Network activity is strong"
        if value >= 30:
            return "Moderate activity — keep reaching out"
        return "Low activity — approve more contacts in the queue to build momentum"

    return ""
```

### Anti-Patterns to Avoid

- **Adding a chart library (Chart.js, D3) to the PWA:** The project has no build step; a CDN import adds latency and breaks the "no external dependencies" pattern. Inline CSS bars are consistent with existing `buildFunnelSection()`.
- **Querying raw `snapshot_data` in the PWA for complex logic:** All aggregation happens Python-side. The PWA is a thin renderer of pre-computed snapshot data.
- **Loading all Connection records client-side for analytics:** The snapshot pattern exists precisely to avoid this. The pipeline computes and pushes; the PWA reads a single row.
- **Creating a new Supabase table for distribution data:** Extending the `snapshot_data` JSON is zero-migration and consistent with `data_quality` (which already stores multiple sub-objects in the same snapshot).
- **Generating insight text in JavaScript:** Text with thresholds and percentages is easier to maintain and test in Python. The PWA only renders strings.
- **Querying `raw_enrichment` directly from the PWA for industry:** Industry is in nested JSON. Only the Python pipeline can reliably compute the dual-key extraction at scale.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dual-key industry extraction from raw_enrichment | Custom JSON traversal | `get_enrichment_data(conn)` + `enrichment.get("company_industry") or enrichment.get("companyIndustry")` | Pattern already established in `scoring.py:199`, `feedback_processor.py:87`, `prose.py:116` |
| Role keyword extraction | New keyword list | Extend existing keyword list from `src/ui/views/dashboard.py:256` | Keyword list already exists and covers the common role types in this network |
| Snapshot schema versioning | Migration or schema table | Just add new top-level keys to `snapshot_data` JSON | Schema-less JSON column — backward compatible; PWA uses `|| {}` default for missing keys |
| Percentage calculation | Custom math | `round(count / total * 100, 1) if total > 0 else 0` | Same pattern used in `compute_data_quality()` throughout |
| Score tier bucketing | Complex range logic | Three simple comparisons (`>= 70`, `>= 40`, else) | Same tier thresholds already used in `dashboard.js:82` for health score color |

**Key insight:** The entire data pipeline for dashboard analytics is already in place. This phase is wiring four new compute functions into an existing pipeline and rendering their output in an existing PWA page — not building new infrastructure.

---

## Common Pitfalls

### Pitfall 1: Missing Snapshot Keys in Old Snapshots

**What goes wrong:** The PWA reads the latest `dashboard_snapshots` row. If the pipeline hasn't run since Phase 5 was deployed, the snapshot will lack the four new keys. `snapshot.health_breakdown`, `snapshot.industry_distribution`, etc. will be `undefined` in JavaScript. Calling `.forEach()` on undefined throws `TypeError`.

**Why it happens:** `compute_dashboard_snapshot()` is extended to call the four new functions, but the snapshot in Supabase is stale (created before Phase 5 code deployed).

**How to avoid:** All four new build functions must guard against `undefined` or empty data with an early return of `''` (empty string), so `renderDashboard()` gracefully omits the section rather than crashing. After Phase 5 ships, the next pipeline run will regenerate the snapshot with all four new keys.

```javascript
// Correct guard pattern
function buildIndustryDistributionSection(industries) {
  if (!industries || industries.length === 0) return '';
  // ... render
}
```

**Warning signs:** Dashboard renders no new sections after deploying Phase 5 (expected until next pipeline run). Dashboard throws console errors (missing guard).

### Pitfall 2: Unknown Industry Inflating Distribution

**What goes wrong:** Many contacts have `raw_enrichment = null` or lack `company_industry`/`companyIndustry` keys. They all fall into `"Unknown"` bucket. The industry distribution shows `"Unknown"` as the largest segment.

**Why it happens:** Only enriched contacts have industry data. The `compute_industry_distribution()` function should scope to `enriched_at IS NOT NULL` contacts only — and even then, some may lack industry in their enrichment response.

**How to avoid:** Query only `Connection.enriched_at.isnot(None)` contacts. In the PWA render, either filter out `"Unknown"` or render it last with a gray/muted style. Document in the section header: "INDUSTRY (enriched contacts)".

**Warning signs:** Industry distribution shows 30%+ "Unknown" in the first bucket.

### Pitfall 3: Score Tier Count Including Un-Scored Contacts

**What goes wrong:** `Connection.reconnect_score` is `None` for un-enriched/un-scored contacts. If the query doesn't filter `reconnect_score IS NOT NULL`, the SQL count won't include them in any tier — but the percentage calculation will be wrong if it divides by `total_contacts` (which includes un-scored). The tiers would sum to less than 100%.

**Why it happens:** `total` in `compute_data_quality()` uses all contacts. Score tier distribution needs to use only contacts with a non-null `reconnect_score`.

**How to avoid:** Scope the score tier query to `Connection.reconnect_score.isnot(None)`. Report "of scored contacts" in the section subtitle.

**Warning signs:** Tier percentages sum to substantially less than 100%.

### Pitfall 4: Health Breakdown Diverging from Existing Health Score Display

**What goes wrong:** The existing dashboard already renders the four health components as metric cards (lines 92-109 in `dashboard.js`). Adding a new `buildHealthBreakdownSection()` could duplicate those four numbers on the page.

**Why it happens:** DASH-01 says "show what drives the score with actionable insights" — it's tempting to build a completely new section, not realizing the components are already displayed.

**How to avoid:** DASH-01 should augment the existing component display, not duplicate it. The existing 4-card metric grid renders values. The new section adds insight text below each component OR replaces the plain value cards with value+insight cards. The simplest approach: add `insights` array rendering below the existing `<div class="metric-grid">` block in `renderDashboard()`.

**Warning signs:** Dashboard shows the same four numbers twice (once as metric cards, once in new breakdown section).

### Pitfall 5: Role Keyword Matching Too Broad

**What goes wrong:** The role keyword `"manager"` appears in titles like "Project Manager", "Account Manager", "Community Manager" — vastly different seniority levels. The keyword `"senior"` in "Senior Manager" would put someone in Senior tier even if the role is mid-management.

**Why it happens:** Simple substring matching on `current_role` is coarse. `"senior"` before a keyword implies higher tier, but the algorithm classifies by first matching tier.

**How to avoid:** Apply executive keywords first, then senior, then mid. This order-of-priority already handles the common case ("Senior Director" matches executive via "director" before mid-level via anything else). Document in code that this is intentional approximate classification, not precise HR taxonomy. The goal is directional insight, not HR accuracy.

**Warning signs:** Seniority distribution shows 90%+ "Unknown" (keyword list too narrow) or 70%+ "Executive" (keyword matching too broad).

---

## Code Examples

Verified patterns from direct codebase inspection:

### How `compute_dashboard_snapshot()` Will Be Extended

```python
# Source: src/services/dashboard_service.py lines 254-267 — extend this function

def compute_dashboard_snapshot() -> dict:
    """Compute full dashboard data and return as dict."""
    snapshot = {
        "network_health": compute_network_health(),
        "opportunity_alerts": compute_opportunity_alerts(),
        "feedback_insights": compute_feedback_insights(),
        "data_quality": compute_data_quality(),
        # Phase 5 additions:
        "health_breakdown": compute_health_breakdown(),          # DASH-01
        "industry_distribution": compute_industry_distribution(), # DASH-02
        "role_seniority_mix": compute_role_seniority_mix(),      # DASH-03
        "score_tier_distribution": compute_score_tier_distribution(), # DASH-04
        "computed_at": datetime.utcnow().isoformat(),
    }
    return snapshot
```

### How `renderDashboard()` Will Be Extended

```javascript
// Source: pwa/js/dashboard.js lines 171-172 — extend before container.innerHTML = html

// After existing sections, before container.innerHTML = html:
html += buildHealthBreakdownSection(snapshot.health_breakdown || null);          // DASH-01
html += buildIndustryDistributionSection(snapshot.industry_distribution || []);  // DASH-02
html += buildRoleSenioritySection(snapshot.role_seniority_mix || null);         // DASH-03
html += buildScoreTierSection(snapshot.score_tier_distribution || []);           // DASH-04

container.innerHTML = html;
```

### Existing CSS Classes Available (no new CSS needed)

```css
/* Source: pwa/css/app.css — classes already available for use */
.detail-section   /* wrapper section with top margin */
.metric-grid      /* 2-column grid for metric cards */
.metric-card      /* individual metric card */
.metric-label     /* label text above value */
.metric-value     /* large numeric value */
.metric-sub       /* subtitle text below value */
.funnel-stage     /* horizontal bar row */
.funnel-label     /* left label of bar */
.funnel-bar       /* bar background */
.funnel-fill      /* bar fill (uses width:X%) */
.funnel-count     /* right count label */
```

All four new sections can be built entirely from these existing CSS classes. No new CSS rules are needed.

### Dual-Key Industry Extraction (established pattern)

```python
# Source: src/llm/scoring.py:199, src/pipeline/feedback_processor.py:87,
#         src/llm/prose.py:116 — same pattern in 3 places already

enrichment = get_enrichment_data(conn)  # handles raw_enrichment.data or raw_enrichment
industry = (
    enrichment.get("company_industry")   # RapidAPI format
    or enrichment.get("companyIndustry") # Apify format
    or "Unknown"
)
```

### Existing Score Color Logic (reuse for score tier section)

```javascript
// Source: pwa/js/dashboard.js line 82 — threshold values to reuse
const healthScore = Math.round(health.score || 0);
const healthColor = healthScore >= 70 ? 'var(--success)' : healthScore >= 40 ? 'var(--warning)' : 'var(--danger)';
// Score tiers: High = >=70 (success/green), Medium = 40-69 (warning/orange), Low = <40 (danger/red)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Streamlit Plotly charts for distribution | Inline CSS bars in Vanilla JS | v1.0 PWA introduced | Plotly is Streamlit-only; PWA uses inline HTML/CSS bars |
| Snapshot computed only for existing 4 keys | Snapshot extended with 4 new keys | Phase 5 | No migration; pipeline recomputes on next run |
| Health components shown as plain values | Health components with insight text | Phase 5 | Text generated Python-side where thresholds are testable |

**Deprecated/outdated:**
- `src/ui/views/dashboard.py` (Streamlit) — still contains duplicate analytics logic (`_render_network_composition()`, `_render_score_distribution()`) but Streamlit is being removed in Phase 6. Do not reference it for Phase 5 except as a reference for keyword lists and bucketing logic.

---

## Open Questions

1. **Should DASH-01 modify the existing health component display or add a new section?**
   - What we know: The existing 4-card metric grid at lines 92-109 of `dashboard.js` already shows data_completeness, enrichment_pct, email_coverage_pct, and activity_score as plain numbers
   - What's unclear: DASH-01 says "show what drives the score with actionable insights" — this could mean (a) add insight text below the existing cards, (b) replace cards with value+insight cards, or (c) add a new separate section
   - Recommendation: Approach (a) — add insight strings below the existing component grid. Minimal code change, no duplication, and avoids redesigning an already-working layout. Add `insights: []` to `compute_health_breakdown()` return and render them as a list below the grid.

2. **How many enriched contacts have industry data in practice?**
   - What we know: Industry lives in `raw_enrichment` as `company_industry` or `companyIndustry`; RapidAPI mock data shows it present; Apify mock shows it present
   - What's unclear: What percentage of the 139 scored contacts actually have enriched industry data vs. having `raw_enrichment = null` or industry missing from the API response
   - Recommendation: `compute_industry_distribution()` should include an `enriched_count` in its return dict so the PWA can show "X of Y enriched contacts classified". If most are "Unknown", the section is still useful — it documents the gap.

3. **Should the score tier section show all contacts or only scored contacts?**
   - What we know: 139 contacts are scored (per Phase 4 SUMMARY); total contact count is larger
   - What's unclear: Whether the user wants to see tier distribution "of all contacts" or "of scored contacts"
   - Recommendation: Show "of scored contacts" — un-scored contacts have no tier by definition. Subtitle in the section: "Score tier distribution (scored contacts only)".

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4.0+ (already in pyproject.toml dev deps) |
| Config file | pyproject.toml (uses defaults — no [tool.pytest] section needed) |
| Quick run command | `python -m pytest tests/test_phase5_dashboard.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | `compute_health_breakdown()` returns `insights` list with at least one string when a component is below threshold | unit | `python -m pytest tests/test_phase5_dashboard.py::test_health_breakdown_low_values -x` | Wave 0 |
| DASH-01 | `compute_health_breakdown()` returns "strong" insight when all components are above threshold | unit | `python -m pytest tests/test_phase5_dashboard.py::test_health_breakdown_high_values -x` | Wave 0 |
| DASH-02 | `compute_industry_distribution()` returns list sorted by count descending, max 10 items | unit | `python -m pytest tests/test_phase5_dashboard.py::test_industry_distribution_sorted -x` | Wave 0 |
| DASH-02 | `compute_industry_distribution()` handles both `company_industry` and `companyIndustry` keys | unit | `python -m pytest tests/test_phase5_dashboard.py::test_industry_dual_key -x` | Wave 0 |
| DASH-02 | `compute_industry_distribution()` returns empty list when no enriched contacts exist | unit | `python -m pytest tests/test_phase5_dashboard.py::test_industry_no_enriched -x` | Wave 0 |
| DASH-03 | `compute_role_seniority_mix()` classifies "CEO" as Executive, "Senior Engineer" as Senior, "Analyst" as Mid-level | unit | `python -m pytest tests/test_phase5_dashboard.py::test_seniority_classification -x` | Wave 0 |
| DASH-03 | `compute_role_seniority_mix()` returns `roles` and `seniority` keys in result dict | unit | `python -m pytest tests/test_phase5_dashboard.py::test_role_seniority_structure -x` | Wave 0 |
| DASH-04 | `compute_score_tier_distribution()` correctly buckets scores: 75 → High, 55 → Medium, 25 → Low | unit | `python -m pytest tests/test_phase5_dashboard.py::test_score_tier_buckets -x` | Wave 0 |
| DASH-04 | `compute_score_tier_distribution()` excludes contacts with `reconnect_score IS NULL` | unit | `python -m pytest tests/test_phase5_dashboard.py::test_score_tier_excludes_unscored -x` | Wave 0 |
| DASH-04 | Tier percentages sum to 100% (±0.5% rounding tolerance) | unit | `python -m pytest tests/test_phase5_dashboard.py::test_score_tier_pct_sums -x` | Wave 0 |
| DASH-01–04 | `compute_dashboard_snapshot()` includes all 4 new top-level keys | unit | `python -m pytest tests/test_phase5_dashboard.py::test_snapshot_includes_new_keys -x` | Wave 0 |
| DASH-01–04 | PWA renders new sections without crash when keys are missing from snapshot (stale snapshot guard) | manual smoke | Open dashboard in browser after deploy | N/A |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_phase5_dashboard.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_phase5_dashboard.py` — covers all 11 automated test cases above
- [ ] No new conftest.py needed — existing `conftest.py` fixtures apply; mock Connection pattern from `test_phase4_foundation.py` is reusable

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection: `pwa/js/dashboard.js` — existing render patterns, CSS class usage, snapshot data shape
- Direct codebase inspection: `src/services/dashboard_service.py` — all existing compute functions, `compute_dashboard_snapshot()` structure
- Direct codebase inspection: `src/database/models.py` — `Connection` fields (`current_role`, `reconnect_score`, `enriched_at`, `raw_enrichment`), `DashboardSnapshot.snapshot_data` JSON column
- Direct codebase inspection: `src/llm/scoring.py:199` — dual-key industry extraction pattern
- Direct codebase inspection: `src/pipeline/feedback_processor.py:87` — dual-key industry extraction pattern (second reference)
- Direct codebase inspection: `src/ingestion/rapidapi_linkedin.py:219` — `company_industry` key in RapidAPI response shape
- Direct codebase inspection: `src/ingestion/apify_client.py:80` — `companyIndustry` key in Apify response shape
- Direct codebase inspection: `src/ui/views/dashboard.py:256-265` — role keyword list for network composition (Streamlit reference for keyword catalogue)
- Direct codebase inspection: `pwa/css/app.css` — all CSS classes available for new sections
- Direct codebase inspection: `src/sync/push.py:233-243` — `DashboardSnapshot` sync to Supabase confirmed working

### Secondary (MEDIUM confidence)

- None required — all findings directly verified from codebase

### Tertiary (LOW confidence)

- None — no speculative claims in this research

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all changes are to existing files using established patterns
- Architecture: HIGH — snapshot extension pattern is directly observed; all integration points verified by reading source
- Pitfalls: HIGH — all pitfalls derived from reading actual code paths (missing key guards, dual-key extraction, score filter scope)

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable domain; no external API dependencies for this phase)
