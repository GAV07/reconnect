# Phase 8: Email + Signal UI + Profile Content - Research

**Researched:** 2026-03-11
**Domain:** Vanilla JS PWA UI modification, HTML email redesign, Python digest rebuild, PostgREST writes from PWA
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Email digest redesign:**
- Remove all per-contact action buttons (Approve/Skip/Snooze) from email
- Email becomes a notification + preview, not an action surface
- Single "Review in App" CTA button links to PWA queue
- Keep top 5 featured contacts per email
- Each featured card shows: name, role@company, Why Today reasoning, industry
- Drop data health section (missing emails, enrichment status, skip patterns)
- Drop feedback rating stars
- Compact remainder list stays (just names/count to show queue depth)
- Keep table-based HTML for Gmail compatibility (established pattern)
- Keep query parameter deep links for contact names linking to PWA profile pages
- Action tokens for email buttons are no longer generated (no per-contact actions)

**Signal picker interaction:**
- Queue cards show a single "Assign Signal" tap area (collapsed by default)
- Tapping expands an inline picker with 7 color-coded chips with short labels
- Chips fit 3-4 per row on mobile (e.g. green "Warm Lead", blue "Nurture")
- After assigning a signal: signal badge appears on the card, card stays in place (no removal, no dimming)
- User can reassign by tapping again to change signal
- ARCHIVE signal hides contact from queue and dashboard (per spec, sets user_priority "never")
- PostgREST direct write to contact_signals + connection update (no new Edge Function — decided in Phase 7)

**Queue filtering and default view:**
- Default queue view shows only untriaged contacts (no signal assigned yet)
- Filter/tab mechanism lets user view contacts by signal type (e.g. show all Warm Leads)
- Existing status filter (All/Pending/Approved/Sent/Skipped) evolves to signal-based filtering
- SIG-05 requirement: user can filter queue by signal type

### Claude's Discretion
- Exact color palette for 7 signal chips (should be visually distinct, accessible)
- Signal chip layout mechanics (CSS grid vs flexbox for chip rows)
- Queue card expand/collapse animation
- Profile page layout for notes and signal history sections
- Profile key factors fallback strategy when enrichment is sparse
- Conversation starters generation from scoring rationale when activity_log is empty
- Contact notes inline edit UX (on queue card vs profile page)
- How much of note text to show on queue cards (truncation strategy)

### Deferred Ideas (OUT OF SCOPE)
- Signal-based email digest bucketing (group contacts by signal in email) — v1.3+ (SIG-08)
- Signal analytics on dashboard (distribution, trends) — v1.3+ (SIG-09)
- Per-contact cadence override — v1.3+ (CAD-05)
- Separate "signaled contacts" page/view beyond queue filter — future consideration
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EMAIL-01 | User receives daily email digest with contact recommendations via Gmail | `send_digest_email()` already wired in `daily_pipeline.py` step at the end; Gmail OAuth path confirmed in `gmail.py`. Needs digest HTML rebuilt. |
| EMAIL-02 | Email digest includes "Review in App" CTA linking to PWA queue for signal assignment | PWA queue URL pattern is `pwa_url + "/#/queue"`. Existing code already has `pwa_link` for footer CTA; needs the main CTA button upgraded. |
| EMAIL-03 | Email action buttons use signal-aligned vocabulary (not legacy approve/skip/snooze) | All token-based Yes/Skip/Snooze buttons must be removed from `_build_digest_html()`. `create_action_tokens()` call is dropped. Single "Review in App" button replaces per-card action rows. |
| EMAIL-04 | Telegram notifications retained as backup for pipeline failure alerts | `send_pipeline_notification()` already wired in `daily_pipeline.py` — no changes needed. |
| SIG-01 | User can assign one of 7 intent signals to any queue contact | `contact_signals` table and `SIGNAL_ACTIONS` dict exist from Phase 7. PWA must render signal picker and POST to `contact_signals` via PostgREST anon grants. |
| SIG-02 | Signal picker replaces legacy Reach Out / Skip / Snooze buttons on queue cards | `queue.js` currently renders 3 action buttons in `isPending` branch. Replace with expand/collapse signal picker section. |
| SIG-03 | Each signal assignment stored with timestamp and persisted to Supabase | Already complete from Phase 7 (schema + `apply_signal()`). PWA write path must use same pattern. |
| SIG-04 | User can view signal history for a contact on their profile page | `contact.js` must query `contact_signals` table filtered by `connection_id`, render assignment history list. |
| SIG-05 | User can filter queue by assigned signal type | `queueFilters` object in `queue.js` must add `signalFilter` key. Filter bar needs a signal select/tab control. Query joins `connections` to read `latest_signal`. |
| SIG-06 | ARCHIVE signal hides contact from queue and dashboard (data preserved) | Default queue filter must exclude `connections.user_priority = 'never'`. When ARCHIVE assigned via PWA, write `user_priority = 'never'` to `connections` via PostgREST. |
| PROF-01 | Profile key factors shows meaningful fallback content when enrichment data is sparse | `contact.js` `buildKeyFactors()` currently only renders if `keyFactors.length > 0`. Add fallback path using `raw_enrichment` fields (headline, industry, career path). |
| PROF-02 | Conversation starters generated from enrichment data and scoring rationale when activity_log empty | `contact.js` `buildHooks()` renders `conversation_hooks` from `score_reasoning`. Add fallback: construct starters from enrichment (headline, recent role changes) when hooks array is empty. |
| PROF-03 | User can add and edit free-form notes on any contact's profile | `contact.js` must render notes section: display existing `connections.notes` + `contact_notes` records, provide textarea/edit UI, POST new notes to `contact_notes` via PostgREST. |
| PROF-04 | Contact notes visible on queue cards | `queue.js` card rendering must fetch/show first N chars of `connections.notes` field. Already in model, just not displayed. |
| QUX-01 | Queue cards show industry, first key factor, and last interaction date | `queue.js` card HTML must add: industry chip from `connections.raw_enrichment`, first key_factor from `outreach_queue.mini_key_factors` or `connections.score_reasoning`, `last_message_date` from `connections`. |
| QUX-02 | Signal picker updates card in-place without removing it from the list | No card removal on signal assignment. Badge updates in DOM using `dataset.connectionId`. Do NOT call `card.remove()` after signal assignment. |
</phase_requirements>

