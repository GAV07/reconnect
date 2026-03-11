# Architecture Research

**Domain:** Personal networking tool — intent signal system integration (v1.2)
**Researched:** 2026-03-11
**Confidence:** HIGH (all analysis derived from direct codebase inspection, no speculation)

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         LOCAL MACHINE (macOS)                            │
├──────────────────────────────────────────────────────────────────────────┤
│  LaunchAgent (8AM)                                                        │
│      │                                                                    │
│      ▼                                                                    │
│  reconnect pipeline run (Click CLI)                                       │
│      │                                                                    │
│      ▼                                                                    │
│  daily_pipeline.py (10 steps + email digest)                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ import   │→ │ prescore │→ │ enrich   │→ │  score   │→ │  queue   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │complete- │→ │ feedback │→ │  enrich  │→ │dashboard │→ │ sync +   │  │
│  │ ness     │  │ proc.    │  │  plan    │  │ snapshot │  │ digest   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                                           │
│  SQLite (source of truth for all pipeline data)                           │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ connections · outreach_queue · user_profile · user_feedback       │   │
│  │ user_preferences · action_tokens · dashboard_snapshots            │   │
│  │ contact_signals (NEW) · contact_notes (NEW) · + more              │   │
│  └───────────────────────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────────────┤
│                    SYNC (bidirectional, end of pipeline)                  │
│  push.py → Supabase PostgreSQL ← pull.py (actions, signals, notes)       │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                         SUPABASE (Cloud)                                  │
├──────────────────────────────────────────────────────────────────────────┤
│  PostgreSQL (mirror of local SQLite, minus gmail_credentials)             │
│                                                                           │
│  PostgREST API ◄──────────────────────────────── PWA (anon key)          │
│  (reads + writes for signals, notes, queue actions)                       │
│                                                                           │
│  Edge Functions                                                           │
│  ┌──────────────────┐  ┌───────────────────┐  ┌──────────────────┐      │
│  │ action/index.ts  │  │ draft/index.ts    │  │feedback/index.ts │      │
│  │ (email triage    │  │ (OpenAI draft gen │  │ (user_feedback + │      │
│  │  action tokens)  │  │  + signal tone)   │  │  priority writes)│      │
│  └──────────────────┘  └───────────────────┘  └──────────────────┘      │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                         PWA (Netlify)                                     │
├──────────────────────────────────────────────────────────────────────────┤
│  Vanilla JS SPA — hash-based routing                                      │
│  ┌──────────┐  ┌───────────┐  ┌─────────────┐  ┌───────────────────┐   │
│  │ queue.js │  │contact.js │  │dashboard.js │  │ preferences.js    │   │
│  │ (signal  │  │(profile + │  │(analytics)  │  │(scoring weights + │   │
│  │ selector)│  │ notes +   │  │             │  │  user goals)      │   │
│  │          │  │ sig hist) │  │             │  │                   │   │
│  └──────────┘  └───────────┘  └─────────────┘  └───────────────────┘   │
│                                                                           │
│  All reads: PostgREST (anon key)                                          │
│  Writes: PostgREST direct for signals, notes, queue updates               │
│          Edge Functions for drafts (needs OPENAI_API_KEY secret)         │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Current Responsibility | v1.2 Addition |
|-----------|------------------------|---------------|
| `daily_pipeline.py` | Orchestrates 10 pipeline steps | Runs signal-based rescore pass in Step 8 |
| `llm/scoring.py` | LLM-based contact scoring, 5 dimensions | Accepts signal context; applies signal nudges to prompt |
| `pipeline/queue_generator.py` | Selects and creates OutreachQueueItem rows | Respects cadence (cadence_due_at); boosts WARM_LEAD priority; computes mini_key_factors |
| `pipeline/feedback_processor.py` | Analyzes approve/skip patterns, derives weight adjustments | Analyzes signal patterns; triggers selective rescoring |
| `sync/push.py` | Pushes SQLite to Supabase | Includes contact_signals, contact_notes, new connection fields |
| `sync/pull.py` | Pulls review actions from Supabase | Pulls signals, notes, latest_signal/cadence_due_at updates |
| `services/signal_service.py` | (does not exist) | NEW: canonical signal → action + cadence mapping |
| `supabase/functions/draft/index.ts` | Generates drafts via OpenAI | Accepts `signal` param; injects tone guidance into prompt |
| `supabase/functions/action/index.ts` | Email triage token handler | No change needed (signal triage happens in PWA, not email) |
| `supabase/functions/feedback/index.ts` | Records user_feedback | No change needed (signal writes go direct to PostgREST) |
| `pwa/js/queue.js` | Queue cards, approve/skip/snooze | 7-option signal selector; enriched card context (mini_key_factors, notes) |
| `pwa/js/contact.js` | Contact profile, AI rationale | Shows contact notes; signal history panel |
| `pwa/js/preferences.js` | Scoring weight preferences | Adds user goals/projects editing form |
| `database/models.py` | SQLModel table definitions | New: ContactSignal, ContactNote; modified: Connection, OutreachQueueItem, UserProfile |

