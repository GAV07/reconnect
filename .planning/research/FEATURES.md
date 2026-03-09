# Feature Research

**Domain:** Personal networking CRM — v1.1 Network Intelligence milestone
**Researched:** 2026-03-09
**Confidence:** HIGH (all findings grounded in direct codebase analysis; no guessing)

---

## Context: What Already Exists (Not In Scope)

These features are fully built and working in v1.0. This document focuses only on the
new v1.1 capabilities:

- Daily email digest with tap-to-act cards (Yes/Skip/Snooze)
- PWA contact profiles with 5-dimension AI scoring rationale (bars rendered in `contact.js`)
- Pipeline funnel view, enrichment status, feedback history in dashboard
- Network health score (single number, 4 component sub-metrics)
- Outreach queue with Reach Out / Skip / Snooze actions
- Bidirectional sync, action tokens, deep links from email to PWA
- Gmail App Password email sending (smtplib)
- Streamlit admin UI (`src/ui/` — 7 views)

---

## Table Stakes

Features that feel missing or broken in the existing product without them.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Score breakdown showing non-zero values | Profile already has dimension bars UI; they silently show 0 for contacts scored before `dimension_scores` field was added | LOW | Bug fix — `contact.js` parser is correct; affected contacts need re-scoring |
| Queue sort by score | Queue already defaults to score sort; users expect to toggle it and see options | LOW | Query param change; UI control |
| Queue filter by status | Natural triage flow — "show me what I already approved" | LOW | Status enum: pending_review / approved / sent / skipped |
| Health score breakdown with action strings | Score is 0-100; users want to know what's low and what to do about it | LOW | Data already in `compute_network_health()` — needs action text |
| Gmail OAuth replacing App Password | App Passwords are disallowed on some Google Workspace accounts; OAuth is the correct long-term path | MEDIUM | `GmailCredentials` model already exists with the right fields |

---

## Differentiators

Features that add intelligence beyond basic CRM capabilities.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dashboard demographic charts | Answers "am I networking in the right circles?" — industry distribution, role mix, score tier breakdown | MEDIUM | Data requires pipeline aggregation step; PWA needs Chart.js |
| AI contact search ("Who knows about X?") | Turns the network into a queryable asset — instant semantic search across all enriched contacts | HIGH | Core LLM logic built in `opportunity_match.py`; needs Edge Function + PWA route |
| Health score actionable insights | Transforms a number into a to-do list — "enrich 12 more contacts to reach 70" | LOW | Logic lives in `dashboard_service.py`; needs action-text generation layer |
| Queue filter by industry | Cross-filters the queue to focus — "show me only fintech contacts today" | MEDIUM | Industry in JSON, not indexed column; client-side filter for v1.1 |
| CLI commands replacing Streamlit | `reconnect pipeline run`, `queue reset`, `queue stats` — removes 800+ LOC Streamlit dependency | MEDIUM | Thin wrappers around existing functions; Click framework |

---

## Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time demographic charts on-demand | Feels more live | Querying 1000+ contacts with JSON extraction on every PWA load is slow; `raw_enrichment` is a JSON blob with no indexed `company_industry` column | Compute charts in pipeline snapshot step; serve pre-computed arrays from `dashboard_snapshots` |
| Semantic vector search with embeddings | "Proper" AI search would use pgvector | Overkill for <10K contacts on a personal tool; adds embedding cost per contact update; requires pgvector migration | Keep batch LLM matching from `opportunity_match.py`; it already works and is cheap |
| OAuth for PWA AI search | Search is user-facing, so it "should" use user auth | Single-user anon-key tool; adding OAuth to PWA adds login friction with zero security benefit | Route AI search through Edge Function using anon key + rate limiting |
| Score weight tuning UI in PWA | Power users want to tune dimension weights | `UserPreference` scoring weights already work via feedback processor; a weight editor in PWA adds complex interaction for a rarely-used feature | CLI command to set weights; preferences UI can come in v1.2+ |
| Geographic distribution chart | Pretty visualization | Limited location coverage (many contacts have no location); chart is mostly empty; low signal | Defer to v1.2; threshold: only build if >60% of contacts have location data |
| Streamlit preservation as "fallback" | Keep it around just in case | Streamlit crashes on import (`review.py` references removed OAuth functions); maintaining both Streamlit and CLI doubles the surface area | Delete `src/ui/` cleanly after all operations have CLI equivalents |

