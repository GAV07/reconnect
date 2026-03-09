# Phase 2: Email Reliability - Research

**Researched:** 2026-03-08
**Domain:** HTML email rendering (Gmail), Supabase Edge Functions (Deno), PWA deep linking
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EMAIL-02 | Email card layout uses table-based HTML (not Flexbox) for Gmail mobile compatibility | Gmail strips Flexbox sub-properties; table layout with inline styles is the only reliable method across all Gmail clients |
| EMAIL-03 | Email action buttons are 44px+ tap targets with 600px max-width and 16px+ font | 44px is the iOS/Android HIG minimum; must be implemented with padding on `<td>` or `<a>` elements, not CSS height |
| EMAIL-04 | "View full profile" links use query parameters that survive Gmail's redirect chain | URL fragments (`#`) are stripped by HTTP redirects per RFC 3986; query parameters survive; PWA already has `getQueryParams()` that reads from the hash portion |
| EMAIL-05 | "Open LinkedIn" direct link included per contact in email digest | Straightforward `conn.linkedin_url` already stored in Connection model; needs dedicated link in email card |
| EMAIL-06 | "Yes" action auto-queues contact for outreach (no extra step) | Edge Function `action` already sets `status: "approved"` — the user sees "Open Queue to draft your message"; the gap is the EMAIL-04 deep link so PWA goes directly to contact |
| EMAIL-07 | Action Edge Function uses GET/POST split — GET shows confirmation page, POST executes action — preventing Gmail scanner token consumption | Gmail security scanner (and corporate link scanners) issue GET requests to all links in an email; executing state-changing actions on GET is the root bug; confirmed pattern: GET returns confirmation HTML with a POST form |
</phase_requirements>

---

## Summary

Phase 2 fixes six email reliability failures rooted in three distinct technical problems. First, the current `email_digest.py` uses `display:flex` and `justify-content` for the card layout — Gmail strips Flexbox sub-properties silently, causing the name and score badge to stack vertically rather than sit side-by-side. Second, the current action Edge Function executes state-changing operations (approve/skip/snooze) on any GET request, which means Gmail's security scanner can silently consume tokens before the user ever taps anything. Third, "View full profile" links embed a hash-fragment deep link that Gmail's redirect chain strips, landing users on the homepage instead of the contact page.

Each problem has a well-established fix. Gmail email layout must use `<table>` with `role="presentation"`, inline styles, and no Flexbox or Grid. The GET/POST scanner defense is a standard two-step pattern: GET returns a confirmation HTML page with a `<form method="POST">`, POST executes and marks the token used. Deep links must use query parameters on the page URL (`?view=contact&id=123`), not hash fragments, and the PWA must bridge them to hash routing on load.

The "Yes auto-queues" requirement (EMAIL-06) is already partially implemented — the Edge Function already sets `status: "approved"` when action is `"approve"`. The remaining gap is the deep link (EMAIL-04 / EMAIL-05 combined): the confirmation page for "Yes" should link back to the PWA contact page so the user can immediately draft, which requires the deep-link pattern from EMAIL-04.

**Primary recommendation:** Rewrite `_build_digest_html()` with table-based layout, add GET/POST branching to the `action` Edge Function, and add a query-parameter bridge to the PWA's init code. These are three focused, independent changes.

---

## Standard Stack

### Core (all already in use — no new dependencies)

| Component | Version | Purpose | Notes |
|-----------|---------|---------|-------|
| Python `email_digest.py` | existing | HTML email body builder | Rewrite card HTML only |
| Supabase Edge Function `action/index.ts` | Deno/TypeScript | Token-based action handler | Add GET vs POST branching |
| PWA `pwa/js/app.js` | vanilla JS | Hash router + query bridge | Add startup query param check |
| `src/api/tokens.py` | existing | Token creation | No changes needed |
| `pytest` + `pytest-mock` | >=7.4 | Test framework | Already installed |

### No New Libraries Required

All six requirements are solvable with changes to existing files. No npm packages, no Python packages, no new Edge Functions.

