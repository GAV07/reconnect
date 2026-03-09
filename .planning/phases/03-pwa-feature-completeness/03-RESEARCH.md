# Phase 3: PWA Feature Completeness - Research

**Researched:** 2026-03-08
**Domain:** Vanilla JS PWA, Supabase JS client, hash router, CSS, Python dashboard service
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROFILE-01 | Contact profile page displays AI scoring rationale with dimension breakdown (Goal Alignment, Industry Overlap, Mutual Value, Conversation Hooks, Network Reach) | `contact.js` already parses `score_reasoning` JSON and renders dimension bars. The field exists on all enriched+scored connections. Gap: connection strength and enrichment sub-sections are missing. |
| PROFILE-02 | Contact profile page shows professional context (current role, company, industry, career trajectory) | `current_role`, `current_company`, `location`, `industry` are top-level columns on `connections`. Career trajectory lives inside `raw_enrichment.data.experiences`. Needs a dedicated "Professional Context" section in contact.js. |
| PROFILE-03 | Contact profile page shows connection strength (how you know them, mutual connections, last interaction) | `message_count`, `conversation_status`, `last_message_date`, `conversation_summary`, `engagement_score`, `engagement_direction`, `endorsement_count`, `has_recommendation` are all on the `connections` model. Needs a "Connection Strength" section. |
| PROFILE-04 | Contact profile page surfaces full enrichment fields (location, headline, email status, LinkedIn URL) | `location`, `email`, `linkedin_url` are top-level columns. `headline` is inside `raw_enrichment.data`. `data_completeness_score` and `missing_data_fields` flag gaps. Need an "Enrichment" section in contact.js. |
| VIEW-01 | Pipeline funnel view showing contact flow: imported → scored → reviewed → reached out → connected | Dashboard snapshot `data_quality` section has `total_contacts` and `scored` counts. `outreach_queue` status codes provide reviewed/reached-out counts. No "connected" count exists — must be derived from `outreach_log.outcome = 'replied'` or flag as 0. Needs a funnel section added to dashboard.js. |
| VIEW-02 | Enrichment status view showing contacts with full data vs. need more enrichment | `data_quality.need_enrichment` count exists in the dashboard snapshot. For a per-contact list, query `connections` where `data_completeness_score < threshold` or `enriched_at IS NULL`. Needs a new view or dashboard section. |
| VIEW-03 | Feedback history view showing past yes/no decisions and scoring accuracy over time | `user_feedback` table has all approve/skip/rating rows. `outreach_queue` has status history. These can be surfaced in the existing Preferences page or as a new History tab. |
| VIEW-04 | PWA reads query parameters on load and navigates to correct hash route (email deep link bridge) | ALREADY IMPLEMENTED in `app.js` via `checkDeepLinkQueryParams()`. The function reads `?view=contact&id=X` and converts to `#/contact/{id}`. Only verification work needed. |
</phase_requirements>

---

## Summary

Phase 3 is almost entirely front-end work inside the existing vanilla JS PWA. The data layer (Supabase tables, sync pipeline, dashboard snapshots) is already in place — the gap is purely in what the PWA renders. The `connections` table holds every field needed for PROFILE-01 through PROFILE-04, and the `dashboard_snapshots` table holds the aggregated counts needed for VIEW-01 and VIEW-02. VIEW-04 is already implemented and just needs a smoke test.

The architecture is intentionally simple: no build tooling, no frameworks, no bundler. All changes are edits to existing JS files (`contact.js`, `dashboard.js`, `preferences.js`) plus CSS additions to `app.css`. The Supabase anon key + PostgREST REST API is the only data layer; no new Edge Functions are needed for this phase.

The two non-trivial decisions are: (1) whether VIEW-01 funnel data is read from the dashboard snapshot or computed live via Supabase queries, and (2) whether VIEW-03 feedback history is a new nav tab or merged into the existing Preferences page. Both have answers in the research below.

