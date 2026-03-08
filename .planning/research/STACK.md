# Technology Stack

**Project:** Reconnect v2 — Actionable PWA + Rich Email Digests
**Researched:** 2026-03-08
**Scope:** PWA deployment on Netlify + actionable HTML email digests

---

## Context: What Already Exists

This is an additive milestone on top of an existing working system. The Python pipeline,
Supabase backend, Edge Functions, and vanilla JS PWA code all exist. This research covers
only what's needed to deploy the PWA properly and make the email digests actionable.

**Do not replace:** SQLModel, Supabase JS SDK, Edge Functions, smtplib/Gmail API stack.

---

## Recommended Stack

### PWA Hosting

| Technology | Version/Tier | Purpose | Why |
|------------|-------------|---------|-----|
| Netlify | Free tier | Static site hosting + SPA routing | Proper SPA redirect rules, auto HTTPS, CI/CD from GitHub, free netlify.app subdomain (`reconnect-app.netlify.app`). Supabase Storage can't do SPA routing — direct URL navigation fails because storage returns 404 for non-existent paths. |
| netlify.toml | — | Deployment config | Declarative, version-controlled, activates SPA rewrite in one redirect block. Already partially in repo but needs SPA rewrite uncommented and build command removed. |

**Configuration** (MEDIUM confidence — from Netlify docs):

```toml
[build]
  publish = "pwa"
  # No build command — this is a pre-built static site

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

[[headers]]
  for = "/service-worker.js"
  [headers.values]
    Cache-Control = "max-age=0, no-cache, no-store, must-revalidate"

[[headers]]
  for = "/manifest.json"
  [headers.values]
    Content-Type = "application/manifest+json"
```

**Why this matters:** The existing `netlify.toml` has the redirect block commented out and
incorrectly sets `command = "npm run build"` — the PWA is pre-built vanilla JS with no build
step. Both issues need fixing before the PWA will work on any URL except `/`.

### Frontend (PWA)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Vanilla JS (ES6+) | — | App logic | Already written, working. No justification to add a framework for a single-user tool with no team ownership concerns. Keep what exists. |
| @supabase/supabase-js | 2.x (CDN, pin to @2) | Supabase client | Already in use via CDN at `cdn.jsdelivr.net/npm/@supabase/supabase-js@2`. Latest is 2.98.0 as of March 2026. Pinning to `@2` gets automatic minor/patch updates without breaking changes. |
| Hash-based routing (`#/route`) | — | Client-side routing | Already implemented. Correct choice for this setup — hash routing means the server never sees the route path, so SPA redirects are only needed for edge cases, not every navigation. More robust than pushState for a static host. |
| Service Worker (existing `service-worker.js`) | — | Offline support + caching | Already exists. Use cache-first for static assets, network-first for Supabase API calls. No Workbox needed at this scale. |

**Do not add:** TypeScript compilation, Webpack/Vite build pipeline, any JS framework (React,
Vue, Svelte). The entire point of the existing architecture is zero build complexity. Adding a
build step creates CI/CD complexity for no user-visible benefit on a single-user tool.

### Email Sending (Python)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `smtplib` (stdlib) | Python 3.11+ | SMTP send | No dependencies, works with Gmail App Password. Much simpler than the existing OAuth flow which requires running a local web server to complete authorization. For a single-user CLI pipeline, App Password is the right tradeoff. |
| `email.mime` (stdlib) | Python 3.11+ | MIME construction | Already used in gmail.py. Keep as-is. |
| Gmail App Password | — | Auth for SMTP | 16-char app password from Google Account settings. Requires 2FA on the account. One-time setup in `.env`. No token refresh complexity, no redirect URIs, no local HTTP server. |

**OR keep Gmail API OAuth** (existing `gmail.py`): The existing OAuth implementation is
correct — it just needs the one-time setup done (create OAuth client in Google Cloud, run
auth flow once, store refresh token in DB). If the project already has a Google Cloud project
for the Gmail API, use it. The OAuth approach is more secure and doesn't require 2FA on the
account.

**Decision:** Use Gmail App Password via `smtplib` as the default path. It unblocks email
sending in one step (add `GMAIL_APP_PASSWORD=xxx` to `.env`) vs. the multi-step OAuth setup.
Replace `gmail.py` with a 20-line `smtplib` implementation. The existing OAuth code can be
kept as a fallback/alternative.

