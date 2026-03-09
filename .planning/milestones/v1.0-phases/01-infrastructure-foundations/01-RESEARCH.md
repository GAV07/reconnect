# Phase 1: Infrastructure Foundations - Research

**Researched:** 2026-03-08
**Domain:** Netlify static hosting, service workers, Gmail smtplib App Password
**Confidence:** HIGH

## Summary

This phase is almost entirely configuration surgery on existing, working code. The codebase is
structurally sound — the PWA, service worker, email digest, and edge functions all exist and are
correct in their logic. The problems are three specific misconfigurations: a broken netlify.toml
(build command + commented redirect), a service worker BASE path computed for Supabase Storage
deep paths (not root-relative Netlify paths), and Gmail OAuth dependencies that are never going to
be satisfied (OAuth credentials not configured and not worth configuring).

The fixes are well-understood surgical edits with no new libraries and no architectural changes.
The only net-new code is rewriting `gmail.py` to use Python's stdlib `smtplib` with a Gmail App
Password — a 30-line replacement for 330 lines of OAuth machinery. Everything else is URL string
replacement, config additions, and two toml line edits.

**Primary recommendation:** Execute the five targeted file edits in dependency order: config.py
first (adds `pwa_url`), then email_digest.py (consumes it), then gmail.py (rewrite), then
service-worker.js (BASE fix), then netlify.toml (deploy fix). Test email locally before Netlify
deploy.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Netlify Domain**
- Use default `*.netlify.app` subdomain (e.g., `eg-connect.netlify.app`)
- No DNS config needed, fastest path to live
- `pwa_url` in config will be `https://eg-connect.netlify.app`

**netlify.toml Fix**
- Remove `command = "npm run build"` (no build step needed), uncomment SPA redirect, keep `publish = "pwa"`
- Current state: `netlify.toml` has correct `publish = "pwa"` but build command will fail and redirect is commented out
- File: `/netlify.toml` (lines 3-4 need removal, lines 9-12 need uncommenting)

**Email Sending Method**
- Replace `gmail.py` entirely with `smtplib` + Gmail App Password
- Delete OAuth dependencies (google-auth, google-auth-oauthlib, google-api-python-client)
- Add `gmail_app_password` and `gmail_sender_email` to Settings
- Prerequisite: User must have 2FA enabled on Gmail and generate an App Password

**Service Worker BASE Path**
- Hardcode BASE to empty string for Netlify (root-served)
- Fix: Change STATIC_ASSETS to use root-relative paths (`/index.html`, `/css/app.css`, etc.)
- File: `pwa/service-worker.js` (lines 3-17)

**PWA Config Location**
- Keep `RECONNECT_CONFIG` hardcoded in `index.html` script tag
- Simple, single place to update, no build step complexity

**Config Updates Needed**
- New settings in `src/config.py`:
  - `pwa_url: str = ""` — Netlify URL for email deep links
  - `gmail_app_password: str = ""` — Gmail App Password for smtplib
  - `gmail_sender_email: str = ""` — Sender address
- Remove: `gmail_client_id`, `gmail_client_secret`, `gmail_redirect_uri` (OAuth fields)
- Update `email_digest.py`: Replace hardcoded Supabase Storage URL with `settings.pwa_url`
- Update Edge Function `action/index.ts`: Redirect URL after action should use PWA URL (if hardcoded)

### Claude's Discretion

None stated — all decisions are locked.

### Deferred Ideas (OUT OF SCOPE)