---

## New vs Modified Components

### New Tables Required

#### `contact_signals` (new table)

Core of the intent signal system. Replaces binary approve/skip/snooze with 7 named signals. Stored as a history — a contact can change signals over time.

```sql
CREATE TABLE contact_signals (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id TEXT NOT NULL REFERENCES connections(id),
    queue_item_id INTEGER REFERENCES outreach_queue(id),
    -- NULL for signals applied directly from profile page
    signal        TEXT NOT NULL,
    -- WARM_LEAD | NURTURE | VALUE_DROP | SYNERGY
    -- | RECONNECT | FUTURE_PIVOT | ARCHIVE
    context       TEXT,          -- Free-form note at decision time
    signaled_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_signals_connection ON contact_signals(connection_id, signaled_at DESC);
CREATE INDEX idx_signals_signal ON contact_signals(signal);
```

**Why new table, not a field on `connections`:** Signals are a time-series. A contact is NURTURE today and WARM_LEAD after they post about a topic matching your goals. The history is auditable and enables signal-pattern analysis in `feedback_processor.py`.

**Sync direction:** PWA writes → Supabase (via PostgREST, same pattern as user_feedback). Pull to local SQLite on next pipeline run.

#### `contact_notes` (new table)

Free-form notes per contact. Visible on queue cards (truncated) and profile pages (full text).

```sql
CREATE TABLE contact_notes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id TEXT NOT NULL REFERENCES connections(id),
    text          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_notes_connection ON contact_notes(connection_id);
```

**Why new table, not `connections.notes`:** The `Connection` model already has a `notes` column (TEXT) but it is not pushed to Supabase in `push.py` and is not synced. Creating a separate `contact_notes` table makes notes first-class, syncable, and queryable from the PWA independently of the full connections row.

**Sync direction:** Bidirectional. PWA writes notes → Supabase. Pull.py pulls notes to local SQLite so the LLM scoring prompt can reference them.

### Modified Tables

#### `connections` — new columns

| Column | Type | Null | Purpose |
|--------|------|------|---------|
| `latest_signal` | TEXT | YES | Cached most-recent signal (avoids aggregation JOIN in queue generation) |
| `latest_signal_at` | TIMESTAMPTZ | YES | When `latest_signal` was last set |
| `cadence_due_at` | TIMESTAMPTZ | YES | Next eligible queue-entry date (set by signal system; NULL = always eligible) |

**Why `latest_signal` cache:** Queue generation (`is_contact_excluded()`) and queue sorting both need to know a contact's current signal. A subquery on `contact_signals` per connection adds JOIN complexity to the hottest pipeline path. Denormalization is safe at single-user scale.

**`cadence_due_at` replaces per-signal skip cooldowns.** It is set deterministically by `signal_service.py` when a signal is applied. NURTURE → NOW() + 30d. WARM_LEAD → NOW() + 7d. ARCHIVE → NULL (contact is excluded via `user_priority = 'never'` instead).

#### `outreach_queue` — new columns

| Column | Type | Null | Purpose |
|--------|------|------|---------|
| `signal` | TEXT | YES | Signal assigned when this queue item was triaged |
| `signal_context` | TEXT | YES | Note attached to the signal decision |
| `mini_key_factors` | TEXT | YES | Pre-computed 1-2 sentence summary for queue card (avoids parsing score_reasoning JSON in the browser) |

**Why `mini_key_factors` in the queue table:** Queue card enrichment requires showing key factors. Computing them from `score_reasoning` (a nested JSON blob) in the browser means either exposing full enrichment JSON to the client or adding complex JS parsing. Pre-computing a plain-text summary in the Python queue generator is simpler and keeps the PWA lightweight.

#### `user_profile` — new columns

The existing `goals` (TEXT) and `interests` (TEXT) columns are already used in `build_scoring_prompt()`. v1.2 adds structured goals alongside them so the signal rescoring step can make precise matches without parsing free-form text.

