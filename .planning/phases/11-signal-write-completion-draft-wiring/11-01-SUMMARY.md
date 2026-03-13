---
phase: 11-signal-write-completion-draft-wiring
plan: "01"
subsystem: pwa-queue, pipeline-cadence, draft-tone
tags: [signal-write, cadence, postgrest, tdd, pers-05, cad-02]
requirements: [PERS-05, CAD-02]

dependency_graph:
  requires:
    - Phase 10 Plan 01: SIGNAL_TONE_CONFIG in draft Edge Function (complete)
    - Phase 09: _get_cadence_expired_candidates() in queue_generator.py (complete)
    - Phase 07: SIGNAL_ACTIONS const in pwa/js/queue.js (complete)
  provides:
    - outreach_queue.signal written at signal-assignment time (PERS-05)
    - connections.cadence_due_at written at signal-assignment time (CAD-02)
  affects:
    - supabase/functions/draft/index.ts — SIGNAL_TONE_CONFIG branches now reachable
    - src/pipeline/queue_generator.py — _get_cadence_expired_candidates() now returns populated contacts

tech_stack:
  added: []
  patterns:
    - "PostgREST UPDATE with cadenceDueAt computed from SIGNAL_ACTIONS[signal].cadence (null-guarded)"
    - "Write ordering: all PostgREST writes complete before DOM mutation (ARCHIVE fade-out)"
    - "TDD: cadence query tests with SQLite in-memory (mirrors test_phase9_cadence.py pattern)"
    - "Data-driven tone-config completeness assertions (Python mirror of TypeScript SIGNAL_TONE_CONFIG)"

key_files:
  created:
    - tests/test_phase11_signal_write.py
  modified:
    - pwa/js/queue.js

decisions:
  - "Compute cadence_due_at in JS client using SIGNAL_ACTIONS[signal].cadence × 86400000ms — no server round-trip needed"
  - "cadenceDays null check uses !== null && !== undefined guard — prevents null×number=0 pitfall (Research pitfall 2)"
  - "ARCHIVE writes cadence_due_at: null explicitly — clears any existing value, prevents re-queuing"
  - "outreach_queue UPDATE keyed on itemId (not connectionId) — per Research pitfall 1"
  - "signal_context written as null (not empty string) — semantically correct per Research pitfall 5"
  - "Write 3 (outreach_queue) placed AFTER Write 2 (connections) and BEFORE ARCHIVE fade-out — per Research pitfall 6"

metrics:
  duration: "2m 22s"
  completed_date: "2026-03-13"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 11 Plan 01: Signal Write Completion + Draft Wiring Summary

**One-liner:** Two missing PostgREST writes added to `assignSignalFromCard()` — `connections.cadence_due_at` (cadence re-queuing) and `outreach_queue.signal` (signal-aware draft tone) — closing PERS-05 and CAD-02 end-to-end.

## What Was Built

Phase 11 Plan 01 is a surgical gap-closure: all downstream consumers of signal data (SIGNAL_TONE_CONFIG branches in the draft Edge Function, `_get_cadence_expired_candidates()` in the pipeline) were already implemented correctly. The only missing pieces were two PostgREST writes that `assignSignalFromCard()` in `pwa/js/queue.js` never made.

### Task 1: Test scaffold for signal write correctness and cadence end-to-end

Created `tests/test_phase11_signal_write.py` with 7 test cases across 3 test classes:

- **TestAssignSignalWrites** — Simulates post-write state: WARM_LEAD (cadence=7) expired contact returned by `_get_cadence_expired_candidates()`; ARCHIVE (cadence_due_at=None, user_priority='never') not returned.
- **TestCadenceEndToEnd** — Direct query validation: past-due returns, future-due excluded, archived-with-expired-cadence excluded.
- **TestDraftToneIntegration** — Data-driven completeness: all 6 non-ARCHIVE signals present in SIGNAL_TONE_CONFIG mirror with non-empty toneDirective; ARCHIVE sentinel value matches Edge Function guard string.

All 7 tests pass. Pattern follows `tests/test_phase9_cadence.py` (SQLite in-memory + SQLModel).

### Task 2: Add writes to assignSignalFromCard()

Edited `pwa/js/queue.js` `assignSignalFromCard()` function (lines 342-368):

1. **Cadence computation** — `const cadenceDueAt = (cadenceDays !== null && cadenceDays !== undefined) ? new Date(Date.now() + cadenceDays * 24 * 60 * 60 * 1000).toISOString() : null;`

2. **Extended Write 2** — Added `cadence_due_at: cadenceDueAt` to the `connections` UPDATE `updateData` object. ARCHIVE sets `cadence_due_at: null` explicitly (clears any existing value).

3. **New Write 3** — Added `outreach_queue` UPDATE after the connections UPDATE and before the ARCHIVE fade-out animation:
   ```javascript
   .from('outreach_queue')
   .update({ signal: signal, signal_context: null })
   .eq('id', itemId)
   ```

Write order: contact_signals INSERT → connections UPDATE (with cadence_due_at) → outreach_queue UPDATE (with signal) → ARCHIVE fade-out DOM mutation.

## Verification Results

- `pytest tests/test_phase11_signal_write.py -x -v` — 7/7 passed
- `pytest tests/ -x` — 169 passed, 9 skipped, 0 failures (no regressions)
- `grep -c "cadence_due_at" pwa/js/queue.js` — 3 (computation comment + update comment + updateData object)
- `grep -c "outreach_queue" pwa/js/queue.js` — 5 (includes existing fetch + realtime subscription)
- `grep -n "signal_context: null" pwa/js/queue.js` — line 365 confirmed
- Write order verified: connections UPDATE (line 355) → outreach_queue UPDATE (line 363) → ARCHIVE fade (line 370)

## Deviations from Plan

None — plan executed exactly as written.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Compute cadence_due_at in JS client | One-liner using SIGNAL_ACTIONS const; no server round-trip; avoids new Edge Function overhead |
| Explicit null guard: `!== null && !== undefined` | Prevents `null * 86400000 = 0` pitfall (ARCHIVE would get near-past timestamp) |
| outreach_queue keyed on itemId | Prevents updating ALL queue items for a connection if contact has multiple queue rows |
| signal_context: null (not '') | Semantically correct; prevents empty-string injection into draft prompt |
| Write 3 before ARCHIVE fade | Ensures all DB writes succeed before irreversible DOM mutation |

## Self-Check: PASSED

- `tests/test_phase11_signal_write.py` — FOUND (268 lines)
- `pwa/js/queue.js` — FOUND (modified: cadence_due_at + outreach_queue writes present)
- Task 1 commit `ac6d777` — FOUND
- Task 2 commit `8424a78` — FOUND
- Full test suite: 169 passed, 0 failures
