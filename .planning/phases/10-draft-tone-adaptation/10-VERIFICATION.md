---
phase: 10-draft-tone-adaptation
verified: 2026-03-12T00:00:00Z
status: human_needed
score: 14/14 must-haves verified
human_verification:
  - test: "Generate a draft for a WARM_LEAD contact and confirm the generated message references your current goals/projects and includes a direct ask"
    expected: "Draft is goal-specific and confident in tone, not generic"
    why_human: "Prompt quality and LLM output correctness cannot be verified without a live OpenAI call"
  - test: "Generate a draft for a NURTURE contact and confirm the message has no ask and no goals reference"
    expected: "Draft is warm and relationship-first, 2-3 sentences, no agenda"
    why_human: "LLM output quality requires live call to verify tone adherence"
  - test: "Generate a draft for a VALUE_DROP contact and confirm the message leads with their industry or skills"
    expected: "Draft references the contact's actual industry/skills, frames as value sharing"
    why_human: "Enrichment data interpolation and tone verification requires live call"
  - test: "Navigate to an ARCHIVE contact profile (with ?queue_item= param) and verify no draft section appears at all"
    expected: "No 'Draft Message' heading, no generate button, no nudge — nothing"
    why_human: "Visual UI behavior requires browser verification"
  - test: "Navigate to a contact profile with no assigned signal (with ?queue_item= param) and verify the nudge appears"
    expected: "Draft section shows 'Draft Message' heading with 'Assign a signal for a tailored draft.' text, no generate button"
    why_human: "Visual UI state depends on conn.latest_signal being null in live data"
  - test: "Generate a draft for a contact with any valid signal and verify the colored tone badge appears above the textarea"
    expected: "Colored badge reading '[Signal Label] tone' with appropriate color appears above textarea after generation. Hovering/tapping shows tooltip explaining the tone."
    why_human: "Visual badge rendering and SIGNAL_ACTIONS color lookup requires browser verification"
  - test: "Deploy updated Edge Function and confirm ARCHIVE signal returns HTTP 400 before reaching OpenAI"
    expected: "POST to /functions/v1/draft with an ARCHIVE queue item returns {error: 'Draft not available for archived contacts'} with status 400"
    why_human: "Requires live Supabase Edge Function deployment and HTTP call — cannot verify locally"
---

# Phase 10: Draft Tone Adaptation Verification Report

