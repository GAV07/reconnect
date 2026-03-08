# Architecture Patterns

**Domain:** Netlify PWA + actionable HTML email + Supabase backend
**Researched:** 2026-03-08

---

## Current Architecture (Baseline)

```
Local Python Pipeline (LaunchAgent @ 8AM)
  └── SQLite (local) ←→ Supabase PostgreSQL (cloud sync via push.py/pull.py)
        └── Supabase Edge Functions (action, draft, feedback)
              └── PWA (vanilla JS, served from Supabase Storage — broken path)
Email digest HTML generated locally, not sent (Gmail OAuth missing)
```

**What's broken today:**
- PWA served from Supabase Storage object URL — not a real SPA deployment, hash routing works by accident, no custom domain, no CI/CD
- Email digest generates HTML but cannot send (Gmail OAuth not configured)
- `pwa_link` in email digest still points to Supabase Storage URL, not Netlify

---

## Target Architecture

```
┌──────────────────────────────────────────────────────────┐
│  LOCAL (macOS, LaunchAgent @ 8AM)                        │
│                                                          │
│  daily_pipeline.py                                       │
│    ├── Import / prescore / enrich / score / queue       │
│    ├── Generate action tokens → action_tokens table     │
│    ├── Build HTML digest (pwa_link = Netlify URL)       │
│    └── Send email via SMTP/Resend → user's inbox        │
│                                                          │
│  SQLite ←→ push.py / pull.py ←→ Supabase PostgreSQL    │
└──────────────────┬───────────────────────────────────────┘
                   │ Supabase REST / Realtime WS
        ┌──────────▼─────────────────────────────────┐
        │  SUPABASE (AWS US East 2)                   │
        │                                             │
        │  PostgreSQL tables:                         │
        │    connections, outreach_queue,             │
        │    action_tokens, user_feedback,            │
        │    user_preferences, pipeline_runs, ...     │
        │                                             │
        │  Edge Functions (Deno):                     │
        │    /functions/v1/action   (--no-verify-jwt) │
        │    /functions/v1/draft    (anon key)        │
        │    /functions/v1/feedback (--no-verify-jwt) │
        └──────────┬──────────────────────────────────┘
                   │ HTTPS
        ┌──────────▼──────────────────────────────────┐
        │  NETLIFY (CDN, static hosting)              │
        │                                             │
        │  Publishes: /pwa → index.html               │
        │  netlify.toml: publish = "pwa"              │
        │  _redirects: /* → /index.html 200          │
        │  (hash routing: client-side only, no        │
        │   server routing needed)                    │
        │                                             │
        │  PWA pages (vanilla JS, hash router):       │
        │    #/queue          — daily triage          │
        │    #/contact/:id   — enriched profile       │
        │    #/dashboard     — pipeline funnel        │
        │    #/preferences   — settings               │
        └─────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `daily_pipeline.py` | Orchestrates all 10 pipeline steps each morning | SQLite, Supabase (via push.py), email SMTP |
| `email_digest.py` | Generates HTML email with token-based action buttons | `tokens.py`, pipeline results, Supabase (via push.py) |
| `tokens.py` | Creates one-time-use UUID tokens in `action_tokens` table | SQLite → synced to Supabase |
| `push.py / pull.py` | Bidirectional sync local SQLite ↔ Supabase PostgreSQL | SQLite, Supabase REST |
| `action` Edge Function | Validates tokens, executes approve/skip/snooze, returns HTML confirmation | Supabase DB (service role), redirects to Netlify PWA |
| `draft` Edge Function | Generates outreach message via LLM on demand | Supabase DB, OpenAI API |
| `feedback` Edge Function | Records user feedback from PWA actions | Supabase DB |
| PWA (`pwa/`) | Daily review queue, contact profiles, dashboard | Supabase REST (anon key), Edge Functions |
| Netlify | Hosts PWA static files with proper SPA deployment | CDN delivery only — no server logic |

---

## Data Flow

### Morning Email Flow (daily)

```
8AM LaunchAgent
  → daily_pipeline.py
  → generates outreach_queue items (Supabase + SQLite)
  → for each featured contact, tokens.py inserts into action_tokens
  → email_digest.py builds HTML with:
      - "Reach Out" button → https://PROJECT.supabase.co/functions/v1/action?token=UUID
      - "Skip" button     → https://PROJECT.supabase.co/functions/v1/action?token=UUID
      - "Snooze" button   → https://PROJECT.supabase.co/functions/v1/action?token=UUID
      - "View Profile" link → https://NETLIFY_DOMAIN/#/contact/CONNECTION_ID?queue_item=ITEM_ID
      - "Open Queue" link  → https://NETLIFY_DOMAIN/#/queue
  → email sent to inbox via SMTP/Resend
