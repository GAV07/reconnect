# Phase 4: Foundation Fixes + Queue UX - Research

**Researched:** 2026-03-09
**Domain:** Vanilla JS PWA (PostgREST filtering), Python scoring fix, Gmail OAuth (google-auth-oauthlib)
**Confidence:** HIGH — all findings from direct codebase inspection and project-level research

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | User can send daily email digest via Gmail OAuth using GCP JSON credentials | `GmailCredentials` table exists in SQLite and Supabase; `gmail.py` currently uses App Password path only — OAuth send path must be added; `push.py` currently syncs `gmail_credentials` to Supabase (security fix needed simultaneously) |
| INFRA-02 | User can see accurate score breakdowns on contact profiles (all 5 dimensions show real values, not 0) | `contact.js` reads `score_reasoning` JSON correctly; scoring.py writes `dimension_scores` to `score_reasoning`; bug is in existing data — contacts scored before rubric change have no `dimension_scores` key; fix is a re-score operation, not a code change |
| QUEUE-01 | User can sort queue contacts by composite score (ascending/descending) | `queue.js` already queries `.order('priority_score', { ascending: false })`; adding ascending toggle requires state var + UI control + re-query; PostgREST `.order()` handles server-side |
| QUEUE-02 | User can filter queue by status (pending, approved, sent) | `queue.js` hardcodes `.eq('status', 'pending_review')`; removing the hardcoded filter + adding a status selector enables this; PostgREST `.eq()` or `.in_()` handles server-side |
| QUEUE-03 | User can filter queue by industry | Industry is inside `connections.raw_enrichment` JSON, not a top-level column; client-side JS filter after fetch is the correct v1.1 approach (no migration needed); PostgREST `ilike` on embedded JSON is not reliable — confirmed gap in project SUMMARY.md |
</phase_requirements>

---

## Summary

Phase 4 has three distinct workstreams: (1) fix the score breakdown display bug, (2) add sort/filter controls to the queue, and (3) add Gmail OAuth send path. All three are surgical changes to existing files — no new tables, no new edge functions, and no new Python packages beyond the three Google auth packages.

The score breakdown bug (INFRA-02) is caused by contacts that were scored before the current 5-dimension rubric was in place. Their `score_reasoning` column either lacks a `dimension_scores` key entirely or has an empty dict `{}`. The PWA code in `contact.js` already handles this gracefully by defaulting to 0, which is why bars show 0 rather than crashing. The fix is to re-score those contacts via `score_connections_batch()`. No code change to `contact.js` is needed — only data.

Queue sorting and filtering (QUEUE-01, QUEUE-02, QUEUE-03) require modifying `queue.js` to hold filter state and rebuild the PostgREST query dynamically. Status and score sorting are server-side via PostgREST params. Industry filtering must be client-side because industry lives in `raw_enrichment` JSON, not a top-level column.

Gmail OAuth (INFRA-01) requires adding the `google-auth-oauthlib` + `google-auth` + `google-api-python-client` packages, an `InstalledAppFlow` authorization flow, and a new send path in `gmail.py` that reads from the `GmailCredentials` SQLite table. Critically, `push.py` currently syncs `GmailCredentials` to Supabase — this must be removed in the same task as the OAuth addition to prevent OAuth tokens from being exposed in the cloud database.

**Primary recommendation:** Implement in order — (1) re-score existing contacts to fix INFRA-02 first (validates scoring pipeline is healthy), (2) add queue filter/sort UI (QUEUE-01, QUEUE-02, QUEUE-03), (3) add Gmail OAuth send path (INFRA-01).

---

## Standard Stack

### Core (no changes to existing stack)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| supabase-js | CDN (already in PWA) | PostgREST queries with `.order()`, `.eq()`, `.in_()` | Already in use; all filter operations map directly to PostgREST params |
| SQLModel | >=0.0.14 (installed) | `GmailCredentials` table access | Already in use |
| openai | >=1.10.0 (installed) | Re-scoring contacts via `score_connection()` | Already in use |