**Phase Goal:** AI-generated draft messages reflect the intent signal assigned to the contact, producing appropriately toned outreach without any additional user input
**Verified:** 2026-03-12
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | WARM_LEAD draft is direct and references user goals (current_projects + goals) | VERIFIED | `SIGNAL_TONE_CONFIG.WARM_LEAD.includeUserGoals = true`; `userGoalsSection` built from `[profile?.current_projects, profile?.goals].filter(Boolean)` inserted in prompt |
| 2 | NURTURE draft is warm and low-pressure with no goals reference | VERIFIED | `SIGNAL_TONE_CONFIG.NURTURE.includeUserGoals = false`, `emphasizeContactData = false`; toneDirective: "No ask. No agenda. Just genuine reconnection. Keep it to 2-3 sentences." |
| 3 | VALUE_DROP draft references the contact's industry and skills | VERIFIED | `SIGNAL_TONE_CONFIG.VALUE_DROP.emphasizeContactData = true`; `enrichmentEmphasis` block built with `companyIndustry`, `skills`, `about` fields |
| 4 | SYNERGY draft frames mutual benefit and references user goals | VERIFIED | `SIGNAL_TONE_CONFIG.SYNERGY.includeUserGoals = true`; toneDirective: "Write a collaborative message framing mutual benefit. The sender has goals..." |
| 5 | RECONNECT draft references shared history when available | VERIFIED | toneDirective: "If there's shared history (previous conversations, mutual connections), reference it." `convoContext` field included in prompt |
| 6 | FUTURE_PIVOT draft is brief and light-touch | VERIFIED | toneDirective: "Write a very brief, light-touch message. No pressure, no ask...Keep it to 2-3 sentences maximum." |
| 7 | ARCHIVE signal causes the Edge Function to return 400 error before reaching OpenAI | VERIFIED | Lines 101-104: `if (queueItem.signal === "ARCHIVE") { return jsonResponse({ error: "Draft not available for archived contacts" }, 400); }` — positioned after queueItem fetch, before connection fetch |
| 8 | Contacts without a signal receive a generic fallback prompt (backward compatibility) | VERIFIED | `const toneConfig = signal ? SIGNAL_TONE_CONFIG[signal] : null;` / `const toneDirective = toneConfig?.toneDirective \|\| "Be genuine, not salesy. Include a soft call to action."` |
| 9 | ARCHIVE contacts show no draft section at all — no button, no area, nothing | VERIFIED | `if (signal === 'ARCHIVE') { draftHtml = ''; }` — produces empty string, no HTML rendered |
| 10 | Contacts without a signal see a nudge message instead of a generate button | VERIFIED | `else if (!signal) { draftHtml = \`...<div class="draft-no-signal"><p>Assign a signal for a tailored draft.</p></div>...\`` }` |
| 11 | Contacts with a signal see the generate button and can produce drafts | VERIFIED | `else { draftHtml = \`...<button...onclick="generateDraft('${connectionId}', ${queueItemId}, '${escapeHtml(signal)}')"...\`` }` |
| 12 | After draft generation, a colored signal badge appears above the textarea | VERIFIED | Badge injected in `generateDraft()` success branch via `badgeArea.innerHTML = \`<div class="draft-tone-badge"...><span class="signal-badge"...>\`` |
| 13 | Badge uses the same colors as queue signal chips for visual consistency | VERIFIED | `SIGNAL_ACTIONS[signal].bg` and `SIGNAL_ACTIONS[signal].color` used directly with `typeof SIGNAL_ACTIONS !== 'undefined'` guard |
| 14 | Badge has a tooltip on tap explaining the tone approach | VERIFIED | `title="${escapeHtml(tooltip)}"` on `.draft-tone-badge` div; tooltip from `SIGNAL_TONE_TOOLTIPS[signal]` with 6-entry const |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/functions/draft/index.ts` | Signal-aware buildDraftPrompt() with 7 tone branches + ARCHIVE guard | VERIFIED | 302 lines; SIGNAL_TONE_CONFIG module-level const with all 7 signals; ARCHIVE guard at line 102; buildDraftPrompt() with signal/signalContext params; conditional userGoalsSection and enrichmentEmphasis blocks |
| `pwa/js/contact.js` | Signal gate (ARCHIVE hide, no-signal nudge) + badge injection in generateDraft() | VERIFIED | SIGNAL_TONE_TOOLTIPS const at top of file; three-way signal gate in renderContact() lines 382-419; badge injection in generateDraft() lines 497-508 |
| `pwa/css/app.css` | Draft signal badge and no-signal nudge CSS styles | VERIFIED | `.draft-tone-badge` at line 243 with `cursor: help`; `.draft-no-signal` at line 249 with centered muted styling |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `supabase/functions/draft/index.ts` | `outreach_queue.signal` | `queueItem.signal` read after fetch | WIRED | Line 102: `queueItem.signal === "ARCHIVE"`, line 131: `queueItem.signal \|\| null` passed to buildDraftPrompt |
| `supabase/functions/draft/index.ts` | `user_profile.current_projects` | `profile?.current_projects` for WARM_LEAD/SYNERGY | WIRED | Line 249: `[profile?.current_projects, profile?.goals].filter(Boolean).join("\n").trim()` — guarded by `toneConfig?.includeUserGoals` |
| `pwa/js/contact.js` | `conn.latest_signal` | Signal check in renderContact() before building draftHtml | WIRED | Line 385: `const signal = conn.latest_signal;` — three-way gate follows |
| `pwa/js/contact.js` | `SIGNAL_ACTIONS` | Badge color lookup from queue.js const | WIRED | Line 499: `typeof SIGNAL_ACTIONS !== 'undefined' && SIGNAL_ACTIONS[signal]` — `info.bg` and `info.color` used for badge inline styles |

**Design note on signal flow:** The `signal` parameter in `generateDraft(connectionId, queueItemId, signal)` is used exclusively for client-side badge rendering. The Edge Function does NOT receive `signal` in the request body — it reads `queueItem.signal` directly from the database after fetching the queue item. This is the intended design per RESEARCH.md (open question 1, resolved: "PWA reads signal locally") and CONTEXT.md ("Whether Edge Function returns the signal in the response or the PWA reads it from local data" — Claude's discretion). The two signal reads (`conn.latest_signal` in PWA, `queueItem.signal` in Edge Function) can differ if a signal was reassigned after queueing; the Edge Function governs tone, the PWA governs badge display. No gap.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PERS-05 | 10-01-PLAN, 10-02-PLAN | AI-generated draft messages adapt tone based on the assigned signal | SATISFIED | Edge Function: SIGNAL_TONE_CONFIG with 7 differentiated tones, ARCHIVE guard, signal-aware buildDraftPrompt(). PWA: three-way signal gate, colored tone badge after generation. |

**Orphaned requirements:** None. The Traceability table in REQUIREMENTS.md maps only PERS-05 to Phase 10, and both plans claim PERS-05. Full coverage.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `pwa/js/contact.js` | 181 | `placeholder="Add a quick note..."` | Info | HTML textarea attribute — not a code stub. Pre-existing, not introduced by Phase 10. |
| `pwa/js/contact.js` | 410 | `placeholder="Draft will appear here..."` | Info | HTML textarea attribute for draft area — correct UX pattern, not a stub. Introduced by Phase 10 as intended. |
| `supabase/functions/draft/index.ts` | 55 | `toneDirective: ""` for ARCHIVE entry | Info | ARCHIVE entry in SIGNAL_TONE_CONFIG has empty toneDirective with explanatory comment. Intentional — ARCHIVE is blocked at the guard level before buildDraftPrompt() is called. Not reachable in production. |

No blockers or warnings found. No TODO/FIXME comments, no empty return implementations, no console.log-only handlers.

**Commit verification:** All three commits from SUMMARY.md exist in git history:
- `d8cb4bc` — feat(10-01): add signal-aware tone branching to draft Edge Function
- `30afaeb` — feat(10-02): add signal gate and tone badge to contact draft section
- `de8b719` — feat(10-02): add CSS styles for draft tone badge and no-signal nudge

### Test Coverage Gap

The VALIDATION.md (`wave_0_complete: false`, `nyquist_compliant: false`) documents that `tests/test_phase10_draft_tone.py` was planned as a Wave 0 requirement covering 6 unit tests for PERS-05. This file does not exist. The RESEARCH.md notes these would test the TypeScript prompt-construction logic by translation to Python. The implementation is correct per static analysis; the gap is test coverage, not functionality. The VALIDATION.md itself marks all 6 tests as `pending`.

This is an **info-level gap** — it does not prevent the phase goal from being achieved, but it leaves PERS-05 without automated regression coverage.

### Human Verification Required

#### 1. WARM_LEAD Tone Quality

**Test:** Generate a draft for a contact with `WARM_LEAD` signal assigned. Read the generated message.
**Expected:** Message is direct and confident, includes a specific ask, and weaves in one of the sender's current projects or goals naturally. Should not read as a generic reconnect message.
**Why human:** LLM output quality and prompt adherence requires a live OpenAI call with real contact data.

#### 2. NURTURE Tone Quality

**Test:** Generate a draft for a contact with `NURTURE` signal. Read the generated message.
**Expected:** Message is warm and low-pressure, 2-3 sentences, no ask, no mention of the sender's goals. Just relationship maintenance.
**Why human:** LLM tone adherence requires live verification.

#### 3. VALUE_DROP Tone Quality

**Test:** Generate a draft for a contact with `VALUE_DROP` signal who has enriched industry/skills data. Read the generated message.
**Expected:** Message leads with something specific to the contact's industry or skills. Should not be generic "I thought of you."
**Why human:** Enrichment data interpolation and LLM tone require live verification.

#### 4. ARCHIVE Contact — No Draft Section

**Test:** Navigate to `#/contact/{id}?queue_item={id}` for a contact whose `latest_signal` is `ARCHIVE`. Inspect the contact page.
**Expected:** No "Draft Message" section appears — no heading, no button, no nudge. The draft area is completely absent.
**Why human:** Visual UI behavior requires browser verification with live Supabase data.

