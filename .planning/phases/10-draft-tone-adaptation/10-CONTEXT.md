# Phase 10: Draft Tone Adaptation - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

AI-generated draft messages reflect the intent signal assigned to the contact, producing appropriately toned outreach without any additional user input. ARCHIVE contacts have the draft button disabled. The existing draft flow for contacts without a signal is replaced with a nudge to assign a signal first.

</domain>

<decisions>
## Implementation Decisions

### Tone definitions per signal
- Each of the 7 signals produces a distinctly toned draft message via the Edge Function prompt
- Claude's discretion on the level of prompt specificity per signal (detailed guidance vs light hints)
- WARM_LEAD and SYNERGY drafts incorporate user goals context to make the ask more targeted
- Goals source: combine both `current_projects` (Phase 9 networking goals) and `goals` (generic field) in the prompt
- VALUE_DROP drafts reference the contact's enrichment data (industry, skills, interests) to suggest what kind of value might be relevant — not vague "I have something for you"
- FUTURE_PIVOT, NURTURE, RECONNECT: tone adapts but does not reference user goals (contact-focused)

### ARCHIVE draft blocking
- Hide the draft section entirely on ARCHIVE contact profiles — no button, no area, nothing
- Claude's discretion on whether to add an explicit `latest_signal === 'ARCHIVE'` guard in addition to the existing "no queue item = no button" behavior
- Claude's discretion on whether the Edge Function should also reject ARCHIVE draft requests server-side

### Draft UI signal feedback
- Show a colored signal badge above the draft textarea after generation (e.g., green chip "Warm Lead tone")
- Badge uses color from existing SIGNAL_ACTIONS const for visual consistency with queue signal chips
- Badge includes a brief tooltip on tap explaining the tone approach (e.g., "Direct and specific — references your goals")
- No badge shown if somehow no signal was used (shouldn't happen given the no-signal gate)
- Claude's discretion on whether the Edge Function returns the signal in the response or the PWA reads it from local data

### No-signal fallback
- Draft generation is gated on having an assigned signal — contacts without a signal cannot generate drafts
- Draft section shows a nudge: "Assign a signal for a tailored draft" instead of a generate button
- No "generate generic draft anyway" override — this forces the triage-before-draft workflow
- The current generic one-size-fits-all prompt is effectively retired once this phase ships

### Claude's Discretion
- Exact prompt text and structure for each of the 7 signal tones
- Level of detail in per-signal prompt guidance (some signals may need more specificity than others)
- Guard implementation details (PWA-only vs belt-and-suspenders with Edge Function)
- Whether Edge Function response format changes (adding signal_used field) or PWA reads signal locally
- Tooltip text for each signal badge
- How the "assign signal first" nudge integrates with the existing profile page layout

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `supabase/functions/draft/index.ts`: Full draft Edge Function with `buildDraftPrompt()` — needs signal-aware prompt branching. Already fetches queue item (has `signal` field), connection, and user profile.
- `pwa/js/queue.js`: `SIGNAL_ACTIONS` const with label, cadence, color, bg per signal — reuse colors for draft badge
- `pwa/js/contact.js`: `generateDraft()` function and draft section HTML builder — needs signal badge addition and no-signal gate
- `src/services/signal_service.py`: Canonical `SIGNAL_ACTIONS` dict with cadence_days, queue_status, priority_boost, description per signal

### Established Patterns
- Edge Function prompt construction: string template in `buildDraftPrompt()` with connection/profile data interpolation
- Signal chip styling: color-coded chips with `.signal-chip` class in queue cards (reuse pattern for draft badge)
- PostgREST reads: `db.from('table').select('*').eq('field', val)` for fetching signal data
- Queue item already has `signal` field (populated when signal assigned in Phase 8)

### Integration Points
- `supabase/functions/draft/index.ts`: Main change — `buildDraftPrompt()` reads `queueItem.signal` and branches prompt tone
- `pwa/js/contact.js`: Draft section builder — add signal badge above textarea, add no-signal gate logic
- `pwa/css/app.css`: Badge styling (reuse signal chip pattern from queue)
- `user_profile` table: `current_projects` and `goals` fields already exist — Edge Function reads via existing profile fetch

</code_context>

<specifics>
## Specific Ideas

- VALUE_DROP should feel like "I came across something relevant to your work in [their industry]" — grounded in their enrichment data, not generic
- WARM_LEAD + SYNERGY drafts weave in user's goals naturally ("I'm working on X and thought of you") rather than listing goals as a preamble
- The signal badge builds user trust in the system — they see the AI is adapting, not just generating the same message every time
- Requiring signal before draft reinforces the triage-first workflow that v1.2 is built around

</specifics>

<deferred>
## Deferred Ideas

- Signal-based email digest bucketing (group contacts by signal in email) — v1.3+ (SIG-08)
- VALUE_DROP prompting user to attach a resource/link before outreach — v1.3+ (SIG-07)
- Draft history / draft versioning per contact — future consideration
- Channel-specific tone adaptation beyond LinkedIn/email (e.g., Twitter DM, WhatsApp) — future consideration

</deferred>

---

*Phase: 10-draft-tone-adaptation*
*Context gathered: 2026-03-12*
