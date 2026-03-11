# Pitfalls Research

**Domain:** Adding intent-based triage signals, cadence scheduling, personalization, and contact notes to existing networking tool (v1.2 Intent-Driven Triage)
**Researched:** 2026-03-11
**Confidence:** HIGH for migration and sync patterns (code reviewed, official docs verified); MEDIUM for feedback loop dynamics (multiple research sources, no single authoritative reference for this exact use case); HIGH for PWA state management patterns (code reviewed, MDN + community patterns verified)

---

## Critical Pitfalls

Mistakes that cause rewrites, silent data corruption, or hard-to-reverse behavioral regressions.

---

### Pitfall 1: Signal Migration Leaves Orphaned "Skipped" Items That Block Re-Queue Forever

**What goes wrong:**
The existing system stores `status = "skipped"` for both "user consciously chose not to reach out" (old Skip) and "user wants to see this later" (old Snooze). The queue generator's exclusion logic in `queue_generator.py` blocks re-queuing of contacts whose most-recent queue item has `status = "skipped"` within the `skip_cooldown_days` window (default: 7 days).

When 7 signals replace the three existing actions, every existing "skipped" item becomes ambiguous: was this a Skip (which might map to ARCHIVE or VALUE_DROP) or a Snooze (which maps to NURTURE or RECONNECT with cadence re-queue)? If migration simply leaves old `status = "skipped"` rows untouched, the cadence re-queue logic for NURTURE and RECONNECT contacts will skip them during the cooldown window — even though they were "snoozed" and should be re-queued.

**Why it happens:**
The migration adds new signal fields to the model but does not backfill the intent of old "skipped" items. The new queue generator checks for the latest skipped item's timestamp, not whether the skip was intent-driven. Old snooze entries (stored as `status = "skipped", skip_reason = "Snoozed via email (3 day cooldown)"`) fall into the same bucket as deliberate skips.

**How to avoid:**
Before adding signal logic to the queue generator, write a one-time migration that categorizes existing skipped items:

```python
# Pseudocode for migration
for item in old_skipped_items:
    if "snooze" in (item.skip_reason or "").lower():
        item.triage_signal = "RECONNECT"   # re-queueable
        item.skip_reason = "Migrated from snooze"
    else:
        item.triage_signal = "ARCHIVE"     # intentional skip, respect it
```

The new queue generator exclusion logic should check `triage_signal` rather than (or in addition to) `status`. A contact with `triage_signal = "RECONNECT"` and an elapsed cadence window is eligible to re-enter the queue regardless of `status`.

**Warning signs:**
- After migration, RECONNECT and NURTURE contacts never re-appear in the queue despite elapsed cadence windows
- `is_contact_excluded()` returns `True` with reason "Skipped N days ago" for contacts that were snoozed under the old model
- Queue `added` count in pipeline stats drops significantly compared to pre-migration runs

**Phase to address:** Signal model + queue generator phase — migration script must run before the new exclusion logic is deployed.

---

### Pitfall 2: Cadence Re-Queue Creates Duplicate Queue Items When Pipeline Runs Twice

**What goes wrong:**
The cadence re-queue logic adds a contact back to `outreach_queue` when their signal is NURTURE/RECONNECT and the configured cadence interval has elapsed since `reviewed_at`. The existing exclusion check in `is_contact_excluded()` only blocks contacts already in `outreach_queue` with `status IN ("pending_review", "approved")`.

If the pipeline runs twice in a single day (manual run + scheduled run), or if the `reviewed_at` timestamp is interpreted slightly differently due to timezone handling (the existing code uses `datetime.utcnow()` which is deprecated in Python 3.12+ — a known tech debt item), the cadence check may pass on both runs, creating two pending queue items for the same contact.

The existing `is_contact_excluded()` Rule 3 checks for `status IN ("pending_review", "approved")` — but only for items in the queue at the time of check. Two concurrent pipeline runs can both pass this check before either inserts the new row.

**Why it happens:**
The exclusion check and the insert are not atomic. There is a TOCTOU (time-of-check-to-time-of-use) race window. For a single-user daily batch tool this is low-risk — but manual pipeline runs (`reconnect pipeline run`) combined with the LaunchAgent's scheduled run can trigger it. The deprecated `datetime.utcnow()` compounding with timezone offset bugs in cadence calculations increases the chance of a false "cadence elapsed" check.

**How to avoid:**
Add a unique constraint or upsert guard at the database level:

```sql
-- Migration: prevent duplicate pending items for same contact
CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_one_pending_per_contact
ON outreach_queue(connection_id)
WHERE status IN ('pending_review', 'approved');
```