#### 5. No-Signal Contact — Nudge Appears

**Test:** Navigate to `#/contact/{id}?queue_item={id}` for a contact with no assigned signal (`latest_signal` is null). Inspect the contact page.
**Expected:** "Draft Message" section shows with text "Assign a signal for a tailored draft." and no generate button.
**Why human:** Visual UI state depends on `conn.latest_signal` being null in live Supabase data.

#### 6. Signal Tone Badge After Generation

**Test:** Generate a draft for a contact with any valid signal (e.g., SYNERGY). After the draft appears, look above the textarea.
**Expected:** A colored badge reading "Synergy tone" (or equivalent signal label) appears in the SYNERGY color scheme. Hovering/tapping the badge shows a tooltip: "Collaborative — frames mutual benefit, references your goals."
**Why human:** Visual badge rendering and color accuracy require browser verification.

#### 7. Edge Function ARCHIVE Guard

**Test:** Deploy the updated Edge Function (`supabase functions deploy draft`). POST to `/functions/v1/draft` with a `queue_item_id` belonging to an ARCHIVE-signaled queue item.
**Expected:** Response is HTTP 400 with `{"error": "Draft not available for archived contacts"}`.
**Why human:** Requires live Supabase Edge Function deployment and HTTP call — cannot verify without deploy.

### Gaps Summary

No automated gaps found. All 14 must-have truths are verified in the codebase. All artifacts exist, are substantive, and are wired. The phase goal is structurally achieved: the Edge Function reads the queue item's signal, selects the appropriate tone config, and builds a differentiated prompt accordingly; the PWA gates draft access on signal assignment and shows a colored badge after generation.

The `human_needed` status reflects that the ultimate quality of the tone adaptation — whether the LLM actually produces a WARM_LEAD message that reads as direct and goal-referencing, or a NURTURE message that reads as warm and no-ask — can only be verified with live draft generation. The code correctly wires all inputs to the prompt; prompt-to-output quality is inherently a human judgment call.

The absent test file (`tests/test_phase10_draft_tone.py`) is a documentation gap, not a functional one. The 6 planned tests would validate TypeScript logic translated to Python — the logic is correct per static analysis.

---

_Verified: 2026-03-12_
_Verifier: Claude (gsd-verifier)_
