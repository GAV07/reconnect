# Phase 10: Draft Tone Adaptation - Research

**Researched:** 2026-03-12
**Domain:** OpenAI prompt engineering, Deno Edge Functions, Vanilla JS UI patterns
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Tone definitions per signal:**
- Each of the 7 signals produces a distinctly toned draft message via the Edge Function prompt
- WARM_LEAD and SYNERGY drafts incorporate user goals context (`current_projects` + `goals`) to make the ask more targeted
- VALUE_DROP drafts reference the contact's enrichment data (industry, skills, interests) to suggest relevant value — not vague
- FUTURE_PIVOT, NURTURE, RECONNECT: tone adapts but does not reference user goals (contact-focused)

**ARCHIVE draft blocking:**
- Hide the draft section entirely on ARCHIVE contact profiles — no button, no area, nothing

**Draft UI signal feedback:**
- Show a colored signal badge above the draft textarea after generation
- Badge uses color from existing `SIGNAL_ACTIONS` const for visual consistency with queue signal chips
- Badge includes a brief tooltip on tap explaining the tone approach
- No badge shown if no signal was used (gate prevents this case)

**No-signal fallback:**
- Draft generation is gated on having an assigned signal
- Draft section shows nudge: "Assign a signal for a tailored draft" instead of generate button
- No "generate generic draft anyway" override
- The current generic one-size-fits-all prompt is retired once this phase ships

### Claude's Discretion
- Exact prompt text and structure for each of the 7 signal tones
- Level of detail in per-signal prompt guidance
- Guard implementation details (PWA-only vs belt-and-suspenders with Edge Function)
- Whether Edge Function response format changes (adding `signal_used` field) or PWA reads signal locally
- Tooltip text for each signal badge
- How the "assign signal first" nudge integrates with the existing profile page layout

### Deferred Ideas (OUT OF SCOPE)
- Signal-based email digest bucketing — v1.3+ (SIG-08)
- VALUE_DROP prompting user to attach a resource/link before outreach — v1.3+ (SIG-07)
- Draft history / draft versioning per contact
- Channel-specific tone adaptation beyond LinkedIn/email
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERS-05 | AI-generated draft messages adapt tone based on the assigned signal | Signal-aware `buildDraftPrompt()` branching in Edge Function; PWA gate on `latest_signal`; signal badge UI after generation |
</phase_requirements>

---

## Summary

Phase 10 is a focused prompt-engineering and UI gate phase. The core change is adding signal-aware branching to the existing `buildDraftPrompt()` function in `supabase/functions/draft/index.ts` — replacing the current generic reconnect prompt with 7 distinct tone templates driven by the queue item's `signal` field. The Edge Function already fetches the queue item (which has a `signal` field), the connection (which has enrichment data), and the user profile (which has `current_projects` and `goals`) — all the data needed is already available.

On the PWA side, `pwa/js/contact.js` needs two changes: a signal gate before rendering the draft section (showing a nudge instead of a generate button for unsignaled contacts, and hiding the draft section entirely for ARCHIVE contacts), and a signal badge injected above the draft textarea after successful generation. The badge reuses the established `signal-badge` CSS class and colors from `SIGNAL_ACTIONS` in `queue.js`.

No new backend infrastructure is needed. No database migrations are needed. No new Edge Functions are needed. This phase is purely: update the existing Edge Function prompt logic, update the PWA draft section rendering, and add badge CSS.

**Primary recommendation:** Gate in the PWA (simplest, already has `latest_signal` available from the `connections` table), add an optional server-side guard in the Edge Function as belt-and-suspenders, and build signal-aware prompt branches directly in `buildDraftPrompt()` using a switch/map on `queueItem.signal`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| OpenAI API (gpt-4o-mini) | Already configured | Draft generation | Already in use; `max_tokens: 300, temperature: 0.7` established |
| Supabase Edge Functions (Deno) | Already deployed | Server-side draft | OPENAI_API_KEY secret already set; deploy pattern established |
| Supabase JS client | @supabase/supabase-js@2 | PWA data reads | Already in use; `db.from('connections').select('*').eq('id', ...)` pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| SIGNAL_ACTIONS (queue.js) | Existing const | Badge colors/labels | Read `SIGNAL_ACTIONS[signal].color` and `.bg` for badge styling |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Single `buildDraftPrompt()` with signal branching | Separate prompt functions per signal | Single function is simpler; branching via a signal-to-prompt-config map keeps additions easy |
| PWA-only ARCHIVE guard | Edge Function ARCHIVE guard | Edge Function adds server-side safety; costs ~5 lines; worth it |

