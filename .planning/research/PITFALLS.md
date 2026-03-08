# Domain Pitfalls

**Domain:** Vanilla JS PWA on Netlify + actionable HTML email digest linked to Supabase backend
**Researched:** 2026-03-08
**Confidence:** HIGH (most verified with official docs or multiple sources)

---

## Critical Pitfalls

Mistakes that cause rewrites, security incidents, or features that silently never work.

---

### Pitfall 1: Service Worker BASE Path Breaks on Netlify

**What goes wrong:**
The existing `service-worker.js` computes its `BASE` path by stripping `/service-worker.js` from `self.location.pathname`. When hosted on Supabase Storage, this produced a long prefix like `/storage/v1/object/public/pwa`. On Netlify, the service worker is served from root `/`, so `BASE` becomes an empty string and all pre-cached asset paths become `//index.html`, `//css/app.css`, etc. — double-slash URLs that 404 silently. The SW registers successfully but caches nothing, breaking offline support.

**Why it happens:**
The current code was written to accommodate Supabase Storage's deep URL path. Netlify serves from a real domain root, so the detection logic produces the wrong value.

**Consequences:**
- Offline mode fails silently (no error, SW registers fine)
- Install banner may never appear (PWA installability requires a working SW with fetch handler)
- Stale assets served after deploy if old SW is still alive

**Prevention:**
Replace the dynamic `BASE` detection with a hardcoded empty string `''` and use absolute paths for all STATIC_ASSETS. Netlify serves from root. Update `CACHE_NAME` version string on every meaningful deploy so old caches are busted.

**Detection:**
- Chrome DevTools → Application → Service Workers: check that "Status" is "activated and running" and that Cache Storage shows non-empty entries after first load
- Lighthouse PWA audit will flag missing cache entries

**Phase:** PWA Netlify Deployment (first phase)

---

### Pitfall 2: No `_redirects` File Means Direct URL Access Returns 404

**What goes wrong:**
Hash-based routing (`#/queue`, `#/contact/123`) is immune to this, but Netlify still needs to serve `index.html` for any direct navigation to the root path and for non-HTML asset requests that miss. More critically: email "View Full Queue" links, action confirmation page "Open Queue" buttons, and any bookmarks to the PWA will 404 if Netlify's publish directory isn't configured correctly as `pwa/` — because Netlify currently points at the wrong directory.

**Why it happens:**
The repo's existing Netlify site was configured before `pwa/` was the intended root. Without a `netlify.toml` specifying `publish = "pwa"`, Netlify defaults to repo root, which has no `index.html`.

**Consequences:**
- Every email link that resolves to the PWA returns a blank page or 404
- PWA is completely inaccessible until `netlify.toml` is committed to the repo

**Prevention:**
Commit a `netlify.toml` at repo root with:
```toml
[build]
  publish = "pwa"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```
The `_redirects` fallback rule is belt-and-suspenders insurance for any future non-hash routes.

**Detection:**
- Visit Netlify dashboard → Site configuration → Build settings → Publish directory: must say `pwa`, not `.` or blank
- Direct URL `https://yoursite.netlify.app` should serve the PWA, not a directory listing

**Phase:** PWA Netlify Deployment (first phase)

---

### Pitfall 3: Email Links with Hash Fragments Are Stripped or Broken by Gmail

**What goes wrong:**
The current `email_digest.py` PWA link is constructed as:
```python
pwa_link = f"{pwa_url}/.../index.html#/queue"
```
And the Edge Function `htmlResponse` builds confirmation page links as:
```
href="${pwaUrl}#/queue"
```
Gmail and many other email clients either strip the URL fragment (`#/queue`) entirely when rewriting links for Safe Browsing (Google proxies all links through `https://www.google.com/url?q=...`) or drop the fragment because HTTP redirects cannot preserve fragments. The user lands on the PWA root with no route, defaulting to `/queue` only by luck if the fallback default is set.

**Why it happens:**
HTTP redirects (301/302) do not transmit the URL fragment — fragments are browser-only and never sent to the server. Gmail's click-time link protection rewrites URLs through a redirect chain, which discards the fragment.

**Consequences:**
- "View full profile" links from email (`#/contact/123`) land on the queue page instead — contact profile is never shown
- If the app adds more entry points (funnel view, feedback history), all email deep links silently go to the wrong page
- Feedback token links already use query parameters (`?token=UUID`) and work correctly — only hash-based deep links are affected

