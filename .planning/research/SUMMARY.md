# Project Research Summary

**Project:** Reconnect v1.1 — Network Intelligence milestone
**Domain:** Personal networking CRM with Python pipeline + Vanilla JS PWA
**Researched:** 2026-03-09
**Confidence:** HIGH (all research grounded in direct codebase inspection and official docs)

## Executive Summary

Reconnect v1.1 is a focused incremental upgrade to a working personal networking CRM. The core system (Python pipeline, SQLite, Supabase PostgreSQL, PostgREST, Edge Functions, Vanilla JS PWA) is fully operational at v1.0. The v1.1 milestone adds network intelligence features — dashboard analytics, AI-powered contact search, Gmail OAuth, queue filtering, and a CLI to replace the broken Streamlit admin UI. Research confirms that most of the hard work is already done: the LLM scoring logic, data models, and pipeline architecture all exist. The remaining work is primarily wiring, UI additions, and one new Edge Function.

The recommended approach is strictly additive: extend existing patterns rather than replace them. All new dashboard charts should use the pre-existing snapshot-based architecture (compute in pipeline, read in PWA). AI search should port the existing `opportunity_match.py` batch LLM pattern to a new Edge Function — not adopt pgvector or RAG, which would be over-engineered for a sub-10K contact dataset. The CLI should wrap existing functions with Click; all state lives in SQLite with no new in-memory abstractions. Gmail OAuth uses the standard `google-auth-oauthlib` `InstalledAppFlow` pattern, which the `GmailCredentials` table schema was already designed to support.

The primary risk cluster is ordering. Three features have hard dependencies that, if violated, cause irreversible operational loss: (1) the score breakdown bug must be fixed before dimension bars can be trusted, (2) CLI commands must reach parity with Streamlit's admin operations before Streamlit is deleted, and (3) AI search requires a two-stage pre-filter + LLM-rank architecture to avoid context window overflow. Secondary risks are Chart.js instance leakage on SPA navigation and Gmail OAuth's 7-day refresh token expiry when the GCP consent screen is left in "Testing" mode. Both have clear prevention strategies.

## Key Findings

### Recommended Stack

The existing stack is locked and should not change. V1.1 adds five targeted packages. Chart.js 4.5.1 via CDN script tag (lazy-loaded into the Dashboard route only) handles all chart types needed. Click 8.3.1 replaces Streamlit's multi-subcommand admin UI with a `reconnect` CLI group. Three Google packages (`google-api-python-client`, `google-auth-oauthlib`, `google-auth`) implement the Gmail OAuth flow. AI search reuses the existing `openai` package already in requirements. Streamlit and Plotly are deleted entirely after CLI parity is confirmed.

**Core technologies added:**
- **Chart.js 4.5.1 (CDN, lazy-loaded):** Dashboard bar/doughnut charts — zero-dependency, PWA-compatible, no build step; lazy-load into Dashboard route only to avoid 200KB download on every page
- **Click 8.3.1:** CLI subcommand framework replacing Streamlit — cleaner than argparse for multi-level subcommand groups; decorator-based, automatic `--help` generation
- **google-api-python-client 2.192.0 + google-auth-oauthlib 1.3.0 + google-auth 2.49.0:** Gmail OAuth send path — official Google stack, InstalledAppFlow token.json pattern, all three must be updated together
- **pgvector (Supabase built-in, DEFERRED):** NOT recommended for v1.1 — batch LLM approach from `opportunity_match.py` is cheaper, proven, and sufficient below 5K contacts

**Removed:**
- `streamlit >= 1.30.0` — replaced by CLI
- `plotly >= 5.18.0` — only used by Streamlit; redundant once Streamlit is deleted

### Expected Features

Research identified a clear P1/P2/P3 priority structure with hard feature dependencies grounded in codebase inspection.

**Must have — P1 (removes debt, unblocks daily workflow):**
- Score breakdown bug fix — dimension bars show 0 for pre-rubric contacts; destroys trust in scoring display; fix is a rescore CLI command, not a code change
- Health score actionable insights — transforms the single 0-100 number into per-component action strings; data already in `compute_network_health()`; needs action-text generation layer
- Queue sort + status filter — users need to toggle sort and see approved/sent items; Supabase PostgREST params handle this server-side
- CLI commands: `pipeline run`, `queue reset`, `queue stats`, and six more — required before Streamlit can be removed
- Streamlit removal — `review.py` already crashes on import; maintaining both CLI and Streamlit doubles maintenance surface
- Gmail OAuth CLI flow — App Passwords disallowed on some Workspace accounts; `GmailCredentials` table already modeled for OAuth from day one

