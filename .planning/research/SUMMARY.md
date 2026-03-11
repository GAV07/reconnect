# Project Research Summary

**Project:** Reconnect v1.2 — Intent-Driven Triage
**Domain:** Personal networking CRM — intent signal system, cadence scheduling, goals profile, contact notes, signal-informed rescoring, draft tone adaptation
**Researched:** 2026-03-11
**Confidence:** HIGH

## Executive Summary

Reconnect v1.2 replaces the binary approve/skip/snooze triage model with a seven-signal intent system (WARM_LEAD, NURTURE, VALUE_DROP, SYNERGY, RECONNECT, FUTURE_PIVOT, ARCHIVE). The signal a user assigns is not just a label — it drives cadence re-queuing, draft tone adaptation, and signal-pattern rescoring over time. Research confirms this is architecturally achievable as a pure extension of the existing stack: no new Python libraries, no new npm packages, no new Deno imports. Every feature maps to an existing hook in the pipeline, sync layer, or PWA. The two new database tables (`contact_signals`, `contact_notes`) and nullable columns on three existing tables are the only schema footprint.

The recommended approach is six sequential phases, starting with schema and the canonical signal service, then the PWA signal UI, then user goals profile, sync coverage, pipeline integration, and finally draft tone adaptation. The dependency chain is strict: the PWA writes signals to Supabase, pull sync brings them to local SQLite, then the pipeline learns from them. Building in the wrong order produces signal data that exists in one layer but not the other — silent failures that are hard to diagnose. The critical constraint throughout is that schema migrations and sync payload updates must ship in the same step as model changes, never after.

The highest-risk element is signal-informed rescoring. The existing feedback processor already applies weight adjustments from approve/skip patterns, and extending it to consume signals creates a confirmation bias feedback loop that can homogenize the queue toward the user's early preferences within two to three weeks. Prevention requires raising the minimum sample threshold before any weight adjustment fires (at least 25 actions over 14 days), capping cumulative drift at plus or minus 40%, and logging weight history so drift is auditable. A second major risk is cadence scheduling correctness: using absolute `cadence_due_at` timestamps rather than age-based eligibility causes cohort saturation when many contacts are assigned the same signal on the same day. Both risks have concrete mitigation strategies documented in PITFALLS.md.

## Key Findings

### Recommended Stack

No new libraries or framework additions are required for any v1.2 feature. The entire milestone is achievable within the verified existing stack: Python 3.11+, SQLModel 0.0.31, OpenAI 2.15.0, psycopg2-binary 2.9+, Supabase JS client v2 (CDN), and Deno TypeScript on Supabase Edge Functions. All v1.2 functionality maps to existing capabilities: stdlib `datetime` for cadence arithmetic, stdlib `json` for parsing `score_reasoning`, stdlib `collections.Counter` for signal pattern analysis. The only deployment action beyond the migration is `supabase functions deploy draft`.

**Core technologies (v1.2 usage):**
- Python pipeline + SQLite: signal service layer, cadence re-queuing, feedback processor extension — no runtime changes
- Supabase PostgreSQL + PostgREST: two new tables (`contact_signals`, `contact_notes`) plus nullable columns on `connections`, `outreach_queue`, and `user_profile`; migration follows the established psycopg2-direct pattern
- Supabase Edge Function `draft/index.ts`: add optional `signal` parameter with a tone mapping dict; deploy via `supabase functions deploy draft`
- Vanilla JS PWA: signal picker replaces three-button triage; PostgREST direct writes for signals and notes (no Edge Function needed, no server-side secrets required)
- Bidirectional sync (`push.py` + `pull.py`): extend both to cover new tables and fields; user-intent data (signals, notes, priorities) is cloud-authoritative; pipeline-computed data (scores, enrichment) is local-authoritative

**What not to add:**
- APScheduler or Celery — cadence re-queuing is a daily batch check, not real-time
- React or Vue — signal picker is seven buttons, not a UI rewrite
- pgvector or semantic embeddings — signal pattern analysis via Counter is sufficient
- New Edge Function for signals or notes — PostgREST with anon key + RLS handles these writes identically to existing `user_feedback` writes

### Expected Features