---

## Architecture Patterns

### Recommended Project Structure

No new files needed. All changes are in-place edits:

```
supabase/functions/draft/index.ts    # Add signal-aware buildDraftPrompt() branching
pwa/js/contact.js                    # Add signal gate + badge injection
pwa/css/app.css                      # Add .draft-signal-badge + .draft-signal-tooltip CSS
```

### Pattern 1: Signal-Aware Prompt Map in Edge Function

**What:** Replace generic prompt template with a signal-keyed configuration object inside `buildDraftPrompt()`. Each entry defines tone instructions, what user context to include, and what contact data to emphasize.

**When to use:** The queue item has a `signal` field; branch on it. Fall through to a conservative default if null (backward compatibility).

**Example:**
```typescript
// Source: derived from existing buildDraftPrompt() in supabase/functions/draft/index.ts
const SIGNAL_TONE_CONFIG: Record<string, {
  toneDirective: string;
  includeUserGoals: boolean;
  emphasizeContactData: boolean;
}> = {
  WARM_LEAD: {
    toneDirective: "Direct, confident, specific. Reference user goals naturally. Make a clear ask.",
    includeUserGoals: true,
    emphasizeContactData: false,
  },
  NURTURE: {
    toneDirective: "Warm, low-pressure, relationship-first. No ask. Just re-establishing contact.",
    includeUserGoals: false,
    emphasizeContactData: false,
  },
  VALUE_DROP: {
    toneDirective: "Lead with something specific to their industry or skills. Helpful, not salesy.",
    includeUserGoals: false,
    emphasizeContactData: true,
  },
  SYNERGY: {
    toneDirective: "Collaborative framing. Reference user goals. Mutual benefit angle.",
    includeUserGoals: true,
    emphasizeContactData: false,
  },
  RECONNECT: {
    toneDirective: "Nostalgic but forward-looking. Reference shared history if available. Warm re-entry.",
    includeUserGoals: false,
    emphasizeContactData: false,
  },
  FUTURE_PIVOT: {
    toneDirective: "Keep it light. No pressure. Just planting a seed. Very brief.",
    includeUserGoals: false,
    emphasizeContactData: false,
  },
  ARCHIVE: {
    toneDirective: "", // Should never reach here — reject at guard
    includeUserGoals: false,
    emphasizeContactData: false,
  },
};
```

### Pattern 2: ARCHIVE Guard in Edge Function

**What:** Early return with 400 error if the resolved queue item's signal is ARCHIVE, before reaching OpenAI.

**When to use:** After fetching queue item, before calling `buildDraftPrompt()`.

**Example:**
```typescript
// Belt-and-suspenders server-side guard
if (queueItem.signal === 'ARCHIVE') {
  return jsonResponse({ error: "Draft not available for archived contacts" }, 400);
}
```

### Pattern 3: PWA Signal Gate in `renderContact()`

**What:** Check `conn.latest_signal` before building `draftHtml`. Three cases: ARCHIVE (no draft section at all), null/undefined (nudge message), or valid signal (normal generate button).

**When to use:** In the `renderContact()` function where `draftHtml` is currently assembled.