**Should have — P2 (intelligence layer):**
- Demographic charts (score tier first, then industry/role after pipeline aggregation step) — answers "am I networking in the right circles?"
- AI contact search PWA route + Edge Function — surfaces network value via semantic query; `opportunity_match.py` already implements the core LLM logic
- Queue industry filter (client-side, via JSON traversal) — additive on top of status filter

**Defer to v1.2+:**
- Score weight tuning UI in PWA — `UserPreference` weights work via feedback processor; preferences UI is cosmetic overhead
- `industry` top-level column on `connections` — proper fix for industry filtering; requires migration; client-side JSON filter is acceptable for v1.1
- Geographic distribution chart — less than 40% of contacts have location data; chart would be mostly empty
- Pipeline controls in PWA — CLI is sufficient per PROJECT.md

**Critical feature dependency chain:**
```
Score breakdown bug fix → enables trustworthy profile display
CLI commands → enables Streamlit removal
AI search Edge Function → replaces Streamlit "Ask My Network" page (required before full removal)
Streamlit removal → reduces maintenance surface
```

### Architecture Approach

All v1.1 work fits within four established patterns and requires no new database migrations for the core scope. The snapshot-based dashboard pattern (pipeline computes, PWA reads) is extended with two new top-level keys (`demographics`, `health_insights`). The Edge Function pattern gets one new member: `supabase/functions/search/index.ts`. Direct PostgREST filtering handles queue filtering. The CLI wraps existing function calls with Click decorators.

**Major components and their v1.1 changes:**

1. **`src/services/dashboard_service.py`** (MODIFY) — Add `compute_demographics()` and `compute_health_insights()` helpers; include in snapshot dict. No new API calls; pure extension of `compute_dashboard_snapshot()`.
2. **`supabase/functions/search/index.ts`** (NEW) — Port `opportunity_match.py` batch LLM pattern to Deno TypeScript. Query contacts, batch 50, call gpt-4o-mini, return top matches. Mirrors `draft` Edge Function structure exactly.
3. **`src/cli.py`** + **`src/cli/auth.py`** (NEW) — Click group with all pipeline/queue/sync/gmail subcommands. LaunchAgent plist updated to call `python -m src.cli pipeline`.
4. **`src/integrations/gmail.py`** (MODIFY) — Add OAuth send path alongside App Password fallback. Load from `GmailCredentials` row id=1; auto-refresh via `google-auth`; save refreshed tokens back to SQLite.
5. **`pwa/js/dashboard.js`** (MODIFY) — Add CSS-bar demographics rendering and health insight cards. Existing funnel bar pattern (`buildFunnelSection()`) is sufficient — Chart.js optional.
6. **`pwa/js/queue.js`** (MODIFY) — Add filter state, modify query builder to use PostgREST chained filters (`.eq()`, `.ilike()`, `.gte()`), add filter UI controls.
7. **`pwa/js/search.js`** (NEW) — Search UI + POST to `/functions/v1/search`; add `#/search` route to `app.js`.
8. **`src/sync/push.py`** (MODIFY) — Remove `gmail_credentials` from sync payload (security fix: OAuth tokens must not be pushed to Supabase).

**No new DB migrations needed** for the core v1.1 scope. All new data flows through existing tables.

### Critical Pitfalls

1. **Chart.js instances not destroyed on SPA navigation** — every `new Chart(canvas, config)` call on an already-used canvas leaks memory and renders doubled charts after the user navigates away and returns. Prevention: module-level instance registry with explicit `chart.destroy()` before re-creating; also lazy-load Chart.js via dynamic script injection only when Dashboard route activates (saves 200KB on non-Dashboard pages).

2. **Gmail OAuth consent screen left in "Testing" mode** — refresh tokens expire after exactly 7 days in Testing mode, silently breaking the daily email digest with `invalid_grant`. Prevention: publish the GCP consent screen (or add your email as a test user) before running the authorization flow for real use. Wrap `credentials.refresh(Request())` in try/except for `RefreshError`; skip digest gracefully rather than crashing the pipeline.

3. **AI search passing all raw_enrichment JSON to the LLM** — at 100+ enriched contacts, full raw_enrichment context overflows gpt-4o-mini's 128K token window and causes `context_length_exceeded`. Prevention: mandatory two-stage architecture — SQL pre-filter first (free, milliseconds via PostgREST), then pass only compact summaries (~200 tokens per contact) to gpt-4o-mini for 20-50 candidates.