The v1.2 feature set has a strict internal dependency: signals must exist before everything else builds on them, and queue card enrichment is a prerequisite for informed signal choice. Contact notes are independent but synergistic. Email digest fix is independent and should be repaired first to restore daily workflow reliability.

**Must have (table stakes — P1):**
- Email digest fix — daily workflow is broken without reliable delivery; fix before any signal work
- 7 intent signals (DB + PWA picker) — milestone is incoherent without this foundation
- Signal storage in `user_feedback` log — required by rescoring, history, and pattern analysis downstream
- Queue card enrichment (industry chip, first key factor, last interaction) — users cannot make a confident signal choice without context; all data is already in the existing joined query
- Contact notes PWA wire-up — `Connection.notes` column exists; only the PWA edit path is missing
- Signal-driven cadence re-queuing — signals must produce behavior or they are inert labels
- Profile key factors fallbacks — empty profiles feel broken; a basic product quality fix

**Should have (differentiators — P2):**
- Draft tone adaptation — pass signal to `draft/index.ts` with a tone mapping dict; meaningfully improves draft quality with minimal effort
- Signal-informed rescoring — extends existing `feedback_processor.py` weight logic; compounds value over time
- User goals profile (`current_projects` field) — incremental improvement to WARM_LEAD precision in scoring
- Conversation starters from alternative sources — frontend-only; high return on effort
- Signal history on contact profile — retrospective value; low complexity

**Defer (v1.3+):**
- Signal-based queue filter in PWA — `reconnect contacts list --signal WARM_LEAD` CLI covers the power-user case
- Configurable cadence per signal via CLI — defaults work for 90% of use cases
- Signal-driven email digest bucketing — complex digest redesign
- Signal analytics on dashboard
- Resource prompt for VALUE_DROP contacts

**Signal taxonomy and system actions:**

| Signal | Cadence | Queue Status | Draft Tone |
|--------|---------|--------------|------------|
| WARM_LEAD | 7 days | approved | Direct, specific ask |
| NURTURE | 30 days | pending_review | Warm, low-pressure, no ask |
| VALUE_DROP | 90 days | skipped | Helpful, generous, lead with value |
| SYNERGY | 14 days | approved | Peer-to-peer, propose concrete step |
| RECONNECT | 14 days | approved | Warm, reference shared history |
| FUTURE_PIVOT | 60 days | pending_review | Exploratory, no ask |
| ARCHIVE | never | skipped | No draft; set user_priority = never |

### Architecture Approach

The architecture is a pure extension of the existing local-pipeline to SQLite to Supabase to PWA pattern. The canonical signal mapping is defined once in `src/services/signal_service.py` (Python) and mirrored as a JS constant in `queue.js`, then consumed by all other components — this eliminates silent drift between PWA and pipeline cadence values. Signal writes from the PWA go directly to PostgREST because no server-side secrets are required; this follows the same pattern already used for `user_feedback` and `user_preferences` writes. Draft tone adaptation requires an Edge Function because it needs the OpenAI key, so the signal is passed in the POST body from the PWA.

**Major components and v1.2 responsibilities:**

1. **`src/services/signal_service.py` (new)** — canonical `SIGNAL_ACTIONS` map and `apply_signal()` function; single source of truth for signal to cadence, status, and priority boost mapping
2. **`pwa/js/queue.js` (modify)** — 7-option signal picker replacing 3-button triage; PostgREST writes to `contact_signals`, `outreach_queue`, and `connections`; enriched card display with industry, key factors, notes preview
3. **`pwa/js/contact.js` (modify)** — contact notes display and signal history panel
4. **`pwa/js/preferences.js` (modify)** — user goals and current_projects editing form
5. **`src/pipeline/queue_generator.py` (modify)** — two new exclusion rules (cadence not due, ARCHIVE); WARM_LEAD priority boost; `_compute_mini_key_factors()` pre-computation from `score_reasoning`
6. **`src/pipeline/feedback_processor.py` (modify)** — signal pattern analysis; rescore candidate identification; conservative weight adjustments (25+ actions over 14 days, plus or minus 40% cap)
7. **`src/sync/push.py` + `pull.py` (modify)** — extended to cover `contact_signals`, `contact_notes`, and new connection fields; cloud wins for user-intent data, local wins for pipeline-computed data
8. **`supabase/functions/draft/index.ts` (modify)** — accepts optional `signal` parameter; injects tone guidance from a `SIGNAL_TONE_MAP`
9. **Database migration (new)** — `contact_signals` table, `contact_notes` table, new columns on three existing tables, anon role grants for new tables

