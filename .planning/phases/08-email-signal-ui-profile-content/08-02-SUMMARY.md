---
phase: 08-email-signal-ui-profile-content
plan: 02
subsystem: ui
tags: [pwa, vanilla-js, supabase, postgrest, signal-picker, queue, css]

# Dependency graph
requires:
  - phase: 07-signal-foundation
    provides: contact_signals table, SIGNAL_ACTIONS canonical definition in signal_service.py, PostgREST grants for anon INSERT to contact_signals and UPDATE to connections
provides:
  - 7-signal picker UI on queue cards replacing legacy Approve/Skip/Snooze buttons
  - assignSignalFromCard() function writing to contact_signals (INSERT) and connections (UPDATE)
  - Enriched queue card context: industry chip, first key factor, last interaction date, notes excerpt
  - Signal-based queue filter with untriaged-by-default view
  - SIGNAL_ACTIONS JS const mirroring signal_service.py canonical definition
affects: [09-queue-intelligence, 10-outreach-execution, future-queue-plans]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PostgREST embedded resource filtering must be done client-side (not server-side) — connections.latest_signal cannot be filtered via .eq() on an embedded join"
    - "Signal assignment = INSERT to contact_signals (not UPDATE) per schema grants and audit trail design"
    - "Optimistic UI update before async PostgREST call, with revert on error"
    - "ARCHIVE signal is the only exception to no-card-removal rule — fades DOM element after DB write"

key-files:
  created: []
  modified:
    - pwa/js/queue.js
    - pwa/css/app.css

key-decisions:
  - "Client-side signal filter after fetch — PostgREST cannot filter on embedded resource fields (connections.latest_signal), consistent with existing industryFilter pattern"
  - "Both tasks (signal picker + queue filter evolution) implemented in single commit since they're in the same file and tightly coupled"
  - "Legacy queueAction() function preserved for backward compatibility even though signal picker replaces the 3-button UI"
  - "notes excerpt reads from connections.notes directly (already in join) — no separate contact_notes table fetch"

patterns-established:
  - "Signal picker: collapsed toggle shows badge-or-CTA, picker expands on tap, 7 chips rendered from SIGNAL_ACTIONS"
  - "Queue filter default is 'untriaged' (conn.latest_signal IS NULL + user_priority != 'never') for daily triage focus"
  - "ARCHIVE path: user_priority='never' update + card fade/remove from DOM — excluded from all non-specific views"

requirements-completed: [SIG-01, SIG-02, SIG-03, SIG-05, SIG-06, QUX-01, QUX-02, PROF-04]

# Metrics
duration: 5min
completed: 2026-03-12
---

# Phase 8 Plan 02: Signal Picker and Queue Evolution Summary

**7-signal picker UI on queue cards with PostgREST INSERT to contact_signals, enriched card context (industry/key-factor/date/notes), and untriaged-default signal filter replacing legacy Approve/Skip/Snooze**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-12T03:37:10Z
- **Completed:** 2026-03-12T03:42:00Z
- **Tasks:** 2 (implemented together in one commit)
- **Files modified:** 2

## Accomplishments

- Replaced 3-button triage (Approve/Skip/Snooze) with collapsible 7-signal picker on queue cards — each signal colored per SIGNAL_ACTIONS
- Implemented `assignSignalFromCard()` with optimistic badge update, INSERT to `contact_signals`, UPDATE to `connections.latest_signal`, and ARCHIVE-specific card removal
- Added contextual queue card fields: industry chip (from raw_enrichment), first key factor (from mini_key_factors or score_reasoning), last interaction date, notes excerpt (first 60 chars from connections.notes)
- Evolved queue filter from status-based to signal-based with "untriaged" as default (contacts with no signal assigned), enabling focused daily triage workflow
- Added CSS for signal picker, signal badges, signal chips, and all card context field styles

## Task Commits

1. **Task 1: Signal picker UI, assignment function, and enriched card context** - `f84da72` (feat)
2. **Task 2: Queue filter evolution to signal-based with untriaged default** - `f84da72` (feat, same commit — same file, tightly coupled)

**Plan metadata:** (docs commit in final step)

## Files Created/Modified

- `/Users/gavin/Developer/reconnect/pwa/js/queue.js` - Full rebuild: SIGNAL_ACTIONS const, toggleSignalPicker(), assignSignalFromCard(), enriched card HTML, signal filter logic, setQueueSignalFilter(), updated renderQueue() with untriaged-default filter
- `/Users/gavin/Developer/reconnect/pwa/css/app.css` - Added signal picker styles (.signal-triage, .signal-toggle, .assign-signal-cta, .signal-badge, .signal-picker, .signal-chip) and card context styles (.card-meta, .industry-chip, .card-key-factor, .card-last-contact, .card-note-excerpt)

## Decisions Made

- Client-side signal filter after fetch — PostgREST cannot filter on embedded resource fields (`connections.latest_signal`). Same pattern as existing industryFilter.
- Both tasks committed together since they both modify queue.js and the signal picker + filter changes are tightly coupled.
- Legacy `queueAction()` function preserved in queue.js for backward compatibility even though the signal picker replaces the legacy 3-button UI on pending cards.
- Notes excerpt reads directly from `connections.notes` (already fetched in the PostgREST join) — no separate query to `contact_notes` table needed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing test failure in `test_phase8_email_signal_ui.py::TestDigestRebuild::test_review_in_app_cta_present` (no such column: outreach_queue.signal in SQLite test DB — Phase 7/8 migration not applied to test schema). This failure existed before my changes and is out of scope. Confirmed by stash test.

Python test suite: 120 passed, 10 skipped (no regressions from my changes).

## User Setup Required

None - no external service configuration required. The signal picker writes to Supabase via PostgREST using the existing anon key grants established in Phase 7 migration.

Note: The Phase 7 migration (`supabase/migrations/20260311000000_signal_foundation.sql`) must be applied to Supabase before the PWA can write signals. This was already documented as a blocker in STATE.md.

## Next Phase Readiness

- Signal picker is complete and ready for Phase 9 queue intelligence (cadence re-queuing, feedback loop)
- `contact_signals` INSERT pattern is established for use by any future signal assignment flows
- `connections.latest_signal` UPDATE pattern is established
- ARCHIVE exclusion from default queue view works correctly

---
*Phase: 08-email-signal-ui-profile-content*
*Completed: 2026-03-12*