4. **Streamlit removal before CLI parity** — six admin operations have no CLI equivalent yet (reset empty enrichments, batch rescore, Hunter.io email lookup, pipeline run history, import LinkedIn dump, reset stale queue). Removing Streamlit first loses all access to these operations permanently until CLI is built. Prevention: audit all Streamlit pages, build CLI equivalents, verify parity, then delete `src/ui/`. Note: `review.py` crashes on import and should be deleted immediately as a pre-condition — but this does not mean the rest of Streamlit is safe to remove yet.

5. **AI search hallucinating contact details** — gpt-4o-mini may infer skills or context from training data rather than the provided contact summaries, producing match reasons that reference data not in the database. Prevention: prompt instructs model to only cite data from the provided list; verify match reasons reference actual contact fields before displaying.

## Implications for Roadmap

Based on the feature dependency graph and pitfall sequencing, a 4-phase structure is recommended. Phases 1-3 address the P1 must-haves; Phase 4 delivers the highest-value P2 differentiator.

### Phase 1: Foundation Fixes + Queue UX
**Rationale:** Score breakdown bug and queue filtering have zero dependencies, high daily-use value, and low implementation cost. Fix these first to establish a trustworthy, usable baseline before adding any new capability. Pitfall research confirms queue filtering must be server-side via PostgREST params — client-side full-table fetch is a performance trap at 50+ items.
**Delivers:** Trustworthy scoring display on all contact profiles (via rescore command); queue sort/filter controls for status, score range, and industry
**Addresses:** Score breakdown bug fix (P1); Queue sort + status filter (P1); Queue industry filter (P2, client-side via JavaScript for v1.1)
**Avoids:** Score dimension trust damage; client-side full-fetch performance trap; filter state loss on navigation (encode active filters in URL or sessionStorage)
**Research flag:** Standard patterns — PostgREST filtering is well-documented; rescore function already exists in `src/ui/app.py`. No additional research needed.

### Phase 2: Dashboard Intelligence
**Rationale:** Dashboard charts are medium complexity with no dependencies on other v1.1 features. The snapshot pattern is fully established — extending `compute_dashboard_snapshot()` is safe and well-understood. Health insights require the same snapshot extension. Build before AI search to validate the pipeline-to-PWA data flow is working before adding a new Edge Function.
**Delivers:** Industry distribution, role mix, and score tier charts (using CSS bar pattern from existing `buildFunnelSection()`); health score breakdown with per-component action strings and color-coded thresholds
**Addresses:** Demographic charts — score tier first (P2), industry/role after aggregation step; Health score actionable insights (P1)
**Uses:** `compute_dashboard_snapshot()` extension; `pwa/js/dashboard.js` additions; Chart.js 4.5.1 lazy-loaded if CSS bars are insufficient for specific chart types
**Avoids:** Chart.js instance leakage (destroy-before-create registry required); live aggregation queries in PWA (use snapshot only — PostgREST does not support GROUP BY natively); Supabase Realtime channel duplicate subscription if realtime is added for snapshot refresh
**Research flag:** Standard patterns — snapshot extension is established in this codebase. Chart.js CDN integration is HIGH confidence from official docs. No additional research needed.

### Phase 3: CLI Commands + Gmail OAuth + Streamlit Removal
**Rationale:** CLI must exist and be verified before Streamlit is deleted. This is the gate phase. All six Streamlit admin operations need CLI equivalents confirmed before deletion. Gmail OAuth is bundled here because `src/cli/auth.py` is shared between the CLI and the `reconnect gmail auth` command. Streamlit removal is the final step of this phase, not the first — delete only after verifying every CLI equivalent.
**Delivers:** `reconnect` CLI with full subcommand coverage (pipeline, queue, sync, contacts, gmail); Gmail OAuth send path replacing App Password; `src/ui/` deleted; `streamlit` and `plotly` removed from requirements; `gmail_credentials` removed from Supabase sync payload
**Addresses:** CLI commands (P1); Gmail OAuth (P1); Streamlit removal (P1)
**Uses:** Click 8.3.1; google-api-python-client 2.192.0; google-auth-oauthlib 1.3.0; google-auth 2.49.0
**Avoids:** Premature Streamlit removal — verify CLI parity against all 6 admin operations before deleting `src/ui/`; Gmail OAuth 7-day Testing mode expiry — publish GCP consent screen before running authorization; OAuth refresh tokens in Supabase — remove `gmail_credentials` from `push.py` sync payload immediately when adding OAuth
**Research flag:** Standard patterns for both Click CLI and Gmail OAuth (HIGH confidence from official docs). No additional research needed.