---

## Feature Dependencies

```
[Score breakdown bug fix]
    └──unblocks──> [Profile is trustworthy]
    └──unblocks──> [Health score insights reference same dimensions]

[Demographic charts in pipeline snapshot]
    └──required by──> [PWA demographic charts]
    └──builds on──> [compute_dashboard_snapshot() in dashboard_service.py]

[CLI pipeline commands]
    └──required by──> [Streamlit removal]
    └──depends on──> [All pipeline operations work without UI]

[AI contact search Edge Function]
    └──required by──> [PWA search route]
    └──reuses──> [opportunity_match.py LLM pattern (re-implemented in Deno)]

[Gmail OAuth CLI flow]
    └──independent──> (infra fix; no PWA changes needed)
    └──writes to──> [GmailCredentials table (already modeled)]
```

### Dependency Notes

- **Score breakdown fix unblocks profile trust:** The dimension bars are the primary transparency feature. Showing 0/25 everywhere destroys trust in the scoring system. Fix must come first.
- **Demographic charts require pipeline step:** Aggregating `raw_enrichment.company_industry` across 1000+ contacts cannot happen at PWA load time. The `compute_dashboard_snapshot()` step must do this aggregation and store it in the snapshot JSON.
- **CLI before Streamlit removal:** Streamlit is the only way to run the pipeline manually and reset the queue. CLI commands must cover `pipeline run`, `queue reset`, and `queue stats` before Streamlit can be deleted.
- **AI search is a frontend + glue task:** `opportunity_match.py` has the LLM logic. The remaining work is: (1) TypeScript Edge Function that re-implements the batch pattern, (2) PWA route with search UI. The AI part is done.

---

## Feature-by-Feature UX Specification

### 1. Dashboard Health Score Breakdown with Actionable Insights

**Current state:** PWA shows a single `healthScore` number (0-100) and 4 metric cards (Data Quality %, Enriched %, Email Coverage %, Activity score). No explanation of what's low or how to improve it.

**Expected UX (v1.1):**
- Each of the 4 component metric cards renders a color-coded status:
  - Green (above threshold), Yellow (approaching threshold), Red (below threshold)
- Below each card, when below threshold: one-line action string
  - Data Quality < 60%: "Enrich more contacts for richer scoring context"
  - Enriched % < 50%: "Run pipeline — N contacts are ready to enrich"
  - Email Coverage < 40%: "N scored contacts missing email — use Hunter lookup"
  - Activity score < 40: "Send more outreach — score improves with sent messages"
- No new API calls needed — all data is in the existing snapshot JSON

**Minimum viable version:** Add `action_hint` strings to each component in `compute_network_health()` return value; render them conditionally in `dashboard.js` metric cards.

**Complexity:** LOW — backend has the numbers; frontend needs conditional text rendering.

---

### 2. Demographic Charts (Industry Distribution, Role Mix, Score Tier)

**Current state:** Streamlit dashboard has `_render_network_composition()` (companies + role keywords via Plotly). PWA dashboard has no charts.

**Expected UX (v1.1):**
- **Score tier distribution:** Horizontal bar chart: Low (0-39), Medium (40-69), High (70-100). Shows what proportion of the network is in each tier.
- **Industry distribution:** Horizontal bar chart, top 8-10 industries by contact count. Pulls from `raw_enrichment.company_industry` (handles both `company_industry` and `companyIndustry` key variants).
- **Role/seniority mix:** Bar chart bucketed by keyword: Founder/CEO/CTO, VP/Director, Manager, Engineer/Developer, Analyst/Researcher, Other. Extracted from `current_role` text.

**Data source:** All three computed in a new `compute_network_demographics()` pipeline step, stored in `snapshot_data.demographics`. PWA reads pre-computed arrays — no direct DB queries at render time.

**Chart library:** Chart.js loaded from CDN (`cdn.jsdelivr.net/npm/chart.js`). 60KB gzipped, vanilla JS compatible, good mobile rendering. No build step needed.