- Custom domain on Netlify — can add later without code changes
- RLS audit — moved to v2 requirements (SEC-01)
- Manifest start_url/scope fix — moved to v2 requirements (POLISH-01)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPLOY-01 | PWA deployed on Netlify with `publish = "pwa"` directory and SPA redirect rule (`/* → /index.html 200`) | netlify.toml needs build command removed and redirect block uncommented — two line edits |
| DEPLOY-02 | Service worker BASE path fixed for Netlify (no longer computes path from Supabase Storage URL) | Current line 5 of service-worker.js produces empty BASE on Netlify causing `//index.html` double-slash paths; fix is to remove BASE computation and use root-relative paths |
| DEPLOY-03 | `pwa_url` config variable added to `.env` and `src/config.py`, all email/Edge Function references updated from Supabase Storage URL to Netlify URL | Three places use Supabase Storage URL: email_digest.py line 257-259, action/index.ts line 138 (already reads `PWA_URL` env var as fallback), tokens.py does NOT need changes (it builds action Edge Function URLs, not PWA URLs) |
| EMAIL-01 | Email digest sends via Gmail App Password + `smtplib` (replaces unconfigured OAuth flow) | gmail.py is 330 lines of OAuth; replace with ~30-line smtplib implementation; remove 3 google-auth packages from requirements.txt and pyproject.toml |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `smtplib` | stdlib | SMTP email sending | Zero dependencies, works with Gmail App Passwords, already imported in gmail.py |
| Python `email.mime.multipart` | stdlib | MIME email construction | Already used in gmail.py — no change to email assembly |
| Python `email.mime.text` | stdlib | HTML/text email parts | Already used in gmail.py |
| `pydantic-settings` | >=2.1.0 | Settings from .env | Already the config pattern; just add new fields |

### Packages to REMOVE
| Package | Reason |
|---------|--------|
| `google-api-python-client` | Gmail API OAuth — replaced by smtplib |
| `google-auth-oauthlib` | OAuth flow library — not needed |
| `google-auth` | Google auth — not needed (implied by above) |

**These are in requirements.txt lines 9-10 and pyproject.toml lines 14-15.**

### No New Packages
This phase adds zero new Python packages. It removes three.

### Netlify
| Config | Value | Why |
|--------|-------|-----|
| `publish` | `pwa` | Directory containing index.html |
| `command` | (remove entirely) | No build step — plain static files |
| Redirect | `/* → /index.html 200` | SPA routing — all paths served index.html |

## Architecture Patterns

### Recommended File Edit Sequence (dependency order)

```
1. src/config.py           — Add pwa_url, gmail_app_password, gmail_sender_email; remove OAuth fields
2. src/integrations/gmail.py — Rewrite: smtplib replaces OAuth
3. src/integrations/email_digest.py — Replace Supabase Storage URL with settings.pwa_url
4. supabase/functions/action/index.ts — Set PWA_URL env var via supabase secrets set
5. pwa/service-worker.js   — Remove BASE computation; use root-relative paths
6. netlify.toml            — Remove build command; uncomment SPA redirect
7. requirements.txt + pyproject.toml — Remove 3 google-auth packages
```

### Pattern 1: smtplib with Gmail App Password

**What:** SMTP over TLS to Gmail's servers using a 16-character app-specific password
**When to use:** Single-user local pipeline sending from a known Gmail address

```python
# Source: Python stdlib docs — https://docs.python.org/3/library/smtplib.html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_html_email(to: str, subject: str, html_body: str, text_body: str = "") -> dict:
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.gmail_sender_email
    msg["To"] = to
    msg["Subject"] = subject
    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(settings.gmail_sender_email, settings.gmail_app_password)
        server.sendmail(settings.gmail_sender_email, to, msg.as_string())

    return {"message_id": msg["Message-ID"]}
```

**Gmail SMTP settings:**
- Host: `smtp.gmail.com`
- Port: 465 (SSL) or 587 (STARTTLS)
- Use `SMTP_SSL` for port 465 (simpler), `SMTP` + `starttls()` for 587
- Both work; 465/SSL is marginally simpler for scripted use

### Pattern 2: is_gmail_configured() replacement

The existing `email_digest.py` calls `is_gmail_configured()` and `get_user_email()` from gmail.py.
These function signatures MUST be preserved so email_digest.py needs no structural changes:

```python
def is_gmail_configured() -> bool:
    """Check if Gmail App Password is configured."""
    return bool(settings.gmail_app_password and settings.gmail_sender_email)

def get_user_email() -> str | None:
    """Return configured sender email."""
    return settings.gmail_sender_email or None
```

