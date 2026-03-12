---
phase: 08-email-signal-ui-profile-content
plan: "03"
subsystem: pwa
tags: [profile, signals, notes, enrichment-fallback, contact-details]
requirements: [SIG-04, PROF-01, PROF-02, PROF-03]

dependency_graph:
  requires:
    - 07-01 (ContactSignal, ContactNote models + migration SQL)
    - 07-02 (push sync for contact_signals and contact_notes)
  provides:
    - Signal history UI on profile page
    - Contact notes UI (quick edit + timestamped history)
    - Key factors fallback from enrichment data
    - Conversation starters fallback from enrichment data
  affects:
    - pwa/js/contact.js (all profile page functionality)

tech_stack:
  added: []
  patterns:
    - PostgREST direct writes (anon grants) for contact_signals, contact_notes, connections
    - Async section builders returning HTML strings (same pattern as buildProfessionalContextSection)
    - Graceful fallback: empty string on fetch failure, no section on empty data

key_files:
  created: []
  modified:
    - pwa/js/contact.js

decisions:
  - "SIGNAL_ACTIONS guard: typeof SIGNAL_ACTIONS !== 'undefined' — safe when 08-02 not yet executed"
  - "Note UI uses textarea + two-button split: Save Note (quick update) vs Add to History (timestamped insert)"
  - "Fallback content reuses identical HTML structure as primary paths — consistent rendering"
  - "Signal history inserted after enrichment section, before draft section"

metrics:
  duration_minutes: 3
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
  completed_date: "2026-03-12"
---

# Phase 8 Plan 03: Profile Page Enhancements Summary

**One-liner:** Contact profile enhanced with PostgREST-backed signal history timeline, two-mode notes (quick edit + timestamped history), and enrichment-derived fallback content for key factors and conversation starters.

## Objective

Enhance the contact profile page so every contact shows meaningful, useful content regardless of enrichment completeness, and users can add their own context via notes and see the full triage signal history.

## Tasks Completed

### Task 1: Signal history and contact notes sections (commit: ce9efe7)

Added four new functions to `pwa/js/contact.js`:

- **`buildSignalHistorySection(connectionId)`** — async, fetches up to 20 signals from `contact_signals` table ordered by `assigned_at DESC`, renders as a flex-row timeline with signal badge (color from SIGNAL_ACTIONS if available, graceful default otherwise), date, assigned_by, and context
- **`buildNotesSection(connectionId, conn)`** — async, fetches up to 20 notes from `contact_notes` table, renders timestamped history plus a textarea pre-filled with `connections.notes` for quick editing
- **`saveQuickNote(connectionId)`** — updates `connections.notes` via PostgREST `.update()`, shows green/red border flash as visual feedback
- **`addTimestampedNote(connectionId)`** — inserts into `contact_notes` via PostgREST `.insert()`, clears textarea and re-renders the profile page

Both async sections are awaited in `renderContact()` and inserted after the enrichment section, before the draft section.

### Task 2: Key factors and conversation starters fallback (commit: c7de26c)

Modified key factors and conversation starters rendering in `renderContact()`:

- **Key factors fallback** — when `score_reasoning.key_factors` is empty, synthesizes from: `enrichment.headline`, industry (`company_industry` or `companyIndustry`), previous career step (`experiences[1]`), message count
- **Conversation starters fallback** — when `conversation_hooks` is empty, builds from: `enrichment.headline` framed as a question, current company from `experiences[0]`, `conversation_summary` truncated to 80 chars, industry topics
- Both use identical HTML structure as primary paths (consistent rendering)
- Empty enrichment = no section rendered (no empty boxes)

## Verification

All must-have checks pass:
- `grep -c "contact_signals" pwa/js/contact.js` = 1 (>= 1 required)
- `grep -c "contact_notes" pwa/js/contact.js` = 2 (>= 1 required)
- `grep -c "fallback" pwa/js/contact.js` = 17 (>= 2 required)
- `wc -l pwa/js/contact.js` = 514 (>= 250 required)
- Phase 7 + Phase 8 test suites: 65 passed, 7 skipped (all green)

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Items

- `tests/test_phase2_email.py::test_button_tap_targets` fails due to unstaged changes in `email_digest.py` from other in-progress work — pre-existing, unrelated to this plan's scope. Tracked as out-of-scope per deviation rules.

## Self-Check: PASSED

- FOUND: pwa/js/contact.js
- FOUND: .planning/phases/08-email-signal-ui-profile-content/08-03-SUMMARY.md
- FOUND commit: ce9efe7 (feat(08-03): add signal history and contact notes sections)
- FOUND commit: c7de26c (feat(08-03): add key factors and conversation starters fallback)