| Column | Type | Null | Purpose |
|--------|------|------|---------|
| `current_projects` | TEXT | YES | What the user is working on right now (informs WARM_LEAD matching) |
| `goals_structured` | JSON | YES | Array of `{goal, domain, urgency}` for LLM-readable matching |

**Why not just extend the existing `goals` field:** `goals` is a free-form string read by the existing scoring prompt. Changing its format breaks existing scoring calibration. Adding structured goals alongside it gives the signal rescoring step precise criteria without disrupting the working scoring prompt.

---

## Signal Flow Architecture

### Signal Lifecycle

```
User opens queue card in PWA
        |
        v
Selects one of 7 signals (with optional context note)

Signal → Status + Cadence mapping (signal_service.py canonical map):

  WARM_LEAD    → status: approved,       cadence: NOW() + 7d,  priority boost: +10
  NURTURE      → status: pending_review, cadence: NOW() + 30d, priority boost: 0
  VALUE_DROP   → status: skipped,        cadence: NOW() + 90d, priority boost: -5
  SYNERGY      → status: approved,       cadence: NOW() + 14d, priority boost: +5
  RECONNECT    → status: approved,       cadence: NOW() + 14d, priority boost: 0
  FUTURE_PIVOT → status: pending_review, cadence: NOW() + 60d, priority boost: 0
  ARCHIVE      → status: skipped,        cadence: NULL,        user_priority: 'never'

        |
        v
PWA writes (PostgREST — same pattern as existing user_feedback writes):

  INSERT INTO contact_signals (connection_id, queue_item_id, signal, context)
  UPDATE outreach_queue SET signal=?, signal_context=?, status=?, reviewed_at=NOW()
  UPDATE connections SET latest_signal=?, latest_signal_at=?, cadence_due_at=?
     (for ARCHIVE also: user_priority = 'never')

        |
        v
Next pipeline run (8AM)

  pull.py: pulls contact_signals, contact_notes, latest_signal/cadence_due_at updates

  Step 6 — queue_generator.py:
    is_contact_excluded() Rule 6: cadence_due_at > NOW() → excluded
    is_contact_excluded() Rule 7: latest_signal = 'ARCHIVE' → excluded
    generate_queue_item(): WARM_LEAD contacts → priority_score += 10
    generate_queue_item(): computes mini_key_factors from score_reasoning JSON

  Step 8 — feedback_processor.py (extended):
    Reads contact_signals from last 30 days
    Identifies NURTURE contacts where reconnect_score < 40 as rescore candidates
    Derives signal-pattern weight adjustments
    Calls score_connections_batch() for flagged candidates

  Step 5 — scoring.py (when rescoring flagged contacts):
    build_scoring_prompt() includes latest_signal and signal context
    WARM_LEAD adds explicit note to LLM prompt to boost goal_alignment assessment

  push.py: pushes updated connections (latest_signal, cadence_due_at) back to Supabase
```

### Draft Tone Adaptation Flow

```
PWA: User clicks "Generate Draft" on queue card
        |
        v
POST /functions/v1/draft
{
  "queue_item_id": 123,
  "channel": "email",
  "signal": "WARM_LEAD",         // new parameter
  "signal_context": "Met at conf, can intro to my CTO"
}
        |
        v
draft/index.ts buildDraftPrompt() extended:

  signal → tone guidance injected at end of prompt:

    WARM_LEAD    → "This is a warm lead. Be direct and reference the specific opportunity."
    NURTURE      → "This is a nurture touch. Share something valuable, make no explicit ask."
    SYNERGY      → "Clear collaboration potential. Propose a concrete next step."
    RECONNECT    → "You have shared history. Be casual and reference it briefly."
    FUTURE_PIVOT → "Person is in career transition. Be forward-looking and supportive."
    (VALUE_DROP, ARCHIVE → no draft generated; PWA disables draft button for these)

  If signal_context provided, inject as additional context line in prompt.

        |
        v
Returns draft with signal-appropriate tone
```

### Signal-Informed Rescoring Flow

```
feedback_processor.py (daily, extended Step 8):

  1. Query contact_signals WHERE signaled_at > NOW() - 30d
  2. Group by signal type:

     WARM_LEAD signals → extract their domains/industries
       if >40% are in "AI/ML", boost goal_alignment weight for that domain
       (writes to user_preferences as scoring_weight override — existing mechanism)

     ARCHIVE signals → ensure user_priority = 'never' on those connections
       (defense: PWA sets this, pipeline confirms)

     NURTURE signals where reconnect_score < 40 → flag for rescore
       (low-scored contact was worth nurturing → maybe score was wrong)

  3. Write weight adjustments to user_preferences (existing _upsert_scoring_weight())

  4. For flagged NURTURE contacts: call score_connections_batch(ids, signal_context=True)
     score_connection() extended: reads latest_signal + context, appends to prompt
```

