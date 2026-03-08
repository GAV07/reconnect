# Project Research Summary

**Project:** Reconnect v2 — Actionable PWA + Rich Email Digests
**Domain:** Personal CRM PWA + actionable HTML email digest (networking / outreach tool)
**Researched:** 2026-03-08
**Confidence:** HIGH

## Executive Summary

Reconnect is a working system that is one deployment step away from being fully usable. The Python pipeline, Supabase backend, Edge Functions, and vanilla JS PWA all exist and function — but the PWA is stranded on Supabase Storage (which cannot do SPA routing) and the daily email digest generates correct HTML but cannot send because Gmail SMTP is unconfigured. The research confirms that the correct fix for both blockers is already understood: migrate the PWA to Netlify with a `netlify.toml` specifying `publish = "pwa"`, and add a Gmail App Password to `.env` to enable `smtplib` email sending. These two changes unblock the entire end-to-end daily workflow.

The recommended approach is additive and conservative: do not replace the existing stack. The vanilla JS PWA, hash-based routing, Supabase JS SDK, and hand-rolled inline CSS email templates are all technically correct choices for a single-user tool. The architecture research confirms a clean critical path — Netlify deployment must come first because it unblocks PWA deep links in email, service worker scope, and PWA installability. Config changes (PWA URL, email sender) must immediately follow, because every email link is built from configuration. Email send capability unlocks the daily habit driver and token-based actions. After these three foundational steps, all PWA feature polish and new views can proceed in parallel.

The key risks are non-obvious implementation bugs rather than architectural uncertainty. Gmail's link scanner can pre-click and consume one-time action tokens before the user acts; the fix is GET-shows-confirmation, POST-executes-action. Gmail strips Flexbox CSS properties from email HTML; the fix is table-based card layouts. Gmail's link protection proxies URLs through a redirect chain that strips URL hash fragments; the fix is query parameter deep links for all email-to-PWA navigation. All three of these are confirmed, documented pitfalls with clear prevention strategies — they should be addressed in the first two phases before any email is sent.

## Key Findings

### Recommended Stack

The existing stack requires no new technologies. The only configuration changes are: (1) fix `netlify.toml` to remove the erroneous `npm run build` command and uncomment the SPA redirect rule; (2) replace the Gmail OAuth path with a 20-line `smtplib` implementation using a Gmail App Password (one env var vs. multi-step OAuth setup); (3) add `pwa_url` to `src/config.py` and set it via `.env` after Netlify deployment. The Supabase JS SDK on CDN, hash-based routing, service worker, and Edge Functions are all correct as-is.

**Core technologies:**
- Netlify (free tier): PWA hosting with SPA routing — Supabase Storage cannot serve SPA deep links
- `smtplib` (Python stdlib): Email sending via Gmail App Password — replaces unconfigured OAuth flow
- Vanilla JS (ES6+): PWA logic — no build step, no framework overhead; correct for single-user tool
- `@supabase/supabase-js@2` (CDN): Supabase client — already in use, pin to `@2` for minor/patch updates
- Table-based HTML layout: Email card structure — required for Gmail compatibility; `display:flex` is stripped

### Expected Features

The gap between "exists" and "works end-to-end" is small. Most features are implemented; the blockers are infrastructure (Netlify deployment, email sending) and a handful of bug-class issues (Flexbox in email, hash fragment links, token scanner vulnerability).

**Must have (table stakes — blocks daily usability):**
- Netlify deployment with `publish = "pwa"` and SPA redirect rule — PWA is completely inaccessible without this
- Gmail email sending (App Password via `smtplib`) — email is the entry point and daily habit driver
- Email mobile layout audit (44px tap targets, 600px max-width, 16px+ font) — >60% of email opened on mobile
- PWA URL updated in config and email digest — every email link points to the wrong host until this is fixed

**Should have (completes the core loop):**
- Contact profile page enrichment fields surfaced (location, headline, email stored but not shown)
- Pipeline funnel view (`#/funnel`) — data exists in `dashboard_snapshots`; needs a new page
- Enrichment status dedicated view — surfaces existing quality stats from dashboard snapshot

**Defer (v2+):**
- Feedback history with approve/skip pattern charts (data exists; visualization is cosmetic)
- Push notifications (redundant with email digest)
- Social graph visualization, bulk actions, calendar integration — confirmed anti-features for this tool

### Architecture Approach

The target architecture is a three-tier system with clean separation: a local Python pipeline runs at 8AM via LaunchAgent, pushing data to Supabase PostgreSQL; Supabase Edge Functions handle token-based email actions and on-demand draft generation; a Netlify-hosted vanilla JS PWA reads from Supabase via the anon key. The critical architectural insight is that hash-based routing means Netlify never sees PWA routes — the `/* → /index.html 200` redirect is only a safety net, not required for core navigation. The email deep-link problem is solved at the application layer by converting hash fragment links to query parameter links (`?view=contact&id=123`) which survive redirect chains.