---

## Architecture Patterns

### Pattern 1: Table-Based Email Card Layout (EMAIL-02, EMAIL-03)

**What:** Replace `display:flex` card header with a `<table role="presentation">`. The two cells are: left cell = name + role, right cell = score badge.

**Why tables, not flexbox:** Gmail Web strips `justify-content`, `align-items`, `flex-direction`, and `flex-wrap` while keeping `display:flex`, resulting in a broken layout with default flex values. Gmail Mobile (iOS/Android) strips the entire `<style>` block, so only inline styles on elements survive. Tables with `width` and `valign` attributes on `<td>` are the only layout mechanism that works identically across Gmail Web, Gmail iOS, and Gmail Android.

**Key constraints from official Gmail CSS docs (developers.google.com/workspace/gmail/design/css):**
- `<style>` blocks in `<head>` survive on Gmail Web but are stripped on Gmail mobile apps
- Inline `style=""` attributes survive everywhere
- `display:flex` is absent from the official supported property list
- `table-layout`, `width`, `padding`, `vertical-align`, `border` are all explicitly supported
- `max-width` on the outer wrapper (`600px`) is supported inline

**Card layout pattern:**
```html
<!-- CORRECT: table-based two-column card header -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td style="vertical-align:top; padding-right:12px;">
      <!-- name + role -->
      <a href="{linkedin_url}" style="color:#0a66c2;text-decoration:none;font-weight:bold;font-size:17px;">{name}</a>
      <div style="color:#555;font-size:14px;margin:2px 0;">{role_line}</div>
    </td>
    <td style="vertical-align:top; text-align:right; white-space:nowrap; width:80px;">
      <!-- score badge -->
      <span style="background:#e8f4fd;color:#0a66c2;font-weight:bold;font-size:14px;padding:4px 10px;border-radius:12px;display:inline-block;">Score: {score:.0f}</span>
    </td>
  </tr>
</table>
```

**Tap target pattern (EMAIL-03):** Buttons must be `<a>` tags styled as blocks with `padding` creating the touch area — NOT `height:44px` (CSS height is unreliable in email). Use `padding:12px 20px` which naturally produces ~44px height at 16px font size. Set `font-size:16px` minimum. Place each button in its own `<td>` for spacing control.

```html
<!-- CORRECT: 44px+ tap targets via padding, not CSS height -->
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:10px;">
  <tr>
    <td style="padding-right:6px;">
      <a href="{approve_url}" style="display:inline-block;background:#1a7f37;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:4px;font-size:16px;font-weight:bold;">Yes</a>
    </td>
    <td style="padding-right:6px;">
      <a href="{skip_url}" style="display:inline-block;background:#6c757d;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:4px;font-size:16px;">Skip</a>
    </td>
    <td>
      <a href="{snooze_url}" style="display:inline-block;background:#f0ad4e;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:4px;font-size:16px;">Snooze</a>
    </td>
  </tr>
</table>
```

---

### Pattern 2: GET/POST Split for Email Action Links (EMAIL-07)

**What:** The `action` Edge Function currently executes the action on any HTTP method. Gmail's security scanner (and corporate email security gateways like Mimecast, Proofpoint) issue GET requests to every link in an email before delivery. This consumes the one-time token, making the link dead before the user sees it.

**The fix:** Branch on `req.method`:
- `GET` → return an HTML confirmation page with a `<form method="POST" action="same-url">` and a visible button. No token is consumed. The page shows the contact name and action.
- `POST` → validate token, execute action, mark token used, return confirmation.

**Why this works:** Security scanners only issue GET requests (they cannot submit forms). Humans tapping the link get the GET confirmation page, then tap the button which issues a POST.

**Deno pattern (from official Supabase docs supabase.com/docs/guides/functions/http-methods):**
```typescript
Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  const url = new URL(req.url);
  const token = url.searchParams.get('token');

  // Validate token (read-only — no side effects on GET)
  const { data: tokenRow } = await supabase
    .from('action_tokens')
    .select('*')
    .eq('token', token)
    .single();

  if (req.method === 'GET') {
    // Show confirmation page — do NOT execute action or mark token used
    return confirmationPageResponse(tokenRow, token);
  }

  if (req.method === 'POST') {
    // Execute action, mark token used
    return executeAction(supabase, tokenRow);
  }

  return new Response('Method not allowed', { status: 405 });
});
```