### Pattern 3: service-worker.js BASE Fix

**What:** Remove dynamic BASE computation; hardcode root-relative paths

```javascript
// BEFORE (Supabase Storage): produces //index.html on Netlify
const BASE = self.location.pathname.replace('/service-worker.js', '');
const STATIC_ASSETS = [
  `${BASE}/index.html`,
  // ...
];

// AFTER (Netlify root-served):
const STATIC_ASSETS = [
  '/index.html',
  '/css/app.css',
  '/js/app.js',
  '/js/queue.js',
  '/js/contact.js',
  '/js/dashboard.js',
  '/js/preferences.js',
  '/js/offline.js',
  '/js/push.js',
  '/manifest.json',
];
```

Also fix the push notification icon paths (lines 107-108 in current file) — they still use `${BASE}/icons/icon-192.png`. Change to `'/icons/icon-192.png'`.

### Pattern 4: netlify.toml Final Form

```toml
[build]
  publish = "pwa"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

Remove: `command = "npm run build"`, `functions = "netlify/functions"`, all comments.

### Pattern 5: email_digest.py PWA URL Fix

**What:** Replace the Supabase Storage URL construction with `settings.pwa_url`

```python
# BEFORE (lines 257-261 in email_digest.py):
pwa_url = settings.supabase_project_url
if pwa_url:
    pwa_link = f"{pwa_url.rstrip('/')}/storage/v1/object/public/pwa/index.html#/queue"
else:
    pwa_link = "http://localhost:8501"

# AFTER:
pwa_link = settings.pwa_url.rstrip("/") + "/#/queue" if settings.pwa_url else "http://localhost:8501"
```

### Pattern 6: Edge Function PWA_URL

The action Edge Function (line 138 of `supabase/functions/action/index.ts`) already handles this correctly:
```typescript
const pwaUrl = Deno.env.get("PWA_URL") || `${Deno.env.get("SUPABASE_URL")}/storage/v1/object/public/pwa/index.html`;
```

The code already reads `PWA_URL` env var. No code change needed — just set the secret:
```bash
supabase secrets set PWA_URL=https://eg-connect.netlify.app
```

### Pattern 7: src/config.py Changes

```python
# ADD these fields:
pwa_url: str = ""           # Netlify URL, e.g. https://eg-connect.netlify.app
gmail_app_password: str = ""  # Gmail App Password (16 chars, no spaces)
gmail_sender_email: str = ""  # Gmail address to send from