**Minimum viable version:** Score tier distribution only (uses `reconnect_score` column — no JSON extraction needed, no new pipeline step required beyond a count query). Industry and role charts come after the aggregation pipeline step is built.

**Complexity:** MEDIUM — pipeline aggregation step + Chart.js integration. Score tier is LOW.

---

### 3. AI Contact Search ("Who in my network knows about X?")

**Current state:** `opportunity_match.py` is fully built — batches contacts in groups of 50, calls gpt-4o-mini with a structured prompt, returns ranked matches with relevance score and reason. Exposed only in Streamlit "Ask My Network" — not in the PWA.

**Expected UX (v1.1):**
- PWA has a new "Search" route (`#/search`) accessible from the bottom nav
- Text input: placeholder "Who can help with fundraising? Who works in healthcare AI?"
- Submit button triggers Edge Function call to `/functions/v1/search` (new function)
- Results render as a ranked list: name, role @ company, relevance score badge, one-sentence reason
- Each result links to `#/contact/:id`
- Loading state: spinner with "Searching your network..."
- Empty state: "No strong matches found. Try a different query."
- Error state: "Search unavailable. Check your connection."

**Edge Function design:** New `supabase/functions/search/index.ts`. Pattern:
  1. Accept POST `{ query: string }`
  2. Query Supabase for contacts where `current_role IS NOT NULL OR current_company IS NOT NULL`
  3. Batch into groups of 50
  4. For each batch: call OpenAI with the same structured prompt from `opportunity_match.py` (re-implemented in TypeScript)
  5. Collect results, sort by score, return top 10
  6. Uses `Deno.env.get('OPENAI_API_KEY')` (already set in Supabase secrets)

**Single-batch minimum viable version:** Query first 200 contacts with role data, use up to 4 batches of 50. Fast for a personal tool. Full pagination of all contacts deferred.

**Rate limiting:** Single-user tool — no abuse concern. Add empty query check (< 3 chars → 400).

**Complexity:** HIGH — new Edge Function, new PWA route, TypeScript re-implementation of LLM batch pattern.

---

### 4. Queue Filtering and Sorting

**Current state:** `queue.js` fetches all `pending_review` items, sorted by `priority_score DESC`. No user controls.

**Expected UX (v1.1):**
- **Sort controls (pills or select):** Score High→Low (default), Score Low→High, Name A-Z
- **Status filter:** Pending Review (default) | Approved | Sent | All
- **Score range filter:** All (default) | High 70+ | Medium 40-69 | Low <40
- **Industry filter:** "All Industries" | dropdown populated from unique industries in fetched items
- Filter bar collapses on mobile behind a "Filter" toggle button
- Count updates: "Showing 3 of 12 contacts"
- Filters persist for session (module-level JS variable, not localStorage — no need to persist across sessions)

**Implementation approach:**
- Sort and status filter: Supabase query params (`.order()`, `.eq('status', ...)`)
- Score range filter: Supabase `.gte()` / `.lte()` on `priority_score`
- Industry filter: Industry lives in `connections.raw_enrichment` JSON — not queryable via PostgREST on a JSON subfield. **Use client-side filter** for v1.1. Fetch all queue items with their connection data, filter in JS. For a personal tool with <200 queue items this is fast enough. Adding a top-level `industry` column to `connections` is the right long-term fix, deferred to v1.2.

**Minimum viable version:** Sort toggle (already default score sort) + Status tabs (Pending / Approved / Sent). Score range and industry filters are additive.

**Complexity:** LOW for sort + status; MEDIUM for industry (client-side with JSON traversal).

---

### 5. Gmail OAuth Flow for Python Email Sending

**Current state:** `gmail.py` uses App Password + smtplib. `GmailCredentials` DB table already exists with the right shape (`access_token`, `refresh_token`, `expiry`, `client_id`, `client_secret`, `scopes`). Config already has `gmail_client_id` and `gmail_client_secret` fields in `Settings`.

**Expected UX (v1.1):**
- `reconnect gmail auth` CLI command
  - Opens browser to Google OAuth consent URL
  - Starts local HTTP server on `localhost:PORT` to catch redirect
  - Exchanges authorization code for tokens
  - Saves tokens to `gmail_credentials` table (row id=1)
  - Prints: "Gmail authorized as user@gmail.com. Token expires 2026-04-09."