**Confirmation page pattern (GET response):**
```html
<form method="POST" action="/functions/v1/action?token={TOKEN}">
  <p>Confirm: mark {contactName} for outreach?</p>
  <button type="submit" style="...">Confirm: Yes, reach out</button>
</form>
<a href="/functions/v1/action?token={SKIP_TOKEN}">Skip instead</a>
```

The token is passed as a query parameter on the form's `action` URL. The browser POSTs to the same URL. The Edge Function reads the token from `url.searchParams` for both GET and POST.

**Action message update (EMAIL-06):** When `action === "approve"`, the current result message says "Open the queue to draft your message." The confirmation page for the GET should link directly to the PWA contact page using the deep-link pattern (EMAIL-04). The POST success page should do the same.

---

### Pattern 3: Query Parameter Deep Link Bridge (EMAIL-04)

**What:** Email links cannot use hash fragments because HTTP redirects strip fragments per RFC 3986. Gmail also passes links through its own redirect proxy (`https://mail.google.com/...`), which further loses the fragment. Query parameters survive both.

**The gap in current code:** `email_digest.py` builds `pwa_link = settings.pwa_url.rstrip('/') + '/#/queue'` — this works for the "View Full Queue" link because the queue page is the default route. But "View full profile" links need to target a specific contact: `https://eg-connect.netlify.app/?view=contact&id={connection_id}`.

**PWA bridge:** The PWA's `app.js` already has `getQueryParams()` that reads from the hash string, but it doesn't check the page-level query string (`window.location.search`) on startup. A startup bridge is needed:

```javascript
// In app.js DOMContentLoaded handler, BEFORE render()
function checkDeepLinkQueryParams() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get('view');
  const id = params.get('id');
  if (view === 'contact' && id) {
    // Replace the URL (clean up query params) and navigate to hash route
    history.replaceState(null, '', window.location.pathname);
    window.location.hash = `/contact/${id}`;
  }
}
```

This runs before `render()`, sets the hash, and then render() picks it up normally. The `history.replaceState` cleans the URL bar.

**Deep link URL format:**
```
https://eg-connect.netlify.app/?view=contact&id={connection_id}
```

This survives Gmail's redirect chain because it uses query parameters only.

---

### Pattern 4: LinkedIn Direct Link (EMAIL-05)

**What:** Add a direct "Open LinkedIn" link per contact card. The `conn.linkedin_url` field already exists and is already used for the contact name link in some cards.

**Implementation:** The current card makes the contact name a LinkedIn link, but this is subtle and easy to miss. Add an explicit `<a>` button in the button row.

```html
<!-- In the button row table, add a LinkedIn cell -->
<td>
  <a href="{linkedin_url}" style="display:inline-block;background:#0a66c2;color:#ffffff;text-decoration:none;padding:12px 16px;border-radius:4px;font-size:16px;">LinkedIn</a>
</td>
```

Only render this if `conn.linkedin_url` is set.

---

### Recommended Change Scope per File