**Example:**
```javascript
// Source: pwa/js/contact.js — extend existing draftHtml block
let draftHtml = '';
if (queueItemId) {
  const signal = conn.latest_signal;
  if (signal === 'ARCHIVE') {
    draftHtml = ''; // Hidden entirely — per CONTEXT.md decision
  } else if (!signal) {
    draftHtml = `
      <div class="detail-section" id="draft-section">
        <h3>Draft Message</h3>
        <div class="draft-no-signal">
          <p>Assign a signal for a tailored draft.</p>
          <a href="#/queue" class="btn btn-outline">Go to Queue</a>
        </div>
      </div>`;
  } else {
    draftHtml = `
      <div class="detail-section draft-area" id="draft-section">
        <h3>Draft Message</h3>
        <div style="text-align: center; margin: 16px 0;">
          <button class="btn btn-primary" onclick="generateDraft('${connectionId}', ${queueItemId})" id="generate-btn">
            Generate Draft
          </button>
        </div>
        <div id="draft-content" class="hidden">
          <div id="draft-signal-badge-area"></div>
          <div class="draft-box"><textarea id="draft-text" placeholder="Draft will appear here..."></textarea></div>
          <div class="draft-actions">
            <button class="btn btn-outline" onclick="copyDraft()">Copy</button>
            ${linkedinUrl ? `<a href="${escapeHtml(linkedinUrl.replace(/\/$/, ''))}/overlay/new-message/" target="_blank" class="btn btn-primary">Open LinkedIn DM</a>` : ''}
            ${email ? `<a href="mailto:${escapeHtml(email)}" class="btn btn-outline">Send Email</a>` : ''}
          </div>
        </div>
      </div>`;
  }
}
```

### Pattern 4: Signal Badge Injection After Draft Generation

**What:** After `generateDraft()` receives a successful response, inject a colored signal badge above the textarea. Badge reuses `.signal-badge` CSS class and SIGNAL_ACTIONS colors. Tooltip is a `title` attribute for simplicity (or a CSS tooltip via `data-tooltip`).

**When to use:** In the success branch of `generateDraft()`, after populating `draftText.value`.

**Example:**
```javascript
// Source: pwa/js/contact.js — extend generateDraft() success branch
if (result.draft) {
  draftText.value = result.draft;
  draftContent.classList.remove('hidden');
  btn.textContent = 'Regenerate';
  btn.disabled = false;

  // Inject signal badge above textarea
  const badgeArea = document.getElementById('draft-signal-badge-area');
  if (badgeArea && signal && SIGNAL_ACTIONS[signal]) {
    const info = SIGNAL_ACTIONS[signal];
    badgeArea.innerHTML = `
      <div class="draft-tone-badge" title="${escapeHtml(SIGNAL_TONE_TOOLTIPS[signal] || info.label)}">
        <span class="signal-badge" style="background:${info.bg};color:${info.color};">
          ${escapeHtml(info.label)} tone
        </span>
      </div>`;
  }
}
```

Note: `signal` is already available in `renderContact()` scope — the `generateDraft()` function needs to receive it as a parameter or read `conn.latest_signal` from closure/data attribute.

### Pattern 5: Goals Context in Prompt

**What:** The Edge Function already reads `profile.goals`. For WARM_LEAD and SYNERGY, also read `profile.current_projects` (added in Phase 9). Combine both into a goals context string passed to the prompt.

**When to use:** In `buildDraftPrompt()` for signals where `includeUserGoals: true`.