### New Packages (INFRA-01 only)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-api-python-client | 2.192.0 | Gmail API send (MIMEText → base64 → `users.messages.send`) | Official Google library; works with OAuth tokens from `google-auth` |
| google-auth-oauthlib | 1.3.0 | `InstalledAppFlow` to run browser-based OAuth consent and save token | Official Google library; `run_local_server(port=0)` is current (OOB flow deprecated 2022) |
| google-auth | 2.49.0 | Token refresh (`google.oauth2.credentials.Credentials`, auto-refresh via `Request()`) | Dependency of both above; handles `invalid_grant` refresh cycle |

**Installation (INFRA-01 only):**
```bash
pip install google-api-python-client==2.192.0 google-auth-oauthlib==1.3.0 google-auth==2.49.0
```
These must be added to `requirements.txt` and `pyproject.toml` together.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| server-side PostgREST filter for industry | client-side JS filter | Server-side requires a migration to add `industry` top-level column; client-side JS filter on fetched items is correct for v1.1 at <=50 queue items |
| InstalledAppFlow (browser OAuth) | Service Account with domain delegation | Service accounts require Google Workspace; not available for personal Gmail; InstalledAppFlow is the correct pattern for single-user tools |
| Gmail API via `google-api-python-client` | smtplib + OAuth2 token as password | Gmail API is the modern approach; smtplib XOAuth2 SASL is fragile and poorly documented |

---

## Architecture Patterns

### Recommended Project Structure (changes only)
```
src/
├── integrations/
│   └── gmail.py          # ADD: oauth_send_html_email(), is_oauth_configured(), authorize_gmail_oauth()
├── llm/
│   └── scoring.py        # NO CHANGE — score_connections_batch() already works
pwa/
└── js/
    └── queue.js          # MODIFY: add filter state + dynamic query builder + filter UI HTML
```

No new files needed. `gmail.py` gains OAuth functions alongside existing App Password functions. The rescore operation calls `score_connections_batch()` directly — no new function needed.

### Pattern 1: PostgREST Dynamic Filter Construction (QUEUE-01, QUEUE-02)

**What:** Build the Supabase JS query dynamically from a filter state object rather than hardcoding `.eq('status', 'pending_review')`.

**When to use:** Any time the user controls filter/sort params without a full page reload.

**Example:**
```javascript
// Source: Supabase JS client docs — https://supabase.com/docs/reference/javascript/select

// Module-level filter state
const queueFilters = {
  sortAscending: false,        // QUEUE-01: toggle sort direction
  statusFilter: null,          // QUEUE-02: null = all, 'pending_review', 'approved', 'sent'
  industryFilter: null,        // QUEUE-03: null = all, or string for client-side filter
};

async function renderQueue(container) {
  // Build base query
  let query = db
    .from('outreach_queue')
    .select('*, connections(*)')
    .order('priority_score', { ascending: queueFilters.sortAscending });

  // Status filter — server-side via PostgREST
  if (queueFilters.statusFilter) {
    query = query.eq('status', queueFilters.statusFilter);
  }
  // No status filter = show all statuses (pending + approved + sent)

  const { data: items, error } = await query;

  // Industry filter — client-side (raw_enrichment JSON, no top-level column)
  let filtered = items || [];
  if (queueFilters.industryFilter) {
    filtered = filtered.filter(item => {
      const enrichment = item.connections?.raw_enrichment?.data
        || item.connections?.raw_enrichment
        || {};
      const industry = (enrichment.company_industry || enrichment.companyIndustry || '').toLowerCase();
      return industry.includes(queueFilters.industryFilter.toLowerCase());
    });
  }

  // render filtered items...
}
```

### Pattern 2: Gmail OAuth InstalledAppFlow (INFRA-01)

**What:** Run browser-based OAuth consent once, save tokens to `GmailCredentials` table, auto-refresh on every send.