| File | Change | Requirement |
|------|--------|-------------|
| `src/integrations/email_digest.py` | Replace `_build_digest_html()` card HTML with table layout; add LinkedIn button; add "View full profile" query-param link | EMAIL-02, EMAIL-03, EMAIL-05, EMAIL-04 |
| `supabase/functions/action/index.ts` | Add GET/POST branching; GET returns confirmation form, POST executes; update result message to include PWA contact deep link | EMAIL-07, EMAIL-06, EMAIL-04 |
| `pwa/js/app.js` | Add `checkDeepLinkQueryParams()` bridge in `DOMContentLoaded` | EMAIL-04 |
| `supabase/functions/action/index.ts` (deploy) | `supabase functions deploy action --no-verify-jwt` | All Edge Function changes |

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Email layout testing | Custom rendering harness | Generate HTML, inspect with a real email client OR use Litmus/Email on Acid | Only real client rendering is authoritative |
| Scanner detection | User-agent sniffing, IP blocklists | GET/POST split pattern | Scanner behavior is indistinguishable from human GET; the form submission is the only reliable gate |
| Token replay protection | Custom HMAC / signature schemes | Keep existing UUID + `used` boolean; the GET/POST split prevents scanner consumption | Already-used tokens return 409; scanner cannot POST |
| Multi-step confirmation wizard | Complex JS confirmation flow | Simple HTML `<form method="POST">` in Edge Function response | Works without JavaScript, works in any browser |

---

## Common Pitfalls

### Pitfall 1: Flexbox Properties Silently Dropped
**What goes wrong:** `display:flex;justify-content:space-between` renders correctly in browser previews but produces stacked layout in Gmail iOS/Android.
**Why it happens:** Gmail mobile strips the `<style>` block entirely. Without the style block, there is no `display:flex` declaration, so the element becomes block. Even with inline `display:flex`, sub-properties like `justify-content` are not in Gmail's supported property list and are stripped.
**How to avoid:** Use `<table role="presentation">` with `width` and `valign` attributes. Test by disabling all `<style>` blocks and verifying layout still works.
**Warning signs:** Card looks correct in browser but shows stacked layout in real Gmail mobile test.

### Pitfall 2: GET Request Consuming Action Token
**What goes wrong:** The morning digest arrives; Gmail scanner fetches all links before delivery; the "Yes" token is marked `used: true`; user taps "Yes" and sees "Already Used."
**Why it happens:** The current Edge Function executes on any HTTP method. Scanners always use GET.
**How to avoid:** The GET handler must NEVER call `update({used: true})`. Only the POST handler should mark the token used.
**Warning signs:** Action links report "already used" on first tap, or tokens are consumed before the email arrives in inbox.

### Pitfall 3: Hash Fragment Lost in Gmail Redirect
**What goes wrong:** `https://eg-connect.netlify.app/#/contact/abc` — Gmail's redirect proxy drops the `#/contact/abc` fragment. User lands on `/` which shows the queue homepage.
**Why it happens:** RFC 3986: fragments are client-side only and are never sent to servers. When Gmail's redirect proxy fetches the URL to check it, the fragment is dropped, and the redirect target loses it.
**How to avoid:** Use `?view=contact&id=abc` query parameters. The PWA startup bridge reads `window.location.search` and converts to a hash route.
**Warning signs:** "View profile" links work in browser direct navigation but land on homepage when clicked from Gmail.

### Pitfall 4: 102KB Gmail Clipping
**What goes wrong:** Long digests with many contacts are clipped by Gmail at ~102KB, hiding action buttons for contacts near the bottom.
**Why it happens:** Gmail clips HTML bodies exceeding ~102KB with a "[Message clipped] View entire message" link.
**How to avoid:** The current `digest_top_n = 5` default keeps HTML well under limit. Monitor HTML byte size. The remaining contacts shown as a compact list (no action buttons) is the correct pattern.
**Warning signs:** Users report action buttons missing for contacts below the fold.

### Pitfall 5: Edge Function Redeployment Required
**What goes wrong:** Changes to `supabase/functions/action/index.ts` are made locally but not deployed; the live function still has the old GET behavior.
**How to avoid:** Always deploy after changes: `supabase functions deploy action --no-verify-jwt`.
**Warning signs:** Testing with local files shows the fix but production still has the bug.

### Pitfall 6: POST Body vs Query Parameter for Token
**What goes wrong:** Moving the token from query parameter to POST body breaks the form submission pattern because the `<form method="POST">` form's `action` URL must include the token.
**How to avoid:** Keep `token` in the query string for both GET and POST. The form `action="/functions/v1/action?token={TOKEN}"` puts the token on the URL. The Edge Function reads `url.searchParams.get('token')` for both methods.

