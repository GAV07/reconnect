---
phase: 02-email-reliability
verified: 2026-03-08T00:00:00Z
status: human_needed
score: 7/9 must-haves verified (2 require human)
gaps:
human_verification:
  - test: "Open digest email in Gmail on iOS or Android — confirm contact name and score badge appear side-by-side (not stacked)"
    expected: "Card header shows name/role on left, score badge on right in a two-column layout"
    why_human: "Gmail mobile strips <style> blocks; table layout must be verified in a real Gmail client — no emulator faithfully reproduces Gmail mobile rendering"
  - test: "Visit an action URL directly in the browser (e.g. from a test token). Confirm: (1) you see a confirmation page with a form button, NOT 'Done!' immediately. (2) Clicking the button shows the success page. (3) For 'Yes' approve action, success page shows a 'View Contact' link to ?view=contact&id=X."
    expected: "GET returns confirmation HTML page. POST executes action and returns success page with deep link."
    why_human: "Edge Function is deployed to Supabase production (Deno TypeScript); not covered by pytest. Task 3 of plan 02-02 is an explicit human-verify checkpoint."
---

# Phase 02: Email Reliability Verification Report

**Phase Goal:** Email actions work correctly in Gmail on mobile and desktop without trust-breaking failures
**Verified:** 2026-03-08
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

The phase goal requires email layout, action token handling, and deep links to work correctly in Gmail. The automated implementation is complete and verified. Two items require human confirmation in a real Gmail environment.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Email card header renders name and score side-by-side using table layout, not flexbox | VERIFIED | `email_digest.py:219` — `<table role="presentation" width="100%">` with two `<td>` cells; `test_card_layout_uses_table` passes |
| 2 | Action buttons have 44px+ tap targets (12px+ padding) and 16px+ font size | VERIFIED | `email_digest.py:206-208` — all action buttons have `padding:12px 20px;font-size:16px`; `test_button_tap_targets` passes |
| 3 | View Profile link uses query parameters (?view=contact&id=X), not hash fragments | VERIFIED | `email_digest.py:178` — `profile_url = f"{pwa_base}/?view=contact&id={conn.id}"`; `test_profile_link_uses_query_params` passes |
| 4 | LinkedIn button appears in action row when linkedin_url is set | VERIFIED | `email_digest.py:181-188` — conditional `linkedin_cell` rendered only when `linkedin_url` is truthy; `test_linkedin_button_in_card` passes |
| 5 | LinkedIn button does NOT appear when linkedin_url is empty | VERIFIED | `email_digest.py:181-182` — `if linkedin_url:` guard; `test_linkedin_button_in_card` passes (negative case) |
| 6 | GET request to action Edge Function shows confirmation page, does NOT execute the action or mark the token used | VERIFIED (code) / ? HUMAN | `action/index.ts:69-71` — GET branch calls `confirmationPageResponse()` only; no `.update()` or `.insert()` in GET branch. Requires live browser test. |
| 7 | POST request to action Edge Function validates the token, executes the action, marks it used, and shows a success page | VERIFIED (code) / ? HUMAN | `action/index.ts:74-147` — POST executes action, marks token used at line 136-139. Requires live browser test. |
| 8 | Opening a PWA URL with ?view=contact&id=123 navigates to the #/contact/123 hash route | VERIFIED | `pwa/js/app.js:108-119` — `checkDeepLinkQueryParams()` reads `window.location.search`, calls `history.replaceState()` and sets `window.location.hash = /contact/${id}` |
| 9 | Gmail card layout appears correctly in real Gmail mobile client (name/score side-by-side) | ? HUMAN | Table layout is implemented correctly in source, but Gmail mobile rendering can only be confirmed by sending a real email |