```

### Email Action Flow (click from inbox)

```
User clicks "Reach Out" in email
  → GET https://PROJECT.supabase.co/functions/v1/action?token=UUID
  → action Edge Function:
      1. Looks up token in action_tokens (service role)
      2. Checks: not used, not expired
      3. Updates outreach_queue status = "approved"
      4. Marks token used = true
      5. Returns HTML confirmation page with "Open Queue" button
         pointing to https://NETLIFY_DOMAIN/#/queue
  → User taps "Open Queue" → PWA loads on queue page
```

### PWA → Supabase Direct Flow

```
User opens PWA at https://NETLIFY_DOMAIN/#/queue
  → Supabase JS SDK (CDN) initializes with anon key
  → fetchs outreach_queue JOIN connections via REST
  → User taps "Reach Out" in PWA:
      → PATCH outreach_queue SET status='approved'
      → navigate to #/contact/CONNECTION_ID?queue_item=ITEM_ID
  → Contact profile page:
      → fetch connections WHERE id=CONNECTION_ID
      → render score breakdown, hooks, key factors
      → user taps "Generate Draft":
          → POST /functions/v1/draft {queue_item_id}
          → returns LLM-generated message
  → Realtime subscription:
      → supabase.channel('queue-changes')
      → .on('postgres_changes', INSERT on outreach_queue, refresh)
```

### Email Deep Link to Contact Profile

```
Email contains: <a href="https://NETLIFY_DOMAIN/#/contact/abc123?queue_item=456">View Profile</a>

User clicks link:
  → Browser opens https://NETLIFY_DOMAIN/#/contact/abc123?queue_item=456
  → Netlify serves index.html (hash routes never hit server)
  → app.js parses hash: route = /contact, params.id = "abc123"
  → getQueryParams() extracts queue_item=456
  → renderContact(container, "abc123") fetches connection data
  → contact.js renders profile + score breakdown + draft button
```

**Key insight:** Because this PWA uses hash-based routing (`#/route`), Netlify does NOT need the `/* → /index.html 200` redirect for deep links. The hash fragment is never sent to the server. Netlify serves `index.html` for the root URL, and the JS router handles everything after `#`. The `_redirects` or `[[redirects]]` rule is only needed as a safety net for accidentally clean URLs.

---

## Patterns to Follow

### Pattern 1: Token-Per-Action, Not Token-Per-Contact

**What:** Create separate tokens for approve, skip, snooze per contact.
**When:** Always — each button in email must be an independent one-time link.
**Why:** Prevents double-execution. Token is consumed on first click.

```python
# tokens.py (existing, correct pattern)
for action in ["approve", "skip", "snooze"]:
    token = ActionToken(action=action, queue_item_id=..., expires_at=...)
    session.add(token)
urls[action] = get_action_url(token.token)
```

**TTL recommendation:** Set `action_token_ttl_hours` to 48-72 hours (digest arrives at 8AM, user might act 2 days later). Current code already supports TTL config.

### Pattern 2: Email Security Bot Mitigation

**What:** Email security scanners pre-click links in corporate inboxes to detect phishing. This can consume one-time action tokens before the user acts.

**Why it matters:** The existing token pattern marks tokens as `used=true` on first click. A scanner click = token burned.

**Mitigations (pick one or combine):**
1. **Confirmation page (already implemented):** Action Edge Function returns an HTML page with a "Confirm" button. Scanners fetch the GET URL but do not interact with resulting pages. User still sees a human-readable confirmation before anything is committed. BUT: the existing implementation executes the action immediately on GET — this needs review.
2. **POST-on-confirm:** GET → show confirmation HTML with a form → user submits POST → action executes. Scanners only follow GET. This is the most robust mitigation.
3. **Generous TTL + re-queue:** If a token is scanned and consumed, the user sees "already used" — frustrating but recoverable if you provide a "View queue" link on that page.

**Recommended implementation:** Convert action Edge Function to: GET → show confirmation HTML → POST → execute action. Modify the `htmlResponse` function to render a page with a form `<form method="POST" action="...">` that re-submits to the same Edge Function. Supabase Edge Functions support POST requests natively.

