# Phase 1 Context: Infrastructure Foundations

**Phase Goal:** PWA is live on Netlify and the daily email digest lands in the inbox
**Requirements:** DEPLOY-01, DEPLOY-02, DEPLOY-03, EMAIL-01

## Decisions

### Netlify Domain
- **Decision:** Use default `*.netlify.app` subdomain (e.g., `eg-connect.netlify.app`)
- **Rationale:** No DNS config needed, fastest path to live
- **Impact:** `pwa_url` in config will be `https://eg-connect.netlify.app`

### netlify.toml Fix
- **Decision:** Remove `command = "npm run build"` (no build step needed), uncomment SPA redirect, keep `publish = "pwa"`
- **Current state:** `netlify.toml` has correct `publish = "pwa"` but build command will fail and redirect is commented out
- **File:** `/netlify.toml` (lines 3-4 need removal, lines 9-12 need uncommenting)

### Email Sending Method
- **Decision:** Replace `gmail.py` entirely with `smtplib` + Gmail App Password
- **Rationale:** One env var (`GMAIL_APP_PASSWORD`) vs multi-step OAuth ceremony
- **Impact:** Delete OAuth dependencies (google-auth, google-auth-oauthlib, google-api-python-client), add `gmail_app_password` and `gmail_sender_email` to Settings
- **Prerequisite:** User must have 2FA enabled on Gmail and generate an App Password

### Service Worker BASE Path
- **Decision:** Hardcode BASE to empty string for Netlify (root-served)
- **Current state:** Line 5 computes BASE by stripping `/service-worker.js` from pathname — works on Supabase Storage deep path, produces empty string on Netlify which creates `//index.html` double-slash paths
- **Fix:** Change STATIC_ASSETS to use root-relative paths (`/index.html`, `/css/app.css`, etc.)
- **File:** `pwa/service-worker.js` (lines 3-17)

### PWA Config Location
- **Decision:** Keep `RECONNECT_CONFIG` hardcoded in `index.html` script tag
- **Rationale:** Simple, single place to update, no build step complexity

### Config Updates Needed
- **New settings in `src/config.py`:**
  - `pwa_url: str = ""` — Netlify URL for email deep links
  - `gmail_app_password: str = ""` — Gmail App Password for smtplib
  - `gmail_sender_email: str = ""` — Sender address
- **Remove:** `gmail_client_id`, `gmail_client_secret`, `gmail_redirect_uri` (OAuth fields)
- **Update `email_digest.py`:** Replace hardcoded Supabase Storage URL with `settings.pwa_url`
- **Update Edge Function `action/index.ts`:** Redirect URL after action should use PWA URL (if hardcoded)

## Code Context

### Files to Modify
| File | Change |
|------|--------|
| `netlify.toml` | Remove build command, uncomment redirect |
| `pwa/service-worker.js` | Fix BASE path to root-relative |
| `src/config.py` | Add pwa_url, gmail_app_password, gmail_sender_email; remove OAuth fields |
| `src/integrations/gmail.py` | Rewrite: replace OAuth with smtplib App Password |
| `src/integrations/email_digest.py` | Use `settings.pwa_url` for all links |
| `supabase/functions/action/index.ts` | Update redirect URL if hardcoded |
| `pwa/manifest.json` | Verify start_url and scope are correct for root serving |

### Reusable Assets
- `email_digest.py` HTML generation is solid — only link URLs need updating
- `src/api/tokens.py` token generation works — no changes needed
- `pwa/js/app.js` router already handles hash-based routing correctly
- Edge Functions are deployed and working

### Patterns to Follow
- Config: pydantic-settings `BaseSettings` in `src/config.py`, reads `.env`
- Logging: `logger = logging.getLogger(__name__)`
- Email: `MIMEMultipart` / `MIMEText` from stdlib (already imported in gmail.py)

## Deferred Ideas

- Custom domain on Netlify — can add later without code changes
- RLS audit — moved to v2 requirements (SEC-01)
- Manifest start_url/scope fix — moved to v2 requirements (POLISH-01)

---
*Context gathered: 2026-03-08*