**Primary recommendation:** Read all view data from the existing `dashboard_snapshots` table for aggregate counts (VIEW-01, VIEW-02), and query `connections` + `user_feedback` directly for per-contact detail (PROFILE-*, VIEW-03). Add one new nav tab "History" for VIEW-03. Do not create new Edge Functions — the anon key has direct PostgREST read access to all needed tables.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Supabase JS (CDN) | `@supabase/supabase-js@2` | PostgREST queries, realtime | Already loaded in index.html via CDN |
| Vanilla JS | ES2020 | Routing, rendering, DOM | Established in Phase 1; no build tooling |
| CSS custom properties | N/A | Design tokens (colors, radius, shadow) | Already defined in `app.css` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| None | — | No additional libraries needed | All required UI patterns already exist in the codebase |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw PostgREST queries | Edge Function wrapper | Edge Functions add latency, deploy step, and cold-start. Unnecessary when anon key already grants read access. |
| Dashboard snapshot for funnel | Live COUNT queries | Live queries are fine for this scale; snapshot avoids extra Supabase hits. Snapshot is the established pattern from dashboard.js. |

**Installation:**
No new packages. The PWA has no package.json build step.

---

## Architecture Patterns

### Recommended Project Structure
```
pwa/
├── css/
│   └── app.css          # Add: .funnel-stage, .enrichment-chip, .history-item
├── js/
│   ├── app.js           # No changes needed (routing complete)
│   ├── contact.js       # Add: Professional Context, Connection Strength, Enrichment sections
│   ├── dashboard.js     # Add: pipeline funnel section, enrichment status section
│   ├── preferences.js   # Add: feedback history section (expand existing page)
│   └── queue.js         # No changes needed
└── index.html           # Add: "History" nav item (if VIEW-03 gets its own tab)
```

### Pattern 1: Section-based contact profile (PROFILE-02, PROFILE-03, PROFILE-04)

**What:** The contact detail page (`contact.js`) renders HTML sections sequentially. New sections follow the `<div class="detail-section"><h3>HEADING</h3>...</div>` pattern already established.

**When to use:** Every new block of contact info.

**Example:**
```javascript
// Source: existing contact.js pattern
function buildProfessionalContextSection(conn) {
  const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
  const industry = enrichment.company_industry || enrichment.companyIndustry || 'Unknown';
  const headline = enrichment.headline || '';
  const experiences = enrichment.experiences || enrichment.experience || [];
  const prevRoles = experiences.slice(1, 3).map(e =>
    `${e.title || ''} at ${e.company || e.companyName || ''}`.trim()
  ).filter(Boolean);

  return `
    <div class="detail-section">
      <h3>Professional Context</h3>
      <div class="info-row"><span class="info-label">Role</span><span>${escapeHtml(conn.current_role || '—')}</span></div>
      <div class="info-row"><span class="info-label">Company</span><span>${escapeHtml(conn.current_company || '—')}</span></div>
      <div class="info-row"><span class="info-label">Industry</span><span>${escapeHtml(industry)}</span></div>
      ${headline ? `<div class="info-row"><span class="info-label">Headline</span><span>${escapeHtml(headline)}</span></div>` : ''}
      ${prevRoles.length ? `<div class="info-row"><span class="info-label">Previous</span><span>${escapeHtml(prevRoles.join(' / '))}</span></div>` : ''}
    </div>`;
}
```

### Pattern 2: Dashboard snapshot consumption (VIEW-01, VIEW-02)

**What:** `dashboard.js` already fetches `dashboard_snapshots` and reads `snapshot_data`. The funnel counts come from `data_quality` (for imported/scored) and live queries (for reviewed/reached_out).

**When to use:** Aggregate views that don't need per-contact detail.