---

## Data Flow Changes

### Push Changes (local → Supabase)

`push.py` currently pushes: connections, outreach_queue, dashboard_snapshots, action_tokens.

New additions:
- `contact_signals` — push signals created locally (CLI triage, if any)
- `contact_notes` — push notes created locally
- New fields on connections: `latest_signal`, `latest_signal_at`, `cadence_due_at`

No changes to `outreach_queue` push (new columns are nullable, existing upsert logic handles them).

### Pull Changes (Supabase → local)

`pull.py` currently pulls: outreach_queue status changes, outreach_log, connection.last_contacted_at/user_priority, user_feedback, user_preferences.

New additions:
- `contact_signals` created in PWA — INSERT if not exists (same pattern as user_feedback)
- `contact_notes` created in PWA — INSERT if not exists
- `connections.latest_signal` and `cadence_due_at` — cloud wins (same rule as user_priority)

**Conflict resolution principle:** User-intent data (signals, notes, priorities) comes from the PWA and cloud wins. Pipeline-computed data (scores, enrichment, completeness) comes from local and local wins.

### Queue Generator Changes

```python
# queue_generator.py — is_contact_excluded() gets two new rules:

# Rule 6: Signal-based cadence not yet due
if connection.cadence_due_at and connection.cadence_due_at > now:
    return ExclusionResult(
        excluded=True,
        reason=f"Cadence not due until {connection.cadence_due_at.date()}"
    )

# Rule 7: Archived (belt-and-suspenders with user_priority = 'never')
if connection.latest_signal == 'ARCHIVE':
    return ExclusionResult(excluded=True, reason="Archived by user signal")

# generate_queue_item() gets two additions:

# 1. WARM_LEAD priority boost
from src.services.signal_service import SIGNAL_ACTIONS
priority_boost = SIGNAL_ACTIONS.get(connection.latest_signal, {}).get("priority_boost", 0)
queue_item.priority_score = (connection.reconnect_score or 50) + priority_boost

# 2. mini_key_factors pre-computation
queue_item.mini_key_factors = _compute_mini_key_factors(connection)

def _compute_mini_key_factors(connection: Connection) -> Optional[str]:
    if not connection.score_reasoning:
        return None
    try:
        reasoning = json.loads(connection.score_reasoning)
        factors = reasoning.get("key_factors", [])
        if factors:
            return "; ".join(factors[:2])  # First 2 key factors
    except (json.JSONDecodeError, TypeError):
        return None
    return None
```

### PWA Changes

**queue.js — signal selector replaces 3 buttons:**

```javascript
// Replace the Approve / Skip / Snooze button group with:
const SIGNAL_ACTIONS = {
  WARM_LEAD:    { status: 'approved',       cadenceDays: 7,   label: 'Warm Lead',    emoji: '🔥' },
  NURTURE:      { status: 'pending_review', cadenceDays: 30,  label: 'Nurture',      emoji: '🌱' },
  VALUE_DROP:   { status: 'skipped',        cadenceDays: 90,  label: 'Value Drop',   emoji: '📉' },
  SYNERGY:      { status: 'approved',       cadenceDays: 14,  label: 'Synergy',      emoji: '⚡' },
  RECONNECT:    { status: 'approved',       cadenceDays: 14,  label: 'Reconnect',    emoji: '🔗' },
  FUTURE_PIVOT: { status: 'pending_review', cadenceDays: 60,  label: 'Future Pivot', emoji: '🎯' },
  ARCHIVE:      { status: 'skipped',        cadenceDays: null, label: 'Archive',     emoji: '📦' },
};

async function applySignal(queueItemId, connectionId, signal, context) {
  const action = SIGNAL_ACTIONS[signal];
  const now = new Date();
  const cadenceDueAt = action.cadenceDays
    ? new Date(now.getTime() + action.cadenceDays * 86400000).toISOString()
    : null;

  // Write signal record
  await db.from('contact_signals').insert({
    connection_id: connectionId,
    queue_item_id: queueItemId,
    signal,
    context: context || null,
  });

  // Update queue item
  await db.from('outreach_queue').update({
    signal,
    signal_context: context || null,
    status: action.status,
    reviewed_at: now.toISOString(),
  }).eq('id', queueItemId);

  // Update connection cache
  const connUpdate = {
    latest_signal: signal,
    latest_signal_at: now.toISOString(),
    cadence_due_at: cadenceDueAt,
  };
  if (signal === 'ARCHIVE') connUpdate.user_priority = 'never';
  await db.from('connections').update(connUpdate).eq('id', connectionId);
}
```