With this constraint, the second pipeline run's INSERT will fail gracefully with a unique violation, which the queue generator should catch and log as "already queued" rather than crashing. Also fix the deprecated `datetime.utcnow()` calls to `datetime.now(UTC)` (Python 3.11+) to eliminate timezone ambiguity in cadence comparisons.

**Warning signs:**
- Contact appears twice in the PWA queue (two cards for same person)
- Pipeline `added` count in stats is 2 for a contact that was already in queue
- Duplicate entries in `outreach_queue` with same `connection_id` and `status = "pending_review"`

**Phase to address:** Cadence scheduling phase — database constraint must be added before cadence re-queue logic is written.

---

### Pitfall 3: Signal-Informed Rescoring Creates a Confirmation Bias Feedback Loop

**What goes wrong:**
The existing feedback processor (`feedback_processor.py`) analyzes approve/skip patterns and adjusts scoring dimension weights (e.g., boost `goal_alignment` by 1.1 if approval rate is high). When signals replace skip/approve, the rescoring logic will read WARM_LEAD signals as "approved" and ARCHIVE/VALUE_DROP as "skipped." This is correct directionally.

The problem emerges when the signal distribution becomes skewed: if the user frequently assigns WARM_LEAD to contacts in one specific industry (e.g., SaaS Product), the feedback processor will boost `goal_alignment` and `industry_overlap` weights for that pattern. The next day's scoring run produces higher scores for SaaS Product contacts. They populate the top of the queue. The user sees more SaaS Product contacts, assigns more WARM_LEAD signals, which further boosts those weights. Within 2-4 weeks, the queue becomes dominated by a single industry/role type — not because those contacts are objectively more valuable, but because the feedback loop has amplified an early preference.

**Why it happens:**
The weight adjustment logic in `_derive_weight_adjustments()` reads 30-day windows and applies multipliers (0.9–1.1 range). Small changes compound when applied daily. The signal data for the new model will be sparse in early weeks (few signals, high variance), but the feedback processor applies adjustments even at low signal counts (threshold: 10 actions, line 179 in `feedback_processor.py`). A user who uses WARM_LEAD 8 times in the first week sends a strong signal with very low sample size.

**How to avoid:**
1. **Raise the minimum sample threshold** for weight adjustments from 10 to at least 25 actions, and require at least 14 days of signal history before any weight adjustment fires.
2. **Cap cumulative weight drift.** Multipliers should not compound beyond a max range (e.g., never below 0.7 or above 1.4). Implement this as a clamp in `_upsert_scoring_weight()`.
3. **Log weight history**, not just current values. Store `(dimension, multiplier, updated_at, based_on_n_actions)` so drift is visible. Add a CLI command to show current weight multipliers and their history: `reconnect queue weights`.
4. **Separate signal-driven rescoring from automated weight adjustment.** Signal-informed rescoring (contact-level: "you signaled WARM_LEAD for this contact, boost their score") should be independent from population-level weight adjustment. Conflating them amplifies the feedback loop.

**Warning signs:**
- Queue becomes homogeneous (same industry or role type dominates) after 2-3 weeks of signal use
- `user_preferences` table shows multipliers for `goal_alignment` or `industry_overlap` > 1.3 or < 0.8
- User starts seeing the same 20 contacts cycling back repeatedly
- Pipeline stats show score distribution narrowing (fewer contacts below threshold vs. above)

**Phase to address:** Signal-informed rescoring phase — minimum sample and cap logic must be built before the feedback loop runs for the first time.

---

### Pitfall 4: New Signal Fields Not Synced to Supabase — PWA Reads Stale Data

**What goes wrong:**
The existing push sync in `src/sync/push.py` explicitly lists which `Connection` fields and `OutreachQueueItem` fields to include in the upsert payload. When new fields are added for signals (e.g., `triage_signal`, `cadence_due_at`, `signal_context` on `OutreachQueueItem`, or `last_signal_at`, `current_signal` on `Connection`), they will be silently omitted from the push sync unless the push code is explicitly updated.

The PWA reads directly from Supabase. If `triage_signal` is set locally in SQLite but not pushed, the queue card in the PWA will show no signal badge, and the Edge Function draft generator will not receive tone context. The user will see their signals not reflected after triage, which looks like a bug.

**Why it happens:**
The push sync (`src/sync/push.py`) likely uses explicit field mapping (common pattern to avoid pushing sensitive fields like `gmail_credentials`). New fields that do not exist in the mapping are silently dropped. SQLAlchemy/SQLModel schema migrations are local-only — the Supabase PostgreSQL schema must be updated separately, and if the column does not exist in Supabase, the upsert silently drops the field rather than failing.

