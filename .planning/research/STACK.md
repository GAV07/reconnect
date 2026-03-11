# Stack Research: v1.2 Intent-Driven Triage

**Domain:** Personal networking tool — intent signal system, cadence scheduling, goals profile, contact notes, signal-informed rescoring, draft tone adaptation, queue card enrichment
**Researched:** 2026-03-11
**Confidence:** HIGH — all findings based on direct codebase inspection and installed package verification

---

## Context: What Already Exists (Do Not Re-Implement)

The v1.2 stack additions are incremental. The validated existing stack is:

| Layer | Technology | Verified Version |
|-------|------------|-----------------|
| Python pipeline | Python 3.11+, Click, SQLModel, SQLAlchemy, OpenAI | SQLModel 0.0.31, OpenAI 2.15.0, Click 8.3.1 |
| Database (local) | SQLite via SQLAlchemy | - |
| Database (cloud) | Supabase PostgreSQL + PostgREST | - |
| PWA | Vanilla JS, Supabase JS Client v2 (CDN) | - |
| LLM | OpenAI gpt-4o-mini | - |
| Edge Functions | Deno + TypeScript on Supabase | - |
| Sync | Bidirectional SQLite to Supabase via psycopg2 | psycopg2-binary 2.9+ |

---

## Recommended Stack

### Core Technologies

**No new Python libraries required for any v1.2 feature.**

Every v1.2 feature maps to existing capabilities. The table below shows the analysis:

| Feature | Approach | Why No New Library Needed |
|---------|----------|--------------------------|
| 7 intent signals | New `intent_signal` TEXT column on `outreach_queue` | String enum stored in existing column; SQLModel Optional[str] field |
| Signal actions (ARCHIVE, cadence) | New `requeue_after` DATE column + pipeline step | Pure datetime arithmetic; daily LaunchAgent is the scheduler |
| User goals profile | `UserProfile.goals` Text already exists; add PWA editing form | Pull sync addition handles PWA edits flowing back to pipeline |
| Contact notes | `Connection.notes` Text already exists; add PWA editing UI | Field + sync already in place; only missing is PWA write path |
| Signal-informed rescoring | Extend `feedback_processor.py` to consume signal types | `UserPreference` weight system already built; add signal pattern branch |
| Draft tone adaptation | Pass `intent_signal` in POST body to `draft/index.ts` | Function already accepts POST body parameters; add optional field |
| Queue card enrichment | Parse `key_factors` from `score_reasoning` JSON in `queue.js` | JSON already returned in joined query; client-side parse only |

### Supporting Libraries

None needed. All supporting functionality is covered by:

- `json` (stdlib) — parsing `score_reasoning` for key_factors display
- `datetime` (stdlib) — cadence `requeue_after` date computation
- `collections.Counter` (stdlib) — signal pattern analysis in feedback_processor

### Development Tools

No changes to existing tooling. The existing setup covers all v1.2 work:

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Tests for new pipeline steps | Existing patterns apply |
| ruff | Linting for new Python files | Existing config |
| Supabase CLI | Deploy updated `draft` Edge Function | `supabase functions deploy draft` |

---

## Database Schema Changes

These are the only schema changes needed. All follow existing migration patterns (psycopg2 direct apply).

### outreach_queue — Two New Columns

```sql
-- Intent signal captured during triage
ALTER TABLE outreach_queue ADD COLUMN IF NOT EXISTS intent_signal TEXT;
-- Values: 'WARM_LEAD' | 'NURTURE' | 'VALUE_DROP' | 'SYNERGY' | 'RECONNECT' | 'FUTURE_PIVOT' | 'ARCHIVE'

-- Cadence: when this contact should re-appear in queue (NULL = no auto-requeue)
ALTER TABLE outreach_queue ADD COLUMN IF NOT EXISTS requeue_after DATE;

CREATE INDEX IF NOT EXISTS idx_queue_requeue
  ON outreach_queue(requeue_after)
  WHERE requeue_after IS NOT NULL;
```

**Why signal lives on queue item, not connection:** Triage signal is a decision made at a point in time, not a permanent contact property. The same contact can receive NURTURE today and WARM_LEAD in 6 months. Storing on queue items preserves full signal history. The `user_feedback` table (existing) records the signal event; the queue item column drives system behavior (cadence, tone).

