# Phase 11: Signal Write Completion + Draft Wiring - Research

**Researched:** 2026-03-13
**Domain:** Vanilla JS PostgREST writes, Supabase Edge Function signal propagation, Python pipeline cadence queries
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERS-05 | AI-generated draft messages adapt tone based on the assigned signal | `assignSignalFromCard()` must write `signal` + `signal_context` to `outreach_queue`; Edge Function then reads those values (already implemented in `buildDraftPrompt()`); SIGNAL_TONE_CONFIG branches then become reachable |
| CAD-02 | Contacts with expired cadence automatically re-enter the daily queue | `assignSignalFromCard()` must write `cadence_due_at` to `connections`; `_get_cadence_expired_candidates()` query already correct but returns 0 results because the value is never populated |

</phase_requirements>

---

## Summary

Phase 11 is a surgical gap-closure phase. All the logic for signal-aware drafts and cadence re-queuing already exists — the SIGNAL_TONE_CONFIG branches, the ARCHIVE guard, the `_get_cadence_expired_candidates()` query, the pull sync that propagates `cadence_due_at` back to local SQLite. The only thing missing is two PostgREST writes that `assignSignalFromCard()` in `pwa/js/queue.js` never makes.

The root cause (confirmed by the v1.2 audit) is a single function, `assignSignalFromCard()`, which only makes 2 of 4 required writes on signal assignment: it inserts to `contact_signals` and updates `connections.latest_signal`, but it never updates `outreach_queue.signal` (breaking PERS-05) and never writes `connections.cadence_due_at` (breaking CAD-02). The `apply_signal()` function in `signal_service.py` was written to handle all four writes but is orphaned — the PWA bypasses it by talking directly to PostgREST.

The fix is entirely in `pwa/js/queue.js:assignSignalFromCard()`. The Edge Function draft generation already reads `queueItem.signal` and `queueItem.signal_context`. The pipeline cadence query already reads `connections.cadence_due_at`. No new files are needed. No schema changes are needed. No Edge Function deployment is needed. This phase adds two PostgREST UPDATE calls in an existing JS function and adds integration tests that were missing from Phase 10.

**Primary recommendation:** Add the two missing PostgREST writes inside the existing `try` block in `assignSignalFromCard()`, immediately after the existing `connections.latest_signal` UPDATE. Compute `cadence_due_at` from `SIGNAL_ACTIONS[signal].cadence` (already available in the JS const). Update `outreach_queue.signal` and `outreach_queue.signal_context` via a separate UPDATE keyed on `itemId`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Supabase JS client | @supabase/supabase-js@2 | PostgREST writes from PWA | Already in use; same `db.from('table').update(...).eq('id', val)` pattern as existing writes in `assignSignalFromCard()` |
| PostgreSQL/PostgREST (Supabase) | Managed | Receives the two new writes | Tables already have the columns; `outreach_queue.signal` and `connections.cadence_due_at` exist per migration `20260311000000_signal_foundation.sql` |
| pytest + SQLite in-memory | 7.4+ / :memory: | Integration test harness | Established pattern in `test_phase9_cadence.py` — same SQLModel models work against SQLite |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `SIGNAL_ACTIONS` (queue.js) | Existing const | Source of `cadence_days` per signal for computing `cadence_due_at` | Read `SIGNAL_ACTIONS[signal].cadence` to compute `Date.now() + cadence_days * 86400000` in JS |
| `signal_service.py:SIGNAL_ACTIONS` | Existing | Canonical signal definitions; verify cadence values match JS const | Reference only — do NOT call `apply_signal()` from PWA path |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Two separate PostgREST UPDATE calls | Single combined update in one call | Two-call approach follows existing code style (connections update is already separate); batching would require a custom RPC which adds complexity |
| Computing `cadence_due_at` in JS | Calling a new Edge Function to compute it | JS computation is trivial: `new Date(Date.now() + cadence * 24*60*60*1000).toISOString()`; no server round-trip needed |
| Wiring `apply_signal()` into the PWA path | Adding two writes to `assignSignalFromCard()` | Wiring `apply_signal()` via a new RPC would be over-engineering; direct PostgREST writes stay consistent with the established PWA pattern |