### Pattern 3: Netlify Configuration for PWA Subdirectory

**What:** Netlify's `netlify.toml` must set `publish = "pwa"` to deploy from the `pwa/` subdirectory.
**When:** Required — the repo root is `reconnect/`, not the site root.

```toml
[build]
  publish = "pwa"
  # No build command needed — vanilla JS, no compilation

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

No `_redirects` file needed inside `pwa/` if `netlify.toml` is at repo root. Either approach works; `netlify.toml` is preferred (version controlled, UI-independent).

### Pattern 4: PWA Netlify URL in Email Digest

**What:** `email_digest.py` currently hardcodes `pwa_link` to Supabase Storage URL. Must update to read from config.
**When:** Required — every "Open Queue" and "View Profile" link in email must use the Netlify domain.

```python
# config.py — add setting
pwa_url: str = "https://reconnect.netlify.app"  # or custom domain

# email_digest.py — use config
pwa_link = f"{settings.pwa_url}/#/queue"
profile_link = f"{settings.pwa_url}/#/contact/{conn.id}?queue_item={queue_item.id}"
```

### Pattern 5: Anon Key in Vanilla JS (Acceptable Risk)

**What:** Supabase anon key is hardcoded in `index.html` and `window.RECONNECT_CONFIG`.
**When:** Acceptable for a single-user tool — the anon key is public by design and Supabase RLS policies constrain what it can do.
**Caution:** Do not use service role key in the PWA. Edge Functions use service role server-side, which is correct.

### Pattern 6: Realtime Subscription for Live Queue Updates

**What:** PWA subscribes to `postgres_changes` on `outreach_queue` via Supabase Realtime WebSocket.
**Current state:** Already implemented in `queue.js` via `setupQueueRealtime()`.
**Pattern:** Load initial data with REST query first, then subscribe to changes — avoids the race condition between initial load and subscription.

```javascript
// queue.js (existing — correct pattern)
await renderQueue(content);       // REST fetch first
setupQueueRealtime();             // then subscribe
```

### Pattern 7: Service Worker Cache-Busting on Deploy

**What:** Service worker `reconnect-v1` caches static assets. After Netlify deploys a new version, old SW caches stale files.
**Prevention:** Increment cache version on any significant JS/CSS change (`reconnect-v2`, etc.). The `activate` handler already deletes old cache names.
**Note:** `service-worker.js` uses `self.location.pathname` for BASE path — this works correctly on Netlify (served from root, BASE becomes empty string).

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Supabase Storage as SPA Host

**What:** Hosting PWA via `supabase.co/storage/v1/object/public/pwa/index.html`
**Why bad:** No SPA routing support, files served at deep paths break relative asset URLs, no custom domain, no HTTPS with custom cert, no deployment pipeline, no cache control headers, PWA install/service-worker scope is wrong.
**Instead:** Netlify with `publish = "pwa"` — proper CDN, SPA routing via redirects, custom domain, automatic deploys on git push.

### Anti-Pattern 2: Hardcoded Supabase Storage URL in Email Digest

**What:** `pwa_link = f"{pwa_url}/storage/v1/object/public/pwa/index.html#/queue"`
**Why bad:** Every emailed link becomes stale immediately after switching to Netlify. URLs in sent emails are permanent.
**Instead:** Config-driven `settings.pwa_url`, set in `.env` as `PWA_URL=https://reconnect.netlify.app`.

### Anti-Pattern 3: Immediate GET-Executes-Action Pattern

**What:** Current `action` Edge Function executes the action (approve/skip/snooze) on the initial GET request.
**Why bad:** Email security scanners pre-click all links in inboxes to detect phishing. A scanner click consumes the token before the user acts. User then sees "Token already used" and cannot act from email.
**Instead:** GET request shows a confirmation HTML page. User clicks "Confirm" which submits a POST. Action executes on POST only. Scanners only follow GETs.

### Anti-Pattern 4: Draft Generation at Digest Time

**What:** Pre-generating LLM outreach drafts for all contacts during the pipeline run, embedding them in email.
**Why bad:** Wastes LLM tokens on contacts user may skip. Drafts are stale by the time user acts. Email body bloat.
**Instead:** Current architecture is correct — drafts generated on-demand from the PWA contact page via the `draft` Edge Function.