### connections — No Schema Changes

`Connection.notes` (Text, line 86 of models.py) already exists and is already in `CONNECTION_SYNC_FIELDS` in `push.py` (line 35). No Python model change needed — only PWA editing UI.

### user_feedback — No Schema Changes

`extra_data` (JSONB, maps to `metadata` column) stores signal context. Add `'intent_signal'` as a new `feedback_type` value — this is purely a string convention, no schema constraint to change.

### action_tokens — No Changes for v1.2

Signal assignment is a PWA-only action. The email digest retains simple approve/skip/snooze. Adding 7 signal buttons to email would overwhelm the digest format and violate the email-as-notification constraint. Signals are assigned in the PWA queue card — users tap a signal after reviewing the contact in the app.

### SQLModel Model Change

Add two optional fields to `OutreachQueueItem` in `src/database/models.py`:

```python
# Intent signal (v1.2)
intent_signal: Optional[str] = None  # 'WARM_LEAD' | 'NURTURE' | ... | 'ARCHIVE'
requeue_after: Optional[datetime] = Field(default=None, index=True)
```

---

## Python Pipeline Changes

### New file: src/pipeline/signal_actions.py

Handles cadence computation and ARCHIVE side effects. Pure Python, no new dependencies.

Signal cadence table (fixed per-signal, not configurable per v1.2 scope):

```python
SIGNAL_CADENCES: dict[str, int] = {
    "NURTURE": 90,       # Re-appear after 90 days
    "VALUE_DROP": 60,    # Check back in 60 days
    "SYNERGY": 45,       # Resource sharing — re-check soon
    "RECONNECT": 120,    # Long-range reconnect
    "FUTURE_PIVOT": 180, # Dormant — check in 6 months
    # WARM_LEAD: no auto-requeue (user drives urgently)
    # ARCHIVE: sets user_priority='never', blocks queue permanently
}
```

Run as a new daily pipeline step (step 11 or between steps 4 and 5 in queue generation):

```python
def apply_signal_actions(queue_item_id: int, signal: str) -> dict:
    """Apply side effects when a signal is assigned to a queue item."""
    with get_session() as session:
        item = session.get(OutreachQueueItem, queue_item_id)
        item.intent_signal = signal
        item.status = _signal_to_status(signal)

        cadence_days = SIGNAL_CADENCES.get(signal)
        if cadence_days:
            item.requeue_after = (datetime.utcnow() + timedelta(days=cadence_days)).date()

        if signal == "ARCHIVE":
            conn = session.get(Connection, item.connection_id)
            if conn:
                conn.user_priority = "never"
                session.add(conn)

        session.add(item)
    return {"signal": signal, "requeue_after": item.requeue_after}


def _signal_to_status(signal: str) -> str:
    """Map signal to queue item status."""
    if signal == "WARM_LEAD":
        return "approved"
    elif signal == "ARCHIVE":
        return "skipped"
    else:
        return "skipped"  # Cadenced signals exit queue until requeue_after
```

### queue_generator.py — Cadence Re-queuing

Add cadence check at top of `generate_daily_queue()`. No library needed — pure SQL date comparison:

```python
from datetime import date

# Include contacts past their requeue_after date
requeue_due = session.exec(
    select(OutreachQueueItem)
    .where(OutreachQueueItem.requeue_after <= date.today())
    .where(OutreachQueueItem.intent_signal.in_(
        ["NURTURE", "VALUE_DROP", "SYNERGY", "RECONNECT", "FUTURE_PIVOT"]
    ))
).all()
```

These contacts bypass the `min_queue_score` threshold — they were already evaluated and given an explicit intent signal by the user.

### feedback_processor.py — Signal Pattern Analysis

Extend `_derive_weight_adjustments()` to consume `intent_signal` from queue items. No new library — same `Counter` pattern already used:

```python
# Map signals to dimension weight hints
SIGNAL_WEIGHT_HINTS = {
    "WARM_LEAD": {"goal_alignment": 1.2},      # User cares about goal fit
    "NURTURE": {"conversation_hooks": 0.8},    # Hooks less important for nurture
    "ARCHIVE": {"industry_overlap": 1.1},      # User filters by relevance
    "VALUE_DROP": {"mutual_value": 1.1},       # User cares about value exchange
}
```