**Installation:** No new packages needed.

---

## Architecture Patterns

### No New Files Needed

All changes are in-place edits:

```
pwa/js/queue.js          # Add 2 PostgREST writes in assignSignalFromCard()
tests/test_phase11_signal_write.py   # New test file (Wave 0 gap)
```

### Pattern 1: `cadence_due_at` Computation in JavaScript

**What:** Compute the ISO timestamp for `cadence_due_at` in the JS client before writing to PostgREST. The `SIGNAL_ACTIONS` const already has `cadence` (days) per signal. ARCHIVE has `cadence: null` — write `null` to `cadence_due_at` for ARCHIVE.

**When to use:** Inside `assignSignalFromCard()`, right before the PostgREST writes.

**Example:**
```javascript
// Source: derived from SIGNAL_ACTIONS const in pwa/js/queue.js
const signalInfo = SIGNAL_ACTIONS[signal];
const cadenceDays = signalInfo?.cadence; // null for ARCHIVE
const cadenceDueAt = cadenceDays !== null && cadenceDays !== undefined
  ? new Date(Date.now() + cadenceDays * 24 * 60 * 60 * 1000).toISOString()
  : null;
```

### Pattern 2: `outreach_queue.signal` Write

**What:** After the successful `connections.latest_signal` UPDATE, add a separate UPDATE to `outreach_queue.signal` and `outreach_queue.signal_context` keyed on `itemId`.

**When to use:** Inside the `try` block of `assignSignalFromCard()`, after the connections update.

**Example:**
```javascript
// Write signal to outreach_queue so Edge Function draft receives it
const { error: queueSignalError } = await db
  .from('outreach_queue')
  .update({ signal: signal, signal_context: null })  // signal_context: null initially
  .eq('id', itemId);

if (queueSignalError) throw queueSignalError;
```

Note: `signal_context` is an optional freeform note. For Phase 11, writing `null` is correct — the field is preserved for future use where users could annotate why they assigned the signal.

### Pattern 3: `connections.cadence_due_at` Write