**How to avoid:**
For every new field added to `OutreachQueueItem` or `Connection` in `models.py`:
1. Write a Supabase migration SQL (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) before writing any Python code that sets the field.
2. Add the field explicitly to the push sync payload mapping.
3. Add the field to pull sync if it is a cloud-writable field (e.g., a signal set from the PWA action).

Use a field coverage test: assert that all non-excluded `Connection` and `OutreachQueueItem` model fields are present in the push payload. This prevents silent field drift between local schema and push sync.

**Warning signs:**
- PWA shows queue cards without signal badges even after local triage was done
- Supabase dashboard shows `triage_signal` column as NULL after pipeline runs
- Push sync stats show "0 updated" for `connections` despite local changes
- Draft Edge Function generates wrong-tone messages (because `triage_signal` was not pushed and it cannot read tone intent)

**Phase to address:** Signal model phase (database and sync) — migrations and sync updates must ship together with model changes, not after.

---

### Pitfall 5: Action Edge Function Token Model Cannot Express 7 Signals From Email

**What goes wrong:**
The existing `action` Edge Function handles three actions: `approve`, `skip`, `snooze`. Each is a separate token type. The email digest generates one token per contact per action.

Extending this to 7 signals (WARM_LEAD, NURTURE, VALUE_DROP, SYNERGY, RECONNECT, FUTURE_PIVOT, ARCHIVE) would require generating 7 tokens per contact in the email — 7 action buttons per contact. With 5 contacts in the digest, that is 35 tokens and 35 buttons. This is not a usable email.

The temptation is to pass the signal as a query parameter (`?token=...&signal=WARM_LEAD`) rather than baked into the token's `action` field. This is a security flaw: anyone with a valid unused token could append `?signal=ARCHIVE` and apply a different action than the one the token was created for.

**Why it happens:**
Tokens are currently validated by `action` field, not by `payload`. Putting signal choice in a query parameter outside the token breaks the tamper-resistance of the token model.

**How to avoid:**
The email digest should NOT try to represent all 7 signals as buttons. The correct architecture:

1. **Email digest is a triage notification, not a signal picker.** The digest email shows 3-5 contacts and one primary action each: "Review in App" or (for clear cases) "Queue for Outreach." Full signal assignment happens in the PWA queue card.
2. **If email triage is desired,** limit the email to 2 signal choices per contact (e.g., WARM_LEAD and ARCHIVE — the two highest-intent decisions). Store signal choice in `payload` within the token row at creation time, not as a URL parameter.
3. **The `action` field in `action_tokens`** should remain `"signal"` or `"triage"` generically, with the specific signal stored in `payload.signal`. The Edge Function reads `tokenRow.payload.signal` to determine the action — never a query parameter.

**Warning signs:**
- Email digest HTML becomes unrenderable on mobile (too many action buttons per contact)
- Users are confused about which button corresponds to which contact
- Token table accumulates 7 rows per contact per digest (token exhaustion per email)
- Query parameter `signal=` appears in Edge Function handling code (security smell)

**Phase to address:** Email digest integration phase — redesign the email triage model before generating new token types.

---

### Pitfall 6: User Goals Profile Not Propagated to Draft Edge Function — Personalization Is One-Sided

**What goes wrong:**
The `draft` Edge Function fetches `user_profile` from Supabase and includes `profile.goals` in the draft prompt (line 173 in `draft/index.ts`: `const senderGoals = profile?.goals || "Network expansion"`). When v1.2 adds a user goals profile with current projects and specific interests, this data needs to reach the Edge Function.

If goals are updated in the `user_profile` table locally but not pushed to Supabase, the Edge Function will use stale goals ("Network expansion") for all drafts. The signal-driven tone adaptation will also fail: the draft prompt currently hard-codes tone by channel (`linkedin` = casual, `email` = professional). Signal tone intent (e.g., SYNERGY = collaborative framing, WARM_LEAD = direct value proposition) requires the signal to be in the prompt.

**Why it happens:**
`user_profile` sync is part of the push pipeline but the `goals` field may not be explicitly synced if it is a new column. The `draft` Edge Function also has no knowledge of `triage_signal` — it would need to receive it either via the request body from the PWA or by fetching the relevant `outreach_queue` row (which it does fetch, but currently reads only `channel`).