**Prevention:**
Use query parameters for all deep link targets from email, not hash fragments. The PWA router already parses `getQueryParams()` from the hash. Extend it to also read `window.location.search` and redirect internally:
```
https://your-pwa.netlify.app/?view=contact&id=123
```
The Netlify `/*` → `index.html` redirect preserves query parameters. On load, the PWA reads `?view=contact&id=123` and navigates to the correct hash route.

**Detection:**
- Copy an email link containing `#/contact/123` and paste into a browser after going through a redirect (e.g., use `curl -L` to follow the chain) — the fragment will be absent from the final URL
- Send a test email and click the "View full profile" link on mobile Gmail — observe where you land

**Phase:** Email Digest (actionable email phase) — must be solved before any deep link is embedded in email

---

### Pitfall 4: Supabase Anon Key Exposed in PWA with No RLS Policies

**What goes wrong:**
The anon key is hardcoded in `pwa/index.html` (visible in the repo, visible in browser source). This is acceptable **only if** Row Level Security is enabled on every table and the anon role has been explicitly granted only the minimum required permissions. The CONCERNS.md notes: "Anon key has restricted Row-Level Security (RLS) policies (assumed)" — assumed, not verified. If any table in the `public` schema has RLS disabled, the anon key grants unrestricted SELECT on that table.

**Why it happens:**
Tables created via the SQL editor (not the Supabase Dashboard) do not have RLS enabled by default. Migrations applied directly via psycopg2 (as this project does) will not have RLS unless explicitly added. The project's migration file (`20260305000000_pwa_overhaul.sql`) should be audited.

**Consequences:**
- Any user who visits the PWA can query all contacts, queue items, action tokens, and user feedback via PostgREST with the public anon key
- `action_tokens` table is particularly sensitive — leaked tokens allow approving/skipping contacts without owning an email address

**Prevention:**
Before deploying to Netlify (making the PWA publicly reachable):
1. Run `SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public'` against the Supabase project — every table should show `rowsecurity = true`
2. Add RLS policies that restrict the anon role to read-only on non-sensitive tables: `CREATE POLICY "anon_read_queue" ON outreach_queue FOR SELECT TO anon USING (true);`
3. Restrict `action_tokens` from anon reads entirely: tokens should only be accessed via the Edge Function using the service role key
4. Never expose the service role key in the PWA — it is already correctly confined to Edge Functions

**Detection:**
- Supabase Dashboard → Authentication → Policies: any table with a red "RLS disabled" badge is a risk
- Supabase Dashboard → Database → Database Linter: will flag tables with RLS disabled in public schema

**Phase:** PWA Netlify Deployment — must be verified before the site goes live

---

### Pitfall 5: `display: flex` in Email HTML Breaks Layout in Gmail

**What goes wrong:**
The current `email_digest.py` uses `display:flex;justify-content:space-between` in the contact card style:
```python
'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
```
Gmail strips all Flexbox sub-properties (`justify-content`, `align-items`, `flex-direction`) and in some clients strips `display:flex` itself. On Gmail mobile (iOS and Android), the card layout collapses — the score badge stacks below the name/role text instead of floating right, and the overall layout looks broken.

**Why it happens:**
Gmail renders email HTML inside its own DOM, aggressively sanitizing CSS. Flexbox is a CSS3 layout model that Gmail has historically not supported and only partially supports today. The sub-properties are always stripped; the display property behavior varies by client version.

**Consequences:**
- Score badge drops below contact name on Gmail mobile — the most important target platform
- Action buttons may not space correctly
- Layout appears broken in the client users consume email most

**Prevention:**
Use table-based layout for email cards. Replace the flex container with nested `<table>` elements. This is the only layout model that works identically across Gmail web, Gmail mobile, Outlook, and Apple Mail:
```html
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="vertical-align:top;">Name + role</td>
    <td style="vertical-align:top;text-align:right;white-space:nowrap;">Score badge</td>
  </tr>
</table>
```

**Detection:**
- Use Litmus or Email on Acid to preview the digest HTML in Gmail Mobile before shipping
- Send the digest HTML to a Gmail account and view on an iPhone — the flex container will visually break

**Phase:** Email Digest (actionable email phase) — fix before any email is sent

---

## Moderate Pitfalls

---

### Pitfall 6: Gmail Proxies Action Token Links Through Safe Browsing Redirects