**Major components:**
1. `daily_pipeline.py` — orchestrates all 10 pipeline steps; generates queue, tokens, and HTML digest
2. `email_digest.py` + `tokens.py` — builds HTML with token-based action buttons; tokens are per-action, one-time-use
3. `action` / `draft` / `feedback` Edge Functions — server-side token validation, LLM draft generation, feedback recording
4. PWA (`pwa/`) — daily triage queue, contact profiles, dashboard; reads Supabase via anon key
5. Netlify — static CDN host with SPA redirect; no server logic

### Critical Pitfalls

1. **Service worker BASE path breaks on Netlify** — the existing SW computes BASE by stripping the Supabase Storage path; on Netlify, BASE becomes `''` and all pre-cached asset URLs become double-slash (`//index.html`). Fix: hardcode BASE to `''` and use absolute paths for STATIC_ASSETS before first deploy.

2. **Gmail strips hash fragments from deep links** — Gmail proxies links through `google.com/url?q=...` redirect chain; HTTP redirects cannot transmit URL fragments. "View Profile" links (`#/contact/123`) land on the wrong page. Fix: use query parameters (`?view=contact&id=123`) for all email-to-PWA links; PWA reads `window.location.search` on load and navigates to the correct hash route.

3. **Gmail scanner burns one-time tokens before user acts** — Gmail pre-fetches embedded URLs for Safe Browsing. GET request to the action Edge Function consumes the token immediately. Fix: GET returns an HTML confirmation page; user submits a form POST; action executes only on POST. Scanners do not follow POST requests.

4. **`display:flex` breaks Gmail mobile card layout** — Gmail strips `justify-content`, `align-items`, and other flex sub-properties. Score badge drops below contact name. Fix: replace flex containers in email HTML with `<table>` single-row layout for all card headers.

5. **RLS not verified before PWA goes public** — migrations applied via psycopg2 do not enable RLS by default. Anon key in public PWA grants unrestricted SELECT on any table without RLS. Fix: run `SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public'` and verify all tables before Netlify deployment.

## Implications for Roadmap

Based on research, the architecture has a clear critical path with hard dependencies. The suggested phase structure reflects those dependencies.

### Phase 1: Infrastructure Foundations
**Rationale:** Everything else is blocked until the PWA is deployable and the email can send. These are not features — they are preconditions. Netlify deployment must come before any email link can work. Config changes must come immediately after so that email links point to the right host. RLS audit must happen before the Netlify URL is made public.
**Delivers:** A live, accessible PWA at `reconnect-app.netlify.app`; email digests that actually arrive in inbox; all existing email buttons active
**Addresses:** Netlify SPA deployment, Gmail App Password configuration, PWA URL config update, RLS audit
**Avoids:** Pitfall 1 (SW BASE path), Pitfall 2 (wrong publish directory), Pitfall 4 (RLS exposure), Pitfall 10 (Storage URL in email)

### Phase 2: Email Quality and Reliability
**Rationale:** The email digest is the daily habit driver — if it looks broken on mobile or if action buttons fail due to scanner pre-clicks, the entire system loses trust on day one. These fixes must land before the first real digest is sent. They are also time-sensitive: once email links are in users' inboxes, they are permanent.
**Delivers:** Reliable token-based actions that survive Gmail scanning; correct card layout on Gmail mobile; deep links that navigate to the right page; properly sized tap targets
**Addresses:** Email mobile layout (44px buttons, 600px max-width), table-based card layout, GET/POST action flow, query parameter deep links
**Avoids:** Pitfall 3 (hash fragments stripped), Pitfall 5 (flex CSS breaks), Pitfall 6 (scanner burns tokens), Pitfall 11 (small tap targets)

### Phase 3: PWA Feature Completeness
**Rationale:** With the PWA live and email delivering correctly, fill out the incomplete features that make the tool useful beyond the queue triage. The contact profile page is the primary surface for deeper review — it needs enrichment fields surfaced. The funnel and enrichment views complete the operational visibility promise.
**Delivers:** Contact profile with full enrichment fields visible; pipeline funnel view (`#/funnel`); enrichment status view; service worker and manifest correctness on Netlify
**Addresses:** Enrichment field surfacing, funnel data display, `#/funnel` and `#/enrichment` routes, manifest `start_url`/`scope` fix, SW cache version strategy
**Avoids:** Pitfall 7 (stale SW after deploy), Pitfall 8 (manifest installability), Pitfall 9 (CORS on new Edge Function calls)

### Phase Ordering Rationale

- **Phase 1 before Phase 2:** Cannot send email before the PWA is deployed at a stable URL. Cannot audit email layout if email cannot send. Cannot fix deep links if there is no Netlify domain to point them to.
- **Phase 2 before Phase 3:** Email quality issues need to be baked in before any feature work adds new deep links or new Edge Function endpoints. Getting the token flow and layout right once means all future emails inherit the correct patterns.
- **Phase 3 is internally parallel:** Once the PWA is on Netlify, contact profile improvements, new route pages, and manifest/SW fixes are independent and can be done in any order.

### Research Flags