**Example:**
```typescript
// Combine both goals fields — already fetched in profile query
const userGoalsContext = [
  profile?.current_projects,
  profile?.goals
].filter(Boolean).join('\n').trim() || 'Professional network expansion';

// In prompt template for WARM_LEAD / SYNERGY:
`User's current focus:\n${userGoalsContext}\n\nWeave one of these naturally into the message.`
```

### Anti-Patterns to Avoid

- **Separate prompt functions per signal:** Creates 7 near-identical functions. Use a config map and a single template interpolation instead.
- **Reading signal from Edge Function response in PWA:** The PWA already has `conn.latest_signal` available before calling the Edge Function — no need to round-trip it. The PWA should read signal locally for badge display.
- **Stripping `goals` from non-WARM_LEAD/SYNERGY prompts entirely:** The existing prompt includes `profile.goals` — for non-goal-contextual signals, simply don't include the goals section rather than removing `profile.goals` from the fetch.
- **Tooltip via JS popup:** Vanilla tap tooltips are fine with CSS `title` attribute on mobile, or a CSS `::after` pseudo-element data attribute approach. Don't add a JS tooltip library.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Signal color lookup | Custom color map | `SIGNAL_ACTIONS[signal]` in queue.js | Already defined with `.color` and `.bg` per signal — use it |
| Goals context fetch | New DB query | `profile.current_projects` + `profile.goals` already in existing profile fetch | Profile already fetched in Edge Function; just read additional fields |
| Signal validation | Custom validator | `if (signal === 'ARCHIVE') return error` | Simple guard; no library needed |
| Tooltip behavior | JS tooltip library | CSS `title` attribute or `data-tooltip` with CSS `::after` | Zero dependencies; consistent with existing codebase pattern |

**Key insight:** Every data dependency (signal, enrichment, goals, user profile) is already fetched in the existing Edge Function. This phase is entirely prompt restructuring + gate logic, not data plumbing.

---

## Common Pitfalls

### Pitfall 1: `outreach_queue.signal` vs `connections.latest_signal`
**What goes wrong:** These are two different fields. `outreach_queue.signal` is set when the queue item was created/updated. `connections.latest_signal` is the current signal on the connection record. The PWA contact page uses `conn.latest_signal` (from the connections table), while the Edge Function uses `queueItem.signal` (from the queue item).
**Why it happens:** Both fields exist; it's easy to confuse them.
**How to avoid:**
- PWA gate: read `conn.latest_signal` (available in `renderContact()` from the connections fetch)
- Edge Function guard: read `queueItem.signal` (already fetched in the `outreach_queue` fetch)
- Signal badge: read `conn.latest_signal` from PWA-side data (already in scope in `renderContact()`)
**Warning signs:** Draft generates but badge shows wrong signal; ARCHIVE guard fires on wrong contacts.

### Pitfall 2: `generateDraft()` doesn't have access to `signal`
**What goes wrong:** The current `generateDraft(connectionId, queueItemId)` signature doesn't pass signal. The badge injection needs to know the signal to render the badge.
**Why it happens:** Signal was added to the connection model but `generateDraft()` was written before Phase 8.
**How to avoid:** Either pass `signal` as a third parameter to `generateDraft()`, or store it as a `data-signal` attribute on the generate button and read it inside the function. The data-attribute approach avoids changing the function signature.
**Example:**
```javascript
// In draftHtml button:
<button ... data-signal="${escapeHtml(signal)}" onclick="generateDraft('${connectionId}', ${queueItemId}, '${escapeHtml(signal)}')">

// In generateDraft():
async function generateDraft(connectionId, queueItemId, signal) { ... }
```

### Pitfall 3: ARCHIVE contacts can arrive on the contact page without a queue item
**What goes wrong:** A contact with `latest_signal === 'ARCHIVE'` can be accessed directly via `#/contact/{id}` without a queue item (no `?queue_item=` param). The ARCHIVE draft hide should apply regardless of whether `queueItemId` is present.
**Why it happens:** The existing draft section is already gated on `if (queueItemId)` — so ARCHIVE contacts accessed directly don't show a draft section anyway. But if a user navigates with a queue item param for an ARCHIVE contact, the draft section would appear without the gate.
**How to avoid:** Apply the ARCHIVE check at the outermost level: `if (queueItemId && conn.latest_signal !== 'ARCHIVE')` before building `draftHtml`.