**Example:**
```javascript
// Source: existing dashboard.js pattern — extend with funnel section
function buildFunnelSection(quality) {
  const stages = [
    { label: 'Imported', count: quality.total_contacts || 0 },
    { label: 'Scored', count: quality.scored || 0 },
    { label: 'Reviewed', count: quality.reviewed || 0 },      // add to snapshot
    { label: 'Reached Out', count: quality.reached_out || 0 }, // add to snapshot
    { label: 'Connected', count: quality.connected || 0 },     // outreach_log.outcome='replied'
  ];
  const max = stages[0].count || 1;

  let html = '<div class="detail-section mt-4"><h3>Pipeline Funnel</h3>';
  for (const stage of stages) {
    const pct = Math.round((stage.count / max) * 100);
    html += `
      <div class="funnel-stage">
        <div class="funnel-label">${stage.label}</div>
        <div class="funnel-bar"><div class="funnel-fill" style="width:${pct}%"></div></div>
        <div class="funnel-count">${stage.count}</div>
      </div>`;
  }
  html += '</div>';
  return html;
}
```

### Pattern 3: Deep link query-param bridge (VIEW-04)

**What:** Already implemented in `app.js`. `checkDeepLinkQueryParams()` reads `?view=contact&id=X` from `window.location.search`, calls `history.replaceState`, sets `window.location.hash`, and returns `true` so `render()` is not called twice (the `hashchange` event fires it).

**When to use:** Verification only — the code is already in production.

### Anti-Patterns to Avoid
- **Adding a new `<script src="...">` tag for each new view:** All view logic belongs in the existing JS files. One file per route module.
- **Fetching `connections` inside `renderDashboard`:** The dashboard is for aggregates. Per-contact lists (enrichment status) should query with `.limit()` and link to `#/contact/{id}`.
- **Hardcoding enrichment field paths:** The `raw_enrichment` JSON may have a nested `"data"` key (RapidAPI) or be flat (other providers). Always use the `raw_enrichment?.data || raw_enrichment` unwrap pattern already established in `scoring.py` and visible in `contact.js`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Horizontal progress bars for funnel | Custom SVG or canvas | CSS width % on `<div>` with transition | Established in `.dimension-bar .bar-fill` pattern |
| Escaping user data in HTML strings | Custom escape function | `escapeHtml()` already in `queue.js` | Already defined; all JS files share global scope |
| Supabase queries | REST fetch calls | `db.from(...).select(...)` via supabase-js | Type-safe, handles auth headers automatically |
| Counting funnel stages at query time | Complex SQL in PostgREST | Dashboard snapshot values OR simple `.select('id', { count: 'exact', head: true })` pattern | Supabase JS supports `count` option natively |

**Key insight:** The PWA has no module system — all JS files load into one global scope. `escapeHtml`, `db`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `navigate` are all global. Use them freely across files.

---

## Common Pitfalls

### Pitfall 1: raw_enrichment nested "data" key
**What goes wrong:** Accessing `conn.raw_enrichment.headline` returns `undefined` because RapidAPI wraps fields under a `"data"` key: `conn.raw_enrichment.data.headline`.
**Why it happens:** Different enrichment providers store at different depths. The Python side uses `get_enrichment_data()` to normalize this; the JS side must do the same unwrap.
**How to avoid:** Always resolve with `const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};` before accessing any enrichment sub-field.
**Warning signs:** All enrichment fields show "Unknown" or undefined even for enriched contacts.

### Pitfall 2: VIEW-04 is already implemented — don't duplicate it
**What goes wrong:** Re-implementing deep link handling in a second place causes double-navigation or the hash getting clobbered.
**Why it happens:** The `checkDeepLinkQueryParams()` function in `app.js` already handles `?view=contact&id=X`. It was added in Phase 2.
**How to avoid:** Only write a test that verifies it works. Do not touch `app.js` for VIEW-04.
**Warning signs:** The URL bar shows `?view=contact&id=X` still present after PWA loads (means `history.replaceState` failed).