---

## Summary

Phase 8 is an entirely frontend + Python template modification phase. There are no new database tables, no new Edge Functions, and no new Python dependencies. Everything this phase builds is modification of existing files: `email_digest.py`, `queue.js`, `contact.js`, and `app.css`.

The infrastructure built in Phase 7 (contact_signals table, contact_notes table, latest_signal/cadence_due_at on connections, anon grants for PostgREST PWA writes) is already deployed. Phase 8 is the UI surface that consumes it. The signal picker writes directly to `contact_signals` and `connections` via PostgREST, following the identical pattern used by `queueAction()` today.

The email digest requires surgical removal of three areas: (1) the action token generation block, (2) the data health section, (3) the feedback rating stars. The replacement is a single prominent "Review in App" CTA button using the existing `pwa_link` variable, plus adding `industry` to featured contact cards.

The profile page (`contact.js`) requires adding three new sections: signal history, notes display/editing, and fallback content for key factors and conversation starters when enrichment is sparse.

**Primary recommendation:** Work in three independent tracks — email digest Python modification, queue.js signal picker, contact.js profile enhancements — each can be implemented and tested independently.

---

## Standard Stack

### Core (already in project — zero new installs)

| Library/Tool | Version | Purpose | Why Standard |
|--------------|---------|---------|--------------|
| Vanilla JS | ES2020 | PWA signal picker, queue filters, notes UI | Project constraint: "No React/Vue rewrite" |
| Supabase JS client | @2 (CDN) | PostgREST writes for signals/notes, realtime | Already loaded in index.html via CDN |
| Python `html.escape` | stdlib | XSS-safe email HTML generation | Already used in `email_digest.py` |
| CSS flexbox | - | Signal chip layout (Claude's discretion) | Already used for `.card-actions` |
| pytest | installed | Test coverage | 58+ existing tests; same framework |

### No new dependencies

Zero `pip install` or `npm install` commands needed. This phase touches no requirements files.

**Test run commands:**
- Phase 8 only: `python -m pytest tests/test_phase8_email_signal_ui.py -x -q`
- Full suite: `python -m pytest tests/ -x -q`

---

## Architecture Patterns

### Recommended File Changes

```
src/
└── integrations/
    └── email_digest.py     MODIFY: remove tokens/health/stars; add industry; CTA button
pwa/
├── js/
│   ├── queue.js            MODIFY: signal picker UI, queue filter evolution, QUX-01 card info
│   └── contact.js          MODIFY: signal history, notes, fallback key factors/starters
└── css/
    └── app.css             MODIFY: signal chip colors, picker expand/collapse, notes textarea
tests/
└── test_phase8_email_signal_ui.py   NEW: unit tests for digest rebuild + signal picker behavior
```

### Pattern 1: PostgREST Direct Write (existing pattern — apply verbatim)

**What:** PWA writes to Supabase via `db.from().insert()` or `.update()` — no Edge Function needed
**When to use:** Signal assignment, note creation/editing
**Source:** `queue.js` `queueAction()` function (lines 182–195)

```javascript
// Signal assignment write — mirrors existing queueAction() pattern
async function assignSignal(connectionId, signal, queueItemId) {
  // 1. Write to contact_signals (INSERT)
  const { error: sigError } = await db
    .from('contact_signals')
    .insert({
      connection_id: connectionId,
      signal: signal,
      assigned_by: 'user',
    });
  if (sigError) throw sigError;

  // 2. Update connections.latest_signal (UPDATE)
  const updateData = { latest_signal: signal };
  if (signal === 'ARCHIVE') {
    updateData.user_priority = 'never';
  }
  const { error: connError } = await db
    .from('connections')
    .update(updateData)
    .eq('id', connectionId);
  if (connError) throw connError;
}
```

**Key constraint:** `contact_signals` has INSERT-only anon grant (no UPDATE). To reassign a signal, insert a new record — the latest one wins via `connections.latest_signal` update.

### Pattern 2: Signal Chip Expand/Collapse (new pattern)

**What:** A single "Assign Signal" row that expands to show 7 chips inline
**When to use:** Queue card action area (replaces 3-button row)

```javascript
// Queue card action area replacement
const currentSignal = conn.latest_signal;
const signalBadgeHtml = currentSignal
  ? `<span class="signal-badge signal-${currentSignal.toLowerCase().replace('_', '-')}">${SIGNAL_LABELS[currentSignal]}</span>`
  : '';

const actionsHtml = `
  <div class="card-actions signal-triage">
    <div class="signal-current" onclick="toggleSignalPicker(${item.id})">
      ${signalBadgeHtml || '<span class="signal-assign-cta">Assign Signal &darr;</span>'}
    </div>
    <div class="signal-picker hidden" id="picker-${item.id}">
      ${Object.entries(SIGNAL_LABELS).map(([key, label]) =>
        `<button class="signal-chip signal-chip-${key.toLowerCase().replace('_', '-')}"
                 onclick="assignSignalFromCard(event, '${conn.id}', '${key}', ${item.id})">
           ${label}
         </button>`
      ).join('')}
    </div>
  </div>`;
```

### Pattern 3: Signal JS Const (mirrors signal_service.py)

**What:** JavaScript constant that mirrors `SIGNAL_ACTIONS` from `signal_service.py`
**When to use:** Signal labels, colors, and chip rendering in PWA

```javascript
// At top of queue.js — mirrors src/services/signal_service.py SIGNAL_ACTIONS
const SIGNAL_ACTIONS = {
  WARM_LEAD:    { label: 'Warm Lead',    cadence: 7,  color: '#1a7f37', bg: '#dcfce7' },
  NURTURE:      { label: 'Nurture',      cadence: 21, color: '#0369a1', bg: '#e0f2fe' },
  VALUE_DROP:   { label: 'Value Drop',   cadence: 14, color: '#7c3aed', bg: '#ede9fe' },
  SYNERGY:      { label: 'Synergy',      cadence: 14, color: '#0a66c2', bg: '#e8f4fd' },
  RECONNECT:    { label: 'Reconnect',    cadence: 14, color: '#92400e', bg: '#fef3c7' },
  FUTURE_PIVOT: { label: 'Future Pivot', cadence: 60, color: '#6b7280', bg: '#f3f4f6' },
  ARCHIVE:      { label: 'Archive',      cadence: null, color: '#dc3545', bg: '#fee2e2' },
};
const SIGNAL_LABELS = Object.fromEntries(
  Object.entries(SIGNAL_ACTIONS).map(([k, v]) => [k, v.label])
);
```

**Discretion note:** Color palette above is a recommended starting point based on accessibility contrast. Claude's discretion per CONTEXT.md.

### Pattern 4: Email Digest — Surgical Removal

**What:** Remove 3 specific blocks from `_build_digest_html()`, add industry to card template
**When to use:** Phase 8 email work

```python
# REMOVE these three blocks from _build_digest_html():
# 1. Action token generation (lines ~157-215 in current email_digest.py):
#    from src.api.tokens import create_action_tokens, create_feedback_token
#    urls = create_action_tokens(...)
#    buttons_html = f'<table ...>Yes / Skip / Snooze buttons...</table>'
#
# 2. Data health section (lines ~248-272):
#    health_stats = _get_data_health_stats()
#    health_html = f'...'
#
# 3. Feedback stars (lines ~274-286):
#    feedback_html = f'...<div>Was today's digest useful?</div>...'

# ADD to each featured card:
industry = escape(enrichment.get('company_industry') or enrichment.get('companyIndustry') or '')
industry_html = f'<span style="...">{industry}</span>' if industry else ''

# REPLACE per-card buttons_html with a single top-level CTA
review_cta = (
    f'<div style="text-align:center;margin:20px 0 8px;">'
    f'<a href="{escape(pwa_link)}" style="display:inline-block;background:#0a66c2;color:#ffffff;'
    f'text-decoration:none;padding:14px 32px;border-radius:6px;font-size:16px;font-weight:bold;">'
    f'Review in App &rarr;</a>'
    f'</div>'
)
```

**Key insight:** The `_get_data_health_stats()` and `_get_skip_pattern_insight()` functions can remain in the file (they're not called if we remove the `health_html` block). No need to delete helper functions — just stop calling them.

### Pattern 5: Queue Filter Evolution (signal-aware)

**What:** Add `signalFilter` to `queueFilters`, evolve the filter bar to include a signal dropdown
**When to use:** SIG-05 requirement

```javascript
// Add to queueFilters object
const queueFilters = {
  sortAscending: false,
  statusFilter: null,          // CHANGED: null = untriaged only (default changes)
  signalFilter: null,          // NEW: null = show untriaged; 'WARM_LEAD' etc = show by signal
  industryFilter: null,
};

// Default behavior: show only untriaged (connections.latest_signal IS NULL)
// Signal filter 'WARM_LEAD': show connections with latest_signal = 'WARM_LEAD'
// Status filter 'all': show all

// Query modification:
let query = db
  .from('outreach_queue')
  .select('*, connections(*)');

if (queueFilters.signalFilter === null && queueFilters.statusFilter === null) {
  // Default: untriaged only
  query = query.is('connections.latest_signal', null);
} else if (queueFilters.signalFilter) {
  // Filter by signal type
  query = query.eq('connections.latest_signal', queueFilters.signalFilter);
}
```

**Important:** PostgREST filter on a joined table (`connections.latest_signal`) uses dot notation in `.select()` and may require `cs` (contains) or `eq` operators on the join. If PostgREST doesn't support filtering on joined columns directly, fall back to client-side filtering after fetching (same as the existing `industryFilter` pattern).

### Pattern 6: Notes Display and Edit (contact.js)

**What:** Fetch and render `contact_notes` records, edit `connections.notes`
**When to use:** PROF-03, PROF-04

```javascript
// Fetch notes for contact
const { data: notes } = await db
  .from('contact_notes')
  .select('*')
  .eq('connection_id', connectionId)
  .order('created_at', { ascending: false });

// Add note (INSERT to contact_notes)
async function addContactNote(connectionId, noteText) {
  const { error } = await db
    .from('contact_notes')
    .insert({ connection_id: connectionId, note_text: noteText });
  if (error) throw error;
}

// Update quick note on connection (UPDATE connections.notes)
async function updateConnectionNote(connectionId, noteText) {
  const { error } = await db
    .from('connections')
    .update({ notes: noteText })
    .eq('id', connectionId);
  if (error) throw error;
}
```

**Decision from Phase 7 CONTEXT.md:** Both paths are used — `connections.notes` for quick-edit, `contact_notes` for timestamped history.

### Pattern 7: Profile Key Factors Fallback (PROF-01, PROF-02)

**What:** When `keyFactors` array is empty, build fallback content from enrichment fields
**When to use:** contact.js `renderContact()` — replace empty-check with fallback logic

```javascript
// Key factors fallback strategy (Claude's discretion)
function buildKeyFactorsHtml(conn, keyFactors) {
  if (keyFactors.length > 0) {
    return renderKeyFactorsList(keyFactors);
  }

  // Fallback: synthesize from enrichment
  const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
  const fallbacks = [];
  if (enrichment.headline) fallbacks.push(enrichment.headline);
  if (enrichment.company_industry || enrichment.companyIndustry) {
    fallbacks.push(`Works in ${enrichment.company_industry || enrichment.companyIndustry}`);
  }
  const experiences = enrichment.experiences || enrichment.experience || [];
  if (experiences.length > 1) {
    const prev = experiences[1];
    fallbacks.push(`Previously: ${prev.title || ''} at ${prev.company || prev.companyName || ''}`);
  }
  if (conn.message_count > 0) {
    fallbacks.push(`${conn.message_count} messages exchanged`);
  }

  if (fallbacks.length === 0) return '';  // Truly empty
  return renderKeyFactorsList(fallbacks);  // Reuse same render logic
}

// Conversation starters fallback (PROF-02)
function buildHooksHtml(conn, hooks) {
  if (hooks.length > 0) {
    return renderHooksList(hooks);
  }

  // Fallback from enrichment when activity_log is empty
  const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
  const fallbackHooks = [];
  if (enrichment.headline) {
    fallbackHooks.push(`Ask about their work as: "${enrichment.headline}"`);
  }
  const experiences = enrichment.experiences || enrichment.experience || [];
  if (experiences.length > 0 && experiences[0].started_at) {
    fallbackHooks.push(`Recently joined ${experiences[0].company || experiences[0].companyName || 'their current company'}`);
  }
  if (conn.conversation_summary) {
    fallbackHooks.push(`Last discussed: ${conn.conversation_summary.slice(0, 80)}...`);
  }

  if (fallbackHooks.length === 0) return '';
  return renderHooksList(fallbackHooks);
}
```

### Pattern 8: QUX-01 Card Context Fields

**What:** Add industry chip, first key factor, last interaction date to each queue card
**When to use:** queue.js `renderQueue()` card template

```javascript
// Industry chip (from raw_enrichment)
const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
const industry = enrichment.company_industry || enrichment.companyIndustry || '';
const industryHtml = industry
  ? `<span class="industry-chip">${escapeHtml(industry)}</span>`
  : '';

// First key factor (from outreach_queue.mini_key_factors, fallback to score_reasoning)
let firstFactor = '';
if (item.mini_key_factors) {
  firstFactor = item.mini_key_factors.split('\n')[0];
} else if (conn.score_reasoning) {
  try {
    const reasoning = JSON.parse(conn.score_reasoning);
    firstFactor = (reasoning.key_factors || [])[0] || '';
  } catch(e) {}
}
const factorHtml = firstFactor
  ? `<div class="card-key-factor">${escapeHtml(firstFactor)}</div>`
  : '';

// Last interaction date
const lastDate = conn.last_message_date
  ? new Date(conn.last_message_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  : null;
const lastDateHtml = lastDate
  ? `<span class="card-last-contact">Last: ${escapeHtml(lastDate)}</span>`
  : '';
```

### Anti-Patterns to Avoid

- **Removing card from DOM on signal assign:** The spec requires card stays in place (QUX-02). Do NOT call `card.remove()`. The existing `queueAction()` pattern removes cards — signal assignment must NOT use that pattern.
- **Calling `create_action_tokens()` in rebuilt digest:** The entire token generation block is removed. No tokens for email — all actions happen in PWA.
- **Adding edge function for signal writes:** Phase 7 explicitly decided PostgREST direct writes. Do not create a new Edge Function.
- **Filtering on server via `connections.latest_signal` with PostgREST join filter:** PostgREST does not support filtering on embedded resource fields in a standard `select('*, connections(*)')` query. The signal filter must be done client-side after fetching (same pattern as existing `industryFilter`).
- **Fetching `contact_notes` on every queue card render:** Notes are only needed on the profile page (PROF-03) and as a brief excerpt on queue cards. Do NOT fetch full notes history during queue rendering — only fetch `connections.notes` (already included in the connections join).
- **Using `connections.notes` as the timestamped notes store:** `connections.notes` is the quick-edit field (plain text). `contact_notes` table provides timestamped history. Both exist and serve different purposes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Signal write to Supabase | Custom fetch POST to edge fn | `db.from('contact_signals').insert()` | Anon grants already set; PostgREST handles validation |
| HTML escape in email | Custom regex | `from html import escape` (already imported) | XSS-safe, stdlib |
| Note save debouncing | Custom timer | `setTimeout(..., 800)` on textarea blur | Standard PWA pattern; already used for offline actions |
| Signal chip colors | Custom color algorithm | Predefined CSS classes per signal | Deterministic, no computation needed |
| Last message date formatting | Custom date util | `toLocaleDateString()` | Already used in `contact.js` `buildConnectionStrengthSection()` |

---

## Common Pitfalls

### Pitfall 1: Card Removal on Signal Assign
**What goes wrong:** Developer copies the `queueAction()` skip/snooze pattern which calls `card.remove()`. Signal picker must NOT remove the card.
**Why it happens:** The existing `queueAction()` removes the card after skip/snooze. Signal assignment has different semantics (card stays visible).
**How to avoid:** Write `assignSignal()` as a separate function that only updates the badge, never touches card visibility.
**Warning signs:** Cards disappear from queue after signal click in testing.

### Pitfall 2: Email action token import at module level
**What goes wrong:** `from src.api.tokens import create_action_tokens, create_feedback_token` is currently inside `_build_digest_html()` at line ~157. If you remove the usage but forget to remove the import, it's a silent dead import (won't error, but will be flagged by ruff F401).
**How to avoid:** Remove both the import and all usage when rebuilding the digest. Run `python -m pytest tests/ -x -q` to confirm no import errors.

### Pitfall 3: PostgREST join filter not working for signal filter
**What goes wrong:** Developer writes `query.eq('connections.latest_signal', null)` expecting server-side filter on joined table. PostgREST does not support column filters on embedded resource fields.
**How to avoid:** Use client-side filter on the joined `connections` object after fetch — same approach as `industryFilter` in existing `queue.js` lines 46-54.

### Pitfall 4: email pwa_link uses hash fragment
**What goes wrong:** Current code has `pwa_link = settings.pwa_url.rstrip("/") + "/#/queue"` which includes a hash fragment. Gmail strips hash fragments from hyperlinks. The existing per-contact profile deep links use query params (`?view=contact&id=`) for this reason.
**How to avoid:** For the main "Review in App" CTA, use `pwa_url + "/?view=queue"` (query param routing). The app.js router already handles `?view=` parameters from email context.
**Current code location:** `email_digest.py` line ~289 (`pwa_link` variable).

### Pitfall 5: Contact notes `updated_at` not refreshed on edit
**What goes wrong:** When the PWA updates a note via `.update({ note_text: newText })`, the `updated_at` column is not automatically refreshed (PostgreSQL doesn't auto-update unless a trigger exists).
**How to avoid:** Include `updated_at: new Date().toISOString()` in the update payload when editing notes.

### Pitfall 6: Signal history section attempts write before migration applied
**What goes wrong:** If Phase 7 migration SQL has not been applied to Supabase, reads from `contact_signals` will return 404 (table not found). PWA will show blank signal history.
**How to avoid:** Add a try/catch around `contact_signals` fetch with a graceful fallback. STATE.md notes this is a known blocker: "Migration SQL must be applied to Supabase before PWA can read/write signals."

### Pitfall 7: Email digest tests using real `get_session()`
**What goes wrong:** Tests that instantiate `_build_digest_html()` with a real pipeline flow will attempt database queries.
**How to avoid:** Test `_build_digest_html()` by passing in pre-constructed `(OutreachQueueItem, Connection)` tuples — same mock-injection pattern used in Phase 7 tests.

---

## Code Examples

### Email Digest — Rebuilt Featured Card Template

```python
# Source: Derived from existing _build_digest_html() pattern in email_digest.py
# Phase 8 version: no action tokens, adds industry, removes action buttons

for queue_item, conn in featured:
    name = escape(conn.name or "Unknown")
    score = conn.reconnect_score or conn.pre_score or 0
    role = escape(conn.current_role or "")
    company = escape(conn.current_company or "")
    role_line = f"{role} @ {company}" if company else role

    # Industry (NEW for Phase 8)
    enrichment = {}
    if conn.raw_enrichment:
        enrichment = conn.raw_enrichment.get("data", conn.raw_enrichment) if isinstance(conn.raw_enrichment, dict) else {}
    industry = escape(enrichment.get("company_industry") or enrichment.get("companyIndustry") or "")
    industry_html = f'<span style="background:#f3f4f6;color:#555;font-size:12px;padding:2px 8px;border-radius:10px;margin-left:6px;">{industry}</span>' if industry else ""

    # Why Today hook
    why_today = _extract_why_today(conn, queue_item)
    why_html = f'<div style="color:#1a7f37;font-size:13px;margin:6px 0;"><strong>WHY:</strong> {escape(why_today)}</div>' if why_today else ""

    # Profile deep link (query params — survive Gmail redirect)
    pwa_base = settings.pwa_url.rstrip("/") if settings.pwa_url else ""
    profile_url = f"{pwa_base}/?view=contact&id={conn.id}"

    # Name linked to profile
    name_html = f'<a href="{escape(profile_url)}" style="color:#0a66c2;text-decoration:none;font-weight:bold;font-size:17px;">{name}</a>'

    cards_html += f'''
    <div style="background:#ffffff;border:1px solid #e0e0e0;border-radius:8px;padding:16px 18px;margin-bottom:12px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
                <td>{name_html}{industry_html}<div style="color:#555;font-size:14px;margin:2px 0;">{role_line}</div></td>
                <td style="width:80px;text-align:right;white-space:nowrap;"><span style="background:#e8f4fd;color:#0a66c2;font-weight:bold;font-size:14px;padding:4px 10px;border-radius:12px;display:inline-block;">Score: {score:.0f}</span></td>
            </tr>
        </table>
        {why_html}
    </div>
    '''
# NOTE: No buttons_html. The single "Review in App" CTA is placed once after all cards.
```

### Queue Card with Signal Badge + Picker

```javascript
// Source: pwa/js/queue.js — replaces isPending block
// Replaces: <button class="btn btn-primary" onclick="queueAction(...)">Reach Out</button>

const currentSignal = conn.latest_signal;
const signalInfo = currentSignal ? SIGNAL_ACTIONS[currentSignal] : null;

const signalBadgeHtml = signalInfo
  ? `<span class="signal-badge" style="background:${signalInfo.bg};color:${signalInfo.color};">${signalInfo.label}</span>`
  : '';

const actionsHtml = `
  <div class="card-actions signal-triage" data-expanded="false">
    <div class="signal-toggle" onclick="toggleSignalPicker(event, ${item.id})">
      ${signalBadgeHtml || '<span class="assign-signal-cta">Assign Signal &darr;</span>'}
    </div>
    <div class="signal-picker" id="picker-${item.id}" style="display:none;">
      ${Object.entries(SIGNAL_ACTIONS).map(([key, info]) =>
        `<button class="signal-chip" style="background:${info.bg};color:${info.color};border:1px solid ${info.color}30;"
                 onclick="assignSignalFromCard(event, '${escapeHtml(conn.id)}', '${key}', ${item.id}, '${escapeHtml(conn.id)}')">${info.label}</button>`
      ).join('')}
    </div>
  </div>`;
```

### Signal Assignment (no card removal)

```javascript
// Source: New function for queue.js (replaces queueAction() for signal flow)
async function assignSignalFromCard(event, connectionId, signal, itemId) {
  event.stopPropagation();  // Prevent card navigation click

  const card = document.querySelector(`[data-item-id="${itemId}"]`);
  if (!card) return;

  // Optimistic badge update
  const signalInfo = SIGNAL_ACTIONS[signal];
  const toggleDiv = card.querySelector('.signal-toggle');
  if (toggleDiv) {
    toggleDiv.innerHTML = `<span class="signal-badge" style="background:${signalInfo.bg};color:${signalInfo.color};">${signalInfo.label}</span>`;
  }

  // Close picker
  const picker = document.getElementById(`picker-${itemId}`);
  if (picker) picker.style.display = 'none';

  try {
    // 1. Insert contact_signal record
    const { error: sigError } = await db
      .from('contact_signals')
      .insert({ connection_id: connectionId, signal, assigned_by: 'user' });
    if (sigError) throw sigError;

    // 2. Update connection latest_signal (and user_priority for ARCHIVE)
    const connUpdate = { latest_signal: signal };
    if (signal === 'ARCHIVE') connUpdate.user_priority = 'never';
    const { error: connError } = await db
      .from('connections')
      .update(connUpdate)
      .eq('id', connectionId);
    if (connError) throw connError;

    // ARCHIVE: hide card (user_priority = 'never' means excluded from default view)
    if (signal === 'ARCHIVE') {
      card.style.transition = 'opacity 0.3s';
      card.style.opacity = '0.3';
      setTimeout(() => {
        // If current filter is default (untriaged), remove card
        // since ARCHIVE contacts are excluded from default view
        if (!queueFilters.signalFilter) card.remove();
      }, 400);
    }
    // Note: all other signals keep card in place (QUX-02)

  } catch (err) {
    console.error('Signal assign error:', err);
    // Restore toggle to unassigned state on error
    if (toggleDiv) toggleDiv.innerHTML = '<span class="assign-signal-cta">Assign Signal &#9660;</span>';
  }
}
```

### Pull Sync for Signals and Notes (pull.py addition)

The pull sync in `pull.py` currently does NOT include `contact_signals` or `contact_notes` — it only pulls actions from the cloud to local. Since signals and notes are written from the PWA to cloud, and the daily pipeline reads from local SQLite, the pull sync must bring these back to local.

```python
# Add to pull_from_cloud() in pull.py — after existing section 5

# Section 6: Pull ContactSignal records from cloud
from src.database.models import ContactSignal, ContactNote

signal_query = select(ContactSignal)
if last_pull_at:
    signal_query = signal_query.where(ContactSignal.assigned_at > last_pull_at)
cloud_signals = cloud_session.exec(signal_query).all()

signals_data = [
    {"id": s.id, "connection_id": s.connection_id, "signal": s.signal,
     "signal_context": s.signal_context, "assigned_at": s.assigned_at,
     "assigned_by": s.assigned_by}
    for s in cloud_signals
]

# Section 7: Pull ContactNote records from cloud
note_query = select(ContactNote)
if last_pull_at:
    note_query = note_query.where(ContactNote.created_at > last_pull_at)
cloud_notes = cloud_session.exec(note_query).all()

notes_data = [
    {"id": n.id, "connection_id": n.connection_id, "note_text": n.note_text,
     "created_at": n.created_at, "updated_at": n.updated_at}
    for n in cloud_notes
]
```

**Apply in local session:**
```python
# Insert contact_signals if not exists
for sig_data in signals_data:
    existing = local_session.get(ContactSignal, sig_data["id"])
    if not existing:
        local_session.add(ContactSignal(**sig_data))
        stats["contact_signals_pulled"] += 1

# Insert contact_notes if not exists (update if newer)
for note_data in notes_data:
    existing = local_session.get(ContactNote, note_data["id"])
    if not existing:
        local_session.add(ContactNote(**note_data))
        stats["contact_notes_pulled"] += 1
    elif note_data["updated_at"] and note_data["updated_at"] > existing.updated_at:
        existing.note_text = note_data["note_text"]
        existing.updated_at = note_data["updated_at"]
        local_session.add(existing)
        stats["contact_notes_pulled"] += 1
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Email has Approve/Skip/Snooze per contact | Email is notification only; signals in PWA | Phase 8 | `create_action_tokens()` no longer called from digest |
| 3 action buttons on queue cards | 7-signal picker (collapsed by default) | Phase 8 | Queue becomes triage surface, not action surface |
| Key factors section hidden when empty | Fallback from enrichment + connection data | Phase 8 | Profile always shows meaningful content |
| No contact notes in PWA | `contact_notes` table + `connections.notes` display | Phase 7/8 | Notes visible on cards and profile |
| Status-based queue filter (Pending/Approved/Sent/Skipped) | Signal-based filter (untriaged / by signal type) | Phase 8 | Default view: untriaged contacts only |

**Deprecated/changed behaviors:**
- `queueAction(itemId, connId, 'approve'/'skip'/'snooze')` — replaced by `assignSignalFromCard()` for new cards. Old function stays for any cards that still have legacy status.
- `create_action_tokens()` — no longer called from `send_digest_email()`. Function stays in `src/api/tokens.py` but is unused.
- `_get_data_health_stats()` and `_get_skip_pattern_insight()` — functions remain in `email_digest.py` but are no longer called.
- `create_feedback_token()` — no longer called from digest. Function stays in tokens.py.

---

## Open Questions

1. **PostgREST filter on `connections.latest_signal` for signal-type queue view**
   - What we know: PostgREST embedded resource filters work via `?connections.latest_signal=eq.WARM_LEAD` in raw URL form, but the Supabase JS client `.select('*, connections(*)')` join with `.eq('connections.latest_signal', ...)` may not be supported.
   - Recommendation: Implement signal filter client-side after fetch (same as `industryFilter`). Fetch all pending queue items, then filter by `item.connections?.latest_signal`. This is acceptable for a single-user tool with small queue sizes.

2. **Deep link routing: `?view=queue` vs `/#/queue` in email CTA**
   - What we know: Email clients strip hash fragments. Existing per-contact profile links use `?view=contact&id=` (query params).
   - What's unclear: Does the current `app.js` router handle `?view=queue` on load, or only hash routing?
   - Recommendation: Inspect `pwa/js/app.js` router during implementation. If only hash-based, add a `?view=` handler in the app initialization that calls `navigate('#/queue')` after load. This is a small 3-line addition to `app.js`.

3. **Pull sync for signals/notes: is it strictly necessary for Phase 8?**
   - What we know: Phase 8 signals are written PWA → Supabase (cloud). The local pipeline in Phase 9 will need to read signals from SQLite to evaluate cadence. Pull sync ensures SQLite stays current.
   - What's unclear: Whether Phase 8 requires pull sync or if it can wait until Phase 9 (cadence integration).
   - Recommendation: Include pull sync in Phase 8 since the pipeline already runs daily. Without it, signal assignments made in PWA won't reflect in local SQLite, causing mismatches in dashboard data. This is a targeted addition to `pull.py` following existing patterns exactly.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (currently passing: all phase 7 tests + prior phases) |
| Config file | none — runs via `pytest tests/` with no config file |
| Quick run command | `python -m pytest tests/test_phase8_email_signal_ui.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EMAIL-01 | `send_digest_email()` is callable and returns sent dict | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_send_digest_email_returns_dict -x` | Wave 0 |
| EMAIL-02 | `_build_digest_html()` output contains "Review in App" text | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_review_in_app_cta_present -x` | Wave 0 |
| EMAIL-03 | `_build_digest_html()` output does NOT contain "Approve", "Skip", "Snooze" buttons | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_no_legacy_action_buttons -x` | Wave 0 |
| EMAIL-03 | `_build_digest_html()` does NOT call `create_action_tokens` | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_no_token_generation -x` | Wave 0 |
| EMAIL-04 | Telegram import still present in daily_pipeline.py | unit | `pytest tests/test_phase8_email_signal_ui.py::TestPipelineWiring::test_telegram_wired -x` | Wave 0 |
| EMAIL-02 | `_build_digest_html()` features card includes industry field | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_industry_in_featured_cards -x` | Wave 0 |
| EMAIL-01 | Digest subject format preserved (name-based) | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_digest_subject_format -x` | Wave 0 |
| SIG-01 | SIGNAL_ACTIONS JS const has all 7 signals with labels | manual-only | N/A — JS const is not unit-testable in Python context | - |
| SIG-06 | ARCHIVE signal triggers user_priority=never write pattern | unit | `pytest tests/test_phase8_email_signal_ui.py::TestSignalWrite::test_archive_sets_user_priority -x` | Wave 0 |
| PROF-01 | key factors fallback returns non-empty when keyFactors=[] | unit | `pytest tests/test_phase8_email_signal_ui.py::TestProfileFallback::test_key_factors_fallback_with_enrichment -x` | Wave 0 |
| PROF-01 | key factors fallback returns empty when no enrichment available | unit | `pytest tests/test_phase8_email_signal_ui.py::TestProfileFallback::test_key_factors_fallback_truly_empty -x` | Wave 0 |
| PROF-02 | Conversation starters fallback from enrichment headline | unit | `pytest tests/test_phase8_email_signal_ui.py::TestProfileFallback::test_starters_fallback_uses_headline -x` | Wave 0 |
| PROF-03 | contact_notes INSERT pattern is correct (tablename, fields) | unit | `pytest tests/test_phase8_email_signal_ui.py::TestNoteWrite::test_contact_note_insert_structure -x` | Wave 0 |
| QUX-01 | Queue card template includes industry, key factor, last date variables | unit | `pytest tests/test_phase8_email_signal_ui.py::TestQueueCardContext::test_card_context_fields_populated -x` | Wave 0 |
| QUX-02 | Signal assignment does NOT remove card (ARCHIVE is exception) | manual-only | N/A — DOM manipulation requires browser test | - |
| Pull sync | pull_from_cloud() stats dict has contact_signals_pulled key | unit | `pytest tests/test_phase8_email_signal_ui.py::TestPullSync::test_pull_stats_has_signal_keys -x` | Wave 0 |

**Note on manual-only items:** JS DOM tests for signal picker expand/collapse and card-in-place behavior require a browser environment. These are verified manually during implementation. The automated tests cover all Python-layer logic and data structures.

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_phase8_email_signal_ui.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_phase8_email_signal_ui.py` — covers all automated requirements listed above

*(conftest.py and pytest framework already in place. `mock_settings` fixture in conftest.py provides `PWA_URL`, `GMAIL_APP_PASSWORD`, `GMAIL_SENDER_EMAIL` — needed for digest tests.)*

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection — `src/integrations/email_digest.py` (full file, lines 1-391) — current digest structure confirmed
- Direct codebase inspection — `pwa/js/queue.js` (full file) — current queue rendering and action patterns
- Direct codebase inspection — `pwa/js/contact.js` (full file) — current profile page sections
- Direct codebase inspection — `src/database/models.py` — confirmed Phase 7 schema fields exist: `latest_signal`, `cadence_due_at` on Connection; `signal`, `signal_context`, `mini_key_factors` on OutreachQueueItem; `ContactSignal`, `ContactNote` tables
- Direct codebase inspection — `src/services/signal_service.py` — confirmed `SIGNAL_ACTIONS` with all 7 signals
- Direct codebase inspection — `src/pipeline/daily_pipeline.py` — confirmed `send_digest_email()` is wired, Telegram notification is wired
- Direct codebase inspection — `src/sync/pull.py` — confirmed pull sync does NOT currently include `contact_signals` or `contact_notes`
- `.planning/phases/07-signal-foundation/07-RESEARCH.md` — confirmed anon grants exist for contact_signals (INSERT) and contact_notes (SELECT/INSERT/UPDATE)
- `.planning/phases/08-email-signal-ui-profile-content/08-CONTEXT.md` — all locked decisions sourced from here

### Secondary (MEDIUM confidence)

- Supabase JS client PostgREST join filter behavior: embedded resource filtering requires `?embedded.column=eq.value` syntax; Supabase JS client may not support `.eq('embedded.column', value)` in all versions. Client-side filter fallback is recommended.

### Tertiary (LOW confidence)

- None — all critical findings verified against codebase

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; all patterns verified in codebase
- Architecture patterns: HIGH — all modification targets inspected line-by-line
- Pitfalls: HIGH — card-removal pitfall confirmed by reading `queueAction()` source; email token pitfall confirmed by reading `_build_digest_html()` source; PostgREST join filter based on known behavior
- Pull sync need: HIGH — confirmed pull.py does not currently sync contact_signals/contact_notes

**Research date:** 2026-03-11
**Valid until:** This research is based on static codebase inspection and locked project decisions. Valid until email_digest.py, queue.js, contact.js, or pull.py architecture changes significantly.