### Pitfall 4: `profile.current_projects` may be null
**What goes wrong:** For WARM_LEAD/SYNERGY prompts that reference user goals, if `current_projects` is null (user hasn't set it), the prompt gets an empty goals section that weakens the draft.
**Why it happens:** `current_projects` was added in Phase 9 and may not be populated for all users.
**How to avoid:** Combine `profile.current_projects` and `profile.goals` with null-coalescing. If both are null, fall back to `profile?.goals || 'Professional network expansion'` (existing behavior). Don't fail the draft — degrade gracefully to goals-agnostic framing.

### Pitfall 5: Supabase Edge Function cold start on first deploy
**What goes wrong:** After deploying an updated Edge Function, the first few requests may fail or return stale behavior due to cold-start latency.
**Why it happens:** Deno runtime initialization on Supabase Edge Functions can take 1-3 seconds on first invocation after deploy.
**How to avoid:** After deploying, test with a single manual draft generation before declaring success. The existing error handling in `generateDraft()` shows "Failed — Try Again" and re-enables the button — user can simply retry.

---

## Code Examples

Verified patterns from existing codebase:

### Existing `buildDraftPrompt()` Signature (to be extended)
```typescript
// Source: supabase/functions/draft/index.ts (lines 124-205)
function buildDraftPrompt(
  connection: Record<string, unknown>,
  profile: Record<string, unknown> | null,
  channel: string,
): string {
  // ... existing extraction logic
  return `Generate a short, personalized ${channel} message...`;
}
```

The function already extracts: `headline`, `about`, `companyIndustry`, `skills`, `activityContext`, `convoContext`, `senderName`, `senderRole`, `senderCompany`, `senderGoals`, `contactName`, `contactRole`, `contactCompany`. Adding `signal` as a 4th parameter and `queueItem.signal_context` for optional context notes is straightforward.

### Existing Edge Function Call Site (add signal parameter)
```typescript
// Source: supabase/functions/draft/index.ts (line 78) — current
const prompt = buildDraftPrompt(connection, profile, channel);

// Updated — add signal and optional signal_context
const prompt = buildDraftPrompt(connection, profile, channel, queueItem.signal, queueItem.signal_context);
```

### Existing Signal Badge CSS (reuse verbatim)
```css
/* Source: pwa/css/app.css (lines 592-598) */
.signal-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
```

New `.draft-tone-badge` wrapper just needs `margin-bottom: 8px` to space it from the textarea.

### Existing SIGNAL_ACTIONS Colors (reuse for badge)
```javascript
// Source: pwa/js/queue.js (lines 3-11)
const SIGNAL_ACTIONS = {
  WARM_LEAD:    { label: 'Warm Lead',    cadence: 7,    color: '#1a7f37', bg: '#dcfce7' },
  NURTURE:      { label: 'Nurture',      cadence: 21,   color: '#0369a1', bg: '#e0f2fe' },
  VALUE_DROP:   { label: 'Value Drop',   cadence: 14,   color: '#7c3aed', bg: '#ede9fe' },
  SYNERGY:      { label: 'Synergy',      cadence: 14,   color: '#0a66c2', bg: '#e8f4fd' },
  RECONNECT:    { label: 'Reconnect',    cadence: 14,   color: '#92400e', bg: '#fef3c7' },
  FUTURE_PIVOT: { label: 'Future Pivot', cadence: 60,   color: '#6b7280', bg: '#f3f4f6' },
  ARCHIVE:      { label: 'Archive',      cadence: null, color: '#dc3545', bg: '#fee2e2' },
};
```

### Supabase CLI Deploy Command (verified pattern)
```bash
supabase functions deploy draft
```

---

## Signal Tone Design (Claude's Discretion)

Recommended prompt directives per signal — these are the planner's inputs for the actual prompt text:

| Signal | Tone | Uses User Goals | Uses Contact Enrichment | Draft Length |
|--------|------|-----------------|------------------------|--------------|
| WARM_LEAD | Direct, confident, specific ask | Yes (`current_projects` + `goals`) | No | Standard (3-4 LinkedIn, 4-5 email) |
| NURTURE | Warm, low-pressure, relationship-first, no ask | No | No | Short (2-3 sentences) |
| VALUE_DROP | Lead with contact-relevant value, grounded in their industry/skills | No | Yes (industry, skills, interests) |  Standard |
| SYNERGY | Collaborative, mutual benefit, weave in user goals | Yes (`current_projects` + `goals`) | No | Standard |
| RECONNECT | Nostalgic but forward-looking, reference shared history if available | No | No (but use `conversation_summary` if present) | Short-standard |
| FUTURE_PIVOT | Light touch, no pressure, plant a seed, very brief | No | No | Short (2-3 sentences) |
| ARCHIVE | Blocked — no draft | N/A | N/A | N/A |

### Recommended Tooltip Text Per Signal
| Signal | Tooltip |
|--------|---------|
| WARM_LEAD | Direct and specific — references your current goals |
| NURTURE | Warm and relationship-first — no ask, just reconnecting |
| VALUE_DROP | Value-led — grounded in their industry and work |
| SYNERGY | Collaborative — frames mutual benefit, references your goals |
| RECONNECT | Nostalgic — re-entry framing, references your shared history |
| FUTURE_PIVOT | Light touch — low-pressure, no ask |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Generic reconnect prompt (one-size-fits-all) | Signal-aware prompt branching (7 tones) | Phase 10 | Requires signal assignment before draft generation |
| Generate button always visible | Gate: nudge for no-signal, hidden for ARCHIVE | Phase 10 | Enforces triage-first workflow |

**Effectively retired after this phase:**
- The generic `buildDraftPrompt()` prompt template (replaced by signal-aware branching)
- The unconditional draft section render (replaced by signal gate)

---

## Open Questions

1. **Response format: include `signal_used` field or not?**
   - What we know: PWA already has `conn.latest_signal` in scope when rendering the contact page; no need to round-trip it through the Edge Function response
   - What's unclear: Whether the planner should add `signal_used` to the response for diagnostic logging purposes
   - Recommendation: PWA reads signal locally. No response format change needed. Keeps the response interface stable.

2. **`queueItem.signal` vs `connections.latest_signal` divergence**
   - What we know: These can differ if a signal was re-assigned after the queue item was created
   - What's unclear: Which should govern the draft tone?
   - Recommendation: Use `queueItem.signal` in the Edge Function (tone reflects intent when queue item was acted upon); use `conn.latest_signal` in the PWA gate (current state governs visibility). They should agree in the normal flow.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ |
| Config file | `pyproject.toml` (`[tool.ruff]` section only; pytest runs from project root) |
| Quick run command | `pytest tests/test_phase10_draft_tone.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERS-05 | `buildDraftPrompt()` generates WARM_LEAD-toned prompt with goals context | unit | `pytest tests/test_phase10_draft_tone.py::TestDraftTonePrompt::test_warm_lead_includes_goals -x` | Wave 0 |
| PERS-05 | `buildDraftPrompt()` generates NURTURE-toned prompt without user goals | unit | `pytest tests/test_phase10_draft_tone.py::TestDraftTonePrompt::test_nurture_excludes_goals -x` | Wave 0 |
| PERS-05 | `buildDraftPrompt()` generates VALUE_DROP prompt referencing contact enrichment | unit | `pytest tests/test_phase10_draft_tone.py::TestDraftTonePrompt::test_value_drop_references_enrichment -x` | Wave 0 |
| PERS-05 | ARCHIVE signal causes Edge Function to reject draft request (400) | unit | `pytest tests/test_phase10_draft_tone.py::TestArchiveGuard::test_archive_returns_400 -x` | Wave 0 |
| PERS-05 | All 7 signal keys produce non-empty distinct prompts | unit | `pytest tests/test_phase10_draft_tone.py::TestDraftTonePrompt::test_all_signals_produce_distinct_prompts -x` | Wave 0 |
| PERS-05 | No-signal fallback produces nudge HTML (PWA gate) | unit | `pytest tests/test_phase10_draft_tone.py::TestPWAGate::test_no_signal_nudge_html -x` | Wave 0 |

Note: Edge Function tests are Python unit tests that test the prompt construction logic directly (extracted as testable pure functions or tested via mock). The actual HTTP-level Edge Function behavior is a manual verification step (deploy + call).

### Sampling Rate
- **Per task commit:** `pytest tests/test_phase10_draft_tone.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase10_draft_tone.py` — covers PERS-05 (all 6 test cases above)
- [ ] No conftest changes needed — existing `conftest.py` with `mock_settings` fixture is sufficient

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `supabase/functions/draft/index.ts` — complete Edge Function implementation
- Direct code inspection: `pwa/js/contact.js` — complete contact page + draft flow implementation
- Direct code inspection: `pwa/js/queue.js` — SIGNAL_ACTIONS const with all 7 signal colors
- Direct code inspection: `pwa/css/app.css` — `.signal-badge`, `.draft-area`, `.draft-box` existing classes
- Direct code inspection: `src/database/models.py` — `OutreachQueueItem.signal`, `Connection.latest_signal`, `UserProfile.current_projects` + `goals` fields
- Direct code inspection: `src/services/signal_service.py` — canonical signal definitions and descriptions

### Secondary (MEDIUM confidence)
- Supabase Edge Function deploy pattern: established in phases 8-9 via `supabase functions deploy`
- OpenAI `gpt-4o-mini` at `max_tokens: 300, temperature: 0.7` — already configured and proven in existing draft function

### Tertiary (LOW confidence)
- None — all findings are grounded in direct code inspection of the actual codebase.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all existing
- Architecture: HIGH — all data already fetched; changes are additive edits to two files
- Pitfalls: HIGH — sourced from direct inspection of actual field names and function signatures
- Tone design: MEDIUM — prompt engineering quality depends on iteration; initial structure is sound

**Research date:** 2026-03-12
**Valid until:** Stable (no external dependencies; changes only in project-owned files)