**What:** Extend the existing `connections` UPDATE (which already sets `latest_signal` and handles ARCHIVE's `user_priority`) to also set `cadence_due_at`.

**When to use:** In the same UPDATE call as `latest_signal` (avoids a third round-trip).

**Example:**
```javascript
// Extend existing connections UPDATE — add cadence_due_at
const updateData = { latest_signal: signal, cadence_due_at: cadenceDueAt };
if (signal === 'ARCHIVE') {
  updateData.user_priority = 'never';
  // cadenceDueAt is null for ARCHIVE — explicitly clear it
}

const { error: connError } = await db
  .from('connections')
  .update(updateData)
  .eq('id', connectionId);
```

This is additive: the existing `updateData` object already has `latest_signal`; we add `cadence_due_at` to it.

### Pattern 4: Pull Sync Already Handles `cadence_due_at`

**What:** The pull sync in `src/sync/pull.py` already reads `cadence_due_at` from the cloud `connections` table and writes it to local SQLite (lines 123-126, 253-257). This means once the PWA writes `cadence_due_at` to Supabase, the next pipeline pull sync will propagate it to SQLite, and `_get_cadence_expired_candidates()` will find the contact.

**Implication for planning:** No changes needed in `pull.py`. The sync path is already correct.

### Pattern 5: PostgREST Permission Baseline

**What:** The `outreach_queue` table is already writable by the anon role (confirmed by `queueAction()` successfully calling `db.from('outreach_queue').update(...)` in the existing code). The `connections` table is similarly writable (confirmed by the existing `connections.latest_signal` + `user_priority` updates in `assignSignalFromCard()`). No new GRANT statements are needed.

**Warning:** The `outreach_queue.signal` column was added by `20260311000000_signal_foundation.sql` and the anon role already has permission to write it via the row-level UPDATE grant that covers the entire table.

### Anti-Patterns to Avoid

- **Creating a new Edge Function or RPC for this:** The data is already accessible to the PWA via the anon key. Adding an Edge Function just to compute `cadence_due_at` adds latency, complexity, and cold-start risk.
- **Calling `apply_signal()` from a Python pipeline step that runs daily:** Signal assignment happens at user-triage time in the PWA, not at pipeline time. Hooking `apply_signal()` into the daily pipeline creates a race condition and defeats the real-time write requirement.
- **Batching all 4 writes into a single Supabase transaction:** Supabase JS client does not expose multi-table transactions. The existing code already uses separate `await` calls in series — follow the same pattern.
- **Forgetting the ARCHIVE case for `cadence_due_at`:** ARCHIVE has `cadence: null` in `SIGNAL_ACTIONS`. The write must set `cadence_due_at: null` (not `cadence_due_at: undefined`). Undefined would be omitted from the UPDATE payload, leaving any existing value in place. Null explicitly clears it, which is correct for ARCHIVE (prevents re-queuing).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cadence date computation | Custom date math library | `new Date(Date.now() + days * 24*60*60*1000).toISOString()` | One-liner; no library needed; ISO string is what PostgREST expects for TIMESTAMPTZ columns |
| Signal validation in JS | Custom validator | `SIGNAL_ACTIONS[signal]` guard already at top of `assignSignalFromCard()` | Signal is already validated by the existing guard — if invalid, `signalInfo` is undefined and the function returns early |
| cadence_due_at propagation to SQLite | New sync logic | `pull.py` already syncs `cadence_due_at` (lines 253-257) | Already implemented; zero changes needed to sync |
| ARCHIVE guard in draft Edge Function | Duplicate JS guard | `supabase/functions/draft/index.ts` line 102 already has it | Belt-and-suspenders already in place; once `outreach_queue.signal` is set to ARCHIVE, the guard fires |

**Key insight:** The codebase was built expecting these writes to exist. Every downstream consumer (`_get_cadence_expired_candidates`, `buildDraftPrompt`, `queueItem.signal` ARCHIVE guard) is already wired. This phase only adds the missing producer.

---

## Common Pitfalls

### Pitfall 1: `outreach_queue.signal` write target
**What goes wrong:** Writing signal to `outreach_queue` by `connectionId` instead of `itemId` would update every queue item for that connection (unlikely but possible if a contact has multiple rows).
**Why it happens:** The two UPDATE calls use different keys — `connections` is keyed by `connectionId` (TEXT/UUID), `outreach_queue` is keyed by `itemId` (INTEGER). `assignSignalFromCard()` receives both.
**How to avoid:** Use `.eq('id', itemId)` for the `outreach_queue` UPDATE. The `itemId` parameter is already passed to `assignSignalFromCard(event, connectionId, signal, itemId)`.
**Warning signs:** If multiple queue items for the same contact get their signal updated simultaneously, the write keyed on `connectionId` instead of `itemId` is the likely culprit.

### Pitfall 2: `cadence: null` for ARCHIVE must write `null`, not omit the field
**What goes wrong:** If `cadenceDueAt` is computed as `undefined` (e.g., `null * 86400000` is `0`, `0 + Date.now()` is a valid timestamp) rather than `null`, the ARCHIVE contact would get a near-past `cadence_due_at` and re-enter the queue immediately.
**Why it happens:** JavaScript's `null * number` evaluates to `0`, not `null`. If `cadence` is `null`, the multiplication must be guarded.
**How to avoid:** Use explicit null check: `cadenceDays !== null && cadenceDays !== undefined` before the computation. The SIGNAL_ACTIONS const sets `cadence: null` for ARCHIVE (not `cadence: 0`).
**Verification:** Write a test that assigns ARCHIVE signal and asserts `cadence_due_at` is null in the outreach_queue update payload.

### Pitfall 3: PostgREST UPDATE permission on `outreach_queue` for new columns
**What goes wrong:** Even though `outreach_queue` is generally writable, PostgREST column-level permissions could block writes to specific columns added in a later migration if the grant was column-specific.
**Why it happens:** The `signal_foundation` migration added `signal` and `signal_context` columns but only issued grants for `contact_signals` and `contact_notes`. If the base `outreach_queue` grant is table-level (covers all columns), new columns are automatically included. If it was column-specific, the new columns would be blocked.
**How to avoid:** The existing `queueAction()` function already writes to `outreach_queue` (status, reviewed_at, skip_reason) without issues, indicating a table-level UPDATE grant is in place. Test the write on the actual Supabase instance as part of manual verification.
**Warning signs:** 403 or "permission denied" error from PostgREST on the `outreach_queue.signal` UPDATE call.

### Pitfall 4: Cadence write timing vs. pipeline pull sync lag
**What goes wrong:** A user assigns a signal in the PWA at 9 AM. The pipeline runs at 8 AM (LaunchAgent). `cadence_due_at` is written to Supabase at 9 AM but the pipeline already ran — `_get_cadence_expired_candidates()` won't see the contact until the NEXT day's pipeline run.
**Why it happens:** The pipeline runs on a fixed schedule before the user triages.
**How to avoid:** This is expected behavior — there is no bug, only a design characteristic. The cadence timer starts the moment the user assigns the signal; the pipeline checks the next morning. For a WARM_LEAD with 7-day cadence, the contact re-appears in ~7 days' time, which is correct.
**Note for planning:** This is not a bug to fix — it is a feature of the daily-batch architecture documented in project memory.

### Pitfall 5: `signal_context` field — write null vs. empty string
**What goes wrong:** Writing `signal_context: ''` (empty string) instead of `signal_context: null` would store an empty string in the database, which downstream code would treat as a truthy value and potentially inject an empty "Additional context" line into the draft prompt.
**Why it happens:** PostgREST treats `null` and `''` differently; the `buildDraftPrompt()` function uses `signalContext ? ...contextNote` conditional — empty string is falsy, but a non-null empty-string check depends on the Edge Function TypeScript.
**How to avoid:** Write `signal_context: null` explicitly. Looking at `buildDraftPrompt()` in `index.ts`: `const contextNote = signalContext ? \`\nAdditional context...\` : ""` — this is falsy on empty string, so empty string would also work. But null is semantically correct and matches the DB column default.

### Pitfall 6: Error handling order — don't fail silently on the new writes
**What goes wrong:** If the new PostgREST writes are added after the ARCHIVE card-removal animation (which starts immediately after the connections update), an error on the new writes would be swallowed or the UI state would already be committed.
**Why it happens:** The existing ARCHIVE fade-out runs inside the `if (signal === 'ARCHIVE')` block after the connections update succeeds. The new writes should happen BEFORE the ARCHIVE animation, not after.
**How to avoid:** Order matters — make all PostgREST writes complete before triggering any optimistic DOM changes beyond the badge update (which already happens before the try block). The ARCHIVE card fade is fine to keep after all writes complete.

---

## Code Examples

Verified from direct code inspection:

### Current `assignSignalFromCard()` write sequence (to be extended)
```javascript
// Source: pwa/js/queue.js lines 312-380

async function assignSignalFromCard(event, connectionId, signal, itemId) {
  // ... optimistic badge update ...

  try {
    if (!db) throw new Error('Supabase not available');

    // Write 1 (exists): INSERT contact_signals
    const { error: signalError } = await db
      .from('contact_signals')
      .insert({ connection_id: connectionId, signal, assigned_by: 'user' });
    if (signalError) throw signalError;

    // Write 2 (exists): UPDATE connections.latest_signal
    const updateData = { latest_signal: signal };
    if (signal === 'ARCHIVE') {
      updateData.user_priority = 'never';
    }
    const { error: connError } = await db
      .from('connections')
      .update(updateData)
      .eq('id', connectionId);
    if (connError) throw connError;

    // Write 3 (MISSING): UPDATE outreach_queue.signal
    // Write 4 (MISSING): connections.cadence_due_at (add to Write 2's updateData)

    // ARCHIVE fade-out animation...
  } catch (err) {
    // revert optimistic update
  }
}
```

### Complete fix — all four writes

```javascript
// Source: pwa/js/queue.js — updated assignSignalFromCard()

async function assignSignalFromCard(event, connectionId, signal, itemId) {
  event.stopPropagation();

  const triageArea = document.getElementById(`signal-triage-${itemId}`);
  const picker = document.getElementById(`signal-picker-${itemId}`);
  const signalInfo = SIGNAL_ACTIONS[signal];
  if (!signalInfo) return;

  // Optimistic badge update — unchanged

  try {
    if (!db) throw new Error('Supabase not available');

    // Write 1: INSERT contact_signals (unchanged)
    const { error: signalError } = await db
      .from('contact_signals')
      .insert({ connection_id: connectionId, signal, assigned_by: 'user' });
    if (signalError) throw signalError;

    // Compute cadence_due_at from SIGNAL_ACTIONS const
    const cadenceDays = signalInfo.cadence; // null for ARCHIVE
    const cadenceDueAt = (cadenceDays !== null && cadenceDays !== undefined)
      ? new Date(Date.now() + cadenceDays * 24 * 60 * 60 * 1000).toISOString()
      : null;

    // Write 2: UPDATE connections (now includes cadence_due_at)
    const updateData = { latest_signal: signal, cadence_due_at: cadenceDueAt };
    if (signal === 'ARCHIVE') {
      updateData.user_priority = 'never';
    }
    const { error: connError } = await db
      .from('connections')
      .update(updateData)
      .eq('id', connectionId);
    if (connError) throw connError;

    // Write 3 (NEW): UPDATE outreach_queue.signal so Edge Function receives it
    const { error: queueSignalError } = await db
      .from('outreach_queue')
      .update({ signal: signal, signal_context: null })
      .eq('id', itemId);
    if (queueSignalError) throw queueSignalError;

    // ARCHIVE: fade and remove card (unchanged)
    if (signal === 'ARCHIVE') { /* ... existing fade-out code ... */ }

  } catch (err) {
    // revert optimistic update (unchanged)
  }
}
```

### `_get_cadence_expired_candidates()` — already correct, shown for reference
```python
# Source: src/pipeline/queue_generator.py lines 268-298
# This function is CORRECT and unchanged. It queries:
#   Connection.cadence_due_at IS NOT NULL
#   Connection.cadence_due_at <= now
#   Connection.user_priority NOT 'never'
#   Connection.reconnect_score IS NOT NULL
# Returns [] because cadence_due_at is never populated by PWA today.
# Once Write 4 (cadence_due_at) is added, this query will return results.
```

### `buildDraftPrompt()` signal routing — already correct, shown for reference
```typescript
// Source: supabase/functions/draft/index.ts lines 127-133
// This is CORRECT and unchanged. It reads:
//   queueItem.signal   (currently always null because Write 3 never happens)
//   queueItem.signal_context
// And passes them to buildDraftPrompt() which branches on SIGNAL_TONE_CONFIG.
// Once Write 3 (outreach_queue.signal) is added, all 7 branches become reachable.
const prompt = buildDraftPrompt(
  connection, profile, channel,
  queueItem.signal || null,       // will be 'WARM_LEAD', 'NURTURE', etc.
  queueItem.signal_context || null,
);
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Generic draft prompt (all contacts) | Signal-aware SIGNAL_TONE_CONFIG branches (Phase 10) | Phase 10 (complete) | Branches are defined but UNREACHABLE because `queueItem.signal` is always null |
| Cadence re-queuing via `_get_cadence_expired_candidates()` | Same query (Phase 9) | Phase 9 (complete) | Query is correct but returns 0 results because `cadence_due_at` is never written |
| Phase 11 (this phase) | Wires the missing writes so all existing logic becomes reachable | Phase 11 | PERS-05 and CAD-02 satisfied end-to-end |

**After Phase 11:**
- SIGNAL_TONE_CONFIG all 7 branches: reachable
- ARCHIVE Edge Function guard (line 102 of draft/index.ts): reachable
- `_get_cadence_expired_candidates()` returning > 0 results: works
- `cadence_due_at` in pull sync: propagated correctly
- The test file `tests/test_phase10_draft_tone.py` (listed as tech debt in the audit): should be created in this phase's Wave 0

---

## Open Questions

1. **`signal_context` — does Phase 11 need to expose a UI input?**
   - What we know: `signal_context` is a freeform text field on both `contact_signals` and `outreach_queue`. The Edge Function uses it as "Additional context for this outreach" if non-null. Currently never populated.
   - What's unclear: Is exposing a `signal_context` input in the PWA signal picker in scope for Phase 11?
   - Recommendation: Out of scope for Phase 11. The field was designed for future use. Write `null` for now. The success criterion says "writes signal and signal_context to outreach_queue" — writing `null` for signal_context satisfies the wiring requirement.

2. **Should `apply_signal()` be wired into a pipeline step now that it's orphaned?**
   - What we know: `apply_signal()` correctly computes `cadence_due_at` and writes all 4 fields. It's only called in tests. The audit flags it as tech debt.
   - What's unclear: Is wiring `apply_signal()` (e.g., from pull sync when a new `contact_signals` row is detected) in scope?
   - Recommendation: Out of scope for Phase 11. The PWA PostgREST direct-write approach is established and the pull sync already propagates `cadence_due_at`. `apply_signal()` remains a useful batch/CLI utility but does not need a production caller for Phase 11 to succeed.

3. **PostgREST UPDATE permission — does the anon role have column-level access to `outreach_queue.signal`?**
   - What we know: No GRANT for `outreach_queue` appears in any migration. The existing `queueAction()` writes `status`, `reviewed_at`, `skip_reason` successfully. This implies a table-level grant is configured in the Supabase dashboard or via the default Supabase public schema setup.
   - What's unclear: Whether Supabase auto-grants UPDATE on all columns including those added in later migrations.
   - Recommendation: HIGH confidence that the write will work (existing writes to the same table succeed). Manual verification: test the signal assignment flow on the actual Supabase instance after implementation. If blocked, add `GRANT UPDATE (signal, signal_context) ON outreach_queue TO anon` as a one-time SQL migration.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ |
| Config file | `pyproject.toml` (`[tool.ruff]` section only; pytest runs from project root) |
| Quick run command | `pytest tests/test_phase11_signal_write.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERS-05 | `assignSignalFromCard()` payload includes `outreach_queue.signal` write with correct signal value | unit (mock PostgREST calls) | `pytest tests/test_phase11_signal_write.py::TestAssignSignalWrites::test_outreach_queue_signal_written -x` | Wave 0 |
| PERS-05 | Edge Function receives non-null `queueItem.signal` and routes to correct SIGNAL_TONE_CONFIG branch | unit (via existing SIGNAL_TONE_CONFIG logic) | `pytest tests/test_phase11_signal_write.py::TestDraftToneIntegration::test_signal_reaches_tone_config -x` | Wave 0 |
| PERS-05 | ARCHIVE signal write to `outreach_queue.signal` causes Edge Function ARCHIVE guard to fire | unit | `pytest tests/test_phase11_signal_write.py::TestArchiveGuardWired::test_archive_guard_fires_when_signal_set -x` | Wave 0 |
| CAD-02 | `assignSignalFromCard()` payload includes `connections.cadence_due_at` write computed from `SIGNAL_ACTIONS[signal].cadence` | unit (mock PostgREST calls) | `pytest tests/test_phase11_signal_write.py::TestAssignSignalWrites::test_cadence_due_at_written -x` | Wave 0 |
| CAD-02 | ARCHIVE signal sets `cadence_due_at` to null (not a future date) | unit | `pytest tests/test_phase11_signal_write.py::TestAssignSignalWrites::test_archive_cadence_is_null -x` | Wave 0 |
| CAD-02 | `_get_cadence_expired_candidates()` returns contacts after `cadence_due_at` is written and expired | integration (SQLite in-memory) | `pytest tests/test_phase11_signal_write.py::TestCadenceEndToEnd::test_cadence_query_finds_written_contact -x` | Wave 0 |
| PERS-05 | All 6 non-ARCHIVE signals produce reachable distinct SIGNAL_TONE_CONFIG branches | unit | `pytest tests/test_phase11_signal_write.py::TestDraftToneIntegration::test_all_non_archive_signals_reach_config -x` | Wave 0 |

Note: The test file `tests/test_phase10_draft_tone.py` (planned in Phase 10, flagged in the audit as missing) covers the SIGNAL_TONE_CONFIG prompt construction logic. Phase 11's test file covers the wire-up (write correctness + end-to-end flow). Both Wave 0 gaps should be created.

### Sampling Rate
- **Per task commit:** `pytest tests/test_phase11_signal_write.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase11_signal_write.py` — covers PERS-05 + CAD-02 (all 7 test cases above)
- [ ] `tests/test_phase10_draft_tone.py` — covers SIGNAL_TONE_CONFIG prompt construction (6 tests planned in Phase 10 RESEARCH.md, never created — required as Wave 0 for this phase since PERS-05 validation depends on it)
- [ ] No conftest changes needed — existing `conftest.py` with `mock_settings` fixture is sufficient

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `pwa/js/queue.js` — complete `assignSignalFromCard()` implementation; confirmed 2 of 4 writes present
- Direct code inspection: `supabase/functions/draft/index.ts` — SIGNAL_TONE_CONFIG, ARCHIVE guard, `buildDraftPrompt()` call site; all confirmed correct
- Direct code inspection: `src/pipeline/queue_generator.py` — `_get_cadence_expired_candidates()` query; confirmed correct, confirmed returns 0 because of missing write
- Direct code inspection: `src/sync/pull.py` — `cadence_due_at` sync (lines 123-126, 253-257); confirmed already handled
- Direct code inspection: `src/services/signal_service.py` — `apply_signal()` confirmed orphaned; `SIGNAL_ACTIONS` cadence values verified match `queue.js` const
- Direct code inspection: `src/database/models.py` — `OutreachQueueItem.signal`, `Connection.cadence_due_at` confirmed as existing columns
- Direct code inspection: `supabase/migrations/20260311000000_signal_foundation.sql` — confirms `outreach_queue.signal` and `connections.cadence_due_at` columns exist in schema
- Direct code inspection: `.planning/v1.2-MILESTONE-AUDIT.md` — root cause analysis confirmed; 4 writes identified; 2 missing named
- Direct code inspection: `tests/test_phase9_cadence.py` — test pattern for SQLite in-memory cadence tests

### Secondary (MEDIUM confidence)
- Existing `queueAction()` in `pwa/js/queue.js` (lines 382-452): confirms `outreach_queue` UPDATE works with anon key without explicit GRANT in migrations — table-level permission confirmed by working code

### Tertiary (LOW confidence)
- None. All findings grounded in direct code inspection.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all existing
- Architecture: HIGH — all data flows inspected end-to-end; changes additive
- Pitfalls: HIGH — sourced from direct code reading and audit root cause analysis
- Test design: HIGH — pattern directly mirrors `test_phase9_cadence.py`

**Research date:** 2026-03-13
**Valid until:** Stable (changes only in project-owned files; no external API dependencies)