### Phase 4: AI Contact Search
**Rationale:** Highest implementation effort, highest user value. Requires a new Deno TypeScript Edge Function, a new PWA route, and careful prompt engineering. Placed last because it has no blockers from other phases but benefits from CLI and snapshot infrastructure being stable. Replaces the Streamlit "Ask My Network" page removed in Phase 3. Pitfall research is definitive: two-stage architecture (SQL pre-filter + LLM rank) is mandatory from the start — retrofitting it later is costly.
**Delivers:** `#/search` PWA route with natural language query UI; `supabase/functions/search/index.ts` Edge Function with batch LLM matching (mirrors `draft` Edge Function structure); result cards linked to `#/contact/:id`; loading/empty/error states
**Addresses:** AI contact search (P2)
**Uses:** Existing OpenAI `gpt-4o-mini` via `OPENAI_API_KEY` Supabase secret; TypeScript port of `opportunity_match.py` batch logic; `--no-verify-jwt` deploy flag (same as `draft`, `action`, `feedback`)
**Avoids:** Context window overflow — pre-filter with PostgREST before LLM call; hallucination — grounding prompt that instructs model to cite only provided data; pgvector complexity — batch LLM is sufficient and proven at this contact scale; Supabase free tier 2s CPU limit — sequential batches of 50, cap at first 200 contacts
**Research flag:** Architecture is HIGH confidence (mirrors draft Edge Function). The TypeScript port of the batch LLM pattern in Deno runtime and the Supabase free tier CPU time constraint warrant a brief `/gsd:research-phase` call if the developer is unfamiliar with Deno module imports and Edge Function execution limits.

### Phase Ordering Rationale

- **Phase 1 first:** Score trust is foundational. Dashboard charts built on unreliable dimension scores would compound the trust problem. Queue filtering delivers immediate daily-use value with zero risk.
- **Phase 2 before Phase 3:** Dashboard chart work validates the pipeline-to-PWA snapshot flow before the pipeline's admin surface changes in Phase 3. Confirms snapshot JSON schema extensions work end-to-end.
- **Phase 3 before Phase 4:** `src/cli/auth.py` built in Phase 3 is shared with Gmail OAuth. More importantly, Phase 3 removes the Streamlit "Ask My Network" page — Phase 4 replaces it. Removing before replacing is intentional: Streamlit's version crashes when `review.py` is imported, making the entire Streamlit app unreliable. Better to have no search than a crashing admin UI.
- **Score breakdown bug fix as Phase 1 pre-condition:** Running `reconnect contacts score --rubric-only` (or the Streamlit rescore before CLI exists) is a data fix, not a code change. Do this before any other phase work to validate that dimension scores render correctly in the existing PWA.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (AI Contact Search):** TypeScript port of batch LLM pattern in Deno runtime and Supabase free tier 2s CPU execution limit per invocation warrant a `/gsd:research-phase` call. Specifically: Deno ESM module imports differ from Node.js; sequential batch vs Promise.all strategy needs validation against actual contact count and timing.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation Fixes + Queue UX):** PostgREST filtering via Supabase JS client is well-documented; rescore logic already exists in `src/ui/app.py` and just needs extraction to a CLI command.
- **Phase 2 (Dashboard Intelligence):** Snapshot extension is an established pattern in this codebase; Chart.js CDN lazy-loading is HIGH confidence from official docs.
- **Phase 3 (CLI + Gmail OAuth + Streamlit Removal):** Click CLI and Gmail OAuth `InstalledAppFlow` are thoroughly documented official patterns. Streamlit removal is a systematic audit-and-delete exercise, not a technical challenge.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All new packages verified on PyPI with exact release dates; Chart.js confirmed on jsDelivr; pgvector confirmed pre-installed on all Supabase hosted plans; version compatibility matrix verified |
| Features | HIGH | All findings from direct codebase inspection of actual source files; priorities grounded in current code state, not guessing; dependency chain confirmed by reading function signatures and imports |
| Architecture | HIGH | All integration points confirmed by reading actual source files; no speculative claims; build order rationale grounded in confirmed dependency relationships |
| Pitfalls | HIGH (OAuth, charting) MEDIUM (AI search) | OAuth and charting pitfalls from official docs and well-known GitHub issues; AI search hallucination and context overflow from community sources without official benchmarks at this exact dataset size |