---

## Code Examples

### Complete Revised Card HTML (email_digest.py)

```python
# Source: Gmail CSS docs + verified table layout pattern
cards_html += f'''
<div style="background:#ffffff;border:1px solid #e0e0e0;border-radius:8px;padding:16px 18px;margin-bottom:12px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td style="vertical-align:top;padding-right:10px;">
        {name_html}
        <div style="color:#555;font-size:14px;margin:2px 0;">{role_line}</div>
      </td>
      <td style="vertical-align:top;text-align:right;white-space:nowrap;width:80px;">
        <span style="background:#e8f4fd;color:#0a66c2;font-weight:bold;font-size:14px;padding:4px 10px;border-radius:12px;display:inline-block;">Score: {score:.0f}</span>
      </td>
    </tr>
  </table>
  {why_html}
  {buttons_html}
</div>
'''
```

### Complete Revised Button Row (email_digest.py)

```python
# Buttons: 44px+ tap targets via padding, 16px+ font, table layout
profile_url = f"{pwa_base}/?view=contact&id={conn.id}"
linkedin_cell = f'<td style="padding-right:6px;"><a href="{escape(linkedin_url)}" style="display:inline-block;background:#0a66c2;color:#ffffff;text-decoration:none;padding:12px 14px;border-radius:4px;font-size:16px;">LinkedIn</a></td>' if linkedin_url else ''

buttons_html = f'''<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:10px;">
  <tr>
    <td style="padding-right:6px;">
      <a href="{escape(urls['approve'])}" style="display:inline-block;background:#1a7f37;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:4px;font-size:16px;font-weight:bold;">Yes</a>
    </td>
    <td style="padding-right:6px;">
      <a href="{escape(urls['skip'])}" style="display:inline-block;background:#6c757d;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:4px;font-size:16px;">Skip</a>
    </td>
    <td style="padding-right:6px;">
      <a href="{escape(urls['snooze'])}" style="display:inline-block;background:#f0ad4e;color:#000000;text-decoration:none;padding:12px 14px;border-radius:4px;font-size:16px;">Snooze</a>
    </td>
    {linkedin_cell}
    <td>
      <a href="{escape(profile_url)}" style="display:inline-block;background:#ffffff;border:1px solid #0a66c2;color:#0a66c2;text-decoration:none;padding:12px 14px;border-radius:4px;font-size:16px;">Profile</a>
    </td>
  </tr>
</table>'''
```

### Edge Function GET/POST Branch (action/index.ts)

```typescript
// Source: Supabase Edge Function routing docs
Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  const url = new URL(req.url);
  const token = url.searchParams.get('token');

  if (!token) {
    return htmlResponse('Missing token', 'No action token was provided.', 400);
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );

  const { data: tokenRow, error } = await supabase
    .from('action_tokens')
    .select('*')
    .eq('token', token)
    .single();

  if (error || !tokenRow) {
    return htmlResponse('Invalid Token', 'This action link is invalid or has already been used.', 404);
  }
  if (tokenRow.used) {
    return htmlResponse('Already Used', 'This action was already completed.', 409);
  }
  if (new Date(tokenRow.expires_at) < new Date()) {
    return htmlResponse('Expired', 'This action link has expired.', 410);
  }

  // GET: show confirmation page, do NOT execute
  if (req.method === 'GET') {
    return confirmationPageResponse(tokenRow, token);
  }

  // POST: execute action
  if (req.method === 'POST') {
    return executeAction(supabase, tokenRow, token);
  }

  return new Response('Method not allowed', { status: 405 });
});

function confirmationPageResponse(tokenRow: any, token: string): Response {
  const pwaUrl = Deno.env.get('PWA_URL') || '';
  const action = tokenRow.action;
  const labels: Record<string, string> = {
    approve: 'Yes — Queue for Outreach',
    skip: 'Skip this contact',
    snooze: 'Snooze for 3 days',
  };
  const label = labels[action] || 'Confirm';

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reconnect — Confirm Action</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background:#f5f5f5; display:flex; justify-content:center; align-items:center; min-height:100vh; padding:20px; margin:0; }
    .card { background:white; border-radius:12px; padding:32px; max-width:420px; width:100%; text-align:center; box-shadow:0 2px 8px rgba(0,0,0,0.1); }
    .btn { display:inline-block; background:#1a7f37; color:white; text-decoration:none; padding:14px 28px; border-radius:8px; font-size:16px; font-weight:600; border:none; cursor:pointer; width:100%; box-sizing:border-box; margin-bottom:12px; }
    .btn-cancel { background:#6c757d; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Confirm Action</h1>
    <p>Tap below to confirm your choice.</p>
    <form method="POST" action="/functions/v1/action?token=${token}">
      <button type="submit" class="btn">${label}</button>
    </form>
    <a href="${pwaUrl}#/queue" style="color:#666;font-size:14px;">Cancel — back to queue</a>
  </div>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: { ...corsHeaders, 'Content-Type': 'text/html; charset=utf-8' },
  });
}
```