**What goes wrong:**
Gmail wraps all links in emails through a redirect: `https://www.google.com/url?q=ORIGINAL_URL`. When a user clicks "Reach Out" in the email, Gmail first sends them to Google's link protection service, which then redirects to the Supabase Edge Function URL. This is generally fine — the token parameter is preserved through the redirect chain as a query parameter.

However, if the Edge Function returns a redirect (302) rather than an HTML page, Gmail's link protection may interfere. Additionally, Gmail pre-fetches links for Safe Browsing scanning — this is an `HTTP GET` to the link URL, which means action tokens can be **consumed by Gmail's scanner before the user clicks the button**.

**Why it happens:**
Gmail's link scanner has been observed making GET requests to embedded URLs. One-time-use tokens that are marked as `used = true` on first GET will be burned by the scanner, leaving the user with an "Already Used" error when they actually click.

**Consequences:**
- User clicks "Reach Out" button — gets "Already Used" response — contact is marked approved but user never sees confirmation
- Token scanning is non-deterministic; affects some users/environments and not others

**Prevention:**
Make the token validation idempotent: if the token is already used AND the action was the same as requested, show a success page ("Already done — contact marked for outreach") rather than an error. Pre-scanning cannot fake a different action than what is encoded. Alternatively, use `POST` for the action — scanners only follow GET requests. This requires JavaScript in the email link (not viable in Gmail) or a two-step flow: link opens a confirmation page, confirmation page POSTs the action.

**Detection:**
- Watch Supabase Edge Function logs after sending a digest — if tokens are consumed within seconds of email delivery before you click, pre-scanning is occurring
- The `used_at` timestamp will precede any human-feasible click time

**Phase:** Email Digest — implement idempotent token handling before launch

---

### Pitfall 7: Service Worker Caches Stale PWA After Netlify Deploy

**What goes wrong:**
The service worker uses a static `CACHE_NAME = 'reconnect-v1'`. After a new deploy to Netlify, returning users' browsers still run the old service worker (browsers wait up to 24 hours before checking for SW updates, or until all tabs are closed). Users see old JavaScript and CSS until they hard-refresh or close all tabs. Because `skipWaiting()` is called on install, new SW versions do activate, but only when the old one is no longer controlling any clients — which requires the user to close all PWA tabs.

**Why it happens:**
Service workers are designed to be long-lived. The `CACHE_NAME` version is a manual bump; if a developer forgets to bump it after a deploy, old caches persist indefinitely.

**Consequences:**
- Bug fixes shipped to Netlify don't reach users for hours or days
- If API response shapes change between old and new PWA code, old JS calling new API produces cryptic errors
- No visible feedback to the user that they're running old code

**Prevention:**
Automate the cache version by embedding a build timestamp or content hash. Without a build tool, use a simple approach: maintain a `version.js` file with `const APP_VERSION = '2026-03-08-001'` that is updated on deploy. The service worker imports this and uses the version string as `CACHE_NAME`. Document: always update `version.js` when deploying.

Alternatively, add a `Cache-Control: no-cache` header for `service-worker.js` itself via a `_headers` file in `pwa/`:
```
/service-worker.js
  Cache-Control: no-cache
```
This ensures browsers always fetch the latest SW file even if the content hash matches.

**Detection:**
- After deploying a change, open the PWA in a browser that previously visited it — if the change isn't visible without a hard refresh, the SW is serving stale assets
- Chrome DevTools → Application → Service Workers → "Update on reload" checkbox (useful during development)

**Phase:** PWA Netlify Deployment — set up before first deploy so it never becomes a problem

---

### Pitfall 8: PWA Manifest `start_url` Is Relative to Old Storage URL

**What goes wrong:**
`pwa/manifest.json` currently specifies `"start_url": "index.html#/queue"`. When the PWA was served from Supabase Storage, this resolved correctly. On Netlify, the manifest is served from `https://reconnect.netlify.app/manifest.json`, so `index.html#/queue` resolves to `https://reconnect.netlify.app/index.html#/queue`. This is close to correct, but if the `scope` field is absent (it is not currently set in the manifest), the browser derives scope from `start_url`, which may exclude navigation to paths like `/contact/123` from being "in-scope" for the installed PWA.

More critically: the `start_url` uses a hash fragment (`#/queue`). Some browsers and the Web App Manifest spec treat the URL before the `#` as the canonical start URL for installability checks. Chrome will check that the service worker controls `index.html`, which it does — but the discrepancy can cause Lighthouse to flag the manifest as non-conforming.