**When to use:** One-time setup via CLI or manual script run; daily pipeline uses saved tokens.

**Example:**
```python
# Source: https://developers.google.com/workspace/gmail/api/quickstart/python

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def authorize_gmail_oauth(client_secrets_path: str) -> None:
    """Run one-time OAuth consent flow. Saves tokens to GmailCredentials table."""
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, GMAIL_SCOPES)
    # run_local_server(port=0) opens browser, starts ephemeral localhost server for redirect
    # OOB flow (urn:ietf:wg:oauth:2.0:oob) is deprecated — do not use
    google_creds = flow.run_local_server(port=0)
    _save_credentials(google_creds)

def _load_credentials() -> Credentials | None:
    """Load OAuth tokens from GmailCredentials table and refresh if expired."""
    from src.database.engine import get_session
    from src.database.models import GmailCredentials

    with get_session() as session:
        stored = session.get(GmailCredentials, 1)
        if not stored or not stored.refresh_token:
            return None

        creds = Credentials(
            token=stored.access_token,
            refresh_token=stored.refresh_token,
            token_uri=stored.token_uri,
            client_id=stored.client_id,
            client_secret=stored.client_secret,
            scopes=stored.scopes,
        )
        if stored.expiry:
            creds.expiry = stored.expiry

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_credentials(creds)  # Persist refreshed token
        except Exception:
            return None  # Caller should skip digest gracefully

    return creds

def is_oauth_configured() -> bool:
    """Return True if OAuth tokens exist and are usable."""
    return _load_credentials() is not None

def oauth_send_html_email(to: str, subject: str, html_body: str) -> dict:
    """Send HTML email via Gmail API using OAuth credentials."""
    creds = _load_credentials()
    if not creds:
        raise ValueError("Gmail OAuth not configured. Run authorize_gmail_oauth() first.")

    service = build('gmail', 'v1', credentials=creds)

    msg = MIMEMultipart('alternative')
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()
    return {'sent': True}
```

### Pattern 3: Re-Score Contacts with Missing dimension_scores (INFRA-02)

**What:** Query for contacts where `score_reasoning` exists but lacks `dimension_scores`, then re-score.

**When to use:** One-time data repair. Can be triggered manually or as a pipeline pre-check.

**Example:**
```python
# Source: direct inspection of src/llm/scoring.py + src/database/models.py

from sqlmodel import select
from src.database.engine import get_session
from src.database.models import Connection
from src.llm.scoring import score_connections_batch
import json

def find_contacts_missing_dimension_scores() -> list[str]:
    """Return connection IDs that have a score but no dimension_scores breakdown."""
    with get_session() as session:
        # Contacts that have been scored (have reconnect_score + score_reasoning)
        # but lack dimension_scores (old format or empty dict)
        conns = session.exec(
            select(Connection)
            .where(Connection.reconnect_score.isnot(None))
            .where(Connection.score_reasoning.isnot(None))
            .where(Connection.enriched_at.isnot(None))  # Must have enrichment for rescore
        ).all()

        missing = []
        for conn in conns:
            try:
                reasoning = json.loads(conn.score_reasoning)
                dims = reasoning.get('dimension_scores', {})
                if not dims:  # Empty dict or missing key
                    missing.append(conn.id)
            except (json.JSONDecodeError, AttributeError):
                pass  # Malformed reasoning — skip

        return missing
```

### Anti-Patterns to Avoid