**How to avoid:**
1. Ensure `user_profile.goals`, `user_profile.interests`, and any new goal-profile fields are included in the push sync.
2. Extend the draft Edge Function request body to include `signal` alongside `queue_item_id` and `channel`. The PWA sends it; the Edge Function uses it in the prompt.
3. Add a signal-to-tone mapping in the Edge Function:

```typescript
const toneMappings: Record<string, string> = {
  WARM_LEAD: "Direct and value-focused. Reference why this contact aligns with your current goals.",
  NURTURE: "Warm and relationship-focused. No ask — just rekindling the connection.",
  SYNERGY: "Collaborative. Frame around shared opportunity or mutual interest.",
  RECONNECT: "Personal and nostalgic. Focus on the shared history.",
  FUTURE_PIVOT: "Curious and exploratory. Mention their recent direction change.",
  VALUE_DROP: "Brief and gracious. Acknowledge the connection without pressure.",
  ARCHIVE: "Do not generate a draft for ARCHIVE signals.",
};
```

**Warning signs:**
- Draft messages sound generic despite the user assigning specific signals
- "Network expansion" appears literally in generated drafts (stale goals fallback)
- ARCHIVE signal still triggers draft generation (no guard)
- Tone does not vary between a WARM_LEAD draft and a NURTURE draft for contacts with identical enrichment data

**Phase to address:** Draft tone adaptation phase — requires both the push sync update (goals) and the Edge Function update (signal-to-tone mapping) to ship together.

---

## Moderate Pitfalls

---

### Pitfall 7: Contact Notes Stored Locally Never Reach the PWA (Sync Gap)

**What goes wrong:**
The `Connection` model already has a `notes` field (`Optional[str]`, `Column(Text)`). If v1.2 adds free-form contact notes via the PWA (user types a note on the queue card or contact profile), those notes are written directly to Supabase via the PWA's PostgREST calls. They must also flow back to local SQLite via pull sync, or the pipeline's next run (which reads the local DB for scoring and queue generation) will not see them.

The current pull sync in `pull.py` fetches `Connection.last_contacted_at` and `Connection.user_priority` from cloud (lines 103-117) — but not `Connection.notes`. If a user adds a note in the PWA, it never reaches local SQLite, and signal-informed rescoring cannot use the note as context.

**Why it happens:**
The pull sync explicitly whitelists fields to copy from cloud to local. `notes` was not a user-editable field before v1.2 — it was pipeline-written. Now it is user-writable from the PWA, but pull sync does not know that.

**How to avoid:**
Add `Connection.notes` to the pull sync's contact update logic alongside `last_contacted_at` and `user_priority`. Use last-write-wins: if the cloud timestamp is newer than local, overwrite. Also add `Connection.notes` to the push sync to ensure pipeline-written notes (if any) reach Supabase.

Consider whether notes should ever be written by the pipeline. If notes are purely user-authored, mark them as "pull-only from cloud" in comments to prevent accidental pipeline overwrite.

**Warning signs:**
- User writes a note in PWA, sees it on profile, returns next day and note is gone (pipeline overwrite)
- Signal-informed rescoring prompt includes "user notes: None" even after user added notes
- Pull sync stats show `0 contacts_updated` even when notes were written from PWA

**Phase to address:** Contact notes phase — sync coverage check must happen when notes feature is designed.

---

### Pitfall 8: Cadence Due Date Calculated at Signal-Assignment Time Drifts When Pipeline Skips Days

**What goes wrong:**
If `cadence_due_at` is computed as `reviewed_at + cadence_days` at signal assignment time, a contact assigned NURTURE (14-day cadence) on Day 1 will have `cadence_due_at = Day 15`. If the pipeline does not run on Day 15 (machine off, error), the contact will not be re-queued until Day 16 — fine. But if the pipeline skips multiple days (e.g., days 15-19) and runs again on Day 20, the contact will be re-queued 5 days late.

More critically: if the user assigns NURTURE to 20 contacts on the same day, all 20 will have `cadence_due_at` on the same future date. The pipeline on that date will try to add all 20 to the queue at once, saturating the `daily_queue_size` limit (probably 5-10) and leaving 10-15 contacts whose cadence is "due" but who are pushed out by the daily limit. Their `cadence_due_at` is now in the past — future runs will see them as "overdue" and try to re-queue them again until the limit is not saturated.

**Why it happens:**
Calculating cadence due dates as fixed points in time assumes the pipeline is reliable and the queue is never saturated. Neither is guaranteed.

**How to avoid:**
Instead of `cadence_due_at`, track `signal_assigned_at` and `cadence_days` separately. On each pipeline run, compute `signal_assigned_at + cadence_days <= today AND not already in queue` to find re-queue candidates. This way, cadence eligibility is evaluated fresh each run and does not go "stale in the past."