**Prevention:**
Update `manifest.json` to use clean URLs:
```json
{
  "start_url": "/",
  "scope": "/",
  "start_url": "/?source=pwa"
}
```
Keep the hash-based routing intact — setting `start_url` to `/` still works because the PWA router defaults to `/queue` when no hash is set. The `?source=pwa` query parameter is a useful tracking signal to distinguish PWA installs from browser visits.

**Detection:**
- Lighthouse PWA audit → "Web app manifest meets the installability requirements" — will flag scope/start_url mismatches
- Try installing the PWA from Chrome on Android and observe whether the install prompt appears

**Phase:** PWA Netlify Deployment

---

### Pitfall 9: Edge Function CORS Headers Missing on Error Responses

**What goes wrong:**
The Edge Function `action/index.ts` returns CORS headers on the OPTIONS preflight and on success responses. But if an early return fires (e.g., `if (!token) { return htmlResponse(..., 400); }`) before the CORS headers are attached, the browser's fetch call from the PWA will see a CORS error instead of the actual 400 error. The current `htmlResponse()` function does include `corsHeaders` — but this must be verified on every new code path added to the function.

**Why it happens:**
CORS headers must be present on every response from an Edge Function, including errors. A single missing header on one code path causes a network error that is indistinguishable from a connectivity issue in the browser console.

**Prevention:**
The current implementation correctly includes `corsHeaders` in `htmlResponse()`, which is used for all returns. Maintain this discipline strictly: never add a `return new Response(...)` without spreading `corsHeaders`. When adding new Edge Functions (e.g., a queue fetch proxy), add CORS handling as the literal first block before any logic.

**Detection:**
- Browser DevTools → Network tab: filter by "Type: Fetch" — a CORS failure shows as a red entry with a CORS error, not a status code error
- Test all error paths (expired token, missing token, unknown action) with `curl -H "Origin: https://your-pwa.netlify.app"` and verify `Access-Control-Allow-Origin` header is present

**Phase:** PWA feature development (any phase that adds Edge Function calls)

---

### Pitfall 10: Email Digest PWA Link Points at Supabase Storage, Not Netlify

**What goes wrong:**
In `email_digest.py`, the PWA link is built from `settings.supabase_project_url`:
```python
pwa_link = f"{pwa_url.rstrip('/')}/storage/v1/object/public/pwa/index.html#/queue"
```
This hardcodes the Supabase Storage URL. Once the PWA moves to Netlify, every email digest sent will link to the old broken Supabase Storage URL. The email goes out fine, but every "View Full Queue" click lands on a 404 or the old (potentially stale) Supabase-hosted version.

Similarly, the Edge Function `htmlResponse()` reads `PWA_URL` from Deno env, falling back to the Supabase Storage path. If `PWA_URL` is not set as a Supabase secret, the action confirmation page "Open Queue" button points at the wrong URL.

**Prevention:**
1. Add `PWA_URL` as a setting in `src/config.py` (reads from `.env`)
2. Update `email_digest.py` to use `settings.pwa_url` rather than constructing the Storage URL
3. Set `PWA_URL` as a Supabase Edge Function secret: `supabase secrets set PWA_URL=https://reconnect.netlify.app`
4. Verify with a test digest send after Netlify deployment

**Detection:**
- Send a test digest and click "View Full Queue" — if it lands on a Supabase Storage URL, the config hasn't been updated
- Check Edge Function logs for the `PWA_URL` env var value

**Phase:** PWA Netlify Deployment — must be done at the same time as the Netlify go-live

---

## Minor Pitfalls

---

### Pitfall 11: Email Action Buttons Are Too Small on Mobile

**What goes wrong:**
The current buttons use `padding:8px 16px` — approximately 36px height on a standard font. Apple's HIG and Android guidelines recommend a minimum tap target of 44px. On a phone, the "Reach Out", "Skip", and "Snooze" buttons are adjacent with only `margin-right:6px` between them — three small buttons close together causes frequent mis-taps.

**Prevention:**
Increase button padding to `padding:12px 20px` to hit approximately 44px height. Add `margin-bottom:8px` and consider stacking the buttons vertically on mobile using a `<table>` with `width:100%` rows, so each button is full-width and easy to tap.

**Detection:**
View the email on an actual iPhone in Gmail — attempt to tap "Skip" without accidentally tapping "Reach Out"

