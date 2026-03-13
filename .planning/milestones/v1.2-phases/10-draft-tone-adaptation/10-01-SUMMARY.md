---
phase: 10-draft-tone-adaptation
plan: "01"
subsystem: api
tags: [openai, edge-functions, deno, prompt-engineering, supabase]

# Dependency graph
requires:
  - phase: 08-email-signal-ui-profile-content
    provides: outreach_queue.signal field populated by signal assignment
  - phase: 09-queue-intelligence
    provides: user_profile.current_projects field for WARM_LEAD/SYNERGY goals context

provides:
  - Signal-aware buildDraftPrompt() with 7 tone branches in draft Edge Function
  - ARCHIVE guard returning 400 before reaching OpenAI
  - SIGNAL_TONE_CONFIG map keyed by all 7 signal names
  - Null-signal fallback for backward compatibility with unsignaled queue items

affects: [11-draft-pwa-gate, pwa-draft-ui, future-tone-iteration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Signal-to-config map pattern: SIGNAL_TONE_CONFIG keyed by signal name with toneDirective, includeUserGoals, emphasizeContactData"
    - "Graceful null-signal fallback: toneConfig = signal ? SIGNAL_TONE_CONFIG[signal] : null; then toneDirective = toneConfig?.toneDirective || generic"
    - "Goals combining pattern: [profile?.current_projects, profile?.goals].filter(Boolean).join('\\n').trim() || fallback"

key-files:
  created: []
  modified:
    - supabase/functions/draft/index.ts

key-decisions:
  - "ARCHIVE guard placed after queueItem fetch, before connection fetch — server-side belt-and-suspenders per CONTEXT.md decision"
  - "SIGNAL_TONE_CONFIG as module-level const (not inside function) — readable and extensible without per-call allocation"
  - "Null signal falls back to generic 'Be genuine, not salesy' directive — backward compatibility for any unsignaled queue items in production"
  - "Signal/signalContext passed as explicit parameters (not read from closure) — pure function, easy to test"
  - "userGoalsSection and enrichmentEmphasis conditionally inserted in prompt body — structural adaptation, not just appended label"

patterns-established:
  - "Signal tone branching: use SIGNAL_TONE_CONFIG[signal] lookup with null fallback, never hard-code per-signal if/else chains"
  - "Goals context: always combine current_projects + goals with filter(Boolean); never rely on either field alone"

requirements-completed: [PERS-05]

# Metrics
duration: 2min
completed: 2026-03-13
---

# Phase 10 Plan 01: Draft Tone Adaptation Summary

**Signal-aware buildDraftPrompt() with 7 differentiated tone branches, ARCHIVE guard, and conditional user-goals/enrichment injection in the draft Edge Function**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-13T02:53:30Z
- **Completed:** 2026-03-13T02:55:30Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added `SIGNAL_TONE_CONFIG` — module-level record mapping all 7 signals to `toneDirective`, `includeUserGoals`, and `emphasizeContactData`
- Added ARCHIVE guard after queueItem fetch, returning 400 before any OpenAI call
- Extended `buildDraftPrompt()` to accept `signal` and `signalContext` parameters and branch prompt tone accordingly
- WARM_LEAD and SYNERGY prompts include a `userGoalsSection` weaving in `current_projects` + `goals` naturally
- VALUE_DROP prompts include an `enrichmentEmphasis` block grounded in contact industry, skills, and about snippet
- Null signal falls back gracefully to generic "Be genuine, not salesy" directive (backward compatibility)
- Updated call site to pass `queueItem.signal || null` and `queueItem.signal_context || null`

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ARCHIVE guard and signal-aware prompt branching to Edge Function** - `d8cb4bc` (feat)

**Plan metadata:** (see final commit below)

## Files Created/Modified
- `supabase/functions/draft/index.ts` - Added SIGNAL_TONE_CONFIG, ARCHIVE guard, extended buildDraftPrompt() with signal/signalContext params and conditional prompt sections

## Decisions Made
- ARCHIVE guard placed immediately after queueItem fetch, before the connection/profile fetches — avoids unnecessary DB reads for archived contacts
- SIGNAL_TONE_CONFIG defined as module-level const for readability and zero per-call allocation overhead
- Null signal produces a reasonable generic message matching prior behavior — no breaking change for any queue items created before Phase 8 signal assignment
- `signal_context` (optional freeform context from triage) appended as an "Additional context" note when present — gives the LLM extra signal without making it required

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None — the verification command in the plan used an escaped `\!` that failed in shell context; ran equivalent inline Node.js check directly. All 9 done criteria passed.

## User Setup Required
None — no new environment variables or external services. The Edge Function must be deployed to Supabase for changes to take effect (`supabase functions deploy draft`), but no manual configuration steps are required beyond that.

## Next Phase Readiness
- Edge Function is ready with all 7 tone branches and the ARCHIVE guard
- Plan 02 (PWA signal gate + draft badge) can proceed: `conn.latest_signal` is available in the PWA contact page and the signal badge patterns are documented in RESEARCH.md
- The draft Edge Function is backward compatible — no urgent migration needed for existing unsignaled queue items

---
*Phase: 10-draft-tone-adaptation*
*Completed: 2026-03-13*