For the queue saturation problem: when more cadence-eligible contacts exist than the daily limit, use a priority ordering (WARM_LEAD before NURTURE, then sort by `reconnect_score` descending). Do not skip over cadence-eligible contacts once they are overdue — just queue the highest-priority ones each day until the backlog is cleared.

**Warning signs:**
- Multiple contacts with the same `cadence_due_at` date all appear in queue on the same day, saturating the limit
- After a pipeline outage, cadence-eligible contacts show `cadence_due_at` in the past but never re-appear in queue (exclusion logic checked `due > today` instead of `due <= today`)
- `due_today` count in pipeline stats spikes on first run after a pipeline gap

**Phase to address:** Cadence scheduling phase — use age-based eligibility, not absolute timestamps, for cadence re-queue logic.

---

### Pitfall 9: Vanilla JS Queue Card State Becomes Inconsistent After Partial Signal Actions

**What goes wrong:**
The current `queueAction()` in `queue.js` does optimistic UI: it fades out the card immediately, then removes it from the DOM after 300ms regardless of whether the Supabase write succeeded. For three binary actions (approve/skip/snooze), this is acceptable — the card should leave the queue regardless.

For 7 signals with richer interactions (e.g., signal picker dropdown, optional note input, tone preview before confirming), the optimistic-removal model breaks down. If the user opens a signal picker, selects NURTURE, types a note, and then the Supabase write fails (network flicker), the card is removed but the signal was never stored. The contact disappears from today's queue and does not re-appear until the next pipeline run — with no record of the intended signal.

More subtly: if the PWA renders a "signal already assigned" badge on a queue card (showing the current signal), and the user changes the signal, the badge must update immediately. If the card is re-rendered from scratch (full `renderQueue()` call), the filter state, sort order, and scroll position are all reset — disorienting on mobile.

**Why it happens:**
The current `queueAction()` removes the card on success or failure. For simple approve/skip this is fine because both outcomes result in the card leaving the queue. For signal assignment, failure should leave the card in place with an error state, and partial success (signal saved but note not saved) needs to be shown.

**How to avoid:**
1. **Separate "signal assignment" from "card dismissal."** Assigning a signal should update the card's visual state (show a signal badge) without removing the card. Card removal should only happen when the user confirms they are done with the contact for today (a separate "Done" action or when the card is navigated past).
2. **Use targeted DOM updates instead of full `renderQueue()` re-renders.** When a signal is assigned, update only that card's badge: `card.querySelector('.signal-badge').textContent = signalLabel`. This preserves scroll position and filter state.
3. **On write failure, restore the card to its pre-action state** and show an inline error: `card.classList.remove('loading'); card.classList.add('error')`.

**Warning signs:**
- Signal assignment appears to work but contact does not show the assigned signal on profile page the next day
- Filter state and scroll position reset every time the user assigns a signal (full re-render happening)
- Queue card disappears after a network error, contact does not re-appear until next pipeline run

**Phase to address:** PWA queue card enrichment phase — new interaction model must be designed before adding signal picker UI.

---

### Pitfall 10: User Preferences Pulled from Cloud Overwrite Local Pipeline-Set Weights

**What goes wrong:**
The pull sync in `pull.py` copies `UserPreference` rows from Supabase to local SQLite using "insert if not exists" (lines 206-212). The feedback processor in `feedback_processor.py` also writes `UserPreference` rows for scoring weights. If the user edits a preference from the PWA (e.g., setting a custom `scoring_weight` for `goal_alignment`), and the pull sync runs after the pipeline's feedback processor has written a new weight for the same dimension — the pull sync will not overwrite the local value (because the row already exists in local SQLite). The user's PWA preference effectively loses to the pipeline-computed weight.

Conversely, if "insert if not exists" is changed to "upsert/overwrite" for preferences, the pipeline's computed weights will be silently overwritten by anything the user set from the PWA.

**Why it happens:**
`UserPreference` rows have no `updated_at` field — there is no way to determine which is newer. The current pull sync uses "insert if not exists" which effectively makes local the winner. This was fine when preferences were only set by the pipeline, but breaks when the PWA is also a preference-writing path.

**How to avoid:**
Add `updated_at` to `UserPreference` (both model and migration). Use last-write-wins in pull sync: if the cloud `updated_at > local updated_at`, overwrite. Also distinguish preference sources in `pref_type`: pipeline-computed weights use `pref_type = "scoring_weight_auto"`, user-explicit preferences use `pref_type = "scoring_weight_user"`. User-explicit preferences always win over auto-computed ones regardless of timestamp.

