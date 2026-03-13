---
phase: 10-draft-tone-adaptation
plan: 02
subsystem: ui
tags: [pwa, vanilla-js, css, signal-gate, tone-badge, draft]

# Dependency graph
requires:
  - phase: 08-email-signal-ui-profile-content
    provides: SIGNAL_ACTIONS const and signal-badge CSS class in queue.js/app.css
  - phase: 10-draft-tone-adaptation
    provides: Phase 10-01 CONTEXT.md decision to hide draft for ARCHIVE contacts
provides:
  - Signal gate in contact.js draft section (ARCHIVE=hidden, null=nudge, valid=generate)
  - SIGNAL_TONE_TOOLTIPS constant with tone descriptions for 6 active signals
  - draft-tone-badge CSS class for badge wrapper with help cursor
  - draft-no-signal CSS class for centered muted nudge styling
affects: [10-03-PLAN, supabase/functions/draft]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "typeof SIGNAL_ACTIONS guard pattern (established Phase 08-03) reused for badge injection"
    - "Three-way signal gate: ARCHIVE=empty, null=nudge, valid=generate"

key-files:
  created: []
  modified:
    - pwa/js/contact.js
    - pwa/css/app.css

key-decisions:
  - "ARCHIVE contacts produce empty draftHtml — draft section hidden entirely, not disabled"
  - "No-signal nudge is a static message, not a link — user must go to queue to assign signal"
  - "Badge injection uses typeof SIGNAL_ACTIONS guard (queue.js loaded separately)"

patterns-established:
  - "Signal gate pattern: check ARCHIVE first, then null, then valid — matches CONTEXT.md decision order"
  - "Badge area div pre-rendered in HTML, populated by JS after successful API response"

requirements-completed: [PERS-05]

# Metrics
duration: 2min
completed: 2026-03-13
---

# Phase 10 Plan 02: Signal Gate and Tone Badge Summary

**Three-way signal gate in PWA draft section: ARCHIVE hides draft entirely, unsignaled contacts see a nudge, valid signals show a generate button that injects a colored tone badge after draft generation.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-13T02:53:36Z
- **Completed:** 2026-03-13T02:55:15Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- ARCHIVE contacts no longer see any draft section — enforces triage-first workflow
- Unsignaled contacts see "Assign a signal for a tailored draft" nudge instead of a broken generate button
- Valid-signal contacts see a generate button that passes signal to `generateDraft()`
- After successful draft generation, a colored signal badge with tooltip appears above the textarea
- `SIGNAL_TONE_TOOLTIPS` const provides tone descriptions for all 6 active signals

## Task Commits

Each task was committed atomically:

1. **Task 1: Add signal gate and tone badge to PWA draft section** - `30afaeb` (feat)
2. **Task 2: Add CSS styles for draft tone badge and no-signal nudge** - `de8b719` (feat)

**Plan metadata:** `(see final commit)` (docs: complete plan)

## Files Created/Modified
- `pwa/js/contact.js` - Signal gate in renderContact(), badge injection in generateDraft(), SIGNAL_TONE_TOOLTIPS const
- `pwa/css/app.css` - .draft-tone-badge and .draft-no-signal CSS classes

## Decisions Made
- ARCHIVE check is at the outermost level of the `if (queueItemId)` block — covers the edge case where an ARCHIVE contact arrives with a queue_item URL param
- No-signal nudge is plain text (not a link) — keeps the UI simple; user navigates back to queue to assign signal via the signal picker
- Badge uses `typeof SIGNAL_ACTIONS !== 'undefined'` guard — established Phase 08-03 pattern for safety when queue.js loads separately

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Signal gate and tone badge UI complete — ready for Phase 10-03 (Edge Function signal-aware prompt)
- The `generateDraft()` call to the Edge Function still sends only `queue_item_id`; the Edge Function will need to look up `latest_signal` from the queue item to adapt the prompt (10-03 scope)

---
*Phase: 10-draft-tone-adaptation*
*Completed: 2026-03-13*