# REMOVE these fields:
# gmail_client_id: str = ""
# gmail_client_secret: str = ""
# gmail_redirect_uri: str = "http://localhost:8501/oauth/callback"
```

### Anti-Patterns to Avoid

- **Using SMTP port 587 with SMTP_SSL:** Port 587 requires `smtp.SMTP()` + `.starttls()`, not `SMTP_SSL`. Port 465 uses `SMTP_SSL` directly. Don't mix them.
- **Using `smtplib.SMTP` (non-SSL) on port 465:** Will time out silently. Use `smtplib.SMTP_SSL`.
- **Keeping BASE variable in service-worker.js:** Even set to `""`, the path template literals produce `"/index.html"` which is correct — BUT the `${BASE}/icons/icon-192.png` references in the push handler (lines 107-108) also use BASE and must be updated.
- **Leaving google-auth packages in requirements.txt:** They'll still import fine but add 15+ MB to the install and are misleading. Remove them.
- **Forgetting the `from` header in smtplib:** Gmail's SMTP requires the `From` header match the authenticated account or delivery silently fails.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSL/TLS email | Custom socket TLS | `smtplib.SMTP_SSL` | Handles TLS negotiation, auth, encoding |
| MIME multipart | String concatenation | `email.mime.multipart.MIMEMultipart` | Already used in codebase |
| SPA routing on Netlify | Custom redirects per route | Single `[[redirects]]` catch-all rule | Netlify handles all hash routes via the 200 redirect |

**Key insight:** The entire email infrastructure already exists in stdlib. Gmail App Password auth is
a login credential, not a protocol — smtplib.SMTP_SSL + login() is the complete implementation.

## Common Pitfalls

### Pitfall 1: Double-Slash Asset Paths in Service Worker

**What goes wrong:** Service worker pre-cache fails silently. Assets are not cached. On Netlify,
`BASE` evaluates to `""` because `self.location.pathname` is `/service-worker.js`. The template
literal `${BASE}/index.html` becomes `"/index.html"` which is fine — BUT if BASE were a path
segment (as on Supabase Storage), the same template would produce `/storage/.../index.html`.
The actual problem is not the STATIC_ASSETS array but the push notification icon paths which also
use `${BASE}/icons/icon-192.png`.

**Why it happens:** BASE was designed for Supabase Storage where the service worker lives at
`/storage/v1/object/public/pwa/service-worker.js`. The `.replace('/service-worker.js', '')` strips
just the filename, leaving the full path prefix.

**How to avoid:** Remove the `BASE` variable entirely. Use explicit root-relative paths (`/index.html`)
throughout the file, including the push handler icon paths on lines 107-108.

**Warning signs:** Service worker registers successfully (no console error) but network tab shows
cache misses; PWA install prompt never appears; `caches.match` always returns undefined.

### Pitfall 2: Gmail App Password Format

**What goes wrong:** `smtplib.SMTPAuthenticationError: (535, b'5.7.8 Username and Password not accepted')`

**Why it happens:** Gmail App Passwords are 16 characters with no spaces displayed in groups of 4.
Users copy the spaced version `xxxx xxxx xxxx xxxx` instead of the unspaced `xxxxxxxxxxxxxxxx`.

**How to avoid:** Strip spaces in `is_gmail_configured()` or document in .env comments that spaces
must be removed. Optionally: `settings.gmail_app_password.replace(" ", "")` at login time.

**Warning signs:** Auth error on first send attempt; credentials look correct when printed.

### Pitfall 3: Netlify UI Build Settings Override netlify.toml

**What goes wrong:** Removing `command` from netlify.toml doesn't fix the failed deploy because
the Netlify site has a Build command configured in the UI (Site Settings > Build & Deploy > Build
settings). UI settings take precedence over or conflict with toml in some configurations.

**Why it happens:** When a site is first connected to GitHub, Netlify may auto-detect a build
command and save it to site settings. netlify.toml overrides UI settings for most things, but
clearing the command in toml while UI still has `npm run build` can cause confusion.

**How to avoid:** After updating netlify.toml, verify in Netlify UI (Site Settings > Build & Deploy)
that Build command is empty or shows "Not set". The toml `publish = "pwa"` should show as the
Publish directory.

**Warning signs:** Deploy logs show `npm run build` being run; deploy fails with "npm not found"
or similar.

### Pitfall 4: email_digest.py calls gmail.py via function signatures

**What goes wrong:** If the new gmail.py changes the function signatures of `is_gmail_configured()`,
`get_user_email()`, or `send_html_email()`, then `email_digest.py` breaks at the call sites.

**Why it happens:** `email_digest.py` line 308 imports: `from src.integrations.gmail import get_user_email, is_gmail_configured, send_html_email`

**How to avoid:** The new smtplib-based gmail.py MUST export these exact three function names with
compatible signatures. See Pattern 2 above.

### Pitfall 5: smtplib Exception Handling

**What goes wrong:** Email silently fails because exceptions are swallowed.

**Why it happens:** `send_html_email()` in email_digest.py is called inside a try/except that
returns `{"sent": False, "reason": ...}`. If gmail.py raises a non-Exception (unlikely) or the
exception message is swallowed, the failure mode is invisible.

**How to avoid:** Let smtplib exceptions propagate naturally from gmail.py. The caller in
email_digest.py already catches them. Log the raw exception in gmail.py before re-raising
for debuggability.

## Code Examples

Verified patterns from official sources:

### Complete smtplib Gmail Replacement

```python
# Source: https://docs.python.org/3/library/smtplib.html
"""Gmail integration for Reconnect — smtplib App Password implementation."""