**contact.js — notes and signal history:**

```javascript
// Fetch and display notes
const { data: notes } = await db
  .from('contact_notes')
  .select('*')
  .eq('connection_id', contactId)
  .order('created_at', { ascending: false });

// Fetch signal history
const { data: signals } = await db
  .from('contact_signals')
  .select('signal, context, signaled_at')
  .eq('connection_id', contactId)
  .order('signaled_at', { ascending: false })
  .limit(5);
```

---

## Recommended Project Structure Changes

```
src/
├── database/
│   └── models.py            # MODIFY: ContactSignal, ContactNote classes;
│                            #         Connection: latest_signal, cadence_due_at;
│                            #         OutreachQueueItem: signal, signal_context, mini_key_factors;
│                            #         UserProfile: current_projects, goals_structured
├── services/
│   ├── dashboard_service.py # no change
│   └── signal_service.py    # NEW: SIGNAL_ACTIONS map + apply_signal() function
├── pipeline/
│   ├── daily_pipeline.py    # MODIFY: pass signal_context flag to Step 5/8
│   ├── queue_generator.py   # MODIFY: cadence exclusion Rule 6-7, priority boost,
│   │                        #         mini_key_factors computation
│   └── feedback_processor.py # MODIFY: analyze signal patterns, trigger signal rescore
├── llm/
│   └── scoring.py           # MODIFY: build_scoring_prompt() accepts signal context
└── sync/
    ├── push.py              # MODIFY: push contact_signals, contact_notes, new connection fields
    └── pull.py              # MODIFY: pull contact_signals, contact_notes, latest_signal updates

supabase/
├── functions/
│   └── draft/index.ts       # MODIFY: accept signal param, inject tone guidance
└── migrations/
    └── YYYYMMDD_intent_signals.sql  # NEW: contact_signals, contact_notes, new columns

pwa/js/
├── queue.js                 # MODIFY: signal selector replacing 3-button triage;
│                            #         enriched card (mini_key_factors, notes preview)
├── contact.js               # MODIFY: notes section, signal history panel
└── preferences.js           # MODIFY: user goals/projects editing form
```

---

## Architectural Patterns

### Pattern 1: Canonical Signal Map — One Definition, Two Implementations

**What:** Define the signal → action mapping once in `signal_service.py` (Python) and mirror it as a plain JS object in `queue.js`. All other code imports from these two locations.

**When to use:** Every path that acts on a signal value: queue generator, feedback processor, PWA writes, draft Edge Function.

**Trade-offs:** Slight duplication (Python + JS) but eliminates silent divergence where the PWA sets cadence to 30 days but the pipeline expects 14. The alternative (Edge Function as single source) adds latency to a write-only operation.

```python
# src/services/signal_service.py
from datetime import datetime, timedelta
from typing import Optional

SIGNAL_ACTIONS: dict[str, dict] = {
    "WARM_LEAD":    {"queue_status": "approved",       "cadence_days": 7,   "priority_boost": 10},
    "NURTURE":      {"queue_status": "pending_review", "cadence_days": 30,  "priority_boost": 0},
    "VALUE_DROP":   {"queue_status": "skipped",        "cadence_days": 90,  "priority_boost": -5},
    "SYNERGY":      {"queue_status": "approved",       "cadence_days": 14,  "priority_boost": 5},
    "RECONNECT":    {"queue_status": "approved",       "cadence_days": 14,  "priority_boost": 0},
    "FUTURE_PIVOT": {"queue_status": "pending_review", "cadence_days": 60,  "priority_boost": 0},
    "ARCHIVE":      {"queue_status": "skipped",        "cadence_days": None, "priority_boost": -100},
}

def apply_signal(signal: str, now: Optional[datetime] = None) -> dict:
    now = now or datetime.utcnow()
    action = SIGNAL_ACTIONS.get(signal, {})
    cadence_days = action.get("cadence_days")
    return {
        "queue_status": action.get("queue_status", "skipped"),
        "cadence_due_at": now + timedelta(days=cadence_days) if cadence_days else None,
        "priority_boost": action.get("priority_boost", 0),
    }
```

### Pattern 2: Denormalized Signal Cache on Connections