- **Hardcoding `.eq('status', 'pending_review')` in the new queue query:** The whole point of QUEUE-02 is to make this dynamic. Remove the hardcoded status filter; let the user's selection (defaulting to 'pending_review') drive the query.
- **Re-fetching the full contact list on every filter change:** Use the same PostgREST query with updated params. Do not cache a full-table fetch and filter in memory — the queue can grow to 100+ items.
- **Using OOB OAuth flow (`urn:ietf:wg:oauth:2.0:oob`):** Deprecated by Google in 2022. Use `run_local_server(port=0)` instead.
- **Pushing GmailCredentials to Supabase after adding OAuth:** OAuth tokens in a cloud DB are a security risk. Remove `GmailCredentials` from `push.py` when adding OAuth.
- **Running re-score on all enriched contacts indiscriminately:** Score only contacts that have `enriched_at IS NOT NULL` AND `score_reasoning` exists with an empty/missing `dimension_scores`. Don't re-score contacts with valid dimension scores — wastes OpenAI credits.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token refresh on expiry | Custom HTTP POST to token endpoint | `google.auth.transport.requests.Request()` + `creds.refresh()` | Handles clock skew, retry logic, and token storage correctly |
| Base64 encoding email for Gmail API | Manual urllib or struct encoding | `base64.urlsafe_b64encode(msg.as_bytes()).decode()` | Gmail API requires URL-safe base64 without padding issues |
| PostgREST multi-filter query | String concatenation of query params | Supabase JS client chained `.eq()`, `.order()`, `.in_()` methods | Client handles encoding, null safety, and param ordering |
| Industry extraction from raw_enrichment | Custom JSONPath parser | `enrichment?.data?.company_industry || enrichment?.company_industry` | The dual-path extraction pattern is already established in `contact.js` (line 7) and `scoring.py` (line 199) |

**Key insight:** All the heavy lifting for this phase exists in the codebase already. This phase is wiring and data repair, not new capability.

---

## Common Pitfalls

### Pitfall 1: Re-scoring Contacts Without Enrichment Data

**What goes wrong:** `score_connection()` requires `enriched_at IS NOT NULL` to build a meaningful prompt. Calling it on un-enriched contacts returns `None` (the function checks for `user_profile.goals` but not enrichment), wastes API credits, and writes a low-information score.

**Why it happens:** The `find_contacts_missing_dimension_scores()` filter includes contacts with `score_reasoning` — but some of these may have been scored via `prescoring.py` (pre-enrichment scoring), which doesn't produce `dimension_scores` either.

**How to avoid:** Scope the re-score query to contacts with BOTH `reconnect_score IS NOT NULL` AND `enriched_at IS NOT NULL` AND empty `dimension_scores`. The `scoring.py` full-score path requires enrichment to produce meaningful dimension scores.

**Warning signs:** Re-score returns `result = None` for most contacts; `score_results["failed"]` count is high.

### Pitfall 2: Queue Filter UI Breaking Realtime Subscription

**What goes wrong:** `queue.js` calls `setupQueueRealtime()` at the end of `renderQueue()`. If `renderQueue()` is called again (due to filter change), a new Supabase Realtime channel subscription is created without tearing down the previous one. After 3+ filter changes, you have 3+ duplicate subscriptions firing `renderQueue()` on every INSERT.

**Why it happens:** `db.channel('queue-changes')` creates a new channel object each call. Supabase JS does not deduplicate channels with the same name automatically.

**How to avoid:** Store the channel reference in a module-level variable. Call `.unsubscribe()` before creating a new subscription. Or: call `setupQueueRealtime()` only once on initial page load, not inside `renderQueue()`.

```javascript
// Module-level — only one subscription at a time
let _queueChannel = null;

function setupQueueRealtime() {
  if (_queueChannel) {
    _queueChannel.unsubscribe();
    _queueChannel = null;
  }
  _queueChannel = db.channel('queue-changes')
    .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'outreach_queue' }, () => {
      const content = document.getElementById('app-content');
      if (content && window.location.hash.includes('/queue')) {
        renderQueue(content);
      }
    })
    .subscribe();
}
```

### Pitfall 3: Gmail OAuth Refresh Token Expiry in GCP Testing Mode

**What goes wrong:** When the GCP OAuth consent screen is left in "Testing" mode, refresh tokens expire after exactly 7 days. The daily pipeline runs fine for a week then silently fails with `google.auth.exceptions.RefreshError: invalid_grant`. The digest generates but never sends.