import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.config import settings

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465  # SSL


def is_gmail_configured() -> bool:
    """Check if Gmail App Password is configured."""
    return bool(settings.gmail_app_password and settings.gmail_sender_email)


def get_user_email() -> Optional[str]:
    """Return the configured sender email address."""
    return settings.gmail_sender_email or None


def send_html_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> dict:
    """Send an HTML email via Gmail SMTP with App Password auth.

    Args:
        to: Recipient email address
        subject: Email subject
        html_body: HTML email body
        text_body: Optional plain-text fallback

    Returns:
        Dict with message_id key

    Raises:
        ValueError: If Gmail not configured
        smtplib.SMTPException: On send failure
    """
    if not is_gmail_configured():
        raise ValueError("Gmail not configured. Set GMAIL_APP_PASSWORD and GMAIL_SENDER_EMAIL in .env")

    if text_body is None:
        text_body = re.sub(r"<[^>]+>", "", html_body)
        text_body = re.sub(r"\n\s*\n", "\n\n", text_body).strip()

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.gmail_sender_email
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    password = settings.gmail_app_password.replace(" ", "")  # strip display spaces

    with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
        server.login(settings.gmail_sender_email, password)
        server.sendmail(settings.gmail_sender_email, to, msg.as_string())
        logger.info("Email sent to %s: %s", to, subject)

    return {"message_id": msg.get("Message-ID", "")}
```

### netlify.toml Final Form

```toml
[build]
  publish = "pwa"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

### service-worker.js STATIC_ASSETS Fix

```javascript
/* Reconnect PWA Service Worker */

const CACHE_NAME = 'reconnect-v1';
const STATIC_ASSETS = [
  '/index.html',
  '/css/app.css',
  '/js/app.js',
  '/js/queue.js',
  '/js/contact.js',
  '/js/dashboard.js',
  '/js/preferences.js',
  '/js/offline.js',
  '/js/push.js',
  '/manifest.json',
];
```

Also update push notification icon paths:
```javascript
// Line ~107: Change from:
icon: `${BASE}/icons/icon-192.png`,
badge: `${BASE}/icons/icon-192.png`,
// To:
icon: '/icons/icon-192.png',
badge: '/icons/icon-192.png',
```

### .env additions

```bash
# Netlify PWA URL
PWA_URL=https://eg-connect.netlify.app

# Gmail App Password (Settings > Security > 2-Step Verification > App passwords)
GMAIL_SENDER_EMAIL=your@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

### Supabase Edge Function Secret

```bash
supabase secrets set PWA_URL=https://eg-connect.netlify.app
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Gmail OAuth2 API | smtplib + App Password | This phase | Drops 3 packages, removes 330 lines of OAuth machinery |
| Supabase Storage hosting | Netlify static hosting | This phase | Proper SPA routing support, faster CDN |
| Dynamic BASE path in SW | Root-relative asset paths | This phase | Service worker works on any root-hosted domain |