**Key patterns:**
- Canonical signal map (one Python dict, one JS object) — eliminates cadence drift
- Denormalized `latest_signal` + `cadence_due_at` cache on `connections` — avoids correlated subqueries in queue generation
- Signal context as additive LLM prompt injection — preserves existing scoring calibration
- PostgREST direct for signal writes — no Edge Function cold-start overhead on every signal tap

### Critical Pitfalls

1. **Orphaned "skipped" items block cadence re-queue** — existing `status = "skipped"` rows are ambiguous: was this a Skip (maps to ARCHIVE) or a Snooze (maps to RECONNECT with re-queuing)? A one-time migration must backfill intent before the new exclusion logic deploys. Run before deploying new `is_contact_excluded()` rules.

2. **Cadence as absolute timestamp causes cohort saturation** — do not store `cadence_due_at` as a precomputed fixed date. Instead evaluate `signal_assigned_at + cadence_days <= today` at query time on each pipeline run. When more cadence-eligible contacts exist than the daily queue limit, use priority ordering to clear the backlog gradually across multiple days.

3. **Signal-informed rescoring creates confirmation bias** — the feedback processor's weight adjustment mechanism will amplify early signal patterns, homogenizing the queue toward the user's first few weeks of triage behavior within 2-3 weeks. Prevention: 25-action / 14-day minimum threshold before any weight fires; plus or minus 40% cumulative cap; log every adjustment with sample count.

4. **New signal fields silently dropped from push sync** — for every new field added to a model, write the Supabase migration SQL and add the field to the push payload mapping in the same step. Consider a field coverage assertion to prevent future drift.

5. **Signal logic duplicated across pipeline and PWA** — define `SIGNAL_ACTIONS` once in `signal_service.py` (Python) and once as a JS const in `queue.js`. All other files consume from one of these two locations. If cadence values diverge between the two, contacts re-appear at the wrong time with no error raised.

## Implications for Roadmap

Based on combined research, the dependency chain is strict and the phase order is non-negotiable: schema before PWA before sync before pipeline. Draft tone is the only phase that is genuinely order-independent after Phase 1.

### Phase 1: Schema, Migration, and Signal Service

**Rationale:** Everything downstream depends on the database schema and the canonical signal map existing in both SQLite and Supabase. Must include anon role grants for new tables or PWA writes will silently fail. The backfill migration for existing "skipped" items must run in this phase, before any new exclusion logic is deployed.

**Delivers:** `contact_signals` and `contact_notes` tables in both SQLite and Supabase; new nullable columns on `connections` (latest_signal, cadence_due_at), `outreach_queue` (signal, signal_context, mini_key_factors), and `user_profile` (current_projects, goals_structured); `signal_service.py` with canonical `SIGNAL_ACTIONS` map and `apply_signal()` function; `models.py` updated with new model classes and field additions; one-time backfill migration categorizing existing skipped items; unique index on `outreach_queue(connection_id) WHERE status IN ('pending_review', 'approved')` preventing duplicate queue entries.

**Avoids (pitfalls):** Pitfall 4 (new fields not synced) by migrating Supabase schema before any Python code sets the fields. Duplicate queue item race condition by adding the unique index here. Pitfall 1 (orphaned skipped items) by running the backfill migration before any new exclusion logic is written.

**Research flag:** Standard patterns — migration follows the established psycopg2-direct approach (see `20260305000000_pwa_overhaul.sql`). No additional research needed.

---

### Phase 2: Email Digest Fix + PWA Signal UI

**Rationale:** Email fix is a day-one blocker — the daily workflow is broken without it. The PWA signal UI is the primary user-facing change of the entire milestone and must be built before sync and pipeline integration so real signal data can accumulate. Queue card enrichment belongs here because it is a prerequisite for informed signal choice — users cannot confidently choose SYNERGY vs NURTURE without seeing industry and key factors.