### Pitfall 3: Dashboard snapshot missing funnel stage counts
**What goes wrong:** VIEW-01 needs "reviewed", "reached_out", and "connected" counts, but the current `dashboard_service.py` only provides `total_contacts` and `scored` inside `data_quality`.
**Why it happens:** `compute_data_quality()` queries `OutreachQueueItem` for `need_enrichment` but not for status breakdowns.
**How to avoid:** Either (a) add `reviewed`, `reached_out`, `connected` counts to `compute_data_quality()` in `dashboard_service.py` and push them in the next pipeline snapshot, OR (b) have `dashboard.js` issue a live count query to `outreach_queue` grouped by status. Option (a) is cleaner — update the service and let the snapshot carry the data.
**Warning signs:** Funnel shows 0 for Reviewed/Reached Out/Connected even after real queue activity.

### Pitfall 4: "Connected" count has no reliable column
**What goes wrong:** The funnel's "Connected" stage has no dedicated column. `outreach_queue.status` goes up to `"sent"` but not to "connected/replied".
**Why it happens:** `outreach_log.outcome = 'replied'` is the intended signal, but `outreach_log` rows are created manually or not at all.
**How to avoid:** Show "Connected" as count of `outreach_log` rows with `outcome = 'replied'`. If zero, show 0 (which is accurate — no replies logged yet). Don't invent a column.
**Warning signs:** Temptation to conflate "sent" with "connected".

### Pitfall 5: Missing CSS classes cause layout breakage
**What goes wrong:** New sections (`funnel-stage`, `info-row`, `enrichment-chip`) use class names that don't exist in `app.css`, so they render unstyled.
**Why it happens:** The CSS and JS are tightly coupled — there's no runtime CSS-in-JS.
**How to avoid:** Define all new CSS classes in `app.css` before the JS references them.

### Pitfall 6: Bottom nav active state with a new "History" tab
**What goes wrong:** Adding a fourth nav item without updating the active-state logic in `app.js` `render()` leaves the new tab always looking inactive.
**Why it happens:** `render()` hardcodes the active-state toggle based on route paths: `href === currentPath || (currentPath.startsWith('#/contact') && href === '#/queue')`.
**How to avoid:** If VIEW-03 gets its own `/history` route, add it to `routes` object in `app.js` and add the module case in `render()`'s switch.

---

## Code Examples

Verified patterns from existing codebase:

### Supabase count query (for live funnel counts)
```javascript
// Source: supabase-js@2 API — used as alternative to snapshot counts
const { count: reviewedCount } = await db
  .from('outreach_queue')
  .select('*', { count: 'exact', head: true })
  .in('status', ['approved', 'skipped']);
```

### Unwrapping raw_enrichment safely (JS)
```javascript
// Source: derived from Python get_enrichment_data() pattern in models.py
const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
const headline = enrichment.headline || '';
const industry = enrichment.company_industry || enrichment.companyIndustry || '';
```

### Rendering connection strength indicators
```javascript
// Source: models.py field mapping for connection strength
function buildConnectionStrengthSection(conn) {
  const msgCount = conn.message_count || 0;
  const lastMsg = conn.last_message_date
    ? new Date(conn.last_message_date).toLocaleDateString()
    : 'Never';
  const convStatus = conn.conversation_status || 'unknown';
  const engScore = conn.engagement_score ? Math.round(conn.engagement_score) : null;

  return `
    <div class="detail-section">
      <h3>Connection Strength</h3>
      <div class="info-row"><span class="info-label">Messages</span><span>${msgCount}</span></div>
      <div class="info-row"><span class="info-label">Last Contact</span><span>${lastMsg}</span></div>
      <div class="info-row"><span class="info-label">Conversation</span><span>${escapeHtml(convStatus)}</span></div>
      ${engScore !== null ? `<div class="info-row"><span class="info-label">Engagement</span><span>${engScore}/100</span></div>` : ''}
      ${conn.endorsement_count ? `<div class="info-row"><span class="info-label">Endorsements</span><span>${conn.endorsement_count}</span></div>` : ''}
      ${conn.has_recommendation ? `<div class="info-row"><span class="info-label">Recommendation</span><span>Yes</span></div>` : ''}
    </div>`;
}
```

