---
phase: 09-goals-sync-and-pipeline-intelligence
plan: 01
subsystem: goals-sync-pipeline
tags: [goals, scoring, pull-sync, rescore-trigger, pwa, pipeline]
dependency_graph:
  requires: []
  provides: [goals-ui, scoring-prompt-goals, pull-sync-user-profile, rescore-trigger]
  affects: [pwa/js/preferences.js, src/llm/scoring.py, src/sync/pull.py, src/pipeline/daily_pipeline.py]
tech_stack:
  added: []
  patterns: [PostgREST direct write, cloud-wins-if-newer sync, batch-clear with limit]
key_files:
  created:
    - tests/test_phase9_goals_scoring.py
  modified:
    - pwa/js/preferences.js
    - src/llm/scoring.py
    - src/sync/pull.py
    - src/pipeline/daily_pipeline.py
decisions:
  - "Goals text area writes to user_profile.current_projects via PostgREST (same pattern as signals/notes)"
  - "Pull sync does NOT update local updated_at when pulling goals from cloud (avoids sync loop)"
  - "Rescore trigger uses UserPreference pref_type='rescore_trigger' row written by PWA on goals save"
  - "Batch limit of 10 contacts cleared per pipeline run for gradual rescoring"
  - "goals_structured JSON column reserved for future lookouts feature — not exposed in UI"
metrics:
  duration_minutes: 3
  completed_date: "2026-03-12"
  tasks_completed: 3
  files_modified: 4
  files_created: 1
---

# Phase 9 Plan 01: Goals Sync and Pipeline Intelligence Summary

**One-liner:** Goals text area on Preferences page syncs to user_profile.current_projects via PostgREST, appears in LLM scoring prompt, and triggers batch rescoring of existing contacts when updated.

## What Was Built

### Task 1: Goals in scoring prompt + pull sync + tests

Extended `build_scoring_prompt()` in `src/llm/scoring.py` to include `current_projects` (truncated at 500 chars) as a new "Current projects & focus" line in the user context block. Added section 8 to `pull_from_cloud()` in `src/sync/pull.py` to fetch `user_profile.current_projects` and `goals_structured` from cloud when cloud row is newer than local — without updating `local.updated_at` to avoid sync loops. Added `UserProfile` to pull.py imports and `user_profile_updated` to stats.

### Task 2: Goals text area UI on PWA Preferences page

Added a "Your Networking Goals" section at the top of `renderPreferences()` in `pwa/js/preferences.js`. Fetches `user_profile.current_projects` to pre-populate the textarea. New `saveGoals()` function writes to `user_profile.current_projects` via PostgREST and upserts a `rescore_trigger` UserPreference row (`id='rescore-goals-trigger'`, `pref_type='rescore_trigger'`, `pref_key='goals_updated_at'`). Shows "Saved!" confirmation for 1.5s.

### Task 3: Pipeline rescore trigger check before prescore step

Inserted Step 2b into `run_daily_pipeline()` between profile_update and prescore. Queries for `UserPreference` with `pref_type="rescore_trigger"` and `pref_key="goals_updated_at"`. When found: batch-clears `scored_at` on up to 10 contacts scored before the trigger timestamp. Deletes the trigger row when no more stale contacts remain. Non-fatal (exceptions logged as warnings).

## Verification

All 15 tests in `tests/test_phase9_goals_scoring.py` pass:
- `TestScoringPrompt` (4 tests): current_projects in prompt, 500-char truncation, None fallback, existing fields preserved
- `TestPullSyncGoals` (5 tests): goals pulled when cloud newer, updated_at not changed, local wins when local newer, source inspection checks
- `TestRescoreTrigger` (6 tests): batch clear, 10-contact limit, trigger deleted when all rescored, trigger preserved when more remain, no-op when no trigger, source inspection

## Deviations from Plan

None — plan executed exactly as written.

## Key Decisions

1. Goals text area writes to `user_profile.current_projects` via PostgREST direct write — same pattern as signals/notes from Phase 8
2. Pull sync does NOT update `local.updated_at` when pulling goals from cloud — avoids push sync loop (research pitfall 5)
3. Rescore trigger uses UserPreference row (`pref_type='rescore_trigger'`) written by PWA on goals save — clean separation of concerns
4. Batch limit of 10 contacts cleared per pipeline run — gradual rescoring preserves pipeline performance
5. `goals_structured` JSON column reserved for future lookouts feature — not exposed in this UI

## Self-Check

Files verified:
- `tests/test_phase9_goals_scoring.py` — created ✓
- `pwa/js/preferences.js` — modified ✓
- `src/llm/scoring.py` — modified ✓
- `src/sync/pull.py` — modified ✓
- `src/pipeline/daily_pipeline.py` — modified ✓

## Self-Check: PASSED

All 5 modified/created files exist on disk. All 4 task commits found in git log:
- 6f72b81: test(09-01) — RED phase tests
- dc1f8e4: feat(09-01) — scoring prompt + pull sync
- b54e86f: feat(09-01) — PWA goals UI
- 5ca63bb: feat(09-01) — pipeline rescore trigger