**Delivers:** Email digest reliably sends (or falls back to Telegram notification); 7-signal picker on queue cards replacing 3-button triage; PostgREST writes to `contact_signals`, `outreach_queue`, and `connections`; enriched cards showing industry chip, first key factor, last interaction date; notes preview on cards; contact notes display and editing on profile page; signal history timeline on profile page; email digest updated to "Review in App" and "Archive" buttons (removing Snooze and Reach Out in email to align with signal model).

**Addresses (FEATURES.md):** Email digest fix (P1), 7 intent signals PWA (P1), queue card enrichment (P1), contact notes PWA wire-up (P1), signal storage in user_feedback log (P1), profile key factors fallbacks (P1), signal history on contact profile (P2).

**Avoids (pitfalls):** Pitfall 9 (optimistic UI card removal) — signal assignment updates the card's signal badge without removing the card; card dismissal is a separate "Done" action. Pitfall 5 (action token security) — full signal assignment stays in the PWA exclusively; email keeps at most two simplified actions. Full re-render on signal assignment must be avoided: use targeted DOM updates to preserve scroll position and filter state.

**Research flag:** PWA targeted DOM mutation pattern (signal badge update without full re-render) is a standard pattern but warrants careful testing of scroll position and filter state on mobile before shipping.

---

### Phase 3: User Goals Profile

**Rationale:** Goals profile is a prerequisite for signal-informed rescoring to produce meaningful results (the rescoring step uses `current_projects` to identify WARM_LEAD candidates against active initiatives). Also required for the Edge Function draft to use fresh user context rather than the stale "Network expansion" fallback. Must be built before Phase 5 pipeline integration.

**Delivers:** Goals and current_projects editing form in `preferences.js`; `scoring.py` extended to include `goals_structured` context in `build_scoring_prompt()`; `user_profile` push sync updated to include new goal fields; `user_profile` pull sync added to `pull.py` so PWA-edited goals reach the pipeline; `updated_at` added to `UserPreference` with last-write-wins conflict resolution in pull sync; `scoring_weight_auto` vs `scoring_weight_user` pref_type distinction preventing pipeline overwrites of user-explicit preferences.

**Addresses (FEATURES.md):** User goals profile / current_projects (P2).

**Avoids (pitfalls):** Pitfall 6 (stale goals in Edge Function draft) — push sync update ships in this phase. Pitfall 10 (user preferences overwritten by pipeline) — `updated_at` and pref_type source distinction added here.

**Research flag:** Standard patterns — PostgREST PATCH on `user_profile` is identical to existing preference writes.

---

### Phase 4: Sync Coverage

**Rationale:** PWA-created signals and notes are in Supabase but invisible to the pipeline until pull sync is extended. Pipeline-computed `mini_key_factors` are in local SQLite but invisible to the PWA until push sync is extended. Both gaps must close before Phase 5 pipeline integration can be built or tested.

**Delivers:** `pull.py` extended to pull `contact_signals`, `contact_notes`, `latest_signal`/`cadence_due_at` updates, and `Connection.notes`; `push.py` extended to push `contact_signals`, `contact_notes`, and new connection fields including `latest_signal` and `cadence_due_at`; conflict resolution documented and enforced: cloud wins for user-intent data, local wins for pipeline-computed data.

**Avoids (pitfalls):** Pitfall 4 (push sync coverage gap), Pitfall 7 (contact notes never pulled to local SQLite). The principle that `Connection.notes` is purely user-authored (pull-only from cloud; pipeline must never overwrite) should be documented in code comments to prevent future accidental overwrite.

**Research flag:** Standard patterns — follows identical structure to existing `user_feedback` and `action_token` pull sync.

---

### Phase 5: Pipeline Signal Integration

**Rationale:** Now that signals flow from PWA through Supabase to local SQLite, the pipeline can act on them. This phase wires cadence exclusion into queue generation and signal pattern analysis into feedback processing. Depends on all previous phases. This is the phase with the highest correctness risk (feedback loop dynamics) and requires the most careful implementation.

**Delivers:** `queue_generator.py` with cadence exclusion Rule 6 (age-based eligibility: `signal_assigned_at + cadence_days <= today`, not absolute `cadence_due_at`), Rule 7 (ARCHIVE exclusion), WARM_LEAD priority boost, and `_compute_mini_key_factors()` pre-computation; `feedback_processor.py` extended with signal pattern analysis using 25-action / 14-day minimum threshold, plus or minus 40% multiplier cap, and weight history logging (`scoring_weight_auto` rows with sample count and timestamp); `scoring.py` accepts optional signal context for rescore pass; `daily_pipeline.py` threads signal_context flag into Step 8.