**What:** Cache `latest_signal`, `latest_signal_at`, and `cadence_due_at` on the `connections` row rather than querying `contact_signals` with MAX aggregation.

**When to use:** Everywhere that needs to know a contact's current signal: `is_contact_excluded()`, queue sort, queue card display in PWA.

**Trade-offs:** Slight write duplication (INSERT contact_signals + UPDATE connections) but eliminates a correlated subquery in `generate_daily_queue()`. Every path that inserts a signal MUST also update the connection cache — enforce this by routing all signal writes through `signal_service.py::apply_signal()` on the backend and through `applySignal()` in `queue.js` on the frontend.

**Update discipline:** The `apply_signal()` function in `signal_service.py` ALWAYS returns the connection update fields. Callers that skip the connection update create stale cache — this is a correctness bug, not a performance bug.

### Pattern 3: Signal Context as LLM Prompt Injection (Additive, Not Replacement)

**What:** When a contact has a signal with context, append it as an additional prompt section rather than rewriting the core scoring prompt.

**When to use:** `scoring.py::build_scoring_prompt()` for signal rescoring, `draft/index.ts::buildDraftPrompt()` for tone adaptation.

**Trade-offs:** Keeps the core prompt stable (existing calibration is preserved); signal context is additive. The risk of prompt injection from user-provided `signal_context` text is low (single-user tool, no malicious input).

```python
# In build_scoring_prompt() when signal context is available:
signal_section = ""
if connection.latest_signal and connection.latest_signal != "ARCHIVE":
    signal_section = f"""
TRIAGE SIGNAL (user's intent for this contact):
- Signal: {connection.latest_signal}
- Context: {signal_context or 'No additional context'}
Consider this when scoring Goal Alignment and Conversation Hooks dimensions.
"""
return f"{user_context}\n{contact_context}\n{signal_section}\nTASK: ..."
```

### Pattern 4: PostgREST Direct for Signal Writes (No Edge Function)

**What:** The PWA writes signals, notes, and queue updates directly through PostgREST with the anon key, not through an Edge Function.

**When to use:** Any write that does not require server-side secrets (OPENAI_API_KEY, SERVICE_ROLE_KEY for cross-table operations beyond anon key permissions).

**Why not an Edge Function for signals:** PostgREST already handles inserts to `user_feedback` and `user_preferences` from the PWA. Signal writes follow the identical pattern — one INSERT plus two UPDATEs, no AI, no secrets. An Edge Function would add cold-start latency (~200ms) to every signal tap.

**Supabase RLS note:** The new `contact_signals` and `contact_notes` tables need the same INSERT grant to the `anon` role as `user_feedback`. Add these to the migration.

---

## Integration Points

### Where New Features Touch Existing Code

| Feature | Existing Component | Integration Point |
|---------|--------------------|-------------------|
| 7 signals | `queue.js` | Replace 3-button triage; write to contact_signals + queue + connection via PostgREST |
| 7 signals | `outreach_queue` | New columns: signal, signal_context |
| 7 signals | `queue_generator.py` | New exclusion Rule 6 (cadence_due_at); Rule 7 (ARCHIVE); priority boost from latest_signal |
| Cadence re-queuing | `connections` table | cadence_due_at column; read in is_contact_excluded() |
| Cadence re-queuing | `queue_generator.py` | New exclusion Rule 6 |
| User goals | `user_profile` table | current_projects, goals_structured columns |
| User goals | `scoring.py` | build_scoring_prompt() extended to use goals_structured |
| User goals | `preferences.js` | Add goals editing form (POST to user_profile via PostgREST) |
| Contact notes | `contact.js` | Fetch from contact_notes, render below scoring rationale |
| Contact notes | `queue.js` | Show truncated note on queue card |
| Contact notes | `pull.py` | Pull notes created in PWA to local SQLite |
| Contact notes | `push.py` | Push notes created locally to Supabase |
| Signal rescoring | `feedback_processor.py` | Analyze signal patterns; identify rescore candidates; call score_connections_batch() |
| Signal rescoring | `scoring.py` | build_scoring_prompt() accepts optional signal context param |
| Signal rescoring | `daily_pipeline.py` | Step 8 extended (non-fatal) |
| Draft tone | `draft/index.ts` | Accept signal param; SIGNAL_TONE_MAP → tone guidance injected in buildDraftPrompt() |
| Queue enrichment | `queue_generator.py` | _compute_mini_key_factors() from score_reasoning JSON |
| Queue enrichment | `queue.js` | Display mini_key_factors and latest note snippet on cards |

### External Boundaries Unchanged