### Enrichment status chip pattern
```javascript
// Source: design convention matching existing score-badge pattern
function enrichmentStatusChip(conn) {
  const score = conn.data_completeness_score;
  if (score === null || score === undefined) return '';
  const pct = Math.round(score);
  const color = pct >= 80 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--danger)';
  return `<span class="enrichment-chip" style="background:${color}20;color:${color};">${pct}% complete</span>`;
}
```

### Dashboard snapshot data shape (confirmed from dashboard_service.py)
```javascript
// snapshot_data structure as pushed by compute_dashboard_snapshot():
{
  network_health: {
    score: Number,
    components: { data_completeness, enrichment_pct, email_coverage_pct, activity_score }
  },
  opportunity_alerts: [{ type, connection_id, name, detail, score }],
  feedback_insights: { avg_digest_rating, scoring_adjustments: {} },
  data_quality: {
    total_contacts, scored, scored_pct,
    enriched, enriched_pct,
    has_email, email_pct,
    need_enrichment, need_email
    // NOTE: reviewed, reached_out, connected are NOT yet in snapshot — must be added
  },
  computed_at: ISO string
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Supabase Storage for PWA hosting | Netlify (SPA redirect rule) | Phase 1 | Hash routing now works |
| Hash fragment deep links | Query param `?view=contact&id=X` | Phase 2 | Survives Gmail redirect chain |
| OAuth flow for Gmail | App Password + smtplib | Phase 1 | Email sends reliably |

**Deprecated/outdated:**
- Supabase Storage PWA URL: replaced with Netlify URL in Phase 1. Any remaining references to `*.supabase.co/storage/...` are stale.

---

## Open Questions

1. **Should VIEW-03 be a new nav tab or expand the Preferences page?**
   - What we know: The Preferences page (`preferences.js`) already shows recent feedback rows. VIEW-03 needs past yes/no decisions and scoring accuracy over time.
   - What's unclear: Does "scoring accuracy over time" mean showing approved-vs-skipped ratios, or actual outcome tracking (did the outreach succeed)?
   - Recommendation: Merge VIEW-03 into the Preferences page as a new "Feedback History" section. Avoid a fourth nav tab to keep the UI clean. Show the last 20 `user_feedback` rows with `feedback_type` and rating, plus the `outreach_queue` approved/skipped/sent counts as a summary block.

2. **Should dashboard_service.py be updated to include funnel stage counts in the snapshot?**
   - What we know: `data_quality` in the snapshot has `total_contacts` and `scored` but not `reviewed`, `reached_out`, or `connected`.
   - What's unclear: Whether to compute these counts in the Python pipeline or in JS via live Supabase queries.
   - Recommendation: Add `reviewed`, `reached_out`, and `connected` counts to `compute_data_quality()` in `dashboard_service.py`. This keeps the PWA's Supabase query count low and the snapshot self-contained. Live count queries are a fine fallback if the snapshot is stale.

3. **What is "connected" in the funnel context?**
   - What we know: `outreach_queue.status` tops out at `"sent"`. `outreach_log.outcome = 'replied'` is the reply tracking mechanism.
   - What's unclear: Are any `outreach_log` rows populated yet?
   - Recommendation: Define "Connected" = count of `outreach_log` rows with `outcome = 'replied'`. Show 0 if empty. This is accurate and honest.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-mock (already installed in `.venv`) |
| Config file | `pyproject.toml` or none (pytest discovers `tests/`) |
| Quick run command | `source .venv/bin/activate && pytest tests/test_phase3_pwa.py -x -q` |
| Full suite command | `source .venv/bin/activate && pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROFILE-01 | Score breakdown with 5 dimensions renders in contact page HTML | unit (JS logic via Python-parsed JSON round-trip) | `pytest tests/test_phase3_pwa.py::test_score_reasoning_has_all_dimensions -x` | Wave 0 |
| PROFILE-02 | Professional context section shows role, company, industry, career trajectory | unit | `pytest tests/test_phase3_pwa.py::test_professional_context_fields -x` | Wave 0 |
| PROFILE-03 | Connection strength section shows message_count, last_message_date, conversation_status | unit | `pytest tests/test_phase3_pwa.py::test_connection_strength_fields -x` | Wave 0 |
| PROFILE-04 | Enrichment section shows location, headline, email status, LinkedIn URL | unit | `pytest tests/test_phase3_pwa.py::test_enrichment_fields -x` | Wave 0 |
| VIEW-01 | Dashboard snapshot data_quality contains reviewed, reached_out, connected counts | unit | `pytest tests/test_phase3_pwa.py::test_funnel_counts_in_snapshot -x` | Wave 0 |
| VIEW-02 | Enrichment status section distinguishes full-data contacts vs. need-enrichment | unit | `pytest tests/test_phase3_pwa.py::test_enrichment_status_counts -x` | Wave 0 |
| VIEW-03 | Feedback history shows last 20 user_feedback rows | unit | `pytest tests/test_phase3_pwa.py::test_feedback_history_rows -x` | Wave 0 |
| VIEW-04 | Deep link bridge converts ?view=contact&id=X to #/contact/{id} (already in app.js) | smoke (manual) | Verify in browser: load `?view=contact&id=test-id` → URL bar shows `#/contact/test-id` | manual-only |