**Addresses (FEATURES.md):** Signal-driven cadence re-queuing (P1), signal-informed rescoring (P2).

**Avoids (pitfalls):** Pitfall 1 (orphaned skipped items — new exclusion checks `triage_signal` not just status timestamp), Pitfall 2 (duplicate queue items — unique constraint from Phase 1 prevents this), Pitfall 3 (confirmation bias — 25-action threshold and multiplier cap), Pitfall 8 (cadence cohort saturation — age-based eligibility distributes backlog naturally with priority ordering).

**Research flag:** Feedback loop threshold values (25 actions, plus or minus 40%) are grounded in published ML feedback loop literature but have not been validated against this specific dataset. Plan to inspect `user_preferences` multiplier values after the first two weeks of signal use and tighten thresholds if queue diversity degrades.

---

### Phase 6: Draft Tone Adaptation

**Rationale:** Smallest change, narrowest dependency (only requires Phase 1 schema to exist). Can ship any time after Phase 2 (when the PWA passes `intent_signal` in draft POST requests), but placed last to avoid blocking higher-priority phases on an Edge Function deploy. Delivers immediately visible user value: generated drafts sound appropriate to the relationship intent rather than defaulting to channel-only tone.

**Delivers:** `draft/index.ts` updated with optional `signal` parameter, `SIGNAL_TONE_MAP` constant mapping each of 6 signals to tone guidance, and signal guidance injected into `buildDraftPrompt()`; ARCHIVE signal guard (no draft generated, PWA disables button); `signal_context` passed as additional context line in prompt when provided.

**Addresses (FEATURES.md):** Draft tone adaptation (P2).

**Avoids (pitfalls):** Pitfall 6 (wrong tone because signal not passed) — signal is now in POST body; goals are now synced from Phase 3.

**Research flag:** Standard patterns — adding an optional parameter to an existing Deno TypeScript Edge Function is well-documented.

---

### Phase Ordering Rationale

- **Schema first:** Every other phase creates or reads the new columns and tables. There is no valid alternative sequence.
- **Email fix bundled with PWA UI (Phase 2):** Email and queue card are the two primary interaction surfaces. Fixing email reliability and rebuilding queue triage in the same phase ensures both are consistent when the signal model ships. A user should not see signals in the PWA but Reach Out / Skip / Snooze in the email.
- **Goals profile before pipeline (Phase 3 before Phase 5):** Signal-informed rescoring uses `current_projects` to identify WARM_LEAD candidates. Building rescoring without goals profile makes it produce generic results.
- **Sync before pipeline (Phase 4 before Phase 5):** The pipeline must read signals and notes from local SQLite. Without pull sync, `is_contact_excluded()` has no signal data to read.
- **Draft tone last (Phase 6):** No feature depends on draft tone being complete. Placing it last avoids blocking higher-priority phases on an Edge Function deploy.

### Research Flags

Phases needing monitoring or deeper validation during execution:
- **Phase 5 (Feedback Processor):** The 25-action / 14-day threshold and plus or minus 40% multiplier cap are based on published ML feedback loop research but are not validated against this codebase's specific signal distribution. Monitor `user_preferences` for `scoring_weight_auto` rows after first two weeks. If queue diversity drops (same industry or role type dominates more than 60% of the queue), tighten the minimum threshold further before the next pipeline run.
- **Phase 2 (Mobile PWA State Management):** Targeted DOM updates for signal badge changes (without card removal or full re-render) are a known-solvable pattern but require hands-on testing of scroll position and filter state preservation on mobile, especially during batch triage of 10+ cards.

