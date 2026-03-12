# Phase 9: Goals, Sync, and Pipeline Intelligence - Research

**Researched:** 2026-03-12
**Domain:** Python pipeline intelligence, LLM prompt engineering, scoring weight feedback loops, PWA vanilla JS
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Goals profile UI**
- Goals section lives at the top of the existing Preferences page in the PWA
- Single free-form text area for stable networking objectives ("What are you focused on?")
- Goals change infrequently — these are broad career/networking directions
- Saves to `user_profile.current_projects` (text field, already exists from Phase 7 migration)
- `goals_structured` JSON column reserved for future use (lookouts feature)

**Goals in scoring prompt**
- Both `current_projects` (new goals text) and existing `goals`/`interests` fields feed the LLM scoring prompt
- Goals text influences the `goal_alignment` dimension (0-25 points) of the scoring rubric
- When goals change in the PWA, mark all scored contacts for rescoring on the next pipeline run
- Rescoring after goals change can be batched over multiple days to manage LLM credit usage

**Cadence re-queuing**
- Contacts with expired cadence (`signal_assigned_at + cadence_days <= today`) automatically re-enter the daily queue
- Age-based eligibility per Phase 7 decision — not absolute timestamps
- ARCHIVE contacts never re-appear (user_priority = "never" already handled by is_contact_excluded)

**Signal-informed rescoring**
- Feedback processor evolves to analyze signal triage patterns (not just skip/approval)
- Safety guards: 25-action minimum over 14 days before any weight adjustment
- ±40% multiplier cap on scoring dimension weights (multiplier range: 0.6–1.4)
- Weight history logging for auditability (drift tracking in DB)

**Bidirectional sync**
- Signals and notes already sync bidirectionally (Phase 8 plan 04 delivered this)
- Phase 9 adds: pull sync for `user_profile` goals fields (current_projects) from cloud to local
- Pipeline-computed fields (mini_key_factors, latest_signal cache) continue pushing to cloud via existing push sync
- Goals rescore flag needs to reach the pipeline — either via a preference row or a field on user_profile

### Claude's Discretion
- Cadence re-queuing as a new pipeline step vs integrated into existing queue generation
- Exact prompt structure for goals in scoring
- Lookout card field structure in goals_structured JSON (for future phase)
- Weight drift visualization on preferences page
- Rescore batching strategy (all at once vs spread over days)
- Feedback processor architecture changes (extend existing vs replace)

### Deferred Ideas (OUT OF SCOPE)
- Lookouts feature (active requests matching/flagging)
- Enrichment targeting based on active criteria
- Network search/query
- Signal analytics on dashboard (distribution, trends) — v1.3+ (SIG-09)
- Per-contact cadence override — v1.3+ (CAD-05)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERS-01 | User can define current projects and interests via a goals profile | Goals text area on Preferences page; saves to `user_profile.current_projects` via PostgREST direct write |
| PERS-02 | User goals included in LLM scoring prompt for more relevant WARM_LEAD identification | Extend `build_scoring_prompt()` to include `current_projects` in user context block alongside existing `goals` and `interests` fields |
| PERS-03 | Signal triage patterns adjust scoring dimension weights over time | Evolve `_derive_weight_adjustments()` in feedback_processor.py to analyze ContactSignal patterns from `contact_signals` table |
| PERS-04 | Rescoring has safety guards (25-action minimum, ±40% multiplier cap, drift logging) | Add guards to `_derive_weight_adjustments()`; store weight history as a new `pref_type="weight_history"` row; clamp multiplier before writing |
| CAD-02 | Contacts with expired cadence automatically re-enter the daily queue | Query `connections` where `cadence_due_at <= today` AND `user_priority != 'never'` and no active queue item; inject into `generate_daily_queue()` candidates |
| CAD-03 | Re-queuing uses age-based eligibility to prevent cohort saturation | Cap daily cadence re-queued contacts via a per-run volume limit; age-based check uses `cadence_due_at` (computed as `signal_assigned_at + cadence_days` at signal application time) |
</phase_requirements>

---

## Summary

Phase 9 has four distinct delivery areas that share minimal code but coordinate through the daily pipeline orchestration in `daily_pipeline.py`. All the hard infrastructure — models, sync machinery, signal service, scoring weight system — was built in Phases 7 and 8. Phase 9 primarily *wires* things together and *extends* existing behavior rather than building new subsystems.