**Note on JS testing:** The PWA is vanilla JS with no module system and no Node.js test runner. Unit tests for contact.js rendering logic must be written as Python tests that verify the **data layer** (e.g., `compute_data_quality()` returns the right keys, `score_reasoning` JSON round-trips correctly). The rendering HTML itself is verified by inspection in the human-verify step, or via browser automation (out of scope for this phase). The pattern from Phase 2 is to test the Python-side data generation and verify PWA HTML by manual browser review.

### Sampling Rate
- **Per task commit:** `source .venv/bin/activate && pytest tests/test_phase3_pwa.py -x -q`
- **Per wave merge:** `source .venv/bin/activate && pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase3_pwa.py` — covers PROFILE-01 through VIEW-03 (7 tests)
- [ ] `src/services/dashboard_service.py` update — `compute_data_quality()` must include `reviewed`, `reached_out`, `connected` keys

*(Existing conftest.py and test infrastructure are sufficient; no new fixtures needed.)*

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `pwa/js/contact.js` — score_reasoning parse logic, existing section structure
- Direct code inspection of `pwa/js/dashboard.js` — snapshot fetch pattern, existing section list
- Direct code inspection of `src/services/dashboard_service.py` — snapshot data structure
- Direct code inspection of `src/database/models.py` — all Connection fields available via PostgREST
- Direct code inspection of `pwa/js/app.js` — deep link bridge already implemented

### Secondary (MEDIUM confidence)
- `supabase/migrations/20260305000000_pwa_overhaul.sql` — confirms Supabase table schema matches Python models
- `src/llm/scoring.py` — confirms score_reasoning JSON structure: `{dimension_scores, score, reasoning, key_factors, conversation_hooks}`
- `src/ui/views/dashboard.py` — confirms funnel stage logic (total, scored, queued, sent, replied)

### Tertiary (LOW confidence)
- None needed — all findings are from direct source code inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all existing patterns verified in source
- Architecture: HIGH — existing JS files are the implementation surface; sections are additive
- Pitfalls: HIGH — raw_enrichment nesting pitfall confirmed from scoring.py; VIEW-04 duplication risk confirmed from app.js; snapshot gap confirmed from dashboard_service.py
- Data shape: HIGH — every field verified against models.py and migration SQL

**Research date:** 2026-03-08
**Valid until:** 2026-06-08 (stable stack — vanilla JS, Supabase JS v2)