**Overall confidence:** HIGH

### Gaps to Address

- **Supabase Edge Function CPU time limit:** Free tier enforces 2s CPU per invocation. With 500 enriched contacts = 10 sequential batches × ~400-500ms each = ~4-5s wall-clock. Sequential processing stays under CPU limit but wall-clock may feel slow. Validate with actual contact count during Phase 4 planning. Mitigation: cap at first 200 contacts (4 batches × ~400ms = ~1.6s).
- **PostgREST inner join filter on embedded resources:** The `connections!inner(*)` syntax with `.ilike('connections.current_company', ...)` is documented but not tested against this schema. If it fails, client-side filtering after fetch is an acceptable fallback for ≤50 queue items. Validate in Phase 1 before building filter UI.
- **GCP OAuth consent screen publishing timeline:** For "External" apps requesting the `gmail.send` scope, Google may require a verification form. Timeline is variable (can be instant or take days). Mitigation: add your own email as a test user during development — tokens last 7 days in Testing mode, workable during active development. Publish before leaving the pipeline unattended for more than a week.
- **Raw enrichment JSON key variants:** Industry data is stored as either `$.data.company_industry` or `$.company_industry` depending on enrichment format version. The SQLite `json_extract()` query and the Python aggregation must handle both key paths. Validate with actual data before building the demographics chart in Phase 2.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `src/services/dashboard_service.py`, `src/llm/opportunity_match.py`, `src/llm/scoring.py`, `src/pipeline/queue_generator.py`, `pwa/js/queue.js`, `pwa/js/dashboard.js`, `pwa/js/contact.js`, `src/integrations/gmail.py`, `src/database/models.py`, `src/config.py`, `src/ui/app.py`, `src/sync/push.py`, `supabase/functions/draft/index.ts`
- `.planning/PROJECT.md` — constraints, out-of-scope list, known tech debt
- [Chart.js Installation Docs](https://www.chartjs.org/docs/latest/getting-started/installation.html) — CDN pattern, Canvas API
- [Chart.js Destroy API](https://www.chartjs.org/docs/latest/developers/api.html#destroy) — instance lifecycle
- [Gmail API Python Quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) — InstalledAppFlow token.json pattern
- [google-auth on PyPI](https://pypi.org/project/google-auth/) — v2.49.0, released 2026-03-06
- [google-auth-oauthlib on PyPI](https://pypi.org/project/google-auth-oauthlib/) — v1.3.0, released 2026-02-27
- [google-api-python-client on PyPI](https://pypi.org/project/google-api-python-client/) — v2.192.0, released 2026-03-05
- [Supabase pgvector Docs](https://supabase.com/docs/guides/database/extensions/pgvector) — extension setup, HNSW indexing
- [Supabase Semantic Search Docs](https://supabase.com/docs/guides/ai/semantic-search) — match_documents RPC pattern
- [Click 8.3.1 on PyPI](https://pypi.org/project/click/) — released 2025-11-15
- [Click Entry Points Docs](https://click.palletsprojects.com/en/stable/entry-points/) — pyproject.toml scripts pattern
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings) — text-embedding-3-small, dimensions parameter

### Secondary (MEDIUM confidence)
- [Gmail OAuth refresh token expiry rules](https://developers.google.com/identity/protocols/oauth2#expiration) — 7-day Testing mode expiry, 50-token-per-client limit
- [Google OAuth invalid_grant causes](https://nango.dev/blog/google-oauth-invalid-grant-token-has-been-expired-or-revoked) — community source
- [Google OOB flow deprecated](https://developers.googleblog.com/en/oauth-out-of-band-flow-deprecation-part-2/) — use run_local_server() not oob
- [Supabase Realtime duplicate channel subscription](https://github.com/supabase/supabase-js/issues/1440) — GitHub issue
- [Supabase PostgREST conditional filtering](https://markustripp.medium.com/supabase-conditional-queries-with-filter-chaining-1c2bb48b8388) — community source
- [RAG reducing hallucinations](https://community.openai.com/t/mitigating-hallucinations-in-rag-a-2025-review/1362063) — community source
- 512 vs 1536 embedding dimensions tradeoff — OpenAI community forum + blogs; no official benchmark at contact-scale datasets

---
*Research completed: 2026-03-09*
*Ready for roadmap: yes*
