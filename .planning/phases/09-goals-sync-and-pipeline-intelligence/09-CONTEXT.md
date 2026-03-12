# Phase 9: Goals, Sync, and Pipeline Intelligence - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

User goals inform scoring, signals and notes flow bidirectionally between PWA and pipeline, and cadence re-queuing and signal-informed rescoring run automatically in the daily pipeline. This phase wires the signal service into the pipeline and makes the scoring prompt goal-aware.

</domain>

<decisions>
## Implementation Decisions

### Goals profile UI
- Goals section lives at the top of the existing Preferences page in the PWA
- Single free-form text area for stable networking objectives ("What are you focused on?")
- Goals change infrequently — these are broad career/networking directions
- Saves to `user_profile.current_projects` (text field, already exists from Phase 7 migration)
- `goals_structured` JSON column reserved for future use (lookouts feature)

### Goals in scoring prompt
- Both `current_projects` (new goals text) and existing `goals`/`interests` fields feed the LLM scoring prompt
- Claude's discretion on exact prompt structure — supplement existing fields rather than replace
- Goals text influences the `goal_alignment` dimension (0-25 points) of the scoring rubric
- When goals change in the PWA, mark all scored contacts for rescoring on the next pipeline run
- Rescoring after goals change can be batched over multiple days to manage LLM credit usage

### Cadence re-queuing
- Contacts with expired cadence (`signal_assigned_at + cadence_days <= today`) automatically re-enter the daily queue
- Age-based eligibility per Phase 7 decision — not absolute timestamps
- ARCHIVE contacts never re-appear (user_priority = "never" already handled by is_contact_excluded)
- Claude's discretion on: daily volume cap for re-queued contacts, mixing vs grouping with fresh recommendations, visual differentiation in queue

### Signal-informed rescoring
- Feedback processor evolves to analyze signal triage patterns (not just skip/approval)
- Safety guards: 25-action minimum over 14 days before any weight adjustment
- ±40% multiplier cap on scoring dimension weights (e.g., goal_alignment multiplier range: 0.6–1.4)
- Weight history logging for auditability (drift tracking in DB)
- Claude's discretion on: which signal patterns map to which weight adjustments, where drift logs are stored, preferences page display of weight history

### Bidirectional sync
- Signals and notes already sync bidirectionally (Phase 8 plan 04 delivered this)
- Phase 9 adds: pull sync for `user_profile` goals fields (current_projects) from cloud → local
- Pipeline-computed fields (mini_key_factors, latest_signal cache) continue pushing to cloud via existing push sync
- Goals rescore flag needs to reach the pipeline — either via a preference row or a field on user_profile

### Claude's Discretion
- Cadence re-queuing as a new pipeline step vs integrated into existing queue generation
- Exact prompt structure for goals in scoring
- Lookout card field structure in goals_structured JSON (for future phase)
- Weight drift visualization on preferences page
- Rescore batching strategy (all at once vs spread over days)
- Feedback processor architecture changes (extend existing vs replace)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/services/signal_service.py`: `SIGNAL_ACTIONS` with cadence_days per signal — consumed by re-queuing logic
- `src/llm/scoring.py`: `build_scoring_prompt()` reads `user_profile.goals` and `user_profile.interests` — extend to include `current_projects`
- `src/llm/scoring.py`: `_load_weight_overrides()` and `_apply_overrides()` — existing weight multiplier infrastructure for rescoring
- `src/pipeline/feedback_processor.py`: `process_feedback()` with `_derive_weight_adjustments()` — needs evolution for signal patterns + safety guards
- `src/pipeline/queue_generator.py`: `is_contact_excluded()` — already checks `user_priority == "never"` (ARCHIVE protection)
- `src/pipeline/queue_generator.py`: `generate_daily_queue()` — entry point for adding cadence re-queuing
- `src/sync/pull.py`: `pull_from_cloud()` — already syncs signals, notes, connection fields; needs user_profile goals pull
- `src/sync/push.py`: `push_to_cloud()` — already pushes user_profile as singleton upsert
- `pwa/js/preferences.js`: `renderPreferences()` — add goals section above existing scoring weights

### Established Patterns
- Pipeline steps: lazy imports in `daily_pipeline.py`, each step is try/except non-fatal, results dict accumulates
- Weight storage: `UserPreference` rows with `pref_type="scoring_weight"`, `pref_key=dimension_name`, `pref_value=multiplier`
- PWA data writes: PostgREST direct via Supabase client (`db.from('user_profile').update({...}).eq('id', 1)`)
- User profile: singleton row (id=1), fields pulled from cloud on sync

### Integration Points
- `src/pipeline/daily_pipeline.py`: Wire signal service, add cadence re-queuing step, ensure goals pull happens before scoring
- `src/llm/scoring.py`: `build_scoring_prompt()` — add current_projects to user context section
- `src/pipeline/feedback_processor.py`: Evolve `_derive_weight_adjustments()` for signal patterns with safety guards
- `src/pipeline/queue_generator.py`: Add cadence-expired contacts to daily queue candidates
- `src/sync/pull.py`: Add user_profile goals fields to pull sync
- `pwa/js/preferences.js`: Add goals text area section with save to user_profile

</code_context>

<specifics>
## Specific Ideas

- Goals are stable networking objectives, not transient requests — "What kind of reconnections are valuable to me?"
- The user gets external requests ("find me a marketing VP in fintech") but those need a matching/flagging mechanism, not scoring — deferred to lookouts feature
- Goals change triggers full rescore so the queue reflects updated priorities immediately
- Scoring rubric already has a 0-25 goal_alignment dimension — goals text makes this dimension dramatically more accurate vs the current generic `goals` field

</specifics>

<deferred>
## Deferred Ideas

- **Lookouts feature** (active requests matching/flagging) — user receives requests from others for contacts matching criteria (industry, title, description). Needs: structured lookout cards with criteria, contact matching engine, enrichment targeting for sparse profiles matching lookout criteria, flagging/surfacing matches in queue or dashboard. This is a substantial feature deserving its own phase.
- Enrichment targeting based on active criteria — prioritize enrichment budget for contacts matching specific needs
- Network search/query — "who in my network fits this request?"
- Signal analytics on dashboard (distribution, trends) — v1.3+ (SIG-09)
- Per-contact cadence override — v1.3+ (CAD-05)

</deferred>

---

*Phase: 09-goals-sync-and-pipeline-intelligence*
*Context gathered: 2026-03-12*