**Warning signs:**
- User sets a preference in PWA, pipeline runs, preference reverts
- `user_preferences` table has duplicate rows for the same `pref_key` with different values
- Pull sync stats show 0 for `preferences_pulled` even when new preferences exist in cloud

**Phase to address:** User goals profile phase (or any phase that adds user-editable preferences from PWA).

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems in the context of v1.2.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store signal as `skip_reason` text instead of a dedicated `triage_signal` column | No migration needed | Cannot query by signal type; cadence logic requires string parsing; reporting is impossible | Never for v1.2 — dedicated column is required |
| Compute `cadence_due_at` as a fixed timestamp at signal time | Simple: `reviewed_at + N days` | Contacts go "overdue" silently if pipeline gaps; saturation on cohort due dates | Never — use `signal_assigned_at + cadence_days <= today` at query time instead |
| Apply feedback loop weight adjustments with < 25 actions | Faster "learning" | Feedback loop amplifies noise; queue homogenizes toward early preferences | Only during testing with synthetic data; never in production |
| Pass `triage_signal` as a URL query parameter to Edge Functions | Avoids token payload changes | Breaks token tamper-resistance; any valid token + `?signal=ARCHIVE` can archive any contact | Never — signal must be in the token's `payload` field |
| Re-render full `renderQueue()` on every signal assignment | Simpler code | Resets scroll position and filter state; disorienting on mobile during batch triage | Acceptable only for initial prototype; must use targeted DOM updates before shipping |
| Skip `user_profile.goals` sync update when adding new goal fields | Saves migration work | Edge Function draft tone uses stale goals; signal-driven personalization fails silently | Never — schema and sync must be updated together |

---

## Integration Gotchas

Common mistakes when wiring the new signal system into the existing stack.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Pull sync + UserPreference | "Insert if not exists" makes local always win when both pipeline and PWA write preferences | Add `updated_at` to `UserPreference`; use last-write-wins in pull sync |
| Push sync + new signal fields | New `triage_signal`, `cadence_days` fields silently dropped from push payload | Explicitly add every new model field to the push payload dict; assert field coverage |
| Draft Edge Function + signal | Tone is hard-coded by channel, not by signal | Pass `signal` in request body from PWA; use signal-to-tone mapping in prompt builder |
| Action Edge Function + 7 signals | Bake signal into URL query param to avoid regenerating tokens | Always store signal in `payload` field of `action_tokens` row; never as a URL param |
| Feedback processor + signal data | Treat all non-WARM_LEAD signals as "skip" for weight analysis | Map signals to intent tiers: WARM_LEAD/SYNERGY = approve-equivalent; ARCHIVE/VALUE_DROP = skip-equivalent; NURTURE/RECONNECT/FUTURE_PIVOT = neutral (do not influence weight calculation) |
| Cadence re-queue + exclusion rules | Old skip cooldown blocks cadence-eligible contacts | New exclusion logic must check `triage_signal` — NURTURE/RECONNECT bypass skip cooldown |
| Supabase migration + local SQLite | Add column to Supabase migration SQL but forget to add to `models.py` (or vice versa) | Run both the Supabase migration and local `alembic upgrade` (or SQLite DDL) in same PR/step |

---

## Performance Traps

Patterns that work fine at current scale but break with v1.2 changes.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Pull sync fetches all `UserPreference` rows (no delta) | Grows proportionally as more preferences are added over time | Add `updated_at` and filter by `last_pull_at` in preference query (same pattern as `UserFeedback`) | When preference count exceeds ~200 rows — currently fine but scales poorly |
| Scoring weight multipliers applied every queue generation run without checking if they have changed | Unnecessary DB reads on every run; weight drift not logged | Cache weights with a `loaded_at` timestamp; only reload when a new preference row is newer than the cache | Not a problem at current scale, but `_load_weight_overrides()` is called per `score_connection()` call |
| Queue card full re-render on signal assignment (client-side) | Scroll reset, filter state lost; jank on mobile during batch triage of 10+ cards | Targeted DOM mutations for signal badge updates | Immediately visible when user triages more than 3 contacts in a session |
| Signal history stored in `UserFeedback` with no index on `signal` type | Signal pattern analysis (for feedback processor) requires full table scan | Add index on `(feedback_type, connection_id)` — already exists as `idx_feedback_type` and `idx_feedback_connection`; ensure signal records use a consistent `feedback_type` value like `"triage_signal"` | Not until `user_feedback` grows past ~5,000 rows |

---

## Security Mistakes