### PWA Deep Link Bridge (pwa/js/app.js)

```javascript
// Source: REQUIREMENTS.md EMAIL-04, VIEW-04 pattern
// Run at startup to bridge query-param deep links to hash routes
function checkDeepLinkQueryParams() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get('view');
  const id = params.get('id');
  if (view === 'contact' && id) {
    // Clean the URL bar, then set the hash route
    history.replaceState(null, '', window.location.pathname);
    window.location.hash = `/contact/${id}`;
    // render() will be called by hashchange event OR by DOMContentLoaded below
    return true;
  }
  return false;
}

// In DOMContentLoaded:
document.addEventListener('DOMContentLoaded', () => {
  initSupabase();
  setupOfflineDetection();
  if (!checkDeepLinkQueryParams()) {
    render(); // only call render() if we didn't trigger a hashchange
  }
});
```

---

## State of the Art

| Old Approach | Current Approach | Confidence |
|--------------|------------------|------------|
| Flexbox card layout | Table layout with `role="presentation"` and inline styles | HIGH — Gmail CSS docs confirm |
| GET-only action links | GET shows confirmation form, POST executes | HIGH — standard pattern per email security literature |
| Hash-fragment deep links | Query parameter deep links with PWA startup bridge | HIGH — RFC 3986 is definitive |
| Name linked to LinkedIn (subtle) | Dedicated "LinkedIn" button in action row | HIGH — adds EMAIL-05 explicitly |

**Deprecated/outdated in this codebase:**
- `display:flex;justify-content:space-between` in card header div — replace with table
- `display:inline-block` buttons nested in a `<div style="margin-top:10px;">` — replace with table cell buttons
- Edge Function executing action on GET — add method check

---

## Open Questions

1. **Confirmation page UX for Skip and Snooze**
   - What we know: The GET/POST split requires a confirmation tap for ALL actions including skip and snooze.
   - What's unclear: Is a confirmation step for "Skip" annoying? Currently Skip is a one-tap action.
   - Recommendation: Use the confirmation page for approve (state-changing), but for skip/snooze consider whether a simpler confirmation message is sufficient. Alternative: show different confirmation page text for skip ("Are you sure you want to skip?") vs approve. This is a UX call, not a technical one.

2. **PWA `history.replaceState` interaction with service worker**
   - What we know: The bridge calls `history.replaceState` to clean the query params before setting the hash.
   - What's unclear: Whether the service worker intercepts and caches the query-param URL.
   - Recommendation: The service worker uses `fetch` event based on pathname, not query params. Should be safe. Verify with a single manual test after implementation.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ with pytest-mock |