Phases with standard, well-documented patterns (skip research-phase):
- **Phase 1:** Netlify deployment, `netlify.toml` syntax, and Gmail App Password SMTP are all thoroughly documented with official sources. Implementation is mechanical.
- **Phase 2:** Gmail CSS limitations and token security patterns are fully documented. The GET/POST action flow is a known pattern for email link protection.

Phases that may benefit from brief targeted research during planning:
- **Phase 3 (funnel view):** The pipeline currently writes `dashboard_snapshots` but does not include funnel-stage counts. The schema change and pipeline step to write stage counts should be scoped before implementation begins.
- **Phase 3 (enrichment view):** `data_completeness` step in the pipeline writes quality stats; confirm the exact field names in `dashboard_snapshots` before building the UI against them.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations verified against official docs. No new dependencies required. The only choices are about configuration, not technology selection. |
| Features | HIGH | Codebase was audited directly. Feature status (exists/partial/missing) reflects actual code state, not assumptions. Competitive landscape cross-checked against multiple 2025-2026 sources. |
| Architecture | HIGH | Netlify SPA, hash routing, and Supabase patterns are all verified against official documentation. The email deep-link problem and solution are confirmed by URL fragment behavior specs. |
| Pitfalls | HIGH | All critical pitfalls are verified against official Gmail CSS docs, Netlify docs, or reproducible technical behavior (HTTP redirect fragment stripping). Scanner pre-click behavior is documented by multiple sources. |

**Overall confidence:** HIGH

### Gaps to Address

- **RLS policy state:** The actual RLS status of all Supabase tables is unknown until the SQL query is run against the live project. Cannot assume RLS is enabled because migrations were applied via psycopg2. Must verify before Phase 1 goes live.
- **`dashboard_snapshots` funnel data fields:** The pipeline writes snapshot data but the exact schema fields for funnel-stage counts are not confirmed. Phase 3 funnel view implementation should start by reading the actual snapshot schema from the DB.
- **Netlify site configuration state:** The `netlify.toml` in the repo has the redirect commented out and an incorrect build command. The Netlify UI site settings may also have stale configuration. Both the file and the UI settings need to be verified and corrected in Phase 1.
- **Gmail App Password prerequisite:** Requires 2FA enabled on the Gmail account. If 2FA is not active, this must be set up before the App Password can be generated. This is a one-time external dependency outside the codebase.

## Sources

### Primary (HIGH confidence)
- [Netlify JavaScript SPAs docs](https://docs.netlify.com/configure-builds/javascript-spas/) — SPA redirect configuration, publish directory
- [Netlify File-based configuration](https://docs.netlify.com/build/configure-builds/file-based-configuration/) — `netlify.toml` reference
- [Gmail CSS Support | Google for Developers](https://developers.google.com/workspace/gmail/design/css) — authoritative Gmail CSS support list, flex stripping
- [Supabase RLS docs](https://supabase.com/docs/guides/database/postgres/row-level-security) — anon key scope and RLS policy requirements
- [Supabase CORS for Edge Functions](https://supabase.com/docs/guides/functions/cors) — CORS header requirements
- [Supabase Edge Functions architecture](https://supabase.com/docs/guides/functions/architecture) — Deno runtime behavior
- [Python smtplib / Gmail App Password](https://mailtrap.io/blog/python-send-email-gmail/) — SMTP_SSL pattern, port 465
- [PWA manifest installability](https://developer.chrome.com/docs/lighthouse/pwa/installable-manifest) — start_url, scope requirements
- [Service worker update best practices](https://web.dev/learn/pwa/update) — cache busting, skipWaiting behavior
- Existing codebase: `pwa/`, `supabase/functions/`, `src/integrations/email_digest.py`, `src/database/models.py` — direct audit

### Secondary (MEDIUM confidence)
- [Can I email… display:flex](https://www.caniemail.com/features/css-display-flex/) — email client flex support matrix
- [Mobile Emails 2026 - Saturate Marketing](https://saturate.marketing/designing-emails-for-mobile-in-2026-structure-speed-and-what-still-works) — 600px, 44px buttons, 16px+ font minimums
- [When Bots Interfere With Links in Your Email](https://www.highroadsolutions.com/blog/when-bots-interfere-with-links-in-your-email-heres-what-to-do) — scanner pre-click behavior
- [Capability URLs - W3C TAG](https://w3ctag.github.io/capability-urls/) — token-based email action security pattern
- [URL fragment and redirects](https://medium.com/@90mph/hash-fragments-and-browser-redirects-acf8e33cbaa5) — HTTP redirect fragment stripping behavior
- [Best Personal CRM Software in 2026 - CRM.org](https://crm.org/crmland/personal-crm) — competitive feature landscape

### Tertiary (MEDIUM-LOW confidence)
- [Gmail link protection docs](https://support.google.com/mail/answer/10173182) — link proxy behavior (scanner pre-click is observed behavior, not officially documented by Google)

---
*Research completed: 2026-03-08*
*Ready for roadmap: yes*