Phases with standard patterns (skip deeper research):
- **Phase 1:** psycopg2-direct migration is an established pattern in this codebase (see `20260305000000_pwa_overhaul.sql`).
- **Phase 3:** PostgREST PATCH on `user_profile` mirrors the identical pattern used for existing preference writes.
- **Phase 4:** Pull sync extension follows the `user_feedback` pull pattern exactly.
- **Phase 6:** Optional TypeScript parameter addition to an existing Edge Function is well-documented.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All findings from direct codebase inspection; verified installed package versions; conclusion that no new libraries are needed is unambiguous — every feature maps to an existing dependency |
| Features | HIGH | Feature taxonomy derived from codebase + PROJECT.md; signal definitions align with established CRM cadence patterns; anti-features are justified by concrete architectural constraints, not opinion |
| Architecture | HIGH | All claims grounded in source code inspection; patterns are direct extensions of verified existing patterns (PostgREST writes, bidirectional sync, Edge Function prompt injection); no speculation |
| Pitfalls | HIGH (migration/sync/PWA) / MEDIUM (feedback dynamics) | Migration and sync pitfalls are code-verified; confirmation bias dynamics are supported by ML literature but the specific thresholds (25 actions, plus or minus 40%) are domain judgment, not empirically validated against this dataset |

**Overall confidence:** HIGH

### Gaps to Address

- **Signal cadence day counts vary slightly between research files:** STACK.md and FEATURES.md differ on some cadence values (e.g., NURTURE is 90 days in STACK.md vs 21 days in FEATURES.md, VALUE_DROP is 60 days vs 14 days). Reconcile these before Phase 1. The canonical source must be `signal_service.py` — all other files consume from it.

- **Feedback loop threshold validation:** The 25-action / 14-day minimum and plus or minus 40% cap are reasonable starting points based on published research but need empirical validation against this specific dataset. Plan a review of `user_preferences` multiplier values after the first two to three weeks of v1.2 use.

- **Email digest redesign scope:** Research calls for updating the email to show "Review in App" and "Archive" as simplified buttons, but the exact HTML redesign of the digest template is not fully specified. This needs design decisions during Phase 2 planning.

- **`contact_notes` vs `connections.notes` design decision:** STACK.md recommends using the existing `connections.notes` field (already exists, already in sync fields), while ARCHITECTURE.md recommends a new `contact_notes` table for cleaner separation. The STACK.md approach is simpler; the ARCHITECTURE.md approach is more queryable. Decide before Phase 1 migration is written.

## Sources

### Primary (HIGH confidence — direct codebase inspection)

- `src/database/models.py` — all existing table definitions, field inventory, metadata conventions
- `src/pipeline/daily_pipeline.py` — 10-step pipeline orchestration and step dependencies
- `src/pipeline/queue_generator.py` — exclusion rules, priority scoring, queue item generation
- `src/pipeline/feedback_processor.py` — existing signal learning pattern and threshold values
- `src/llm/scoring.py` — scoring prompt structure, weight override mechanism
- `src/sync/push.py`, `src/sync/pull.py` — bidirectional sync patterns and conflict resolution
- `supabase/functions/draft/index.ts` — `buildDraftPrompt()` structure for tone injection
- `pwa/js/queue.js` — PostgREST write patterns, client-side sort, triage button structure
- `supabase/migrations/20260305000000_pwa_overhaul.sql` — migration pattern reference
- `.planning/PROJECT.md` — v1.2 requirements, constraints, and current state
- Installed package versions verified directly: sqlmodel 0.0.31, openai 2.15.0, click 8.3.1, pydantic 2.12.5

### Secondary (MEDIUM confidence — community consensus, multiple sources agree)

- Personal CRM ecosystem patterns (Clay, Folk, Covve, Cloze) — cadence norms; 14-21 day follow-up as industry baseline for networking CRMs
- ML feedback loop literature (arxiv 2305.06055, 2101.05673; Microsoft Research) — confirmation bias dynamics and threshold guidance for iterative recommendation systems
- Supabase bidirectional sync conflict resolution patterns (stacksync.com)
- Vanilla JS PWA optimistic UI and state management patterns (MDN, medium.com)
- LLM personalization sycophancy with user profiles (MIT News, 2026)

### Tertiary (LOW confidence — needs validation during execution)

- Signal cadence day counts (slight variation between STACK.md and FEATURES.md) — reconcile in `signal_service.py` before Phase 1
- Feedback loop threshold values (25 actions, plus or minus 40% cap) — empirical validation needed after first 2-3 weeks of v1.2 production use

---
*Research completed: 2026-03-11*
*Ready for roadmap: yes*