Domain-specific security issues introduced by the v1.2 signal model.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Signal passed as URL query parameter to Edge Function action handler | Any valid unused token can have `?signal=ARCHIVE` appended to archive any contact it references | Store signal in `payload` field within `action_tokens` row; Edge Function reads only `tokenRow.payload.signal` |
| Contact notes stored in Supabase with no content length limit | A very long note (e.g., pasted document) causes oversized JSONB payloads and slow queries | Add `maxlength` attribute on PWA note input (e.g., 1000 chars); enforce at PostgREST level with a check constraint: `CHECK (char_length(notes) <= 2000)` |
| User goals profile pushed to Supabase (includes sensitive personal strategy info) | Goals/interests data is readable by anyone with the anon key (no RLS) | For a single-user tool with anon key access, this is acceptable but should be noted; if anon key is ever shared or rotated, user_profile contents are exposed |
| Feedback processor writing scoring weight adjustments without audit log | Weight drift is invisible; it is unclear why the queue changed composition | Log every weight adjustment as a `UserFeedback` row with `feedback_type = "auto_weight_adjustment"` so the audit trail exists |

---

## UX Pitfalls

User experience mistakes specific to the signal and cadence model.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| 7 signal choices presented as a flat list without grouping | Decision fatigue; user defaults to the first option or skips triage entirely | Group signals into 2-3 tiers: "Act Now" (WARM_LEAD, SYNERGY), "Later" (NURTURE, RECONNECT, FUTURE_PIVOT), "Not Now" (VALUE_DROP, ARCHIVE) |
| Signal assignment has no confirmation or undo for ARCHIVE | User accidentally archives a high-value contact; no way to recover without raw SQL | Show a brief "Archived — Undo" toast for 5 seconds after ARCHIVE signal; undo sets signal back to previous value |
| Queue card shows signal badge but no explanation of what the signal means | New users do not know what FUTURE_PIVOT means | Show signal label + one-line description on hover/tap: "FUTURE_PIVOT — Interesting career direction, revisit in 90 days" |
| Cadence re-queue surfaces a contact the user has already reached out to (failed sync) | User drafts a message for someone they messaged yesterday; embarrassing | Check `last_contacted_at` in cadence eligibility even if signal is NURTURE; block re-queue if contacted within 30 days |
| Email digest still shows 3 action buttons (Reach Out / Skip / Snooze) after signal model ships | Signal model exists in PWA but email is inconsistent; user is confused which model to use | Update email digest to show 2 simplified buttons ("Review in App" and "Archive") in the same phase that ships signal model in PWA |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces for v1.2.