| Config file | `pyproject.toml` (`[tool.pytest...]` not yet defined — run from project root) |
| Quick run command | `pytest tests/test_phase2_email.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EMAIL-02 | `_build_digest_html()` output contains `<table` not `display:flex` in card header | unit | `pytest tests/test_phase2_email.py::test_card_layout_uses_table -x` | ❌ Wave 0 |
| EMAIL-03 | Button `<a>` elements have `padding` with at least 12px and `font-size:16px` | unit | `pytest tests/test_phase2_email.py::test_button_tap_targets -x` | ❌ Wave 0 |
| EMAIL-04 | "View full profile" URL uses `?view=contact&id=` (not `#/contact/`) | unit | `pytest tests/test_phase2_email.py::test_profile_link_uses_query_params -x` | ❌ Wave 0 |
| EMAIL-05 | LinkedIn button present in card when `linkedin_url` is set | unit | `pytest tests/test_phase2_email.py::test_linkedin_button_in_card -x` | ❌ Wave 0 |
| EMAIL-06 | Edge Function approve action sets `status: "approved"` (existing behavior verified) | manual | Deploy and tap "Yes" | n/a |
| EMAIL-07 | Edge Function GET handler does NOT call `update({used:true})`; returns HTML with `<form method="POST">` | unit (Deno) | Manual review of TypeScript + deployment test | n/a for Python tests |

**Note on EMAIL-07 tests:** The Edge Function is Deno/TypeScript and not covered by pytest. Verification is: (1) code review that GET handler has no `update` call, (2) manual test by visiting the action URL directly in a browser (should see confirmation form, not "Done!").

**Note on EMAIL-06:** EMAIL-06 is already implemented in the Edge Function (`status: "approved"` on approve action). The remaining work is EMAIL-04 ensuring the confirmation page links back to the contact in the PWA.

### Sampling Rate

- **Per task commit:** `pytest tests/test_phase2_email.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_phase2_email.py` — covers EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05
  - Needs: `_build_digest_html()` callable with mock contacts (no DB)
  - Pattern: similar to existing `test_phase1_infra.py` with monkeypatching

None — existing test infrastructure (pytest, pytest-mock, conftest fixtures) covers all Python test needs.

---

## Sources

### Primary (HIGH confidence)

- [Gmail CSS Support — Google Developers](https://developers.google.com/workspace/gmail/design/css) — official property support list; confirms `display:flex` absent, `table-layout` supported, media queries supported
- [Supabase Edge Functions HTTP Methods](https://supabase.com/docs/guides/functions/http-methods) — `req.method` check pattern, `Deno.serve` routing
- RFC 3986 (URI standard) — fragments are client-side only, stripped by HTTP redirects (confirmed by multiple sources)

### Secondary (MEDIUM confidence)

- [emailmavlers.com — Gmail CSS Support and Workarounds](https://www.emailmavlers.com/blog/gmail-css-support-and-workarounds/) — confirmed Flexbox stripped on Gmail mobile; inline styles required
- [DEV Community — Email Client Rendering Differences 2026](https://dev.to/mailpeek/the-complete-guide-to-email-client-rendering-differences-in-2026-243f) — confirmed Gmail strips Flexbox sub-properties, keeps `display:flex` only
- [mailtrap.io — Responsive Email Design](https://mailtrap.io/blog/responsive-email-design/) — table layout pattern for cross-client compatibility
- [suped.com — Email Unsubscribe Best Practices](https://www.suped.com/knowledge/email-deliverability/compliance/email-unsubscribe-link-best-practices-avoiding-bot-clicks-and-ensuring-compliance) — two-step confirmation page as scanner defense

### Tertiary (LOW confidence — pattern well-established but no single canonical source)

- Gmail scanner behavior: multiple sources confirm GET-only prefetch behavior; no official Google documentation explicitly lists scanner behavior. Pattern is extremely well established in email marketing community.

---

## Metadata

**Confidence breakdown:**
- Gmail table layout requirement: HIGH — confirmed by official Gmail CSS docs
- GET/POST scanner defense pattern: HIGH — confirmed by multiple email marketing/security sources
- Query parameter deep link: HIGH — RFC 3986 is definitive; confirmed by Optimizely and other sources
- PWA bridge implementation: MEDIUM — based on reading existing code; no external source needed

**Research date:** 2026-03-08
**Valid until:** 2026-09-08 (Gmail CSS support changes slowly; 6 months is conservative)