**Why it happens:** Google's policy for apps in Testing mode limits refresh token lifetime to prevent unreviewed apps from maintaining long-lived access.

**How to avoid:**
1. Publish the GCP consent screen (or add your own email as a test user) before running the OAuth flow for real use.
2. Wrap `creds.refresh(Request())` in a `try/except RefreshError` block; if refresh fails, `is_oauth_configured()` returns `False` and the pipeline skips the digest gracefully rather than crashing.
3. The pipeline already has `if is_gmail_configured():` guard — the OAuth path needs `if is_oauth_configured():` with the same graceful-skip pattern.

**Warning signs:** `send_digest_email()` returns `{"sent": False, "reason": "Gmail OAuth not configured"}` after working for 7 days.

### Pitfall 4: Pushing OAuth Tokens to Supabase

**What goes wrong:** `push.py` section 5 currently pushes `GmailCredentials` row to Supabase. After adding real OAuth tokens (access_token, refresh_token), this exposes live credentials in the cloud database with no encryption.

**Why it happens:** `GmailCredentials` was synced originally for a hypothetical cloud-send scenario. For this single-user local tool, the pipeline sends email from localhost — there is no reason to sync OAuth tokens to Supabase.

**How to avoid:** Remove section 5 of `push.py` (the `GmailCredentials` push block) and remove `gmail_credentials` from the `stats` dict simultaneously with adding OAuth support. This is a security fix bundled with INFRA-01.

**Warning signs:** `push_to_cloud()` stats show `gmail_credentials: 1` after OAuth tokens are present.

### Pitfall 5: Industry Filter Showing Empty Results for "All" Status

**What goes wrong:** QUEUE-02 changes the status filter from hardcoded `pending_review` to user-selectable. If the user selects "All" (no status filter), and the query returns approved + sent items, those items won't have action buttons (Reach Out / Skip / Snooze) because the action buttons use `onclick` handlers that call `queueAction()` which tries to update `status`. Items with status `approved` or `sent` should show in read-only mode or have different actions.

**Why it happens:** The card rendering in `queue.js` unconditionally renders action buttons for every item. Non-pending items would show "Reach Out" but clicking it would try to set `approved` → `approved` (a no-op at best, confusing at worst).

**How to avoid:** When rendering cards, check `item.status` and conditionally render: action buttons for `pending_review`, a status badge only for `approved`/`sent`/`skipped`.

---

## Code Examples

Verified patterns from direct codebase inspection:

### Score Breakdown: How contact.js Reads dimension_scores
```javascript
// Source: pwa/js/contact.js lines 131-161
// This code ALREADY works — the bug is in the data, not the display code
let dimensions = {};
if (conn.score_reasoning) {
  try {
    const reasoning = JSON.parse(conn.score_reasoning);
    dimensions = reasoning.dimension_scores || {};  // Empty {} causes all bars to show 0
  } catch (e) {}
}

// dimConfig maps key → {label, max}
const dimConfig = {
  goal_alignment:     { label: 'Goal Alignment',  max: 25 },
  industry_overlap:   { label: 'Industry Fit',    max: 20 },
  mutual_value:       { label: 'Mutual Value',    max: 20 },
  conversation_hooks: { label: 'Conv. Hooks',     max: 20 },
  network_reach:      { label: 'Network Reach',   max: 15 },
};

for (const [key, config] of Object.entries(dimConfig)) {
  const val = dimensions[key] || 0;  // 0 when key is missing → empty dict bug
  const pct = Math.round((val / config.max) * 100);
  // renders bar at 0% width when val = 0
}
```

### Queue: Current Query (before changes)
```javascript
// Source: pwa/js/queue.js lines 10-14 — hardcoded filter to change for QUEUE-02
const { data: items, error } = await db
  .from('outreach_queue')
  .select('*, connections(*)')
  .eq('status', 'pending_review')          // QUEUE-02: make this dynamic
  .order('priority_score', { ascending: false });  // QUEUE-01: add toggle for this
```