Apply hints when a signal has appeared 3+ times in the last 30 days. Single occurrences are noise.

### src/sync/pull.py — Add user_profile Pull

This is required for PWA-edited goals to reach the pipeline's scoring prompts. Currently `pull.py` only fetches `user_feedback` and `action_tokens` from Supabase. Add:

```python
def _pull_user_profile(local_session, cloud_session) -> int:
    """Pull user_profile row from cloud (user may update goals in PWA)."""
    cloud_profile = cloud_session.get(UserProfile, 1)
    if not cloud_profile:
        return 0
    local_profile = local_session.get(UserProfile, 1)
    if local_profile:
        # Overwrite only goals/interests — don't clobber inferred fields
        local_profile.goals = cloud_profile.goals
        local_profile.interests = cloud_profile.interests
        local_session.add(local_profile)
    return 1
```

**Note on authoritative source:** Goals and interests are user-managed via PWA. Inferred fields (`inferred_industry`, `inferred_expertise`, etc.) are pipeline-managed. The pull only overwrites user-managed fields.

---

## Edge Function Changes

### draft/index.ts — Signal-Aware Tone Adaptation

Add `intent_signal` to `DraftRequest` interface and `buildDraftPrompt()`. Zero new Deno dependencies.

```typescript
interface DraftRequest {
  queue_item_id: number;
  channel?: string;
  intent_signal?: string;  // NEW in v1.2
}
```

Replace the two-option `toneGuideline` with a signal-indexed map:

```typescript
const SIGNAL_TONE: Record<string, string> = {
  WARM_LEAD:    "Lead with their recent activity or role change. Be direct and specific about wanting to collaborate.",
  NURTURE:      "Keep it warm and low-pressure. No ask — just checking in and sharing something useful.",
  VALUE_DROP:   "Reference a specific resource or insight relevant to their current work. Lead with the value.",
  SYNERGY:      "Focus on one concrete collaboration angle. Propose something specific, not vague 'connecting'.",
  RECONNECT:    "Acknowledge the gap since you last connected. Keep it genuine, not apologetic.",
  FUTURE_PIVOT: "Plant a seed. No immediate ask — just keeping the relationship warm for future opportunities.",
};

// In buildDraftPrompt():
const signalGuidance = intent_signal && SIGNAL_TONE[intent_signal]
  ? `Signal context: ${SIGNAL_TONE[intent_signal]}`
  : "";

const channelTone = channel === "linkedin"
  ? "Use casual LinkedIn DM tone"
  : "Use professional but warm email tone";
```

Deploy via: `supabase functions deploy draft`

---

## PWA Changes

### queue.js — Signal Picker + Card Enrichment

**Signal picker:** Replace three-button action row (Reach Out / Skip / Snooze) with a signal selector. The Supabase JS client v2 (already loaded via CDN) handles the PATCH directly:

```javascript
async function assignSignal(itemId, connectionId, signal) {
  const cadenceDays = {
    NURTURE: 90, VALUE_DROP: 60, SYNERGY: 45,
    RECONNECT: 120, FUTURE_PIVOT: 180
  };

  const requeueAfter = cadenceDays[signal]
    ? new Date(Date.now() + cadenceDays[signal] * 86400000).toISOString().split('T')[0]
    : null;

  const updateData = {
    intent_signal: signal,
    status: signal === 'WARM_LEAD' ? 'approved' : 'skipped',
    reviewed_at: new Date().toISOString(),
    ...(requeueAfter && { requeue_after: requeueAfter }),
  };

  await db.from('outreach_queue').update(updateData).eq('id', itemId);

  if (signal === 'ARCHIVE') {
    await db.from('connections').update({ user_priority: 'never' }).eq('id', connectionId);
  }

  if (signal === 'WARM_LEAD') {
    navigate(`#/contact/${connectionId}?queue_item=${itemId}`);
  }
}
```

**Queue card enrichment — key factors:** `score_reasoning` is already returned in the `select('*, connections(*)')` query. Parse client-side:

```javascript
const reasoning = JSON.parse(conn.score_reasoning || '{}');
const keyFactors = (reasoning.key_factors || []).slice(0, 2);
const keyFactorsHtml = keyFactors.length
  ? `<div class="key-factors">${keyFactors.map(f => `<span class="factor-chip">${escapeHtml(f)}</span>`).join('')}</div>`
  : '';