### Anti-Pattern 5: Additional View Pages not in PWA Pages Missing Features

**What:** Email links to contact profile page (`#/contact/:id`) but the PWA needs pipeline funnel, enrichment status, and feedback history views — these are not currently in the nav or router.
**Why bad:** If user clicks "View Full Queue" from email and expects the full app, missing nav items degrade the experience.
**Instead:** Add missing routes during PWA buildout phase: `#/funnel`, `#/enrichment`, `#/history` — these are additive and follow the existing router pattern.

---

## Component Build Order (Dependencies)

The following order minimizes blocked work:

```
1. Netlify deployment (netlify.toml, _redirects)
   → Unblocks: all PWA deep links, installability, service worker scope

2. Config update (settings.pwa_url, action Edge Function PWA_URL secret)
   → Unblocks: correct links in email digest, correct "Open Queue" button
     in action confirmation page

3. Email send method (Resend/SMTP configuration)
   → Unblocks: actual delivery — digest HTML already generates correctly

4. Action Edge Function: GET confirmation → POST execute
   → Unblocks: bot-safe email actions (can ship without, but should be early)

5. Email "View Profile" deep links per contact
   → Depends on: #1 (Netlify deployed), #2 (correct PWA URL in config)

6. PWA queue review (exists, needs polish + test on Netlify domain)
   → Depends on: #1

7. PWA contact profile (exists, needs enrichment data + reasoning surfaced)
   → Depends on: #1, #6

8. PWA dashboard / funnel view (new page)
   → Depends on: #1

9. PWA enrichment status view (new page)
   → Depends on: #1

10. PWA feedback history (new page)
    → Depends on: #1
```

**Critical path:** Netlify deployment → Config update → Email send → then all features unlock in parallel.

---

## Scalability Considerations

This is a single-user tool, so scalability concerns are minimal, but the architecture has appropriate separation:

| Concern | Current Approach | Notes |
|---------|-----------------|-------|
| Realtime connections | 1 user, 1 Supabase Realtime WS | Fine — Supabase free tier supports hundreds of concurrent |
| Token volume | ~5-10 tokens/day (featured contacts) | Tokens table needs periodic cleanup of expired tokens |
| Edge Function cold starts | Deno runtime, Supabase Edge — cold start ~200-500ms | Only triggered on email action or draft request, acceptable |
| Netlify CDN | Static files, no compute | Netlify free tier has 100GB bandwidth/month — no concern |
| Supabase REST queries | REST with anon key, PostgREST auto-indexes | Connection table may need index on `reconnect_score` as it grows |

---

## Sources

- Netlify SPA documentation: [JavaScript SPAs | Netlify Docs](https://docs.netlify.com/configure-builds/javascript-spas/)
- Netlify file-based config: [File-based configuration | Netlify Docs](https://docs.netlify.com/build/configure-builds/file-based-configuration/)
- Netlify + Supabase integration: [Supabase integration | Netlify Docs](https://docs.netlify.com/extend/install-and-use/setup-guides/supabase-integration/)
- Supabase Edge Functions architecture: [Edge Functions Architecture | Supabase Docs](https://supabase.com/docs/guides/functions/architecture)
- Supabase Realtime patterns: [Realtime - Postgres changes | Supabase Features](https://supabase.com/features/realtime-postgres-changes)
- Email security bot click behavior: [When Bots Interfere With Links in Your Email](https://www.highroadsolutions.com/blog/when-bots-interfere-with-links-in-your-email-heres-what-to-do)
- Magic link / one-time token security: [Magic Links — Clerk Blog](https://clerk.com/blog/magic-links)
- Existing codebase: `pwa/`, `supabase/functions/`, `src/integrations/email_digest.py`, `src/api/tokens.py`

---

**Confidence assessment:**

| Area | Confidence | Notes |
|------|------------|-------|
| Netlify SPA deployment config | HIGH | Official Netlify docs verified |
| Hash routing on Netlify | HIGH | Hash fragment never hits server — no redirect needed for deep links |
| Token-based email actions | HIGH | Pattern verified against existing implementation |
| Bot scanner mitigation via GET/POST split | MEDIUM | Well-known pattern, not Supabase-specific docs found |
| Supabase anon key in vanilla JS | HIGH | By design — Supabase anon key is a published secret |
| Service worker on Netlify | HIGH | Standard behavior, existing SW code is correct |