### Industry Dual-Path Extraction Pattern (already in codebase)
```javascript
// Source: pwa/js/contact.js line 7 + src/llm/scoring.py line 199
// JS:
const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
const industry = enrichment.company_industry || enrichment.companyIndustry || '';

// Python:
industry = enrichment.get('company_industry') or enrichment.get('companyIndustry') or 'Unknown'
```

### score_connection writes dimension_scores (what will be present after re-score)
```python
# Source: src/llm/scoring.py lines 350-357
connection.score_reasoning = json.dumps({
    "reasoning": result.reasoning,
    "key_factors": result.key_factors,
    "conversation_hooks": result.conversation_hooks,
    "dimension_scores": result.dimension_scores,  # Non-empty dict with 5 keys
})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `gmail_app_password` + smtplib SMTP_SSL | `InstalledAppFlow` + Gmail API | v1.1 (Phase 4) | Needed for accounts with App Password disabled (Google Workspace) |
| OOB OAuth flow (`urn:ietf:wg:oauth:2.0:oob`) | `run_local_server(port=0)` redirect flow | Google deprecated OOB in Oct 2022 | Never use OOB — it was deprecated 3 years ago |
| Hardcoded `.eq('status', 'pending_review')` | Dynamic filter state + query rebuilding | v1.1 (Phase 4) | Enables all status views without page reload |

**Deprecated/outdated:**
- `InstalledAppFlow.run_console()` / `flow.run_local_server()` with fixed port: Use `port=0` (ephemeral port) to avoid port conflicts — relevant when the daily LaunchAgent might be running.
- `send_email` import in `review.py` (line 13): `review.py` already crashes on import; this is known broken state. Do not attempt to salvage it.

---

## Open Questions

1. **Does the user have valid Gmail App Password credentials configured?**
   - What we know: `config.py` has `gmail_app_password` and `gmail_sender_email` fields; `is_gmail_configured()` checks both
   - What's unclear: Whether `.env` has valid values; daily pipeline currently calls `is_gmail_configured()` before sending — if App Password works, INFRA-01 may be about adding OAuth as an alternative rather than replacing the only working path
   - Recommendation: INFRA-01 requirement says "GCP JSON credentials" specifically — implement OAuth as the primary path, keep App Password as fallback; `is_oauth_configured()` checked first, then `is_gmail_configured()` as fallback

2. **How many contacts need re-scoring for INFRA-02?**
   - What we know: Any contact scored before the 5-dimension rubric was added lacks `dimension_scores`; the rubric is in the current `scoring.py` — it's been there from the start, but early scores may predate it
   - What's unclear: Exact count; cost to re-score via OpenAI API
   - Recommendation: Plan should include a "count missing dimension scores" check as the first task; if count is 0, INFRA-02 is already solved; if count > 0, run `score_connections_batch()` on the list

3. **GCP project and OAuth consent screen status?**
   - What we know: `STATE.md` notes "Gmail OAuth GCP consent screen: must be published (or add test user) before OAuth tokens are used in production — tokens expire after 7 days in Testing mode"
   - What's unclear: Whether a GCP project exists, whether credentials.json has been downloaded
   - Recommendation: Plan task should include instructions for downloading `credentials.json` from GCP Console as a prerequisite step; `authorize_gmail_oauth(credentials_json_path)` takes the path as argument

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4.0+ (already in pyproject.toml dev deps) |
| Config file | pyproject.toml (no [tool.pytest] section yet — runs with defaults) |
| Quick run command | `python -m pytest tests/test_phase4_foundation.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-02 | `score_reasoning` JSON has non-empty `dimension_scores` dict for re-scored contacts | unit | `python -m pytest tests/test_phase4_foundation.py::test_dimension_scores_populated -x` | Wave 0 |
| INFRA-02 | `find_contacts_missing_dimension_scores()` returns IDs for contacts with empty `dimension_scores` | unit | `python -m pytest tests/test_phase4_foundation.py::test_find_missing_dimension_scores -x` | Wave 0 |
| QUEUE-01 | Queue query uses `ascending: True` when sort toggle is flipped | unit | `python -m pytest tests/test_phase4_foundation.py::test_queue_sort_toggle -x` | Wave 0 |
| QUEUE-02 | Queue query includes `.eq('status', ...)` only when a status filter is active | unit | `python -m pytest tests/test_phase4_foundation.py::test_queue_status_filter -x` | Wave 0 |
| QUEUE-03 | Client-side industry filter correctly extracts industry from both `raw_enrichment.data.company_industry` and `raw_enrichment.company_industry` | unit | `python -m pytest tests/test_phase4_foundation.py::test_industry_dual_path -x` | Wave 0 |
| INFRA-01 | `is_oauth_configured()` returns False when no `GmailCredentials` row exists | unit | `python -m pytest tests/test_phase4_foundation.py::test_oauth_not_configured -x` | Wave 0 |
| INFRA-01 | `oauth_send_html_email()` calls Gmail API with base64-encoded MIMEMultipart | unit (mock) | `python -m pytest tests/test_phase4_foundation.py::test_oauth_send_email_mock -x` | Wave 0 |
| INFRA-01 | `push_to_cloud()` does NOT include `gmail_credentials` in sync payload | unit | `python -m pytest tests/test_phase4_foundation.py::test_no_gmail_creds_in_push -x` | Wave 0 |
| INFRA-01 | Gmail OAuth send integration (actual token + API call) | manual | Run `python -c "from src.integrations.gmail import oauth_send_html_email; ..."` | N/A |