- [ ] **Signal model migration:** Signal field added to `outreach_queue`. Missing: have existing `status = "skipped"` rows been backfilled with intent categories? Does `is_contact_excluded()` check signal type, not just timestamp?
- [ ] **Cadence re-queue logic:** Pipeline adds contacts with elapsed cadence back to queue. Missing: does it deduplicate correctly (unique constraint on `(connection_id, status IN pending/approved)`)? Does it handle cohort saturation (many contacts due on same day)?
- [ ] **Draft tone adaptation:** Edge Function generates different-tone messages for different signals. Missing: has `signal` been added to the request body schema? Does it handle `ARCHIVE` signal gracefully (no draft generated)?
- [ ] **Push sync coverage:** New model fields sync to Supabase. Missing: is every new field in the push payload dict? Has the Supabase migration run on the production project? Have you verified the field appears in Supabase dashboard after a push?
- [ ] **Pull sync coverage:** User-written notes and preferences sync back to local SQLite. Missing: is `Connection.notes` in the pull sync contact update block? Is `UserPreference.updated_at` used for conflict resolution?
- [ ] **Feedback loop guards:** Signal-informed rescoring adjusts weights. Missing: is there a minimum sample threshold (>= 25 actions)? Is there a multiplier cap (never < 0.7 or > 1.4)? Is there a weight history log?
- [ ] **Email digest updated:** Email reflects signal model. Missing: has the email been updated to remove Snooze button and align with new signal vocabulary? Are new token types (if any) generated with signal in `payload`, not URL params?

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Old skipped items blocking cadence re-queue | MEDIUM | Run one-time migration to backfill `triage_signal` on old skipped rows; update exclusion logic to check signal; no data loss |
| Duplicate queue items from double pipeline run | LOW | Add `DELETE FROM outreach_queue WHERE id NOT IN (SELECT MIN(id) FROM outreach_queue GROUP BY connection_id, status)` one-time cleanup; add unique constraint to prevent recurrence |
| Feedback loop homogenized queue | MEDIUM | Reset scoring weights: `DELETE FROM user_preferences WHERE pref_type = 'scoring_weight_auto'`; run pipeline rescore on all contacts; weights restart from baseline; 2-3 days to see results |
| Signal not showing in PWA (push sync gap) | LOW | Add missing field to push payload; run manual `reconnect sync push`; field appears in Supabase within minutes |
| ARCHIVE signal triggered by accident | LOW (if undo exists) / MEDIUM (if not) | Build undo toast in same phase; recovery without undo requires direct Supabase update: `UPDATE outreach_queue SET triage_signal = NULL WHERE ...` |
| Draft tone wrong because signal not passed | LOW | Add `signal` to PWA draft request body; deploy updated Edge Function; no data migration needed |
| Contact notes lost (pull sync gap) | LOW | Add `notes` to pull sync contact update block; run `reconnect sync pull`; notes appear locally; no data loss (notes are in Supabase, just not in local SQLite) |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Orphaned skipped items blocking cadence re-queue | Signal model + database migration phase | Run migration; verify old snooze items have `triage_signal = "RECONNECT"`; run pipeline and confirm they re-enter queue |
| Duplicate queue items from TOCTOU race | Signal model + database migration phase | Add unique constraint; run pipeline twice in same day; confirm second run logs "already queued" instead of inserting duplicate |
| Feedback loop confirmation bias | Signal-informed rescoring phase | After 25+ signals, inspect `user_preferences` for `scoring_weight_auto`; confirm multipliers stay within 0.7–1.4 range |
| New signal fields not pushed to Supabase | Signal model + sync phase | After pipeline push, query Supabase `outreach_queue` — `triage_signal` column must be non-null for processed contacts |
| Email action token security (signal as URL param) | Email digest integration phase | Inspect generated token rows — signal value must be in `payload` column, not constructible from URL manipulation |
| User goals stale in Edge Function draft | Draft tone adaptation phase | Assign WARM_LEAD and NURTURE to same contact; request drafts; verify tone differs |
| Contact notes not pulled to local SQLite | Contact notes phase | Write a note in PWA; run `reconnect sync pull`; query local SQLite for the note |
| Cadence cohort saturation | Cadence scheduling phase | Assign NURTURE to 20 contacts on the same day; advance date to cadence due date; run pipeline; verify only `daily_queue_size` contacts are added, rest queued next run |
| Signal picker UX triggering full re-render | PWA queue card phase | Assign 5 signals in sequence; confirm scroll position does not reset and filter state is preserved |
| Pull sync overwriting user preferences | User goals profile phase | Set a preference in PWA; run full pipeline; re-check preference in PWA — value must not have changed |

---

## Sources

- Existing codebase (reviewed): `src/pipeline/queue_generator.py`, `src/pipeline/feedback_processor.py`, `src/llm/scoring.py`, `src/sync/pull.py`, `src/database/models.py`, `supabase/functions/draft/index.ts`, `supabase/functions/action/index.ts`, `pwa/js/queue.js`
- Feedback loop bias in ML systems: https://arxiv.org/pdf/2305.06055 (Classification of Feedback Loops and Their Relation to Biases in Automated Decision-Making Systems)
- Hidden feedback loops in continuous ML: https://arxiv.org/pdf/2101.05673
- Microsoft Research: When bias begets bias in AI feedback loops: https://www.microsoft.com/en-us/research/blog/when-bias-begets-bias-a-source-of-negative-feedback-loops-in-ai-systems/
- Supabase bidirectional sync conflict resolution patterns: https://www.stacksync.com/blog/supabase-postgresql-integration-real-time-bi-directional-sync
- Zero-downtime migration: add-before-remove column strategy: https://dev.to/ari-ghosh/zero-downtime-database-migration-the-definitive-guide-5672
- Vanilla JS PWA optimistic UI and offline sync: https://medium.com/illumination/modern-pwa-magic-how-i-built-a-resilient-progressive-web-app-with-vanilla-javascript-d2684f1c38f2
- PWA Background Sync browser support gaps (Firefox, Safari): https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Offline_and_background_operation
- State management in Vanilla JS 2026 patterns: https://medium.com/@chirag.dave/state-management-in-vanilla-js-2026-trends-f9baed7599de
- LLM personalization sycophancy with user profiles: https://news.mit.edu/2026/personalization-features-can-make-llms-more-agreeable-0218
- Project context and known tech debt: `.planning/PROJECT.md`

---
*Pitfalls research for: Reconnect v1.2 Intent-Driven Triage milestone*
*Researched: 2026-03-11*
