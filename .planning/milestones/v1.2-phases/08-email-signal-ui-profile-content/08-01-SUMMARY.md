---
phase: 08-email-signal-ui-profile-content
plan: "01"
subsystem: email-digest
tags: [email, pwa, deep-link, tdd, phase8]
dependency_graph:
  requires: []
  provides: [email-digest-rebuilt, phase8-test-scaffold, queue-deep-link]
  affects: [src/integrations/email_digest.py, pwa/js/app.js, tests/test_phase8_email_signal_ui.py]
tech_stack:
  added: []
  patterns: [tdd-red-green, mock-injection, query-param-deep-link]
key_files:
  created:
    - tests/test_phase8_email_signal_ui.py
  modified:
    - src/integrations/email_digest.py
    - pwa/js/app.js
    - tests/test_phase2_email.py
decisions:
  - "Gmail functions patched at source module (src.integrations.gmail.*) since they are imported inside send_digest_email(), not at module level"
  - "CTA button uses padding:14px 32px (>= 12px tap target) — Phase 2 test updated to reflect this"
  - "_get_data_health_stats() and _get_skip_pattern_insight() kept in file but no longer called — backward compat"
metrics:
  duration: "4m 11s"
  completed: 2026-03-12
  tasks_completed: 2
  files_changed: 4
---

# Phase 8 Plan 01: Email Digest Rebuild and Deep Link Fix Summary

Email digest rebuilt as a morning briefing with single "Review in App" CTA (?view=queue deep link), industry chips on featured cards, profile deep links, and no per-contact action buttons or data health/feedback sections; full Phase 8 test scaffold created with TDD.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Phase 8 test scaffold (failing) | 44e127b | tests/test_phase8_email_signal_ui.py |
| 1 (GREEN) | Email digest rebuild + test fixes | 7aca406 | src/integrations/email_digest.py, tests/test_phase8_email_signal_ui.py, tests/test_phase2_email.py |
| 2 | ?view=queue deep link in PWA | 3da70b5 | pwa/js/app.js |

## What Was Built

### Email Digest Rebuild (src/integrations/email_digest.py)

Rebuilt `_build_digest_html()` to transform email from action surface to morning briefing:

**Removed:**
- `from src.api.tokens import create_action_tokens, create_feedback_token` import
- Per-contact Approve/Skip/Snooze action button table (was ~20 lines of token-based HTML)
- Data health section ("Your Network Data" — `_get_data_health_stats()` calls)
- Feedback star rating ("Was today's digest useful?" — `create_feedback_token()` calls)

**Added:**
- Industry chip per featured card: `raw_enrichment.data.company_industry` or `raw_enrichment.company_industry`
- "Review in App" CTA button: `padding:14px 32px`, `background:#0a66c2`, links to `?view=queue`
- Profile name links to PWA profile page via `?view=contact&id=` (not LinkedIn URL)
- LinkedIn shown as small text link below role/company (not a button)
- PWA link updated from `/#/queue` (hash, stripped by Gmail) to `/?view=queue` (query param, survives)

**Preserved:**
- `_get_digest_contacts()`, `_extract_why_today()`, `send_digest_email()` signatures unchanged
- `_get_data_health_stats()`, `_get_skip_pattern_insight()` functions remain (not called)
- Remaining contacts compact list
- Header with date, contact count, pipeline stats line
- Footer with "Sent by Reconnect" and "Open app" link

### Phase 8 Test Scaffold (tests/test_phase8_email_signal_ui.py)

336-line test file with full Phase 8 coverage structure:

**Active tests (12 passing):**
- `TestDigestRebuild::test_review_in_app_cta_present` — "Review in App" + ?view=queue in HTML
- `TestDigestRebuild::test_no_legacy_action_buttons` — Approve/Yes/Skip/Snooze absent
- `TestDigestRebuild::test_no_token_generation` — create_action_tokens/create_feedback_token not called
- `TestDigestRebuild::test_no_data_health_section` — "Your Network Data" absent
- `TestDigestRebuild::test_no_feedback_stars` — "Was today's digest useful?" absent
- `TestDigestRebuild::test_industry_in_featured_cards` — industry chip from nested raw_enrichment
- `TestDigestRebuild::test_industry_in_featured_cards_top_level` — industry chip from top-level
- `TestDigestRebuild::test_digest_subject_format` — "Reconnect Mar N: Name + N more" format
- `TestDigestRebuild::test_send_digest_email_returns_dict` — dict with sent/recipient/contacts
- `TestDigestRebuild::test_featured_cards_have_profile_deep_link` — ?view=contact&id= present
- `TestDigestRebuild::test_remaining_list_preserved` — compact list for > top_n contacts
- `TestPipelineWiring::test_telegram_wired` — Telegram import in daily_pipeline.py

**Future stubs (10 skipped):**
- `TestSignalWrite` (Plan 02), `TestQueueCardContext` (Plan 02)
- `TestProfileFallback`, `TestNoteWrite` (Plan 03)
- `TestPullSync` (Plan 04 / wave 1)

### PWA Deep Link Fix (pwa/js/app.js)

Added `?view=queue` handler to `checkDeepLinkQueryParams()`:
```javascript
if (view === 'queue') {
  history.replaceState(null, '', window.location.pathname);
  window.location.hash = '/queue';
  return true;
}
```

## Verification Results

```
python -m pytest tests/test_phase8_email_signal_ui.py -k "TestDigestRebuild or TestPipelineWiring"
  12 passed, 7 deselected

python -m pytest tests/ -q
  120 passed, 10 skipped

grep -c "create_action_tokens\|create_feedback_token" src/integrations/email_digest.py
  0  (PASS)

grep -c "Review in App" src/integrations/email_digest.py
  4  (PASS)

grep -c "view=queue" src/integrations/email_digest.py
  3  (PASS)

grep -c "view === 'queue'" pwa/js/app.js
  1  (PASS)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Gmail functions patched at wrong module**
- **Found during:** Task 1 GREEN — test_digest_subject_format and test_send_digest_email_returns_dict failing
- **Issue:** Tests patched `src.integrations.email_digest.is_oauth_configured` etc., but those functions are imported inside `send_digest_email()` body, not at module level. mocker.patch requires the attribute to exist on the target module.
- **Fix:** Changed patches to `src.integrations.gmail.is_oauth_configured`, `src.integrations.gmail.get_user_email`, `src.integrations.gmail.send_html_email` — where the functions actually live.
- **Files modified:** tests/test_phase8_email_signal_ui.py
- **Commit:** 7aca406

**2. [Rule 1 - Bug] Phase 2 tap target test failed after action button removal**
- **Found during:** Task 1 GREEN — regression in tests/test_phase2_email.py::test_button_tap_targets
- **Issue:** Phase 2 test checked for `padding:12px` from per-contact action buttons. After removing those buttons in Phase 8, the assertion failed. The CTA uses `padding:14px 32px` (which meets the >= 12px tap target requirement).
- **Fix:** Updated `test_button_tap_targets` to check for `padding:14px` on the CTA button instead. Preserved the intent (tap target compliance) while reflecting the Phase 8 email structure.
- **Files modified:** tests/test_phase2_email.py
- **Commit:** 7aca406

## Self-Check: PASSED

Files exist:
- tests/test_phase8_email_signal_ui.py: FOUND
- src/integrations/email_digest.py: FOUND (rebuilt)
- pwa/js/app.js: FOUND (updated)

Commits exist:
- 44e127b (RED test scaffold): FOUND
- 7aca406 (GREEN rebuild): FOUND
- 3da70b5 (PWA deep link): FOUND