- `reconnect gmail status` CLI command
  - Shows: email address, token expiry, last used
  - Shows: "Configured via App Password" if no OAuth tokens
- **Email sending logic** (in `gmail.py`):
  - Check `gmail_credentials` table for valid access token
  - If token expired: refresh using `google-auth` library, save new token
  - If OAuth configured: use Gmail API (via `google-api-python-client`)
  - If no OAuth: fall back to App Password (existing smtplib path — no breakage)
- Required scopes: `https://www.googleapis.com/auth/gmail.send` (send-only, minimal)
- GCP setup: User needs a GCP project, Gmail API enabled, OAuth 2.0 credentials (Desktop App type). `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET` go in `.env`

**Libraries:** `google-auth-oauthlib`, `google-api-python-client` — standard Google Python client stack. Both handle token refresh automatically.

**Minimum viable version:** `reconnect gmail auth` + token storage + sending via Gmail API. App Password fallback preserved. No token refresh UI (re-run `reconnect gmail auth` if expired).

**Complexity:** MEDIUM — standard OAuth flow pattern; GCP setup documentation needed.

---

### 6. CLI Commands Replacing Streamlit Admin Controls

**Current state:** Streamlit (`src/ui/`) provides 7 functional areas. The PWA now covers contacts, queue, dashboard, and AI search. What CLI must cover: pipeline operations, diagnostics, and user profile management.

**Target Streamlit operations to migrate:**

| Streamlit Operation | CLI Equivalent |
|---------------------|---------------|
| Run daily pipeline | `reconnect pipeline run` |
| Run with LinkedIn import | `reconnect pipeline run --import ~/file.zip` |
| Show queue stats | `reconnect queue stats` |
| Reset stale queue | `reconnect queue reset` |
| Re-score old contacts | `reconnect contacts score --rubric-only` |
| Re-score all enriched | `reconnect contacts score --all` |
| Find emails (Hunter.io) | `reconnect contacts find-emails --limit N` |
| Show user profile | `reconnect profile show` |
| Set profile goals | `reconnect profile set-goals` (interactive) |
| Gmail auth | `reconnect gmail auth` |
| Gmail status | `reconnect gmail status` |

**Operations that stay in PWA and do not need CLI:**
- Contacts list browsing / search
- Queue review (Reach Out / Skip / Snooze)
- Dashboard metrics
- AI search
- Contact profile view

**Framework:** Click (already a transitive dependency; installable cleanly). Entry point: `reconnect/cli.py` with a `reconnect` command group. Install via `pip install -e .` with a `[project.scripts]` entry in `pyproject.toml` or `setup.py`.

**Non-interactive pattern:** All commands print structured output (table or JSON via `--json` flag). Only `profile set-goals` and `gmail auth` require interactive input.

**Minimum viable version:** `pipeline run`, `pipeline status`, `queue stats`, `queue reset`. These are the operations that are currently only accessible via Streamlit and block daily operation without it.

**Complexity:** MEDIUM — thin wrappers around existing functions; Click setup is boilerplate.

---

## MVP Definition

### Launch With (v1.1 — required for milestone coherence)

- [ ] Score breakdown bug fix — profile dimension bars must show real values; unblocks trust in scoring
- [ ] Health score breakdown with action strings — makes dashboard useful, not decorative
- [ ] Queue sort + status filter — minimum queue control; users need to see what they've approved
- [ ] CLI `pipeline run` + `queue reset` + `queue stats` — required before Streamlit can be removed
- [ ] Streamlit removal — removes broken `review.py`, reduces maintenance surface
- [ ] Gmail OAuth CLI flow — replaces App Password; `GmailCredentials` model is already ready

### Add After Core (v1.1 complete, same milestone)

- [ ] Demographic charts — score tier distribution first (low effort); industry/role after aggregation pipeline step
- [ ] AI contact search — PWA route + Edge Function; high value but highest effort
- [ ] Queue industry filter — client-side filter; additive on top of status filter

### Future Consideration (v1.2+)

