---
phase: 02-email-reliability
plan: "02"
subsystem: api
tags: [supabase, edge-functions, deno, pwa, vanilla-js, email]
requirements_completed: [EMAIL-07, VIEW-04]

# Dependency graph
requires:
  - phase: 01-infrastructure-foundations
    provides: Netlify PWA deployment, Supabase Edge Functions, email digest pipeline

provides:
  - GET/POST split on action Edge Function (Gmail scanner cannot consume tokens)
  - Confirmation page on GET with mobile-friendly POST form
  - POST executes action and marks token used (existing logic preserved)
  - Approve success page with ?view=contact&id= deep link to PWA
  - PWA checkDeepLinkQueryParams() bridges ?view=contact&id=X to hash route #/contact/X
  - Edge Function deployed to Supabase production
  - PWA deployed to Netlify production

affects: [03-dashboard-and-ux, email-digest, action-tokens]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - GET-only for reads, POST for mutations on action Edge Function
    - Query parameter deep links (not hash fragments) survive Gmail redirect chain
    - history.replaceState + location.hash for clean URL after deep link bridge

key-files:
  created: []
  modified:
    - supabase/functions/action/index.ts
    - pwa/js/app.js

key-decisions:
  - "GET/POST split: GET returns confirmation page (zero side effects), POST executes action — prevents Gmail scanner token consumption"
  - "Token passed as query param in form action URL (not POST body) — Edge Function reads url.searchParams for both methods"
  - "Approve success page uses ?view=contact&id= deep link (not hash fragment) — survives Gmail redirect chain"
  - "checkDeepLinkQueryParams() runs before render() in DOMContentLoaded — returns true to skip double render via hashchange"

patterns-established:
  - "Edge Function GET handler: read-only (lookup + validation + confirmation page), zero database writes"
  - "Edge Function POST handler: execute action + mark token used"
  - "PWA startup: check query params before hash routing, clean URL with replaceState"

requirements-completed: [EMAIL-06, EMAIL-07, EMAIL-04]

# Metrics
duration: 3min
completed: 2026-03-09
---

# Phase 2 Plan 02: GET/POST Split and PWA Deep Link Bridge Summary

**GET/POST split on action Edge Function blocks Gmail scanner token consumption, plus PWA query-param deep link bridge converts email ?view=contact URLs to hash routes**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-09T01:19:07Z
- **Completed:** 2026-03-09T01:22:01Z
- **Tasks:** 2 of 3 complete (Task 3 is checkpoint:human-verify, awaiting human)
- **Files modified:** 2

## Accomplishments
- Action Edge Function now branches on req.method: GET returns confirmation HTML page (no DB writes), POST executes action and marks token used
- confirmationPageResponse() renders mobile-friendly form with action-specific button labels and a cancel link
- Approve POST success page includes a ?view=contact&id= deep link so users can view the contact in the PWA
- PWA checkDeepLinkQueryParams() reads window.location.search on startup, converts ?view=contact&id=X to #/contact/X route via replaceState, prevents double render
- Edge Function deployed to Supabase production (dxaewlecrkcttfziguer)
- PWA deployed to Netlify production (https://eg-connect.netlify.app)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add GET/POST split to action Edge Function** - `d3772d4` (feat)
2. **Task 2: Add PWA deep link query parameter bridge** - `90dc6fa` (feat)
3. **Task 3: Verify Edge Function and deep link in production** - awaiting human-verify

## Files Created/Modified
- `supabase/functions/action/index.ts` - Rewritten with GET/POST branching, confirmationPageResponse(), updated htmlResponse() with optional deep link
- `pwa/js/app.js` - Added checkDeepLinkQueryParams() function, updated DOMContentLoaded handler

## Decisions Made
- Token is passed as a query parameter in the form's `action` attribute URL (not in POST body). The Edge Function reads `url.searchParams.get('token')` for both GET and POST — this is the simplest approach that requires no form input fields.
- GET branch does zero database writes — all side effects (queue updates, token marking) are exclusively in the POST branch.
- checkDeepLinkQueryParams() returns true when it handles a deep link, telling the DOMContentLoaded handler to skip render() since the hashchange event will trigger it automatically.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test `test_profile_link_uses_query_params` uses a module-level `settings` import in `email_digest.py` that bypasses monkeypatching. This was present before this plan's changes and is tracked as a pre-existing issue. The test passes when email_digest.py uses `get_settings()` at call time (which is a fix scheduled in another plan).

## User Setup Required
- PWA_URL secret was already set in Supabase (`supabase secrets list` confirmed)
- Edge Function deployed with `--no-verify-jwt` (required for email link access without auth headers)

## Next Phase Readiness
- GET/POST split is live in production — Gmail scanner GET requests will now show a confirmation page instead of consuming tokens
- PWA deep link bridge is live — ?view=contact&id=X URLs from emails will navigate to the correct contact page
- Ready for Phase 3 (Dashboard and UX)

---
*Phase: 02-email-reliability*
*Completed: 2026-03-09*