The largest surface area is the feedback processor evolution. The current `process_feedback()` in `feedback_processor.py` analyzes `OutreachQueueItem` skip/approval status. It must be extended to also read `ContactSignal` records (the new Phase 8 signal assignments) and map signal triage patterns (e.g., lots of ARCHIVE vs lots of WARM_LEAD) to weight adjustments with safety guards. The minimum-action threshold needs to change from 10 (current) to 25-over-14-days (locked decision).

Cadence re-queuing requires adding a query for `cadence_expired` candidates in `generate_daily_queue()`. The `cadence_due_at` field on `Connection` already holds the computed due date (set by `signal_service.apply_signal()`), so the check is simple: `cadence_due_at <= today AND user_priority != 'never' AND NOT already in queue`. The daily volume cap for re-queued contacts is at Claude's discretion — a reasonable default is capping cadence re-queues at the same `daily_queue_size` limit, letting them compete with fresh scored candidates rather than running a separate quota.

The goals sync and prompt changes are straightforward: add `current_projects` to the pull sync's `user_profile` fetch, extend `build_scoring_prompt()` with a goals block, and add a rescore-trigger mechanism (a `UserPreference` row with `pref_type="rescore_trigger"` is the least invasive path, avoidable of any schema migration).

**Primary recommendation:** Deliver in four plans: (1) Goals UI + prompt + pull sync, (2) Cadence re-queuing, (3) Signal-informed feedback processor with safety guards, (4) Weight drift display + pipeline wiring. This ordering lets each plan be tested independently.

---

## Standard Stack

### Core (all pre-existing in this project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLModel + SQLAlchemy | 0.0.14+ / 2.0+ | ORM, query building, session management | Established in project — do not change |
| OpenAI Python SDK | 1.10+ | LLM scoring prompt calls | Already used in scoring.py |
| Supabase PostgREST (JS) | via `@supabase/supabase-js` in CDN | PWA direct DB writes | Established pattern — no new Edge Function |
| pytest + pytest-mock | 7.4+ / 3.12+ | Unit tests | Existing test suite pattern |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `collections.Counter` | stdlib | Counting signal pattern frequencies | Already used in feedback_processor.py |
| `datetime.timedelta` | stdlib | Cadence expiry arithmetic | Used in signal_service.py |

### No New Dependencies
Phase 9 adds no new Python packages. All capabilities exist in the current stack.

**Installation:** none required.

---

## Architecture Patterns

### Recommended Project Structure

No new directories needed. All changes land in existing modules:

```
src/
├── llm/
│   └── scoring.py           # extend build_scoring_prompt() — add current_projects
├── pipeline/
│   ├── daily_pipeline.py    # wire cadence step, ensure pull before scoring
│   ├── feedback_processor.py # evolve _derive_weight_adjustments() for signals
│   └── queue_generator.py   # add cadence-expired candidates to generate_daily_queue()
├── sync/
│   └── pull.py              # add user_profile.current_projects pull
pwa/js/
└── preferences.js           # add goals text area section at top
```

### Pattern 1: Extending `generate_daily_queue()` for Cadence Re-queuing (CAD-02, CAD-03)

**What:** Before the main scored-contacts query, query for contacts whose `cadence_due_at <= today` (and who pass exclusion checks). Inject these as additional candidates. The existing `is_contact_excluded()` already handles ARCHIVE (user_priority="never") so those never appear.

**When to use:** Every daily pipeline run.

**Key insight on age-based eligibility (CAD-03):** The `cadence_due_at` field is computed at signal-assignment time as `now + cadence_days`. This is the "age-based" approach — eligibility is based on how much time has elapsed since the signal was assigned, not on a wall-clock schedule. This prevents cohort saturation because cadence timers start at assignment, not at a global batch time.