**Score:** 7/9 truths verified automatically; 2 require human confirmation in production

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_phase2_email.py` | Unit tests for email HTML output | VERIFIED | All 5 tests pass: `test_card_layout_uses_table`, `test_button_tap_targets`, `test_profile_link_uses_query_params`, `test_linkedin_button_in_card`, `test_no_flexbox_anywhere` |
| `src/integrations/email_digest.py` | Table-based email card layout with proper buttons and links | VERIFIED | Contains `role="presentation"` tables at lines 204, 219; no `display:flex` or `justify-content` anywhere in the file; buttons have `padding:12px`; profile URL uses `?view=contact&id=` |
| `supabase/functions/action/index.ts` | GET/POST split action handler with confirmation page | VERIFIED | `req.method` branched at lines 14, 69, 74; GET handler is read-only (zero `.update()`/`.insert()` in GET branch); POST executes action and marks token used; `confirmationPageResponse()` function exists at line 157 |
| `pwa/js/app.js` | Query parameter deep link bridge | VERIFIED | `checkDeepLinkQueryParams()` function at line 108; reads `window.location.search`; calls `history.replaceState()`; called before `render()` in `DOMContentLoaded` handler at line 125 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/integrations/email_digest.py` | `settings.pwa_url` | `profile_url = f"{pwa_base}/?view=contact&id={conn.id}"` | WIRED | Line 177-178: `pwa_base = settings.pwa_url.rstrip("/")` then `profile_url = f"{pwa_base}/?view=contact&id={conn.id}"` |
| `src/integrations/email_digest.py` | `conn.linkedin_url` | LinkedIn button conditional rendering | WIRED | Lines 181-188: `if linkedin_url:` guard with full `<a>` cell rendered |
| `supabase/functions/action/index.ts` | `supabase.from('action_tokens')` | GET reads token (no update), POST marks used | WIRED | GET: `.select("*")` only at line 32; POST: `.update({ used: true })` at line 136-139; no writes in GET branch |
| `supabase/functions/action/index.ts` | `PWA_URL` | Deep link in confirmation/success pages | WIRED | Line 89-91: approve success builds `${pwaUrl}/?view=contact&id=${connectionId}`; passed to `htmlResponse` as `viewContactLink` |
| `pwa/js/app.js` | `window.location.search` | Reads query params on startup, converts to hash route | WIRED | Line 109: `new URLSearchParams(window.location.search)`; line 114-115: `history.replaceState` + `window.location.hash` assignment |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| EMAIL-02 | 02-01-PLAN.md | Email card layout uses table-based HTML (not Flexbox) for Gmail mobile compatibility | SATISFIED | `role="presentation"` tables at lines 204, 219 of `email_digest.py`; zero `display:flex` in file; `test_card_layout_uses_table` passes |
| EMAIL-03 | 02-01-PLAN.md | Email action buttons are 44px+ tap targets with 16px+ font | SATISFIED | All action buttons: `padding:12px 20px;font-size:16px` at lines 206-208; feedback buttons: `padding:12px 14px;font-size:16px` at line 279; `test_button_tap_targets` passes |
| EMAIL-04 | 02-01-PLAN.md, 02-02-PLAN.md | "View full profile" links use query parameters that survive Gmail's redirect chain | SATISFIED | `email_digest.py:178` builds `?view=contact&id=`; `action/index.ts:91` builds `?view=contact&id=`; `pwa/js/app.js:108-119` bridges to hash route |
| EMAIL-05 | 02-01-PLAN.md | "Open LinkedIn" direct link included per contact in email digest | SATISFIED | `email_digest.py:181-188` renders LinkedIn action button when `linkedin_url` set; `test_linkedin_button_in_card` passes |
| EMAIL-06 | 02-02-PLAN.md | "Yes" action auto-queues contact for outreach (no extra step needed) | SATISFIED (code) / ? HUMAN | `action/index.ts:79-87` — approve action sets `status: "approved"` in `outreach_queue`. Note: the GET/POST split (EMAIL-07) adds a confirmation step before execution. This deliberate design trade-off (security vs. friction) is acknowledged — REQUIREMENTS.md marks both EMAIL-06 and EMAIL-07 complete. Human should verify the confirmation flow feels acceptable. |
| EMAIL-07 | 02-02-PLAN.md | Action Edge Function uses GET/POST split — GET shows confirmation page, POST executes action | SATISFIED (code) / ? HUMAN | `action/index.ts:69-71` GET branch returns `confirmationPageResponse()`; `action/index.ts:74-147` POST branch executes and marks token; 405 returned at line 149-153 for other methods. Requires production browser test. |

