# Architecture Research

**Domain:** Personal networking CRM — v1.1 Network Intelligence milestone
**Researched:** 2026-03-09
**Confidence:** HIGH (all findings from direct source-code inspection, no speculation)

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     LOCAL MACHINE (macOS)                        │
├──────────────────────────────────────────────────────────────────┤
│  LaunchAgent @ 8AM                                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              daily_pipeline.py (10 steps)               │    │
│  │  import → prescore → enrich → score → queue →           │    │
│  │  data_completeness → feedback → enrichment_plan →       │    │
│  │  dashboard_snapshot → sync → email_digest               │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │ push/pull                           │
│  ┌────────────┐            │           ┌──────────────────────┐ │
│  │ SQLite DB  │◄───────────┘           │  src/integrations/   │ │
│  │ (primary)  │                        │  gmail.py (smtplib)  │ │
│  └────────────┘                        └──────────────────────┘ │
│                                                                  │
│  CLI (new — replaces Streamlit pipeline controls)                │
│  src/cli.py: pipeline, sync, import, rescore, reset-queue        │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ push.py / pull.py
                                   │ (SQLAlchemy to postgres)
┌──────────────────────────────────▼───────────────────────────────┐
│                        SUPABASE (cloud)                          │
├──────────────────────────────────────────────────────────────────┤
│  PostgreSQL (11 tables)          Edge Functions (Deno)           │
│  ┌──────────────────────┐      ┌────────────────────────────┐   │
│  │ connections          │      │ action (GET/POST)           │   │
│  │ outreach_queue       │      │ draft  (POST → OpenAI)      │   │
│  │ dashboard_snapshots  │      │ feedback (POST)             │   │
│  │ action_tokens        │      │ search  (POST → OpenAI) NEW │   │
│  │ user_feedback        │      └────────────────────────────┘   │
│  │ user_preferences     │                                        │
│  │ gmail_credentials    │      PostgREST (auto REST API)         │
│  │ user_profile         │      ┌────────────────────────────┐   │
│  │ + 3 more tables      │      │ GET /connections            │   │
│  └──────────────────────┘      │ GET /outreach_queue         │   │
│                                │ GET /dashboard_snapshots    │   │
│                                │ PATCH /outreach_queue       │   │
│                                │ PATCH /connections          │   │
│                                └────────────────────────────┘   │
│  Realtime subscriptions (postgres_changes on outreach_queue)     │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ @supabase/supabase-js
┌──────────────────────────────────▼───────────────────────────────┐
│                  PWA (Vanilla JS on Netlify)                     │
├──────────────────────────────────────────────────────────────────┤
│  app.js (hash router + supabase init)                            │
│  queue.js     — PostgREST direct, PATCH for actions, Realtime    │
│  contact.js   — PostgREST direct, calls /functions/v1/draft      │
│  dashboard.js — reads dashboard_snapshots JSON blob              │
│  preferences.js — PostgREST PATCH on user_preferences            │
│  search.js    (NEW) — calls /functions/v1/search Edge Function   │
│  push.js / offline.js / service-worker.js                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `daily_pipeline.py` | Orchestrates all 10 pipeline steps | SQLite, all src/* modules |
| `src/services/dashboard_service.py` | Computes snapshot blob pushed to Supabase | SQLite (read) |
| `src/sync/push.py` | SQLite → Supabase PostgreSQL (delta push) | Both DBs via SQLAlchemy |
| `src/sync/pull.py` | Supabase → SQLite (queue actions, feedback) | Both DBs via SQLAlchemy |
| `src/llm/scoring.py` | LLM scoring per contact, 5-dimension rubric | SQLite, OpenAI API |
| `src/llm/opportunity_match.py` | LLM contact search (batch, text → matches) | SQLite, OpenAI API |
| `src/integrations/gmail.py` | Sends email digest via smtplib App Password | SMTP |
| `supabase/functions/draft/` | On-demand draft via OpenAI (edge) | Supabase PostgreSQL, OpenAI |
| `supabase/functions/action/` | Processes email action tokens (GET confirm, POST execute) | Supabase PostgreSQL |
| `supabase/functions/feedback/` | Records user_priority and feedback signals | Supabase PostgreSQL |
| `pwa/js/dashboard.js` | Renders DashboardSnapshot blob — no live queries | Supabase PostgREST |
| `pwa/js/queue.js` | Fetches queue + PATCH actions, Realtime subscription | Supabase PostgREST + Realtime |
| `pwa/js/contact.js` | Fetches contact detail, calls /functions/v1/draft | Supabase PostgREST + Edge Fn |

---

## Feature Integration Analysis

### 1. Dashboard Charts (industry distribution, role mix, score tier)

**Current state:** `pwa/js/dashboard.js` reads a single `dashboard_snapshots` row from Supabase (JSON blob). The snapshot contains `network_health`, `opportunity_alerts`, `data_quality`, `feedback_insights`. The PWA renders counts and bars from this blob — no live aggregation queries. Snapshot is computed by `src/services/dashboard_service.py:compute_dashboard_snapshot()` at pipeline step 10.

**Integration approach:** Extend the snapshot blob. Do not add live PostgREST aggregation queries to the PWA.

**New data to add to snapshot in `dashboard_service.py`:**
```python
# In compute_dashboard_snapshot(), add:
snapshot["demographics"] = compute_demographics()
snapshot["health_insights"] = compute_health_insights(health, quality)

def compute_demographics() -> dict:
    # industry_distribution: group connections by
    #   raw_enrichment->>'company_industry' (postgres JSON operator)
    #   or fall back to a Python-side groupby on fetched rows
    # role_mix: bucket current_role into keywords
    #   (founder/ceo/cto/vp/director/manager/engineer/designer/analyst)
    # score_tier_distribution: bucket reconnect_score into 0-20/20-40/40-60/60-80/80-100
    # top_companies: top 10 current_company by count
    ...

def compute_health_insights(health: dict, quality: dict) -> list[dict]:
    # Returns actionable "why is this score low?" messages
    insights = []
    if quality["enriched_pct"] < 30:
        insights.append({"type": "warning", "message": "Only X% enriched — run pipeline with enrichment to improve score"})
    if health["components"]["email_coverage_pct"] < 40:
        insights.append({"type": "info", "message": "X contacts missing email — run Find Emails"})
    ...
```

**PWA rendering in `dashboard.js`:** Read `snapshot.demographics` and render:
- Score tier distribution: CSS progress-bar style (same pattern as existing funnel bars — `buildFunnelSection()`)
- Industry distribution: horizontal bar list with percentages
- Role mix: keyword count list
- Health insights: alert cards above the health score

No external chart library required. The existing funnel bar pattern in `dashboard.js` is sufficient for all these visualizations.

**What changes:**
- `src/services/dashboard_service.py` — add `compute_demographics()`, `compute_health_insights()`, include in snapshot dict
- `pwa/js/dashboard.js` — add rendering functions for demographics sections and insight cards
- No new API endpoints, no new DB tables, no migration needed

**Confidence:** HIGH — snapshot pattern is established and syncs to Supabase via `push.py`.

---

### 2. AI Contact Search ("Who in my network knows about X?")

**Current state:** `src/llm/opportunity_match.py:find_matches()` already implements this — batches contacts to gpt-4o-mini, filters by relevance score. It runs locally against SQLite. Streamlit's "Ask My Network" page wraps it. This logic needs to move to the PWA as an Edge Function.

**Integration approach:** New Edge Function `search`, NOT pgvector.

**Why not pgvector:** Enabling pgvector requires extension enable + embedding generation pipeline + sync column + ongoing cost. At hundreds to low thousands of contacts, the existing batch LLM approach (50 contacts/call, gpt-4o-mini) is simpler, cheaper, and already proven. Revisit at 5k+ contacts where batching latency becomes unacceptable.

**New Edge Function `supabase/functions/search/index.ts`:**
```typescript
// POST { query: "Who knows about fundraising?" }
// 1. Fetch all connections with name + role or company set
//    SELECT id, name, current_role, current_company, location FROM connections
//    WHERE current_role IS NOT NULL OR current_company IS NOT NULL
// 2. Batch into groups of 50
// 3. For each batch: call OpenAI gpt-4o-mini with prompt from _build_batch_prompt()
// 4. Collect matches where score >= 60, sort by score desc
// Returns: { matches: [{ connection_id, name, score, reason }] }
```

Port `_build_batch_prompt()` and the OpenAI call pattern from `opportunity_match.py` to TypeScript. Mirrors the `draft` Edge Function structure exactly (uses service role key to read all DB tables, calls OpenAI, returns JSON).

**PWA integration:** New `pwa/js/search.js` module. Add `#/search` route to `app.js` and a nav item. The search page is a text input + button that calls the Edge Function and renders result cards linking to `#/contact/{id}`.

**What changes:**
- NEW `supabase/functions/search/index.ts` — port `opportunity_match.py` logic to TypeScript
- NEW `pwa/js/search.js` — search UI component, calls Edge Function
- `pwa/js/app.js` — add `'/search': { module: 'search', title: 'Search' }` route
- `pwa/index.html` — add `<script src="js/search.js">` and nav item
- No DB changes, no migration needed

**Confidence:** HIGH — mirrors existing `draft` Edge Function pattern. OpenAI key already set as Supabase secret.

---

### 3. Gmail OAuth (replace App Password + smtplib)

**Current state:** `src/integrations/gmail.py` uses `smtplib.SMTP_SSL` with a 16-char App Password. The `GmailCredentials` table (id=1 singleton) already has `access_token`, `refresh_token`, `client_id`, `client_secret`, `scopes`, `expiry` columns — the schema was designed for OAuth from the start.

**Integration approach:** Add OAuth send path alongside the existing App Password path. Keep App Password as fallback — zero regression risk.

**OAuth setup flow (one-time, developer runs manually):**
1. GCP project → OAuth credentials → `client_id` + `client_secret` → save to `.env` as `GMAIL_CLIENT_ID` + `GMAIL_CLIENT_SECRET`
2. Run: `python -m src.cli auth gmail`
   - Builds auth URL, opens browser, listens on `localhost:8080` for callback
   - Exchanges code for tokens via `google-auth-oauthlib`
   - Saves `access_token`, `refresh_token`, `expiry` to `GmailCredentials` row id=1 in SQLite

**Pipeline send flow:**
```python
# src/integrations/gmail.py — updated is_gmail_configured()
def is_gmail_configured() -> bool:
    s = get_settings()
    if s.gmail_app_password and s.gmail_sender_email:
        return True  # App Password path (existing)
    # Check OAuth path
    with get_session() as session:
        creds = session.get(GmailCredentials, 1)
        return bool(creds and creds.refresh_token)

# New: send_html_email_oauth()
def send_html_email_oauth(to, subject, html_body, text_body=None):
    # Load from GmailCredentials row
    # Build google.oauth2.credentials.Credentials object
    # Auto-refresh if expiry < now + 5min (credentials.refresh(Request()))
    # Save refreshed tokens back to GmailCredentials table
    # Call Gmail API: service.users().messages().send()
```

**Token storage security note:** `push.py` currently syncs the `gmail_credentials` table to Supabase. This must be removed — OAuth refresh tokens in a shared DB are a security risk. The tokens are only needed by the local pipeline; there is no cloud use case.

**New dependencies:**
```
google-auth>=2.0
google-auth-oauthlib>=1.0
google-api-python-client>=2.0
```

**What changes:**
- `src/integrations/gmail.py` — add `send_html_email_oauth()`, update `is_gmail_configured()` to check both paths, add token refresh-and-save logic
- `src/config.py` — add `gmail_client_id: str = ""` and `gmail_client_secret: str = ""`
- NEW `src/cli/auth.py` — OAuth dance (build URL, run local callback server, save tokens)
- `src/sync/push.py` — remove `gmail_credentials` from sync payload (security fix)
- `.env` — add `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET` when configuring

**Confidence:** HIGH — `GmailCredentials` table already designed for this. `google-auth` library is the standard Python OAuth2 approach.

---

### 4. Queue Filtering/Sorting

**Current state:** `pwa/js/queue.js` fetches `outreach_queue` with a hardcoded query:
```javascript
.from('outreach_queue')
.select('*, connections(*)')
.eq('status', 'pending_review')
.order('priority_score', { ascending: false })
```
No filtering UI exists. The `connections` table has `current_company`, `current_role`, and `reconnect_score` indexed.

**Integration approach:** PostgREST query params for filtering; lightweight client-side sort as fallback.

**Specific PostgREST patterns:**

Score sort (via embedded resource ordering — PostgREST v11+):
```javascript
.from('outreach_queue')
.select('*, connections(*)')
.eq('status', 'pending_review')
.order('priority_score', { ascending: false })  // keep as primary
// Client-side re-sort by connections.reconnect_score if needed
```

Industry/company filter (PostgREST inner join filter):
```javascript
.from('outreach_queue')
.select('*, connections!inner(*)')
.eq('status', 'pending_review')
.ilike('connections.current_company', `%${company}%`)
```

Status filter tabs (trivial — change the `.eq('status', ...)` value):
```javascript
.eq('status', selectedStatus)  // 'pending_review' | 'approved' | 'all'
```

**Safe fallback for sort:** Since pending queue is typically 5-20 items, client-side sort after fetch is acceptable. Build a `sortItems(items, sortBy)` helper in `queue.js`.

**UI additions to `queue.js`:**
- Filter bar HTML above queue cards: company text input + sort toggle buttons + status tabs
- Filter state variables: `currentFilter = { company: '', sort: 'priority', status: 'pending_review' }`
- `renderQueue()` reads filter state and builds the PostgREST query dynamically

**What changes:**
- `pwa/js/queue.js` — add filter state, modify query builder, add filter UI rendering
- No DB changes, no migration, no new Edge Functions

**Confidence:** HIGH — PostgREST filter/sort is well-documented. Client-side fallback is trivial for small datasets.

---

### 5. CLI Commands (replace Streamlit pipeline controls)

**Current state:** Pipeline is triggered via LaunchAgent cron. Streamlit's pipeline page wraps `run_daily_pipeline()` with a UI button. Streamlit is being removed. The CLI must cover all operations currently only accessible via Streamlit.

**Integration approach:** Add `src/cli.py` entry point using `click` (recommended over `argparse` for subcommand UX).

**Commands to expose:**
```
reconnect pipeline                    # run full daily pipeline
reconnect pipeline --skip-enrich      # skip enrichment step
reconnect pipeline --skip-queue       # skip queue generation step
reconnect sync                        # push + pull only
reconnect import <path>               # import LinkedIn dump ZIP
reconnect rescore                     # re-score all enriched contacts
reconnect reset-queue                 # mark all pending/approved as skipped
reconnect auth gmail                  # OAuth dance for Gmail
reconnect status                      # show pipeline stats + queue counts
reconnect find-emails [--limit N]     # Hunter.io email batch lookup
```

**Wraps existing functions:**
- `pipeline` → `run_daily_pipeline()` from `src/pipeline/daily_pipeline.py`
- `sync` → `run_sync()` from `src/sync/runner.py`
- `import` → `import_linkedin_dump()` from `src/ingestion/linkedin_dump.py`
- `rescore` → `score_connections_batch()` from `src/llm/scoring.py`
- `reset-queue` → direct DB update (copy from Streamlit's `_reset_stale_queue()`)
- `status` → `get_pipeline_stats()` + `get_queue_stats()`

**LaunchAgent migration:** Update plist to call `python -m src.cli pipeline` (or `python /path/to/project/src/cli.py pipeline`).

**What changes:**
- NEW `src/cli.py` — `click` group with all subcommands
- NEW `src/cli/__init__.py` — empty
- NEW `src/cli/auth.py` — Gmail OAuth dance (also needed for Gmail OAuth feature)
- LaunchAgent `.plist` — update `ProgramArguments` to use CLI command
- No DB changes, no migration

**Confidence:** HIGH — all functions exist, CLI is thin wrappers.

---

### 6. Score Breakdown Bug Fix

**Current state (bugfix, not new architecture):** The PWA contact page shows 0 in all 5 scoring dimensions. The bug is in how `score_reasoning` is stored vs read.

**Root cause (confirmed from code inspection):** `src/llm/scoring.py` stores:
```python
connection.score_reasoning = json.dumps({
    "reasoning": result.reasoning,
    "key_factors": result.key_factors,
    "conversation_hooks": result.conversation_hooks,
    "dimension_scores": result.dimension_scores,
})
```

`pwa/js/contact.js` reads:
```javascript
const reasoning = JSON.parse(conn.score_reasoning);
dimensions = reasoning.dimension_scores || {};
```

This should work. The likely bug: contacts were scored BEFORE `dimension_scores` was added to the scoring rubric (old format had no `dimension_scores` key). These contacts need to be re-scored. The `_rescore_contacts(rubric_only=True)` function in `src/ui/app.py` already identifies and re-scores these.

**Fix:** Run `reconnect rescore` (new CLI command). No code change needed — just a data migration via the rescore command.

**Confidence:** HIGH — code paths confirmed by inspection.

---

### 7. Streamlit Removal Audit

**What Streamlit provides (by page) and coverage status:**

| Page | Key Functionality | PWA Coverage | CLI Coverage | Safe to Delete? |
|------|------------------|--------------|--------------|-----------------|
| Contacts (main) | Browse, search, enrich+score batch | Partial (queue only, no browse) | Partial | Not yet — contact browse not in PWA |
| Dashboard | Charts, health, alerts | YES (dashboard.js) | No | YES after PWA charts land |
| Ask My Network | AI contact search | NO → new feature | No | YES after search Edge Fn |
| Review Queue | Approve/skip | YES (queue.js) | No | YES |
| Find Contacts | Opportunity search | Same as Ask | No | YES after search Edge Fn |
| Pipeline | Run pipeline, diagnostics | No | YES (new CLI) | YES after CLI |
| Settings | User profile | YES (preferences.js) | No | YES |

**Contact import — only in Streamlit today.** Must be preserved via CLI:
- `reconnect import <path>` covers explicit path import
- LaunchAgent auto-import from `~/Downloads` is already in `daily_pipeline.py`
- Streamlit import (file upload UI) can be removed — manual imports are rare

**Safe deletion order:**
1. `src/ui/views/review.py` — crashes on import, delete first (no deps)
2. `src/ui/views/dashboard.py` — delete after PWA charts land
3. `src/ui/views/ask.py` — delete after search Edge Function ships
4. `src/ui/views/opportunities.py` — delete with ask.py
5. `src/ui/app.py` + `src/ui/components/` — delete after all views gone
6. `src/config.py` — remove `get_streamlit_secrets()` function
7. `requirements.txt` / `pyproject.toml` — remove `streamlit`, `plotly`

**Do not delete (still used):**
- `src/services/dashboard_service.py` — pipeline step 10
- `src/llm/opportunity_match.py` — keep as local Python library
- Anything in `src/pipeline/`, `src/sync/`, `src/integrations/`, `src/llm/`, `src/ingestion/`

---

## Data Flow Diagrams

### Dashboard Charts Flow

```
Pipeline Step 10
    ↓
compute_demographics()    → { industry_distribution, role_mix, score_tiers, top_companies }
compute_health_insights() → [ { type, message } ]
compute_network_health()  → { score, components }  (existing)
compute_data_quality()    → { total, scored, enriched, ... }  (existing)
    ↓ (all merged into snapshot dict)
save_dashboard_snapshot(snapshot) → DashboardSnapshot row in SQLite
    ↓
push.py → upsert DashboardSnapshot to Supabase PostgreSQL
    ↓
PWA dashboard.js
  → PostgREST: GET /dashboard_snapshots?snapshot_type=eq.daily&order=created_at.desc&limit=1
  → snapshot.demographics → build chart HTML (CSS bar pattern)
  → snapshot.health_insights → render insight cards
```

### AI Search Flow

```
User types "Who can help with fundraising?" in PWA search
    ↓
pwa/js/search.js → POST /functions/v1/search { query: "..." }
    ↓
supabase/functions/search/index.ts
  → SELECT id, name, current_role, current_company, location FROM connections
    WHERE current_role IS NOT NULL OR current_company IS NOT NULL
  → Batch 50 contacts/call
  → For each batch: POST to OpenAI gpt-4o-mini with match prompt
  → Collect matches with score >= 60
  → Sort by score desc, return top 10
    ↓
PWA renders match cards: name, role@company, score, reason
  → Each card links to #/contact/{connection_id}
```

### Gmail OAuth Flow (one-time setup)

```
Developer: python -m src.cli auth gmail
    ↓
src/cli/auth.py
  → Build OAuth URL (gmail_client_id, redirect_uri=localhost:8080, scope=gmail.send)
  → Open browser to Google consent screen
  → Listen on localhost:8080 for OAuth callback
  → Exchange auth code for tokens (google-auth-oauthlib)
  → Save to GmailCredentials row id=1 in SQLite (access_token, refresh_token, expiry)
    ↓
[Pipeline runs daily]
  → is_gmail_configured() checks: App Password OR refresh_token present
  → send_html_email_oauth(): load creds, refresh if needed, save refreshed, call Gmail API
```

### Queue Filtering Flow

```
User sets filter: company="Stripe", sort="score"
    ↓
pwa/js/queue.js
  → currentFilter = { company: 'Stripe', sort: 'score', status: 'pending_review' }
  → Build query:
      .from('outreach_queue')
      .select('*, connections!inner(*)')
      .eq('status', 'pending_review')
      .ilike('connections.current_company', '%Stripe%')
      .order('priority_score', { ascending: false })
    ↓
PostgREST returns filtered results (server-side)
  → Optional: client-side re-sort by connections.reconnect_score
    ↓
Existing queue card template renders filtered items
```

---

## Recommended Project Structure Changes

```
src/
├── cli.py                   # NEW — click entry point, subcommands
├── cli/
│   ├── __init__.py          # NEW (empty)
│   └── auth.py              # NEW — Gmail OAuth dance
├── integrations/
│   └── gmail.py             # MODIFY — add OAuth send path, update is_gmail_configured()
├── services/
│   └── dashboard_service.py # MODIFY — add compute_demographics(), compute_health_insights()
├── sync/
│   └── push.py              # MODIFY — remove gmail_credentials from sync payload
├── config.py                # MODIFY — add gmail_client_id, gmail_client_secret; remove get_streamlit_secrets()
└── ui/                      # DELETE progressively (see audit above)
    └── views/review.py      # delete first (already broken)

pwa/js/
├── app.js                   # MODIFY — add #/search route, add search nav item
├── dashboard.js             # MODIFY — add demographics chart rendering, health insight cards
├── queue.js                 # MODIFY — add filter state, modify query builder, add filter UI
└── search.js                # NEW — search UI + calls /functions/v1/search

supabase/functions/
└── search/
    └── index.ts             # NEW — AI contact search Edge Function
```

---

## Architectural Patterns in This Codebase

### Pattern 1: Snapshot-Based Dashboard (extend, do not replace)

**What:** Pipeline computes all dashboard data and stores as a JSON blob in `dashboard_snapshots`. PWA reads the latest snapshot — no live aggregation queries from the browser.

**When to use:** Any data that (a) only needs to be current as of the last pipeline run and (b) requires aggregation across many rows. Keeps PostgREST calls simple and fast.

**Extension for v1.1:** All new dashboard charts (industry distribution, role mix, score tiers, health insights) fit this pattern. Add new keys to the snapshot dict in `compute_dashboard_snapshot()`. Do not add new PostgREST queries to `dashboard.js`.

### Pattern 2: Edge Function for AI Operations (extend it)

**What:** Anything that needs OpenAI runs in a Supabase Edge Function (Deno TypeScript). The PWA calls Edge Functions directly with the anon key. Edge Functions use the service role key to access all DB tables.

**When to use:** Any AI feature the PWA needs on-demand. Draft generation already uses this pattern.

**For v1.1 AI search:** Create `supabase/functions/search/index.ts`. Mirrors the `draft` Edge Function structure: accept POST body, use service role to read DB, call OpenAI, return JSON result.

**Constraint:** Supabase free tier Edge Function execution limit is 2s CPU per invocation. For 500 contacts = 10 batches × 1 OpenAI call each. Run batches sequentially (not Promise.all) to stay under limits; total wall-clock ~5s is acceptable for a search interaction.

### Pattern 3: Direct PostgREST for CRUD (existing, works well)

**What:** Queue actions, contact updates, preference writes go directly from the PWA through PostgREST using the anon key. No Edge Function intermediary.

**When to use:** Any operation that is a direct table read or update without AI or complex business logic.

**For v1.1 queue filtering:** Add filter params to the existing PostgREST queries in `queue.js`. Do not create an Edge Function for filtering — that would be overengineered.

### Pattern 4: Sync at Pipeline Completion (do not change)

**What:** Pipeline runs locally, computes everything in SQLite, then calls `push.py` as the final step. Pull happens at the start of the next pipeline run.

**Critical invariant:** The `last_push_at` timestamp in `sync_metadata` gates delta pushes. If this timestamp gets corrupted, contacts stop syncing incrementally and a full resync is needed.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Live Aggregation Queries in the PWA Dashboard

**What people do:** Add PostgREST GROUP BY queries directly in `dashboard.js` for industry counts, score distributions, etc.

**Why wrong:** PostgREST does not support GROUP BY natively. For complex aggregations you need a Postgres function/view — additional schema complexity. It also bypasses the snapshot pattern.

**Do this instead:** Add aggregation to `compute_demographics()` in `dashboard_service.py`. Include in the snapshot. The snapshot updates every 24h which is exactly the right cadence for dashboard charts.

### Anti-Pattern 2: Syncing OAuth Tokens to Supabase

**What people do:** `push.py` currently syncs the `gmail_credentials` table to Supabase PostgreSQL.

**Why wrong:** OAuth refresh tokens in a shared database are a security liability, even with RLS. The tokens are only needed locally by the pipeline to send email — there is no cloud-side use case for them.

**Do this instead:** Remove `gmail_credentials` from the sync payload in `push.py`. If the token needs to be recoverable, it should be backed up separately (e.g., encrypted file in a safe location), not in Supabase.

### Anti-Pattern 3: pgvector for AI Search at Current Scale

**What people do:** Reach for semantic vector search when "AI search" is mentioned.

**Why wrong:** At hundreds to low thousands of contacts, embedding generation (OpenAI embeddings API, cost) + pgvector extension + sync column + ongoing maintenance adds complexity without proportional benefit. The existing batch LLM approach is simpler, cheaper, and proven.

**Do this instead:** Port `opportunity_match.py` to an Edge Function. Re-evaluate pgvector when contacts exceed 5,000+ (where 100 batches × 500ms each = 50s latency becomes unacceptable).

### Anti-Pattern 4: Porting Streamlit Session State to the CLI

**What people do:** Try to replicate Streamlit's `st.session_state` (in-memory state between button clicks) in CLI commands.

**Why wrong:** CLI commands are stateless processes. Each invocation is a new Python process. There is no in-memory continuity.

**Do this instead:** All state lives in SQLite. CLI commands read and write DB rows. No in-memory state between invocations. Progress output via `click.echo()`, not a state object.

---

## Integration Points Summary

| Feature | New Files | Modified Files | New DB/Migration? | New Edge Fn? |
|---------|-----------|----------------|-------------------|--------------|
| Dashboard charts + health insights | — | `dashboard_service.py`, `dashboard.js` | No | No |
| AI contact search | `search/index.ts`, `search.js` | `app.js`, `index.html` | No | YES |
| Gmail OAuth | `cli/auth.py` | `gmail.py`, `config.py`, `push.py` | No | No |
| Queue filtering/sorting | — | `queue.js` | No | No |
| CLI commands | `cli.py`, `cli/__init__.py`, `cli/auth.py` | LaunchAgent plist | No | No |
| Score breakdown fix | — | — (rescore command) | No | No |
| Streamlit removal | — | `config.py`, `requirements.txt` | No | No |

---

## Build Order Rationale

Features are independent of each other except:
- Streamlit Removal depends on: CLI commands + AI Search Edge Function + confirmation charts are in PWA
- Score Breakdown fix depends on: rescore CLI command existing (or running Streamlit rescore directly)

```
1. Score Breakdown Bug Fix — run rescore via Streamlit (existing) or new CLI
   No arch work, just confirm existing contact data has dimension_scores populated

2. Queue Filtering — zero dependencies, high daily-use value
   Change: queue.js only

3. Dashboard Charts + Health Insights — extends existing snapshot pattern
   Change: dashboard_service.py + dashboard.js

4. AI Contact Search Edge Function — new pattern, mirrors draft Edge Function
   Change: new search Edge Function + search.js + app.js route

5. CLI Commands — wraps existing functions, unblocks Streamlit removal
   Change: new src/cli.py + cli/auth.py scaffold

6. Gmail OAuth — independent infra, lower urgency than UX features
   Change: gmail.py + cli/auth.py (reuse from step 5) + config.py + push.py

7. Streamlit Removal — last, after steps 4 + 5 cover Streamlit's functionality
   Change: delete src/ui/ progressively, clean requirements
```

---

## Sources

- Direct code inspection: `src/services/dashboard_service.py`
- Direct code inspection: `pwa/js/dashboard.js`, `pwa/js/queue.js`, `pwa/js/contact.js`, `pwa/js/app.js`
- Direct code inspection: `src/integrations/gmail.py`, `src/database/models.py`
- Direct code inspection: `src/sync/push.py`, `src/sync/pull.py`
- Direct code inspection: `supabase/functions/draft/index.ts`, `supabase/functions/action/index.ts`
- Direct code inspection: `src/llm/opportunity_match.py`, `src/llm/scoring.py`
- Direct code inspection: `src/ui/app.py`, `src/ui/views/dashboard.py`, `src/ui/views/ask.py`
- Direct code inspection: `src/config.py`, `.planning/PROJECT.md`

All architectural claims are grounded in source-code inspection. Confidence: HIGH.

---

*Architecture research for: Reconnect v1.1 Network Intelligence*
*Researched: 2026-03-09*