**New gmail.py pattern** (HIGH confidence — Python stdlib, unchanged for years):

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_html_email(to: str, subject: str, html_body: str) -> dict:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.gmail_sender
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(settings.gmail_sender, settings.gmail_app_password)
        smtp.sendmail(settings.gmail_sender, to, msg.as_string())
    return {"sent": True}
```

### HTML Email Construction (Python)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python `html` stdlib | — | HTML escaping | Already in use (`from html import escape`). Keep. |
| Inline CSS only | — | Email styles | Gmail strips `<style>` blocks if they contain `background-image: url(...)`. The existing email template uses inline `style=""` attributes throughout — this is exactly right. |
| Table-based layout | — | Email structure | `display:flex` has only partial Gmail support (the property is accepted but flex child properties like `justify-content` are dropped). The existing template uses `<div>` with inline flex for header elements. Safer to switch card layouts to use a single-row `<table>` for the name/score alignment. |
| No external CSS frameworks | — | — | Frameworks like Foundation for Email or MJML add tooling complexity. The existing hand-rolled inline HTML is correct for a single developer. |

**Gmail compatibility rules** (HIGH confidence — from Google's official CSS support docs and
caniemail.com data as of 2025):
- Inline `style=""` attributes: SUPPORTED everywhere
- `<style>` blocks: SUPPORTED in Gmail (stripped only if they contain `background-image: url(...)`)
- `display:flex`: PARTIALLY supported (Gmail accepts it but drops flex child properties)
- Media queries: SUPPORTED in Gmail mobile apps, NOT in Gmail web desktop
- `<table>` layout: FULLY supported everywhere — use for multi-column card rows
- 102KB size limit: Emails over 102KB get clipped by Gmail. Keep HTML under 80KB target.

**Action buttons in email** (HIGH confidence): Styled `<a>` tags with inline CSS are the
correct approach. The existing button implementation is correct:
```html
<a href="TOKEN_URL" style="display:inline-block;background:#1a7f37;color:#ffffff;
   text-decoration:none;padding:8px 16px;border-radius:4px;font-size:13px;
   font-weight:bold;margin-right:6px;">Reach Out</a>
```
These work in Gmail mobile and desktop without modification.

### PWA Link in Email

The email currently links to the Supabase Storage URL for the PWA. After Netlify deployment,
update `pwa_link` in `email_digest.py` to use the Netlify URL (e.g.
`https://reconnect-app.netlify.app`).

Add this to `src/config.py`:
```python
pwa_url: str = "https://reconnect-app.netlify.app"  # override in .env
```

### Backend (Unchanged)

| Technology | Version | Purpose | Notes |
|------------|---------|---------|-------|
| Supabase PostgreSQL | — | Primary cloud DB | Unchanged |
| Supabase Edge Functions | Deno | Action token handler, feedback | Unchanged — email buttons already hit `/functions/v1/action?token=UUID` |
| SQLite + SQLModel | — | Local pipeline DB | Unchanged |
| Python 3.12 | 3.12.x | Pipeline runtime | Unchanged |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| PWA hosting | Netlify | Vercel | Either works for static vanilla JS. Netlify already linked to `eg-connect` repo — reconfiguring is less work than migrating. |
| PWA hosting | Netlify | Supabase Storage | Storage can't do SPA routing — direct URL nav returns 404. This is the exact problem being solved. |
| Email auth | Gmail App Password | OAuth2 (existing gmail.py) | OAuth requires one-time browser auth flow + local HTTP server + token storage. App Password is one env var. For a local pipeline with a single user, App Password is the right tradeoff. |
| Email auth | Gmail App Password | SendGrid/Postmark | External services add a vendor and cost. Gmail is free and already the sender identity. Only use a transactional email service if volume becomes an issue (Gmail App Password allows ~500/day). |
| Email HTML | Hand-rolled inline CSS | MJML | MJML produces better cross-client HTML but requires a Node.js build step in the Python pipeline. Not worth the complexity for a single-user digest. |
| JS in PWA | Vanilla ES6 | TypeScript + Vite | Would require a build step, changing the Netlify deploy from "serve pwa/ as-is" to "run build, serve dist/". Pure overhead for a solo project. |
| JS routing | Hash-based (`#/`) | History API pushState | pushState requires the SPA redirect rule to serve index.html for every path. Hash routing is more naturally compatible with static hosts. The existing choice is correct. |

---

## Installation / Configuration Changes Required

### 1. Fix `netlify.toml` (REQUIRED)