```

No additional API call. Data is already in the joined response.

**Queue card enrichment — industry chip and last interaction:** Both fields are already in the joined query. Add to card HTML:

```javascript
const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
const industry = escapeHtml(enrichment.company_industry || enrichment.companyIndustry || '');
const industryHtml = industry ? `<span class="industry-chip">${industry}</span>` : '';

const lastContact = conn.last_contacted_at || conn.last_message_date;
const lastInteractionHtml = lastContact
  ? `<span class="last-interaction">Last: ${new Date(lastContact).toLocaleDateString()}</span>`
  : '';
```

**Notes on card:** `conn.notes` is already in the joined response. Display truncated:

```javascript
const notesHtml = conn.notes
  ? `<div class="card-notes">${escapeHtml(conn.notes.slice(0, 120))}${conn.notes.length > 120 ? '…' : ''}</div>`
  : '';
```

### contact.js — Notes Editing

PostgREST PATCH directly from the PWA contact detail page. No Edge Function needed — no server-side secret required for a plain text update:

```javascript
async function saveContactNotes(connectionId, notes) {
  const { error } = await db
    .from('connections')
    .update({ notes, updated_at: new Date().toISOString() })
    .eq('id', connectionId);
  return !error;
}
```

The anon key with appropriate RLS policy handles this. The existing RLS for queue status updates (already in `queue.js`) demonstrates the same pattern is workable.

### preferences.js or new goals-form in contact/profile section

User goals profile editing. Fetch `user_profile` (id=1) and PATCH:

```javascript
async function saveUserGoals(goals, interests) {
  const { error } = await db
    .from('user_profile')
    .update({ goals, interests, updated_at: new Date().toISOString() })
    .eq('id', 1);
  return !error;
}
```

The pipeline will pull this on next sync via the new `_pull_user_profile()` function in `pull.py`.

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| APScheduler or Celery | Cadence re-queuing is daily batch, not real-time. A scheduling library adds operational complexity for a single-user local tool. | LaunchAgent already runs the pipeline at 8AM. Cadence check is a `requeue_after <= today` SQL query inside `generate_daily_queue()`. |
| React or Vue in PWA | Signal picker is 7 buttons — a UI extension, not a UI rewrite. Framework adoption requires build tooling and breaks the Netlify git-push deployment model. | Extend `queue.js` with `renderSignalPicker()`. Same vanilla JS pattern used for existing card actions. |
| Semantic embeddings / pgvector for signal learning | Signal-informed rescoring does not need semantic similarity. Pattern analysis on signal string values + dimension score weights is sufficient for v1.2. | Extend `feedback_processor.py` with Counter-based signal pattern analysis (already used for skip/approval patterns). |
| SQLite full-text search | Contact notes search is not in v1.2 scope. | Defer to v1.3 if AI contact search feature is scoped. |
| Separate signals table | Over-engineering for 7 string values. A TEXT column on `outreach_queue` with an index is sufficient. Signal history is preserved by the queue item records themselves. | `outreach_queue.intent_signal TEXT` column. |
| New Edge Function for notes | Notes are plain text. No server-side secret is needed for a PATCH via PostgREST with anon key + RLS. | Direct PostgREST PATCH from PWA. |
| Redis or caching layer | Draft generation is per-demand, low-frequency. Draft is cached in `outreach_queue.draft_message` after first generation. | Existing draft caching in queue table row. |

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| Signal on `outreach_queue` item | Signal on `connections` table as current_signal | Queue item signal is a triage decision, not a permanent contact state. History is preserved per item. Storing on connection would lose the time dimension. |
| Cadence via `requeue_after DATE` computed at signal-assignment time | Separate `contact_cadences` table | Unnecessary complexity for fixed cadences. `requeue_after = today + SIGNAL_CADENCES[signal]` at assignment time is explicit and self-contained. |
| Extend `draft/index.ts` with optional `intent_signal` param | New `draft-v2` Edge Function | Cold start overhead doubled for no benefit. The existing function is clean TypeScript — adding an optional parameter is straightforward. |
| PWA writes notes directly via PostgREST | Notes via Edge Function | Edge Functions are for operations requiring server-side secrets (OpenAI key, service role key). A notes PATCH requires neither. |
| Inline signal picker on queue card | Modal overlay for signal selection | Modal hides contact context while the user is choosing. Inline picker keeps name/role/score visible during signal assignment — better UX for a decision-support tool. |
| Pull `user_profile` in `sync/pull.py` | PWA goals editing is CLI-only | PWA goals editing is more accessible during the daily triage workflow. Pull sync is the correct data flow pattern for user-initiated changes that need to reach the pipeline. |

---

## Version Compatibility

All v1.2 changes work within existing installed versions. No version changes needed.

| Package | Current Version | v1.2 Requirement | Compatible |
|---------|----------------|-------------------|-----------|
| sqlmodel | 0.0.31 | Optional[str] and Optional[datetime] fields | Yes |
| openai | 2.15.0 | No change | Yes |
| click | 8.3.1 | No change | Yes |
| pydantic-settings | 2.12.5 | No change | Yes |
| psycopg2-binary | 2.9+ | New ALTER TABLE migrations | Yes |
| Supabase JS Client | v2 (CDN) | PATCH on connections + user_profile | Yes — `.update()` works on any table with RLS |
| Deno (Supabase-managed) | v1.x | Optional parameter in DraftRequest | Yes |

---

## Installation

**No new pip packages.** No new npm packages. No new Deno imports.

The only deployment action required for v1.2:

```bash
# Deploy updated draft Edge Function after modifying intent_signal support
supabase functions deploy draft
```

And apply the SQL migration via psycopg2 (consistent with existing migration approach):

```sql
-- New file: supabase/migrations/20260311000000_intent_signals.sql
ALTER TABLE outreach_queue ADD COLUMN IF NOT EXISTS intent_signal TEXT;
ALTER TABLE outreach_queue ADD COLUMN IF NOT EXISTS requeue_after DATE;
CREATE INDEX IF NOT EXISTS idx_queue_requeue
  ON outreach_queue(requeue_after)
  WHERE requeue_after IS NOT NULL;