| Boundary | Status | Notes |
|----------|--------|-------|
| PostgREST API | No breaking changes | New tables and nullable columns; existing queries work as-is |
| Edge Function `action/` | Unchanged | Email triage tokens still work; signal triage is a PWA-only flow |
| Edge Function `feedback/` | Unchanged | Signal writes go direct to PostgREST, not through this function |
| Email digest | Unchanged | The digest links to PWA queue; signal selection happens in PWA |
| Supabase anon key permissions | Needs addition | New tables (contact_signals, contact_notes) need SELECT/INSERT for anon role |

---

## Suggested Build Order

Dependencies flow: schema → service layer → PWA UI → sync → pipeline integration → tone.

### Phase 1: Schema + Signal Service (foundation, no UI yet)

Everything downstream depends on this. No features are testable without it.

1. Write migration: `contact_signals`, `contact_notes` tables; new columns on `connections`, `outreach_queue`, `user_profile`; anon role grants
2. Update `database/models.py`: `ContactSignal`, `ContactNote` classes; field additions to existing models
3. Create `src/services/signal_service.py` with `SIGNAL_ACTIONS` map and `apply_signal()` function

### Phase 2: PWA Signal UI (primary UX change)

Builds on Phase 1 schema. Enables real signal data to accumulate before the pipeline learns from it.

1. `queue.js`: Signal selector (7 options + optional context field) replacing 3-button triage
2. `queue.js`: Write to contact_signals, outreach_queue, connections via PostgREST
3. `queue.js`: Display mini_key_factors on cards (initially from score_reasoning live, later from column)
4. `contact.js`: Fetch and display contact_notes and signal history

### Phase 3: User Goals Profile

Required before signal rescoring produces meaningful results. Also fixes sparse profile issues.

1. `preferences.js`: Add goals editing form (current_projects + goals_structured)
2. `scoring.py`: Extend `build_scoring_prompt()` to include `goals_structured` context

### Phase 4: Sync Updates

Makes PWA-created signals and notes available to the pipeline.

1. `pull.py`: Add contact_signals, contact_notes, latest_signal/cadence_due_at pull
2. `push.py`: Add contact_signals, contact_notes, new connection fields push

### Phase 5: Pipeline Signal Integration

Now that signals flow locally, teach the pipeline to act on them. Depends on Phases 1-4.

1. `queue_generator.py`: cadence exclusion Rule 6-7; signal priority boost; mini_key_factors computation (replaces live JS computation from Phase 2)
2. `feedback_processor.py`: signal pattern analysis; rescore candidate identification
3. `scoring.py`: accept signal context in prompt for rescore pass
4. `daily_pipeline.py`: thread signal_context flag into Step 8

### Phase 6: Draft Tone Adaptation

Smallest change, no dependencies beyond Phase 1. Can be shipped any time after Phase 2.

1. `draft/index.ts`: Accept `signal` parameter; add `SIGNAL_TONE_MAP` constant; inject tone guidance in `buildDraftPrompt()`

### Summary Table

| Phase | Focus | New Files | Modified Files |
|-------|-------|-----------|----------------|
| 1 | Schema + signal service | `signal_service.py`, migration SQL | `models.py` |
| 2 | PWA signal UI | — | `queue.js`, `contact.js` |
| 3 | User goals | — | `preferences.js`, `scoring.py` |
| 4 | Sync | — | `push.py`, `pull.py` |
| 5 | Pipeline integration | — | `queue_generator.py`, `feedback_processor.py`, `scoring.py`, `daily_pipeline.py` |
| 6 | Draft tone | — | `draft/index.ts` |

---

## Anti-Patterns

### Anti-Pattern 1: Storing Signal Logic in Multiple Places

**What people do:** Duplicate the signal → status → cadence mapping independently in `queue.js`, `queue_generator.py`, `feedback_processor.py`, and `draft/index.ts`.

**Why it's wrong:** When NURTURE cadence changes from 30 to 21 days, it must be updated in 4 places. More likely: they diverge silently. PWA sets 30 days, pipeline expects 21, contacts re-appear at the wrong time.

**Do this instead:** Define `SIGNAL_ACTIONS` once in `signal_service.py` (Python) and once as a JS const in `queue.js`. Every other file imports from one of these two canonical sources.

### Anti-Pattern 2: Using `user_feedback` Table for Signals

**What people do:** Store signals as `feedback_type = 'signal'` in the existing `user_feedback` table to avoid a new table.