- [ ] Score weight tuning UI in PWA — `UserPreference` weights work; preferences UI is a v1.2 concern
- [ ] `industry` column on `connections` table — clean solution to industry filtering; requires migration
- [ ] Pipeline controls in PWA (run pipeline from PWA) — per PROJECT.md: CLI sufficient; PWA admin panel deferred
- [ ] Geographic distribution chart — blocked by low location data coverage (<40% of contacts)
- [ ] Contact import via CLI — rare operation; low priority

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Score breakdown bug fix | HIGH | LOW | P1 |
| Health score actionable insights | HIGH | LOW | P1 |
| Queue sort + status filter | HIGH | LOW | P1 |
| CLI pipeline + queue commands | HIGH | MEDIUM | P1 |
| Gmail OAuth | MEDIUM | MEDIUM | P1 |
| Streamlit removal | LOW (infra) | MEDIUM | P1 (enables CLI) |
| Score tier distribution chart | MEDIUM | LOW | P2 |
| Industry + role demographic charts | MEDIUM | MEDIUM | P2 |
| AI contact search (PWA + Edge Fn) | HIGH | HIGH | P2 |
| Queue industry filter | MEDIUM | MEDIUM | P2 |
| Score weight tuning UI in PWA | LOW | HIGH | P3 |
| Geographic distribution chart | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v1.1 — removes debt, unblocks daily workflow, enables Streamlit removal
- P2: Should have — adds intelligence layer that differentiates the tool
- P3: Deferred — value exists but implementation cost doesn't justify v1.1 inclusion

---

## Implementation Notes

### Score Breakdown Bug Root Cause
Contacts scored before the rubric system was added (pre `dimension_scores` field in `score_reasoning` JSON) have `score_reasoning` stored without the `dimension_scores` key. `contact.js` correctly falls back to `{}` so bars show 0. Fix path: CLI `reconnect contacts score --rubric-only` re-scores only contacts where `score_reasoning` JSON lacks `dimension_scores`. The `_rescore_contacts()` function in `src/ui/app.py` already implements exactly this logic — extract it to a service function.

### Demographic Chart Data Aggregation
`compute_dashboard_snapshot()` needs a new `compute_network_demographics()` helper. Industry aggregation in SQLite uses `json_extract()`:
```sql
SELECT json_extract(raw_enrichment, '$.data.company_industry') as industry, COUNT(*) as cnt
FROM connections WHERE raw_enrichment IS NOT NULL
GROUP BY industry ORDER BY cnt DESC LIMIT 10
```
Handle both `$.data.company_industry` and `$.company_industry` key paths (old vs new enrichment format). Store result as `snapshot_data.demographics.industries = [{label, count}, ...]`.

### AI Search Edge Function Pattern
New `supabase/functions/search/index.ts`. Query: `db.from('connections').select('id, name, current_role, current_company').not('current_role', 'is', null)`. Batch 50 at a time, same JSON prompt structure as `opportunity_match.py`. Use `Deno.env.get('OPENAI_API_KEY')` (already set). Return `{results: [{id, name, role, company, score, reason}]}`.

### Gmail Token Refresh Pattern
Use `google.oauth2.credentials.Credentials` with `token_uri`, `client_id`, `client_secret`, `refresh_token`. Refresh check: `if credentials.expiry < datetime.utcnow() + timedelta(minutes=5): credentials.refresh(Request())`. After refresh, save new `access_token` and `expiry` back to `GmailCredentials` table. This is standard `google-auth` library behavior.

### Streamlit Removal Checklist
Before deleting `src/ui/`:
1. All pipeline operations have CLI equivalents
2. No module outside `src/ui/` imports from `src/ui/`
3. `requirements.txt` no longer lists `streamlit` or `plotly`
4. `src/config.py` `get_streamlit_secrets()` function removed (it imports streamlit)

---

## Sources

- Codebase direct analysis (HIGH confidence): `src/services/dashboard_service.py`, `src/llm/opportunity_match.py`, `src/llm/scoring.py`, `src/pipeline/queue_generator.py`, `pwa/js/queue.js`, `pwa/js/dashboard.js`, `pwa/js/contact.js`, `src/integrations/gmail.py`, `src/database/models.py`, `src/config.py`, `src/ui/app.py`
- `.planning/PROJECT.md` — constraints, out-of-scope list, key decisions (HIGH confidence)

---

*Feature research for: Reconnect v1.1 Network Intelligence milestone*
*Researched: 2026-03-09*