```

---

## Integration Points Summary

| Feature | Python Pipeline | Supabase DB | Edge Function | PWA (JS) |
|---------|----------------|-------------|---------------|----------|
| Intent signals | `signal_actions.py` (new) | `outreach_queue.intent_signal` | `draft/index.ts` receives signal | `queue.js` signal picker |
| Cadence re-queuing | `queue_generator.py` checks `requeue_after` | `outreach_queue.requeue_after` | — | Shows requeue badge on card |
| User goals profile | `scoring.py` reads `UserProfile.goals` | `user_profile.goals` (existing) | — | New goals editing form |
| Contact notes | No change needed | `connections.notes` (existing) | — | Notes textarea + save button |
| Signal-informed rescoring | `feedback_processor.py` signal patterns | `user_preferences` (existing) | — | — |
| Draft tone adaptation | — | Signal read by draft function | `draft/index.ts` signal→tone map | Passes `intent_signal` in POST body |
| Queue card enrichment | — | `score_reasoning` JSON (existing) | — | `queue.js` client-side parse |

---

## Sources

- Direct codebase inspection: `src/database/models.py`, `src/pipeline/queue_generator.py`, `src/pipeline/feedback_processor.py`, `src/llm/scoring.py`, `src/sync/push.py`, `src/sync/pull.py`, `pwa/js/queue.js`, `pwa/js/contact.js`, `supabase/functions/draft/index.ts`, `supabase/functions/action/index.ts`, `src/config.py`, `requirements.txt`
- Installed package versions verified directly: sqlmodel 0.0.31, openai 2.15.0, click 8.3.1, pydantic 2.12.5
- Existing migration pattern confirmed: `supabase/migrations/20260305000000_pwa_overhaul.sql` — psycopg2 direct apply
- PostgREST PATCH pattern confirmed: `queue.js` lines 183-194 demonstrate existing direct DB writes via supabase-js `.update()`
- Signal cadence values: networking domain judgment; no external source required for fixed day constants

---

*Stack research for: Reconnect v1.2 Intent-Driven Triage*
*Researched: 2026-03-11*