**Why it's wrong:** `user_feedback` is queried by `feedback_processor.py` for approval rate analysis (skip/approve patterns). Mixing signal records changes those queries and corrupts the existing learning loop. Signal history also needs to be queryable per-contact (for the contact.js history view) without joining on feedback_type.

**Do this instead:** New `contact_signals` table. The schema change is one migration. Clean separation enables clean queries in both the pipeline and the PWA.

### Anti-Pattern 3: Rescoring on Every Signal (Real-Time)

**What people do:** When a user assigns WARM_LEAD, immediately POST to an Edge Function that calls OpenAI to rescore that contact.

**Why it's wrong:** Real-time rescoring adds 1-3 seconds of latency to every signal tap. The user has already made their intent judgment — the score does not need to reflect it instantly. The score is for queue prioritization (pipeline decides ordering), not for the user's triage decision.

**Do this instead:** Batch rescore in Step 8 of the daily pipeline. `feedback_processor.py` identifies candidates based on 30-day signal patterns. One focused `score_connections_batch()` call handles a small set. This is the existing weight-adjustment pattern extended.

### Anti-Pattern 4: Edge Function for Signal Writes

**What people do:** Create a `signal/index.ts` Edge Function to handle signal submissions from the PWA.

**Why it's wrong:** PostgREST already handles the identical write pattern for `user_feedback` and `user_preferences`. An Edge Function adds cold-start latency (~200ms) to every signal tap with no benefit — no secrets, no cross-table logic beyond what PostgREST can do with anon key grants.

**Do this instead:** Write signals directly to `contact_signals` via PostgREST. Reserve Edge Functions for operations that need OPENAI_API_KEY or SERVICE_ROLE_KEY access (drafts, action tokens).

### Anti-Pattern 5: Skipping the `cadence_due_at` Cache Column

**What people do:** Add cadence logic in `is_contact_excluded()` by querying `MAX(signaled_at)` from `contact_signals` and computing cadence on the fly.

**Why it's wrong:** Every contact evaluation in `generate_daily_queue()` would fire a correlated subquery against `contact_signals`. At 12,800+ contacts, that is thousands of subqueries per pipeline run. SQLite handles it but it adds meaningful latency with no benefit.

**Do this instead:** Store `cadence_due_at` on `connections` as a pre-computed cache. Update it atomically with the signal write. `is_contact_excluded()` reads a single column — O(1).

---

## Scaling Considerations

This is a single-user personal tool. Scaling is not a concern. The operational concern is LLM cost.

| Concern | Current | With v1.2 |
|---------|---------|-----------|
| LLM calls (scoring) | Batch on enrichment (~5-20 contacts/day) | +flagged NURTURE rescore candidates (small subset) |
| LLM calls (draft) | On-demand per queue item | Same; tone prompt addition is ~30 tokens overhead |
| Signal write volume | N/A | ~5-15 signal taps/day (single user, daily triage) |
| Contact note storage | connections.notes (never synced) | contact_notes rows: tiny, no concern |
| PostgREST query changes | Existing JOIN pattern | signal/note fetches are indexed by connection_id — fast |

The signal rescore batch in `feedback_processor.py` should be guarded by the same `min_queue_score` check used in enrichment planning — avoid rescoring contacts that will never reach the queue regardless.

---

## Sources

- `src/database/models.py` — all existing table definitions and field inventory
- `src/pipeline/daily_pipeline.py` — 10-step pipeline orchestration and step dependencies
- `src/pipeline/queue_generator.py` — exclusion rules, priority scoring, queue item generation
- `src/llm/scoring.py` — scoring prompt structure, weight override mechanism
- `src/pipeline/feedback_processor.py` — existing signal learning pattern to extend
- `src/sync/push.py`, `src/sync/pull.py` — bidirectional sync patterns and conflict resolution
- `supabase/functions/draft/index.ts` — buildDraftPrompt() structure for tone injection
- `supabase/functions/action/index.ts` — token-based email action pattern
- `supabase/functions/feedback/index.ts` — PostgREST-direct feedback write pattern
- `pwa/js/queue.js` — PostgREST query patterns, client-side sort, triage button structure
- `pwa/js/app.js` — Supabase client init, hash router, PostgREST access pattern
- `supabase/migrations/20260305000000_pwa_overhaul.sql` — migration pattern to follow
- `.planning/PROJECT.md` — v1.2 requirements, constraints, and current state

All architectural claims are grounded in direct source-code inspection. Confidence: HIGH.

---

*Architecture research for: Reconnect v1.2 Intent-Driven Triage*
*Researched: 2026-03-11*