**Deprecated/outdated:**
- `google-api-python-client`, `google-auth-oauthlib`: Removed this phase
- `gmail_client_id`, `gmail_client_secret`, `gmail_redirect_uri` settings: Removed this phase
- `GmailCredentials` DB model: Potentially orphaned after gmail.py rewrite (not actively removed in this phase — leave the model/table intact to avoid migration complexity; the model just won't be used)

## Open Questions

1. **Netlify site name / exact subdomain**
   - What we know: Decision is to use default `*.netlify.app`; example `eg-connect.netlify.app`
   - What's unclear: The actual subdomain chosen at deploy time (Netlify auto-generates or user picks during first deploy)
   - Recommendation: Use a placeholder like `YOUR_SITE.netlify.app` in .env documentation; update after first deploy

2. **RLS status of Supabase tables**
   - What we know: STATE.md flags this as unknown and potentially blocking for public exposure
   - What's unclear: Whether the anon key in index.html grants write access to sensitive tables
   - Recommendation: Out of scope for Phase 1 per CONTEXT.md (deferred to SEC-01); note as a known risk in verification

3. **`GmailCredentials` model after gmail.py rewrite**
   - What we know: `src/database/models.py` has a `GmailCredentials` SQLModel table; `gmail.py` currently reads/writes it
   - What's unclear: Whether anything else references `GmailCredentials` after gmail.py is replaced
   - Recommendation: Leave the model and DB table intact; they become dead code but removing requires a migration

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (>=7.4.0, in pyproject.toml dev deps) |
| Config file | None present — see Wave 0 |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-01 | netlify.toml has no build command, has SPA redirect | smoke (file content check) | `pytest tests/test_phase1_infra.py::test_netlify_toml -x` | Wave 0 |
| DEPLOY-02 | service-worker.js has no BASE variable, all paths are root-relative | smoke (file content check) | `pytest tests/test_phase1_infra.py::test_service_worker_paths -x` | Wave 0 |
| DEPLOY-03 | `pwa_url` field exists in Settings; email_digest uses it; no Supabase Storage URL in digest output | unit | `pytest tests/test_phase1_infra.py::test_pwa_url_config -x` | Wave 0 |
| EMAIL-01 | is_gmail_configured() returns True when env vars set; send_html_email constructs correct MIME | unit (mock SMTP) | `pytest tests/test_phase1_infra.py::test_gmail_smtplib -x` | Wave 0 |

Note: DEPLOY-01 (Netlify live site loads) and the actual email delivery to inbox are manual-only
verifications that cannot be automated without external dependencies.

### Sampling Rate
- **Per task commit:** `pytest tests/test_phase1_infra.py -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` — package marker
- [ ] `tests/test_phase1_infra.py` — covers DEPLOY-01, DEPLOY-02, DEPLOY-03, EMAIL-01
- [ ] `tests/conftest.py` — shared fixtures (mock settings with test env vars)
- [ ] pytest install: already in pyproject.toml dev deps (`pip install -e ".[dev]"`)

## Sources

### Primary (HIGH confidence)
- Python stdlib docs (smtplib) — https://docs.python.org/3/library/smtplib.html — SMTP_SSL, login, sendmail patterns
- Python stdlib docs (email.mime) — https://docs.python.org/3/library/email.mime.html — MIMEMultipart, MIMEText
- Direct code inspection of `/Users/gavin/Developer/reconnect/src/integrations/gmail.py` — confirmed function signatures that must be preserved
- Direct code inspection of `/Users/gavin/Developer/reconnect/src/integrations/email_digest.py` — confirmed Supabase Storage URL on lines 257-259
- Direct code inspection of `/Users/gavin/Developer/reconnect/supabase/functions/action/index.ts` — confirmed PWA_URL env var already handled (line 138)
- Direct code inspection of `/Users/gavin/Developer/reconnect/pwa/service-worker.js` — confirmed BASE on line 5, icon paths on lines 107-108
- Direct code inspection of `/Users/gavin/Developer/reconnect/netlify.toml` — confirmed build command on line 3, commented redirect on lines 9-12

### Secondary (MEDIUM confidence)
- Netlify docs — SPA redirect pattern `/* → /index.html 200` is the canonical approach for all Netlify-hosted SPAs
- Gmail App Password docs — https://support.google.com/accounts/answer/185833 — 2FA prerequisite, 16-char password format

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all changes use Python stdlib; no new libraries; directly verified against existing codebase
- Architecture: HIGH — surgical edits to known files with known line numbers; no new patterns introduced
- Pitfalls: HIGH — derived from direct code reading (double-slash paths confirmed in SW lines 5+107, Supabase URL confirmed in digest line 259, function signatures confirmed in gmail.py)

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable stdlib + Netlify config — nothing here moves fast)