**Requirement ID cross-check:**
- Phase prompt specifies: EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05, EMAIL-06, EMAIL-07
- 02-01-PLAN.md claims: EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05 — all verified
- 02-02-PLAN.md claims: EMAIL-06, EMAIL-07, EMAIL-04 — all verified (EMAIL-04 appears in both plans; both implementations contribute to the requirement)
- All 6 requirement IDs accounted for. No orphaned requirements.

**VIEW-04 note:** `pwa/js/app.js` implements the query-parameter deep link bridge (checkDeepLinkQueryParams), which satisfies VIEW-04 ("PWA reads query parameters on load"). VIEW-04 is formally mapped to Phase 3 in REQUIREMENTS.md, but the implementation was delivered in Phase 2 as part of the email deep link work. This is a beneficial early delivery, not a gap.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

No TODO/FIXME/placeholder patterns found in any phase 2 files. No stub implementations. No empty handlers. Full implementation present in all artifacts.

**Pre-existing test failure (not Phase 2 scope):** `tests/test_phase1_infra.py::test_netlify_toml` fails because commit `0c61753` (Phase 1 fix) added `command = "echo 'Static site - no build step'"` to `netlify.toml` after Phase 1 plan 01 was written. The test asserts `command` should not be in `netlify.toml`. This failure predates Phase 2 and is not caused by any Phase 2 change. The 5 Phase 2 tests all pass.

### Human Verification Required

**1. Real Gmail Mobile Card Layout**

**Test:** Send a live daily digest email and open it in Gmail on iOS or Android (not the web client).
**Expected:** Contact cards show name and score badge side-by-side (table layout). Buttons are large enough to tap comfortably. No broken/stacked layout.
**Why human:** Gmail mobile strips `<style>` blocks entirely — only inline styles survive. The table layout in `email_digest.py` uses inline styles correctly, but the only authoritative test is a real Gmail mobile client. No emulator or HTML renderer faithfully reproduces Gmail mobile's CSS stripping behavior.

**2. Edge Function GET/POST Split in Production**

**Test:** Find a valid action token URL (from a recent digest email or generate a test token via `src/api/tokens.py`). Visit the URL directly in a browser.
1. Confirm: you see a confirmation page (not "Done!" immediately) with a button labeled e.g. "Yes — Queue for Outreach"
2. Click the button — confirm: you see the success page ("Done!") with a "View Contact" link
3. Visit `https://eg-connect.netlify.app/?view=contact&id=<any-id>` — confirm: the URL bar changes to show `#/contact/<id>` and the contact page (or "not found") appears

**Expected:** GET shows confirmation form. POST executes action. PWA deep link navigates correctly.
**Why human:** The Edge Function is deployed to Supabase production (Deno TypeScript). Plan 02-02 includes an explicit `checkpoint:human-verify` gate (Task 3) awaiting human approval. No pytest coverage for Deno TypeScript.

### Gaps Summary

No gaps blocking goal achievement. All code changes are implemented and the 5 automated tests pass. Two behaviors require human confirmation in production:

1. Real Gmail mobile rendering of the table-based card layout (cannot be emulated programmatically)
2. Live Edge Function GET/POST split behavior (deployed to Supabase, awaiting human-verify checkpoint from Plan 02-02 Task 3)

The ROADMAP marks Phase 2 as "Complete (2026-03-09)" and REQUIREMENTS.md marks all 6 requirement IDs as checked. The human verification items are production acceptance tests, not gaps in the implementation.

---

_Verified: 2026-03-08_
_Verifier: Claude (gsd-verifier)_
