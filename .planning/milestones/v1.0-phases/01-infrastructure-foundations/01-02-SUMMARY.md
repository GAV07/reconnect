---
phase: 01-infrastructure-foundations
plan: 02
subsystem: infra
tags: [netlify, pwa, service-worker, email-digest, edge-functions]
requirements_completed: [DEPLOY-01, DEPLOY-02, DEPLOY-03]

# Dependency graph
requires:
  - phase: 01-infrastructure-foundations
    plan: 01
    provides: "pwa_url field in Settings (config.py), Gmail smtplib integration"
provides:
  - "netlify.toml configured for SPA deployment (no build command, SPA redirect)"
  - "service-worker.js with root-relative paths (no BASE variable)"
  - "email_digest.py using settings.pwa_url for all PWA links"
  - "Supabase Edge Function PWA_URL secret set to Netlify domain"
affects:
  - "Phase 2 onwards - all PWA hosting assumes Netlify, not Supabase Storage"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Netlify SPA hosting: publish = 'pwa', [[redirects]] from = '/*' -> /index.html 200"
    - "Root-relative service worker paths: all STATIC_ASSETS use /path/to/file (not ${BASE}/...)"
    - "pwa_url config field: settings.pwa_url used for all email and action token links"

key-files:
  created: []
  modified:
    - netlify.toml
    - pwa/service-worker.js
    - src/integrations/email_digest.py

key-decisions:
  - "netlify.toml has no build command (static HTML) and one SPA redirect rule"
  - "service-worker.js uses root-relative paths — no BASE variable needed on Netlify"
  - "email_digest.py pwa_link = settings.pwa_url.rstrip('/') + '/#/queue'"
  - "PWA_URL secret set via supabase secrets set (not hardcoded in Edge Function)"

patterns-established:
  - "Pattern 1: All PWA links constructed from settings.pwa_url (not supabase_project_url)"
  - "Pattern 2: Service worker STATIC_ASSETS list uses root-relative /path format"

requirements-completed: [DEPLOY-01, DEPLOY-02, DEPLOY-03]

# Metrics
duration: 2min
completed: 2026-03-08
---

# Phase 1 Plan 2: Netlify Deployment Config Summary

**Netlify SPA config, root-relative service worker, and Netlify-linked email digest — all PWA infrastructure migrated from Supabase Storage to Netlify hosting**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-08T23:16:50Z
- **Completed:** 2026-03-08T23:18:32Z
- **Tasks:** 3/3 (Tasks 1-2 automated, Task 3 human-verify checkpoint approved)
- **Files modified:** 3

## Accomplishments
- netlify.toml replaced with clean SPA config: no build command, single redirect rule for hash routing
- pwa/service-worker.js stripped of BASE variable — all 10 STATIC_ASSETS now use root-relative paths, push notification icons updated
- email_digest.py `pwa_link` construction changed from Supabase Storage URL to `settings.pwa_url.rstrip("/") + "/#/queue"`
- Supabase Edge Function PWA_URL secret set via CLI (`supabase secrets set PWA_URL=https://eg-connect.netlify.app`)
- PWA_URL=https://eg-connect.netlify.app added to local .env (gitignored)
- All 7 Phase 1 infrastructure tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix netlify.toml and service-worker.js** - `f194c02` (chore)
2. **Task 2: Update email_digest.py PWA URLs and set Edge Function secret** - `24e70b4` (feat)
3. **Task 3: Verify Netlify deploy and email links** - APPROVED (checkpoint:human-verify)

## Files Created/Modified
- `netlify.toml` - Clean Netlify SPA config: publish = "pwa", SPA redirect rule
- `pwa/service-worker.js` - Removed BASE variable; all paths root-relative including push icons
- `src/integrations/email_digest.py` - PWA link uses settings.pwa_url, not Supabase Storage URL

## Decisions Made
- netlify.toml has no build command because the PWA is static HTML/JS with no build step
- service-worker.js uses root-relative paths because Netlify serves from domain root (unlike Supabase Storage which served from a subdirectory path)
- pwa_link pattern `settings.pwa_url.rstrip("/") + "/#/queue"` uses hash routing consistent with existing PWA navigation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- pytest needed to be invoked via `.venv/bin/pytest` (not on system PATH) — not a real issue, just environment awareness.
- .env is gitignored so PWA_URL env var addition could not be committed — documented in summary instead.

## User Setup Required

After Netlify auto-deploy from the pushed changes:
1. Visit your Netlify site URL (e.g., https://eg-connect.netlify.app) — PWA should load
2. Visit a deep link (e.g., https://eg-connect.netlify.app/#/contact/123) — should route correctly (not 404)
3. Open browser DevTools > Application > Service Workers — should show registered, no errors
4. If the Netlify URL differs from `https://eg-connect.netlify.app`, update:
   - `.env`: `PWA_URL=https://YOUR-ACTUAL-SITE.netlify.app`
   - Supabase secret: `supabase secrets set PWA_URL=https://YOUR-ACTUAL-SITE.netlify.app`

## Next Phase Readiness
- All automated infrastructure code changes are complete and tested
- Task 3 (human-verify) requires pushing to git and verifying Netlify deploys correctly
- Task 3 human-verify approved — Phase 1 is complete and Phase 2 (Email Reliability) can begin

---
*Phase: 01-infrastructure-foundations*
*Completed: 2026-03-08*