**Note:** QUEUE-01/QUEUE-02/QUEUE-03 are Vanilla JS changes. The JS logic (filter state, dual-path extraction) can be unit-tested via Python tests that verify the Python-side data contracts. The actual PWA rendering is a manual smoke test (open browser, verify filter controls appear and update the card list).

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_phase4_foundation.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase4_foundation.py` — covers all 8 automated test cases above
- [ ] No new conftest.py needed — existing fixtures pattern from test_phase1_infra.py applies

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `pwa/js/queue.js`, `pwa/js/contact.js`, `pwa/js/app.js`, `src/llm/scoring.py`, `src/integrations/gmail.py`, `src/database/models.py`, `src/sync/push.py`, `src/pipeline/daily_pipeline.py`, `src/services/dashboard_service.py`, `src/config.py`
- `.planning/research/SUMMARY.md` — project-level architecture decisions, pitfall catalogue
- `.planning/STATE.md` — known blockers, OAuth consent screen warning
- [Gmail API Python Quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) — InstalledAppFlow + `run_local_server()` pattern
- [Supabase JS Client `.order()` docs](https://supabase.com/docs/reference/javascript/order) — `ascending` param
- [Supabase JS Client `.eq()` docs](https://supabase.com/docs/reference/javascript/eq) — status filter

### Secondary (MEDIUM confidence)
- [Google OAuth OOB deprecation](https://developers.googleblog.com/en/oauth-out-of-band-flow-deprecation-part-2/) — confirms `run_local_server()` is current
- [Gmail OAuth refresh token expiry](https://developers.google.com/identity/protocols/oauth2#expiration) — 7-day Testing mode limit
- [Supabase Realtime duplicate channel issue](https://github.com/supabase/supabase-js/issues/1440) — unsubscribe-before-resubscribe pattern

### Tertiary (LOW confidence)
- None for this phase — all critical claims verified by primary sources

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified on PyPI; existing stack confirmed by direct inspection
- Architecture: HIGH — all integration points read directly from source files; no speculative claims
- Pitfalls: HIGH (re-score scope, Realtime duplication, OAuth expiry) — confirmed by reading exact code paths; MEDIUM (GCP setup timeline) — depends on external Google processes

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable domain; Google Auth package versions valid for 30 days)