**Volume cap recommendation (Claude's discretion):** Cadence re-queued contacts should compete for the same `daily_queue_size` slots as fresh candidates, with a soft cap of 50% of the queue maximum (`limit // 2`) reserved for cadence re-queues to prevent stale contacts from crowding out fresh high-scorers.

**Example:**
```python
# Source: pattern derived from existing queue_generator.py structure
def _get_cadence_expired_candidates(
    session: Session,
    limit: int,
) -> list[Connection]:
    """Get contacts whose cadence has expired and are eligible for re-queuing."""
    now = datetime.utcnow()
    return session.exec(
        select(Connection)
        .where(Connection.cadence_due_at.isnot(None))
        .where(Connection.cadence_due_at <= now)
        .where(Connection.user_priority != "never")
        .where(Connection.reconnect_score.isnot(None))
        .order_by(Connection.reconnect_score.desc())
        .limit(limit)
    ).all()
```

This function is called inside `generate_daily_queue()` before the main scored-contacts query. The resulting cadence candidates are merged into `merged` ahead of regular scored contacts (similar to how `always_contacts` are prepended today), but they still pass through `is_contact_excluded()` which blocks anything with an active queue item.

**ARCHIVE protection:** `is_contact_excluded()` in queue_generator.py line 101 already checks `user_priority == "never"`. ARCHIVE signal sets `user_priority = "never"` in signal_service.py line 147. No new guard needed.

### Pattern 2: Goals in Scoring Prompt (PERS-01, PERS-02)

**What:** Extend `build_scoring_prompt()` in scoring.py to include `user_profile.current_projects` as an additional goals block. The existing prompt already includes `user_profile.goals` and `user_profile.interests` on lines 99-100.

**When to use:** Every `score_connection()` call.

**Example:**
```python
# Source: scoring.py lines 94-101, extended pattern
user_context = f"""USER'S PROFILE:
- Name: {user_profile.name or 'Not specified'}
- Current role: {user_profile.current_role or 'Not specified'}
- Company: {user_profile.company or 'Not specified'}
- Industry: {user_profile.industry or 'Not specified'}
- Networking goals: {user_profile.goals or 'General networking'}
- Interests/topics: {user_profile.interests or 'Not specified'}
- Current projects & focus: {user_profile.current_projects or 'Not specified'}
"""
```

The `goal_alignment` dimension in the rubric (lines 21-28 of scoring.py) will naturally use this richer context to score more accurately. The system prompt does not need to change — it already instructs the LLM to evaluate "how directly relevant is this contact to the user's stated networking goals?"

**Goals change rescoring trigger (locked decision):** When the user saves updated goals text in the PWA, the PWA writes to `user_profile.current_projects`. The pipeline detects a change by comparing `user_profile.updated_at` to `Connection.scored_at`. If `user_profile.updated_at > scored_at`, the contact is eligible for rescoring. This avoids a separate flag field and requires no migration.

**Alternative rescore trigger:** Store a `UserPreference` row `pref_type="rescore_trigger", pref_key="goals_updated_at", pref_value=<timestamp>`. Pipeline compares this timestamp against each contact's `scored_at`. This is slightly more explicit and easier to reset. Recommend this approach — it does not require touching `user_profile.updated_at` logic.

**Batching (Claude's discretion):** Rescore at most N contacts per pipeline run where N = `min(10, total_needing_rescore)`. This spreads LLM credit usage over days. Track progress with the `UserPreference` rescore trigger row (delete it when all contacts are rescored).

### Pattern 3: Signal-Informed Feedback Processor (PERS-03, PERS-04)

**What:** Extend `_derive_weight_adjustments()` in feedback_processor.py to analyze `ContactSignal` patterns in addition to the existing skip/approval OutreachQueueItem analysis.

**Current state (from code review):**
- `_analyze_skip_patterns()` looks at `OutreachQueueItem` with `status="skipped"` in the last 30 days
- `_analyze_approval_patterns()` looks at `OutreachQueueItem` with `status in ["approved", "sent"]`
- `_derive_weight_adjustments()` currently requires 10 total actions (line 179) — this must change to 25-over-14-days
- `_upsert_scoring_weight()` writes to `UserPreference` with `pref_type="scoring_weight"`

**New signal analysis function:**
```python
def _analyze_signal_patterns(days: int = 14) -> dict:
    """Analyze ContactSignal assignments for weight adjustment hints.

    Returns signal frequency data from the last N days.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    with get_session() as session:
        signals = session.exec(
            select(ContactSignal)
            .where(ContactSignal.assigned_at >= cutoff)
            .where(ContactSignal.assigned_by == "user")  # user-driven only
        ).all()

    signal_counts = Counter(s.signal for s in signals)
    total = len(signals)
    return {
        "total_analyzed": total,
        "signal_counts": dict(signal_counts),
        "dominant_signal": signal_counts.most_common(1)[0][0] if signal_counts else None,
    }
```

**Safety guard implementation:**
```python
def _derive_weight_adjustments(skip_insights, approval_insights, signal_insights=None) -> dict[str, float]:
    """Derive weight adjustments. Returns empty dict if safety guard not met."""
    adjustments = {}

    # SAFETY GUARD: 25 total actions over 14 days minimum
    signal_total = (signal_insights or {}).get("total_analyzed", 0)
    approval_total = approval_insights.get("total_analyzed", 0)
    skip_total = skip_insights.get("total_analyzed", 0)
    total_actions = signal_total + approval_total + skip_total

    if total_actions < 25:
        return adjustments  # Not enough data — locked decision

    # ... derive adjustments ...

    # SAFETY GUARD: clamp all multipliers to [0.6, 1.4]
    for dim in adjustments:
        adjustments[dim] = max(0.6, min(1.4, adjustments[dim]))

    return adjustments
```

**Signal pattern → weight mapping (Claude's discretion):**
- High WARM_LEAD rate (>40% of signals) → boost `goal_alignment` (user is finding goal-aligned contacts valuable)
- High ARCHIVE rate (>30% of signals) → reduce `conversation_hooks` (user is archiving contacts despite outreach hooks)
- High FUTURE_PIVOT rate (>40% of signals) → reduce `mutual_value` (contacts are not immediately valuable)
- High NURTURE rate (>40% of signals) → boost `network_reach` (user values long-term connectors)

**Weight history logging (PERS-04):** Log each adjustment as a `UserPreference` row with `pref_type="weight_history"` so it is append-only (never upserted). Columns: `pref_key=dimension_name`, `pref_value=new_multiplier`, `created_at=timestamp`. This means the preferences page can show the full history without a schema migration.

### Pattern 4: User Profile Goals Pull Sync

**What:** Add `current_projects` field to the `user_profile` pull in `pull_from_cloud()`.

**Current state (from code review):** `pull_from_cloud()` does NOT currently pull `UserProfile`. The push sync in `push_to_cloud()` (step 1, line 126) pushes the full UserProfile as a singleton upsert. But there is no corresponding pull of `user_profile` in pull.py. The pull sync fetches Connection fields (latest_signal, cadence_due_at) but not UserProfile.

**Required change:** Add a new section to `pull_from_cloud()` that fetches `user_profile` id=1 from cloud and updates the local `current_projects` field if the cloud value is newer (based on `updated_at`):

```python
# In pull_from_cloud(), add after existing sections:
# 8. Pull UserProfile goals fields (current_projects, goals_structured)
with Session(cloud_engine) as cloud_session:
    cloud_profile = cloud_session.get(UserProfile, 1)
    if cloud_profile:
        profile_data = {
            "current_projects": cloud_profile.current_projects,
            "goals_structured": cloud_profile.goals_structured,
            "updated_at": cloud_profile.updated_at,
        }

with Session(local_engine) as local_session:
    local_profile = local_session.get(UserProfile, 1)
    if local_profile and profile_data:
        # cloud wins for user-edited fields if cloud is newer
        cloud_ts = profile_data.get("updated_at")
        if cloud_ts and (local_profile.updated_at is None or cloud_ts > local_profile.updated_at):
            local_profile.current_projects = profile_data["current_projects"]
            local_profile.goals_structured = profile_data["goals_structured"]
            local_profile.updated_at = cloud_ts
            local_session.add(local_profile)
            stats["user_profile_updated"] = 1
```

**Pipeline ordering:** The pull sync runs as part of `run_sync()` at the end of the pipeline (step 11). To ensure goals reach the pipeline BEFORE scoring on the next run, the pull must happen at the START of the next pipeline run. The `run_sync()` call currently runs at the end (line 292-313 of daily_pipeline.py). To use pulled goals for same-day scoring, a lightweight pull-only call should run before step 3 (prescore). The simplest approach: call `pull_from_cloud()` as the first step in `run_daily_pipeline()` when Supabase is configured.

### Pattern 5: Goals UI on Preferences Page (PERS-01)

**What:** Add a goals text area section at the top of `renderPreferences()` in `pwa/js/preferences.js`. Uses the established PostgREST direct write pattern.

**Fetch user_profile.current_projects:**
```javascript
// Add at top of renderPreferences(), before existing prefs fetch:
const { data: userProfile } = await db
  .from('user_profile')
  .select('id, current_projects, updated_at')
  .eq('id', 1)
  .single();
```

**Save goals on blur or button click:**
```javascript
async function saveGoals(text) {
  const { error } = await db
    .from('user_profile')
    .update({ current_projects: text, updated_at: new Date().toISOString() })
    .eq('id', 1);

  if (!error) {
    showToast('Goals saved');
  }
}
```

**UI structure (goals section renders above scoring weights):**
```html
<div class="pref-group">
  <h3>Your Networking Goals</h3>
  <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">
    What kind of reconnections are valuable to you right now? This text
    guides which contacts score as WARM_LEAD.
  </p>
  <textarea id="goals-input"
    style="width: 100%; min-height: 80px; padding: 8px; font-size: 14px;"
    placeholder="e.g. Exploring product leadership roles in fintech. Interested in AI/ML applications..."
  >${escapeHtml(userProfile?.current_projects || '')}</textarea>
  <button class="btn btn-primary" style="margin-top: 8px;" onclick="saveGoals(document.getElementById('goals-input').value)">
    Save Goals
  </button>
</div>
```

### Anti-Patterns to Avoid

- **Modifying SIGNAL_ACTIONS:** The canonical signal definitions in `signal_service.py` are locked. Never duplicate cadence_days values in queue_generator.py — always import from SIGNAL_ACTIONS.
- **Schema migration for rescore trigger:** Avoid adding a new column to `user_profile` or `connections` for the rescore trigger. A `UserPreference` row is sufficient and migration-free.
- **Applying weight adjustments below 25 actions:** The safety guard is a locked decision. The current code's 10-action threshold in feedback_processor.py must be updated to 25-over-14-days.
- **Querying cadence using `signal_assigned_at` directly:** The `cadence_due_at` on `Connection` is the correct field — it was computed as `assigned_at + cadence_days` when the signal was applied. Do NOT re-derive cadence in queue_generator.py; trust the stored `cadence_due_at`.
- **Pulling goals from cloud in push.py:** Goals flow cloud → local (pull direction). The push already handles user_profile (push direction). Do not create a circular update loop by updating `updated_at` in both directions.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cadence expiry query | Custom date arithmetic on signal history | Query `Connection.cadence_due_at <= now` | `cadence_due_at` is pre-computed by signal_service; re-derivation risks inconsistency |
| ARCHIVE contact filtering | New exclusion rule in cadence logic | Existing `is_contact_excluded()` which checks `user_priority == "never"` | Already implemented and tested; adding a parallel check creates drift risk |
| Weight storage | New DB table for weight history | `UserPreference` rows with `pref_type="weight_history"` | Append-only rows with `created_at` give full history without migration |
| Rescore detection | Polling job or webhook | `UserPreference` row as a trigger flag | Zero infrastructure, pipeline-native, idempotent |
| PWA goals save | Edge Function | PostgREST direct write to `user_profile` | Established pattern (same as signal writes, note writes, user_feedback) |

---

## Common Pitfalls

### Pitfall 1: Pull sync runs AFTER scoring in the same pipeline run

**What goes wrong:** User saves new goals in PWA. Pipeline runs that evening. Pull sync at the END of the pipeline fetches the new goals — but scoring already ran at step 5 with the OLD goals. The next day's pipeline uses the new goals.

**Why it happens:** Current pipeline ordering: prescore (step 3) → enrich (step 4) → score (step 5) → ... → sync (step 11). Pull happens inside sync.

**How to avoid:** Call `pull_from_cloud()` as the FIRST step of `run_daily_pipeline()` when Supabase is configured. This is a one-line addition before step 1. Alternatively, accept that goals changes take effect on the NEXT day's run (document this as expected behavior).

**Recommendation:** Accept the one-day delay as expected behavior (goals are "stable networking objectives" per locked decision — a one-day delay is fine). Add a comment in the code explaining the delay.

### Pitfall 2: Cadence re-queuing fills the entire queue with stale contacts

**What goes wrong:** After a period of high-signal activity, dozens of contacts reach `cadence_due_at` on the same day. All of them meet the inclusion criteria. The daily queue becomes 100% cadence contacts, crowding out fresh high-scorers.

**Why it happens:** No volume cap on cadence re-queues.

**How to avoid:** Add a soft cap: cadence re-queued contacts fill at most `limit // 2` slots. Fresh scored candidates get the remaining `limit // 2` minimum. Cadence contacts still pass through `is_contact_excluded()` and the company diversification check.

**Warning signs:** `stats["cadence_added"]` > `limit * 0.5` in queue generation stats.

### Pitfall 3: Weight drift from ARCHIVE-heavy periods over-punishes conversation_hooks

**What goes wrong:** User archives many contacts during a cleanup session (a burst of ARCHIVE signals in one day). The feedback processor sees high ARCHIVE rate and repeatedly reduces `conversation_hooks` multiplier. Each day's pipeline run pushes the multiplier lower, eventually hitting 0.6.

**Why it happens:** The 14-day window with 25-action minimum doesn't distinguish between a legitimate pattern and a one-time cleanup burst.

**How to avoid:** Already addressed by the ±40% cap (locked decision). The multiplier floor of 0.6 prevents extreme drift. Additionally, the `_analyze_signal_patterns()` function should weight ARCHIVE signals differently — ARCHIVE says nothing about conversation hooks quality; it means the user decided a contact is permanently irrelevant. Map ARCHIVE to no weight adjustment (or a small `goal_alignment` reduction only).

**Warning signs:** `goal_alignment` multiplier reaches 0.6 or 1.4 within 2 weeks of first use.

### Pitfall 4: Goals text in the scoring prompt makes the prompt too long

**What goes wrong:** User writes a long goals paragraph. The scoring prompt already includes enrichment data, skills, activity log, career trajectory, and engagement history. Adding a long goals block pushes the prompt over the 600 max_tokens budget for the response.

**Why it happens:** `max_tokens=600` (line 326 of scoring.py) caps the LLM response, but prompt token count is uncapped.

**How to avoid:** Truncate `current_projects` at 500 characters in the prompt. The goals text is user-facing and likely short, but defensive truncation prevents issues.

```python
current_projects_display = (user_profile.current_projects or '')[:500]
user_context += f"- Current projects & focus: {current_projects_display or 'Not specified'}\n"
```

### Pitfall 5: UserProfile pull sync creates an update loop

**What goes wrong:** Pipeline pulls cloud user_profile, sets local `updated_at = cloud_updated_at`. Push sync then sees the updated_at changed and pushes the user_profile back to cloud. This creates unnecessary churn.

**Why it happens:** Push sync always does a full upsert of UserProfile (step 1, push.py line 126-132) without a timestamp gate.

**How to avoid:** The pull should NOT update `updated_at` when copying cloud goals to local. Set only `current_projects` and `goals_structured`, leaving `updated_at` unchanged. The pipeline's own scoring/processing updates will naturally bump `updated_at` only when something real changes.

---

## Code Examples

Verified patterns from existing codebase:

### Cadence query pattern
```python
# Source: signal_service.py apply_signal() — cadence_due_at is stored at assignment time
# This means the re-queue check is just: cadence_due_at <= now
from datetime import datetime
from sqlmodel import select

with get_session() as session:
    now = datetime.utcnow()
    expired = session.exec(
        select(Connection)
        .where(Connection.cadence_due_at.isnot(None))
        .where(Connection.cadence_due_at <= now)
        .where(Connection.user_priority != "never")  # ARCHIVE protection
        .where(Connection.reconnect_score.isnot(None)  # scored contacts only
        .order_by(Connection.reconnect_score.desc())
        .limit(limit)
    ).all()
```

### UserPreference write pattern (weight history log)
```python
# Source: feedback_processor.py _upsert_scoring_weight() — adapted for history log
# History rows are INSERT-only, never upserted
def _log_weight_history(dimension: str, multiplier: float, reason: str) -> None:
    with get_session() as session:
        history_row = UserPreference(
            pref_type="weight_history",  # distinct from scoring_weight
            pref_key=dimension,
            pref_value=str(multiplier),
            # created_at auto-populates as timestamp
        )
        session.add(history_row)
        session.commit()
```

### PostgREST direct write for user_profile (PWA)
```javascript
// Source: established project pattern (same as signal writes in Phase 8)
const { error } = await db
  .from('user_profile')
  .update({
    current_projects: goalsText,
    updated_at: new Date().toISOString()
  })
  .eq('id', 1);
```

### Scoring prompt extension
```python
# Source: scoring.py build_scoring_prompt() lines 94-101 — extend this block
user_context = f"""USER'S PROFILE:
- Name: {user_profile.name or 'Not specified'}
- Current role: {user_profile.current_role or 'Not specified'}
- Company: {user_profile.company or 'Not specified'}
- Industry: {user_profile.industry or 'Not specified'}
- Networking goals: {user_profile.goals or 'General networking'}
- Interests/topics: {user_profile.interests or 'Not specified'}
- Current projects & focus: {(user_profile.current_projects or '')[:500] or 'Not specified'}
"""
```

### Signal pattern analysis
```python
# Source: feedback_processor.py structure — new function following same pattern
from collections import Counter
from datetime import datetime, timedelta

def _analyze_signal_patterns(days: int = 14) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)
    with get_session() as session:
        from sqlmodel import select
        from src.database.models import ContactSignal
        signals = session.exec(
            select(ContactSignal)
            .where(ContactSignal.assigned_at >= cutoff)
            .where(ContactSignal.assigned_by == "user")
        ).all()
    total = len(signals)
    signal_counts = Counter(s.signal for s in signals)
    return {
        "total_analyzed": total,
        "signal_counts": dict(signal_counts),
    }
```

### Safety-guarded weight derivation (updated threshold)
```python
# Source: feedback_processor.py _derive_weight_adjustments() — updated minimum
MIN_ACTIONS_FOR_ADJUSTMENT = 25  # locked decision (was 10)
MAX_MULTIPLIER = 1.4
MIN_MULTIPLIER = 0.6

def _derive_weight_adjustments(skip_insights, approval_insights, signal_insights=None) -> dict[str, float]:
    adjustments = {}
    signal_total = (signal_insights or {}).get("total_analyzed", 0)
    total_actions = (
        approval_insights.get("total_analyzed", 0)
        + skip_insights.get("total_analyzed", 0)
        + signal_total
    )

    if total_actions < MIN_ACTIONS_FOR_ADJUSTMENT:
        return adjustments

    # ... signal pattern → weight logic ...

    # Clamp all values
    for dim in adjustments:
        adjustments[dim] = max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, adjustments[dim]))

    return adjustments
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `goals` field only in scoring | `goals` + `interests` + new `current_projects` | Phase 9 | `goal_alignment` dimension has richer context |
| Feedback from skip/approve only | Feedback from signals + skip/approve | Phase 9 | More behavioral signal to weight from |
| No automatic cadence re-queuing | `cadence_due_at <= today` triggers re-entry | Phase 9 | Contacts re-appear automatically after cadence |
| 10-action threshold for weight adjustment | 25-action / 14-day threshold | Phase 9 | Reduces noise-driven weight drift |

**Deprecated/outdated:**
- `_derive_weight_adjustments()` 10-action threshold (line 179 of feedback_processor.py): must be updated to 25
- `signal_service.py NOT wired into daily_pipeline.py` (Phase 7 decision): Phase 9 wires it in for cadence re-queuing

---

## Open Questions

1. **Rescore trigger timing**
   - What we know: User saves goals in PWA → cloud updated; pipeline runs next morning → pulls goals; scoring runs with new goals
   - What's unclear: Does the pull happen before scoring in the same run? Current pipeline ordering says no.
   - Recommendation: Document one-day delay as expected behavior (goals are stable, not urgent). Add comment in daily_pipeline.py.

2. **Volume cap for cadence re-queues**
   - What we know: No cap currently; could fill entire queue with expired contacts
   - What's unclear: What's the right ratio of cadence vs fresh contacts?
   - Recommendation: Cap at `limit // 2` cadence contacts. This is at Claude's discretion per CONTEXT.md.

3. **Signal → weight dimension mapping**
   - What we know: WARM_LEAD, ARCHIVE, NURTURE, FUTURE_PIVOT are the likely influencers; ±40% cap protects against extremes
   - What's unclear: Exact mapping rules (Claude's discretion)
   - Recommendation: Use simple signal-frequency thresholds (>40% of one type triggers an adjustment). Log every adjustment with reason string.

4. **Preferences page weight history display**
   - What we know: Weight history is logged as `pref_type="weight_history"` rows; preferences page currently shows `pref_type="scoring_weight"` rows
   - What's unclear: How much history to show? How to visualize?
   - Recommendation: Show last 10 entries per dimension in a collapsed section. Simple table: dimension, value, date. This is at Claude's discretion.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ with pytest-mock 3.12+ |
| Config file | `pyproject.toml` (no separate pytest.ini) |
| Quick run command | `pytest tests/test_phase9_goals_pipeline.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERS-01 | `user_profile.current_projects` field exists and is Text | unit | `pytest tests/test_phase9_goals_pipeline.py::TestGoalsModel -x` | Wave 0 |
| PERS-02 | `build_scoring_prompt()` includes `current_projects` text | unit | `pytest tests/test_phase9_goals_pipeline.py::TestScoringPrompt -x` | Wave 0 |
| PERS-03 | `process_feedback()` reads ContactSignal records | unit | `pytest tests/test_phase9_goals_pipeline.py::TestSignalFeedback -x` | Wave 0 |
| PERS-04 | Safety guard blocks adjustment below 25 actions | unit | `pytest tests/test_phase9_goals_pipeline.py::TestSafetyGuards -x` | Wave 0 |
| PERS-04 | Multiplier clamps to [0.6, 1.4] | unit | `pytest tests/test_phase9_goals_pipeline.py::TestSafetyGuards -x` | Wave 0 |
| PERS-04 | Weight history rows written with pref_type="weight_history" | unit | `pytest tests/test_phase9_goals_pipeline.py::TestWeightHistory -x` | Wave 0 |
| CAD-02 | Contacts with cadence_due_at <= today enter queue | unit | `pytest tests/test_phase9_goals_pipeline.py::TestCadenceRequeue -x` | Wave 0 |
| CAD-03 | ARCHIVE contacts never enter cadence queue | unit | `pytest tests/test_phase9_goals_pipeline.py::TestCadenceRequeue::test_archive_never_requeued -x` | Wave 0 |
| CAD-03 | Cadence due_at uses stored field, not re-derived from signals | unit | `pytest tests/test_phase9_goals_pipeline.py::TestCadenceRequeue::test_uses_cadence_due_at -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_phase9_goals_pipeline.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase9_goals_pipeline.py` — covers all PERS-01 through PERS-04, CAD-02, CAD-03
- [ ] `tests/conftest.py` exists and has `mock_settings` fixture — already present, no change needed

*(No new framework installation required — pytest, pytest-mock already in pyproject.toml `[dev]` dependencies)*

---

## Sources

### Primary (HIGH confidence)
- Direct source code inspection: `src/llm/scoring.py` — full scoring system, weight override infrastructure
- Direct source code inspection: `src/pipeline/feedback_processor.py` — current feedback analysis and weight storage
- Direct source code inspection: `src/pipeline/queue_generator.py` — exclusion rules, queue generation logic
- Direct source code inspection: `src/services/signal_service.py` — SIGNAL_ACTIONS, cadence_due_at computation
- Direct source code inspection: `src/sync/pull.py` — pull sync sections, confirmed no user_profile pull currently exists
- Direct source code inspection: `src/sync/push.py` — CONNECTION_SYNC_FIELDS, user_profile push
- Direct source code inspection: `src/database/models.py` — confirmed `current_projects` and `goals_structured` already on UserProfile
- Direct source code inspection: `pwa/js/preferences.js` — existing structure for injection point
- Direct source code inspection: `tests/test_phase7_signal_foundation.py` — test patterns for this codebase
- Direct source code inspection: `supabase/migrations/20260311000000_signal_foundation.sql` — confirmed cloud schema has `current_projects`, `cadence_due_at`
- `.planning/phases/09-goals-sync-and-pipeline-intelligence/09-CONTEXT.md` — locked decisions

### Secondary (MEDIUM confidence)
- Reasoning from existing code patterns about `updated_at` sync loop pitfall — no test exists yet but pattern is clear from push/pull code structure

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are pre-existing, confirmed in pyproject.toml and import statements
- Architecture: HIGH — derived directly from source code inspection of all relevant files
- Pitfalls: HIGH — derived from reading the actual code paths that would be affected
- Test map: HIGH — consistent with test_phase7 and test_phase8 patterns in same repo

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable codebase, no fast-moving dependencies)