**Phase:** Email Digest

---

### Pitfall 12: `display:flex` Fallback Confirmation Page in Edge Function

**What goes wrong:**
The `htmlResponse()` function in `action/index.ts` uses `display: flex; justify-content: center; align-items: center` for the page layout. While this is an actual web page (not an email), it renders correctly in browsers. However, if Gmail's link-scanning GET request receives this HTML and Gmail renders it in a sandboxed preview, the layout may look odd. This is low-severity since users see a full browser page, not an email preview.

**Prevention:**
No immediate action required. The confirmation page is a standard web page served to browsers, not rendered inside Gmail. Flex layout is fine for browser pages.

**Phase:** Not a blocking concern

---

### Pitfall 13: Service Worker Registers with Wrong Scope on Netlify

**What goes wrong:**
In `pwa/index.html`, the service worker is registered as:
```javascript
navigator.serviceWorker.register('service-worker.js')
```
This is a relative path. On Netlify (served from `/`), this registers the SW with scope `/`, which is correct. But if the site is ever served from a subdirectory (e.g., `https://example.com/app/`), the SW scope would be `/app/` only and the registration would fail for root-path navigations.

**Prevention:**
Since this is a dedicated Netlify site served from root, no action is needed. Document: if the deploy path ever changes from root, update the `register()` call to include an explicit `scope: '/'` option.

**Detection:**
Chrome DevTools → Application → Service Workers: verify `Scope` shows `https://yoursite.netlify.app/`

**Phase:** PWA Netlify Deployment (verification step only)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Netlify site configuration | Publish directory wrong, PWA not served | Add `netlify.toml` with `publish = "pwa"` before first deploy |
| Service worker migration | BASE path breaks, stale caches | Rewrite BASE to `''`, add `_headers` for `no-cache` on `service-worker.js` |
| PWA go-live | Anon key exposes data | Audit RLS on all tables before making URL public |
| Email digest deep links | Hash fragments stripped by Gmail proxy | Use `?view=X&id=Y` query params for all email-to-PWA links |
| Email card layout | Flex CSS breaks in Gmail mobile | Replace flex containers with `<table>` layout |
| Action token emails | Gmail scanner burns one-time tokens | Make token validation idempotent on re-use |
| Email PWA links | Still pointing at Supabase Storage | Set `PWA_URL` env/config and update `email_digest.py` |
| Edge Function updates | CORS missing on new error paths | Always use `htmlResponse()` wrapper, never bare `new Response()` |
| PWA manifest | Installability broken by hash start_url | Set `start_url: "/"` and `scope: "/"` in manifest |

---

## Sources

- Netlify SPA routing official docs: https://docs.netlify.com/configure-builds/javascript-spas/
- Netlify file-based configuration: https://docs.netlify.com/build/configure-builds/file-based-configuration/
- Netlify SPA routing support guide: https://answers.netlify.com/t/support-guide-direct-links-to-my-single-page-app-spa-dont-work/126
- Supabase CORS for Edge Functions: https://supabase.com/docs/guides/functions/cors
- Supabase RLS and anon key: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase API key guide: https://supabase.com/docs/guides/api/api-keys
- Gmail CSS support limitations: https://developers.google.com/workspace/gmail/design/css
- Gmail flex in email (HTeuMeuLeu): https://www.hteumeuleu.com/2016/using-flexbox-in-an-email/
- Email client rendering differences 2026: https://dev.to/mailpeek/the-complete-guide-to-email-client-rendering-differences-in-2026-243f
- Bulletproof email buttons (Litmus): https://www.litmus.com/blog/a-guide-to-bulletproof-buttons-in-email-design
- Gmail link protection: https://support.google.com/mail/answer/10173182
- URL fragment and redirects: https://medium.com/@90mph/hash-fragments-and-browser-redirects-acf8e33cbaa5
- PWA manifest installability: https://developer.chrome.com/docs/lighthouse/pwa/installable-manifest
- PWA scope and start_url: https://intercom.help/progressier/en/articles/6866740-how-do-the-scope-and-start_url-properties-of-a-pwa-manifest-work
- Service worker update best practices: https://web.dev/learn/pwa/update
- Service worker cache Netlify issue: https://answers.netlify.com/t/support-guide-understanding-unregistering-service-workers/145
- Netlify caching overview: https://docs.netlify.com/build/caching/caching-overview/