Replace the existing file with:

```toml
[build]
  publish = "pwa"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

[[headers]]
  for = "/service-worker.js"
  [headers.values]
    Cache-Control = "max-age=0, no-cache, no-store, must-revalidate"

[[headers]]
  for = "/manifest.json"
  [headers.values]
    Content-Type = "application/manifest+json"
```

Remove `command = "npm run build"` (there is no build step). Uncomment the redirect rule.

### 2. Add Gmail App Password to `.env`

```
GMAIL_SENDER=your@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
DIGEST_RECIPIENT_EMAIL=your@gmail.com
```

Generate App Password at: https://myaccount.google.com/apppasswords (requires 2FA on account).

### 3. Update PWA URL in `.env` (after Netlify deploy)

```
PWA_URL=https://reconnect-app.netlify.app
```

### 4. Python dependencies (no changes needed)

`smtplib` and `email.mime` are Python stdlib. No new packages required. The existing
`google-api-python-client>=2.100.0` and `google-auth-oauthlib>=1.1.0` can remain in
`pyproject.toml` as-is (they're used for other things or can be kept for the OAuth fallback).

### 5. Netlify site configuration (one-time in Netlify UI)

- Set base directory: `/` (repo root)
- Set publish directory: `pwa`
- Set build command: (leave empty)
- Connect to `eg-connect` GitHub repo if not already
- Site name: customize to `reconnect-app` (gives `reconnect-app.netlify.app`)

---

## Confidence Assessment

| Decision | Confidence | Source |
|----------|------------|--------|
| Netlify SPA redirect syntax | HIGH | Netlify official docs: docs.netlify.com/configure-builds/javascript-spas/ |
| No build command for vanilla JS PWA | HIGH | Netlify official docs: static sites need no build command |
| service-worker.js Cache-Control header | HIGH | Netlify community + Vite PWA docs |
| Gmail inline CSS support | HIGH | Google's official CSS support page for Gmail |
| Gmail 102KB clip limit | HIGH | Multiple sources including Google's own documentation |
| `display:flex` partial Gmail support | HIGH | caniemail.com data, confirmed by multiple sources |
| Gmail App Password SMTP on port 465 | HIGH | Google's own SMTP settings documentation |
| @supabase/supabase-js @2 on CDN | HIGH | jsDelivr package page, latest 2.98.0 confirmed |
| MJML vs hand-rolled HTML recommendation | MEDIUM | Complexity/benefit tradeoff, single-developer context |
| Gmail App Password vs OAuth tradeoff | MEDIUM | Standard practice for personal/pipeline use cases |

---

## Sources

- [Netlify JavaScript SPAs docs](https://docs.netlify.com/configure-builds/javascript-spas/) — SPA redirect configuration
- [Netlify File-based configuration](https://docs.netlify.com/build/configure-builds/file-based-configuration/) — netlify.toml reference
- [Netlify Get started with domains](https://docs.netlify.com/manage/domains/get-started-with-domains/) — Custom domain / netlify.app subdomain
- [Gmail CSS Support | Google for Developers](https://developers.google.com/workspace/gmail/design/css) — Authoritative Gmail CSS support list
- [Can I email… display:flex](https://www.caniemail.com/features/css-display-flex/) — Email client flex support matrix
- [HTML and CSS in Emails: What Works in 2026](https://designmodo.com/html-css-emails/) — Current email CSS landscape
- [The Complete Guide to Email Client Rendering Differences in 2026](https://dev.to/mailpeek/the-complete-guide-to-email-client-rendering-differences-in-2026-243f) — Multi-client compatibility
- [Gmail Email Clipping and How to Avoid It](https://www.emailonacid.com/blog/article/email-development/gmail-email-clipping/) — 102KB limit guidance
- [Why Inline CSS Is Still Essential for HTML Emails](https://www.francescatabor.com/articles/2025/12/12/why-inline-css-is-still-essential-for-html-emails) — 2025 confirmation of inline CSS best practice
- [@supabase/supabase-js on jsDelivr](https://www.jsdelivr.com/package/npm/@supabase/supabase-js) — CDN version reference
- [Python Send Email Gmail smtplib 2026](https://mailtrap.io/blog/python-send-email-gmail/) — SMTP_SSL App Password pattern
- [Gmail API Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) — OAuth alternative reference
- [Vite PWA Netlify deployment](https://vite-pwa-org.netlify.app/deployment/netlify) — PWA headers reference
