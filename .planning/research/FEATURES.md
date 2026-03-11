# Feature Research

**Domain:** Personal networking CRM — v1.2 Intent-Driven Triage milestone
**Researched:** 2026-03-11
**Confidence:** HIGH (codebase direct analysis + verified against industry patterns)

---

## Context: What Already Exists (Not In Scope)

These features are fully built and working in v1.0 and v1.1. This document focuses only on
the new v1.2 capabilities:

**v1.0+v1.1 already built:**
- Queue with Reach Out / Skip / Snooze, sort by score, filter by status/industry
- Contact profile with AI scoring rationale (5 dimensions), key factors, conversation starters
- Email digest with featured contacts, action buttons (approve/skip/snooze via tokens)
- Dashboard with health score, industry distribution, role/seniority, score tiers
- CLI with pipeline, queue, contacts, gmail, sync commands
- Telegram pipeline notifications
- Bidirectional sync, action tokens, deep links from email to PWA

**v1.2 scope (everything below):**
- 7 interest signals replacing Reach Out / Skip / Snooze
- Signal-driven system actions (cadence re-queuing, tone matching, archive, tags)
- User goals profile (current projects/interests inform WARM_LEAD matching)
- Contact notes (free-form, visible on queue cards + profile)
- Signal-informed rescoring (triage patterns improve future scoring)
- Draft tone adaptation (signal drives AI message tone)
- Queue card enrichment (mini key-factors, industry, last interaction for informed triage)
- Email digest fix + Telegram backup
- Profile enrichment (key factors fallbacks, conversation starters from alternative sources)

---

## Table Stakes

Features that feel missing or broken without them — the v1.2 milestone is incoherent without these.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| 7 intent signals (WARM_LEAD, NURTURE, VALUE_DROP, SYNERGY, RECONNECT, FUTURE_PIVOT, ARCHIVE) | The milestone's core premise: qualitative "why" replaces binary reach-out/skip. Without signals, there's no intent layer at all | MEDIUM | New `interest_signal` column on `connections` table + queue card signal picker replaces current action buttons; `OutreachQueueItem.status` still used for workflow state |
| Signal-driven cadence re-queuing | Users expect signals to do something beyond labeling — NURTURE at 21 days, WARM_LEAD at 7 days, FUTURE_PIVOT at 60 days. Without this, signals are inert labels | MEDIUM | Cadence config per signal type stored in pipeline config or `UserPreference`; queue_generator exclusion logic reads signal + last queue date |
| Contact notes | Every non-trivial CRM has free-form notes per contact. Missing this feels primitive. Queue cards need context the user wrote themselves | LOW | `notes` column already exists on `Connection` model — only needs PWA wire-up (queue card inline + profile edit) |
| Queue card enrichment (industry, score, key factors) | Current cards show name + role + score. Without at least industry and one key factor, signal choice is uninformed — "why would I choose SYNERGY vs NURTURE for this person?" | LOW | Data already synced to Supabase. Queue card JS pulls `raw_enrichment` for industry; `score_reasoning` for first key factor. No new backend work |
| Email digest actually sends | Email is the primary interaction surface. Without delivery, the daily workflow breaks entirely | LOW | Config gap + broken OAuth fallback. Fix `email_digest.py` send path; ensure Telegram fires even when email fails |
| Profile key factors with fallbacks | When enrichment is sparse (no headline, no activity), key factors section is empty. Profile feels broken | LOW | `contact.js` needs fallbacks: connection_strength, location, message history, career path if enrichment fields are absent |

---

## Differentiators

Features that make the tool meaningfully smarter than a basic contact list with reminders.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| User goals profile (current projects/interests) | Scoring already uses `user_profile.goals` — adding structured "current projects" allows WARM_LEAD signal to match contacts against active initiatives, not just standing interests. Changes the scoring question from "who is generally relevant?" to "who can help with what I'm doing *right now*?" | MEDIUM | `UserProfile` already has `goals` (text) and `interests` (text). Add `current_projects` JSON array field. Update scoring prompt to weight goal_alignment dimension against current_projects in addition to standing goals. CLI `reconnect profile set-projects` |
| Signal-informed rescoring | Triage choices are implicit preferences. WARM_LEAD signals on contacts in fintech → boost `goal_alignment` for fintech contacts. ARCHIVE signals → suppress similar profiles. Currently `feedback_processor.py` does this with approve/skip patterns; signals make the feedback richer and more categorical | MEDIUM | Extend `feedback_processor.py` to read `interest_signal` history from `UserFeedback` (new `feedback_type: "interest_signal"`). Map signal → dimension weight adjustments. WARM_LEAD → boost goal_alignment + mutual_value; VALUE_DROP → reduce conversation_hooks; ARCHIVE → reduce all dimensions for similar role/industry |
| Draft tone adaptation | The current `generate_outreach_message()` in `prose.py` ignores relationship context. Tone should change: WARM_LEAD = excited and direct, NURTURE = warm and light-touch, SYNERGY = collaborative and peer-to-peer, RECONNECT = nostalgic and curious, FUTURE_PIVOT = exploratory. This meaningfully improves draft quality | MEDIUM | Pass `interest_signal` to `generate_outreach_message()`. Add signal → tone_instruction mapping dict. Inject tone instruction into the prose prompt. 5 new system prompt variants or one extended prompt with conditional instructions |
| Conversation starters from alternative sources | Currently `conversation_hooks` from `score_reasoning` are the only hooks. When activity_log is empty (most contacts), starters are missing. Adding career transitions, shared connections, industry events as fallback sources makes profiles actionable | LOW | Extract from `raw_enrichment`: job change date, previous company overlaps with user profile, education overlap. Use `score_reasoning.key_factors` when hooks are absent. No new LLM calls |
| Signal history visible on profile | Seeing "you tagged this person FUTURE_PIVOT 3 months ago" changes how you approach them. Intent context over time is more valuable than a single score | LOW | Query `UserFeedback` where `connection_id = X` and `feedback_type = "interest_signal"`. Display as a timeline of signal changes on the contact profile page |

---

## Anti-Features

Features that seem obviously good but create problems in this specific context.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Signal assignment from email digest (action buttons) | Feels natural to triage from email | Email action tokens support 3 fixed actions (approve/skip/snooze). 7 signals as email buttons = 7 tokens per contact, making digest HTML enormous and unmanageable in Gmail | Keep email digest for triage-by-feel (Warm / Skip / Snooze maps to WARM_LEAD / no signal / NURTURE cadence); use PWA for nuanced signal assignment. Email stays simple |
| Mandatory signal before queue action | "You must choose a signal to move this contact" | Friction kills daily triage velocity. The whole point is fast morning decisions | Make signal assignment optional. Default behavior (no signal chosen) maps to existing approve/skip/snooze semantics. Signals are enhancements, not gates |
| Real-time signal-to-score propagation | Signal changes immediately re-score contact | Real-time LLM rescoring is expensive and latency-heavy in a PWA. A WARM_LEAD signal should not trigger an OpenAI call on tap | Accumulate signal patterns in `UserFeedback`. Rescoring happens in daily pipeline feedback processing step. Near-real-time is fine for a single-user daily tool |
| Complex cadence editor UI in PWA | Power users want configurable cadences per signal | Cadence values (7, 21, 60 days) are reasonable defaults that won't need adjustment for most users. A cadence editor UI is a high-complexity PWA feature for minimal gain | Hard-code cadence defaults in pipeline config. If needed, expose via `reconnect profile set-cadence` CLI command in v1.3 |
| Multi-signal per contact (tag stacking) | Contacts could be both WARM_LEAD and SYNERGY | Multiple simultaneous signals create ambiguous tone adaptation logic and complex cadence scheduling. A contact has one primary intent | Enforce one active signal per contact. New signal assignment overwrites the previous. Signal history preserved in `UserFeedback` log for retrospective learning |
| Signal-based contact filtering in PWA | "Show me all WARM_LEAD contacts" | Adds another filter dimension to an already multi-filter queue UI. Current filters (status, industry, score) are sufficient for v1.2 | `reconnect contacts list --signal WARM_LEAD` CLI command covers the power-user case. PWA filter can come in v1.3 |

---

## Feature Dependencies

```
[7 Interest Signals — DB + PWA]
    └──required by──> [Signal-driven cadence re-queuing]
    └──required by──> [Draft tone adaptation]
    └──required by──> [Signal-informed rescoring]
    └──required by──> [Signal history on profile]

[Queue card enrichment]
    └──enables──> [Informed signal assignment]
    └──depends on──> [existing raw_enrichment sync to Supabase]

[Contact notes — PWA wire-up]
    └──independent──> (notes column exists; just needs UI)
    └──enhances──> [informed signal assignment on queue card]

[User goals profile — current_projects field]
    └──required by──> [WARM_LEAD signal matching in scoring]
    └──builds on──> [existing UserProfile.goals in scoring prompt]

[Signal-informed rescoring]
    └──depends on──> [7 Interest Signals — DB] (signals must be recorded in UserFeedback)
    └──extends──> [existing feedback_processor.py weight adjustment logic]

[Draft tone adaptation]
    └──depends on──> [7 Interest Signals — DB] (signal must be stored on connection or queue item)
    └──extends──> [existing generate_outreach_message() in prose.py]

[Email digest fix]
    └──independent──> (config gap + OAuth fallback issue; no signal dependencies)
    └──unblocks──> [daily workflow reliability]

[Profile key factors fallbacks]
    └──independent──> (frontend-only fix in contact.js)
    └──enhances──> [informed signal assignment] (better context = better signal choice)

[Conversation starters from alternative sources]
    └──independent──> (frontend data extraction from existing raw_enrichment)
    └──depends on──> [existing score_reasoning + raw_enrichment data]
```

### Dependency Notes

- **Signals must exist before everything else:** WARM_LEAD/NURTURE/etc. are the foundation of the whole milestone. The DB column, PWA signal picker, and `UserFeedback` logging must be built first — everything else in v1.2 extends them.
- **Queue card enrichment is a prerequisite for useful signal assignment:** Choosing SYNERGY vs NURTURE without knowing the contact's industry or relationship strength is guesswork. Enrich the card before asking for a signal.
- **Contact notes are independent but synergistic:** Notes don't depend on signals, but showing a note ("met at SaaStr, building fintech infra") on the queue card makes signal choice far more confident. Build together.
- **User goals profile extends existing scoring infrastructure:** `UserProfile.goals` already feeds the `goal_alignment` dimension. Adding `current_projects` is an additive change to the prompt — no scoring rubric rewrite needed.
- **Signal-informed rescoring builds on existing feedback_processor:** The pattern (skip/approve → weight adjustment) is already implemented. Extending it to read signal types is a targeted addition, not a rewrite.
- **Email digest fix is independent:** No signal dependencies. Fix it first to restore daily workflow reliability before building signal UX on top.

---

## Signal Taxonomy and Behavior

This is the core conceptual framework for v1.2.

### Signal Definitions and System Actions

| Signal | Intent | Tone (Draft) | Cadence Re-queue | System Action |
|--------|--------|--------------|-----------------|---------------|
| WARM_LEAD | Active opportunity — reaching out soon | Direct, energized, specific ask | 7 days | Generate draft immediately; boost goal_alignment in rescoring |
| NURTURE | Good contact, not urgent | Warm, light-touch, value-share | 21 days | Queue low-priority; no immediate draft needed |
| VALUE_DROP | Something valuable to share (article, intro, resource) | Helpful, generous, no ask | 14 days | Prompt: "what resource fits this person?" in queue card |
| SYNERGY | Mutual value / collaboration potential | Peer-to-peer, collaborative, "building together" | 30 days | No immediate action; track until clear ask crystallizes |
| RECONNECT | Lost touch; personal nostalgia | Warm, personal, reference shared history | 45 days | Pull conversation_summary as draft context |
| FUTURE_PIVOT | Relevant to a future goal, not current | Exploratory, light | 60 days | Low priority; surfaced when user updates current_projects |
| ARCHIVE | Not relevant now or in future | N/A | Never re-queued | Set `user_priority = "never"` equivalent; suppress from queue |

### Signal Storage Design

Signal is stored in two places:
1. **Active signal:** `connections.interest_signal` column (new). Current active signal drives cadence + tone.
2. **Signal history:** `user_feedback` table row with `feedback_type = "interest_signal"`, `extra_data = {"signal": "WARM_LEAD", "previous": "NURTURE"}`. Enables learning and profile timeline.

ARCHIVE signal writes `connections.user_priority = "never"` in addition to the signal assignment — this hooks into the existing queue exclusion rule.

---

## MVP Definition

### Launch With (v1.2 core — required for milestone coherence)

- [ ] 7 interest signals: DB column + PWA signal picker on queue cards — without this, nothing in v1.2 exists
- [ ] Signal storage in UserFeedback log — enables everything downstream (rescoring, history)
- [ ] Queue card enrichment: industry + first key factor + last interaction date — informed signal choice
- [ ] Contact notes: inline edit on queue card + display on profile — basic context for triage
- [ ] Signal-driven cadence re-queuing: queue_generator reads signal + cadence table — signals must do something
- [ ] Email digest fix: restore delivery reliability — daily workflow must work
- [ ] Profile key factors fallbacks: fill empty profiles — basic product quality

### Add After Core (v1.2 complete, same milestone)

- [ ] Draft tone adaptation: pass signal to generate_outreach_message() — improves draft quality once drafts are used
- [ ] Signal-informed rescoring: extend feedback_processor.py — compounds value over time
- [ ] User goals profile (current_projects field): adds context to WARM_LEAD matching — enhances WARM_LEAD precision
- [ ] Conversation starters from alternative sources: use career/education overlap as hooks — reduces empty-starters
- [ ] Signal history on contact profile: see past signals as timeline — retrospective value

### Future Consideration (v1.3+)

- [ ] Signal-based queue filter in PWA — "show me WARM_LEAD contacts only" — useful but not v1.2
- [ ] Configurable cadence per signal via CLI — defaults work for 90% of use cases
- [ ] Signal-driven email digest bucketing — "WARM_LEAD contacts first, then NURTURE" — complex digest redesign
- [ ] Signal analytics on dashboard — "signal distribution of your network" — v1.3 dashboard enhancement
- [ ] Resource prompt for VALUE_DROP — "suggest an article to share with this contact" — LLM integration

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Email digest fix | HIGH | LOW | P1 — daily workflow blocker |
| 7 interest signals (DB + PWA picker) | HIGH | MEDIUM | P1 — milestone foundation |
| Signal storage in UserFeedback log | HIGH | LOW | P1 — required by all downstream |
| Queue card enrichment | HIGH | LOW | P1 — prerequisite for informed signal choice |
| Contact notes (PWA wire-up) | HIGH | LOW | P1 — `notes` column exists; just needs UI |
| Signal-driven cadence re-queuing | HIGH | MEDIUM | P1 — signals must produce behavior |
| Profile key factors fallbacks | MEDIUM | LOW | P1 — basic product quality |
| Draft tone adaptation | HIGH | LOW | P2 — extends existing prose.py cleanly |
| Signal-informed rescoring | MEDIUM | MEDIUM | P2 — feedback_processor.py extension |
| User goals (current_projects) | MEDIUM | MEDIUM | P2 — incremental improvement to scoring |
| Conversation starters from alt sources | MEDIUM | LOW | P2 — frontend-only; high return on effort |
| Signal history on profile | LOW | LOW | P2 — retrospective, low complexity |
| Signal-based queue filter in PWA | LOW | MEDIUM | P3 — additive; CLI covers power-user case |
| Configurable cadence per signal (CLI) | LOW | LOW | P3 — defaults are good enough |

**Priority key:**
- P1: Must have for v1.2 — milestone is incomplete without it
- P2: Should have in v1.2 — adds compounding value, feasible in same milestone
- P3: Deferred to v1.3 — real value, but not required for v1.2 coherence

---

## Implementation Notes for Key Features

### Interest Signal Column

Minimal DB change: add `interest_signal` to `Connection` model.
```python
interest_signal: Optional[str] = Field(default=None, index=True)
# Values: "WARM_LEAD" | "NURTURE" | "VALUE_DROP" | "SYNERGY" | "RECONNECT" | "FUTURE_PIVOT" | "ARCHIVE" | NULL
interest_signal_at: Optional[datetime] = Field(default=None)
```
Migration: `ALTER TABLE connections ADD COLUMN interest_signal TEXT;`
Supabase migration file needed. Index on `interest_signal` for cadence queries.

### Queue Card Signal Picker

Replace current three action buttons (Reach Out / Skip / Snooze) with a two-row layout:
- Row 1: WARM_LEAD, NURTURE, VALUE_DROP, SYNERGY (primary intents)
- Row 2: RECONNECT, FUTURE_PIVOT, ARCHIVE (secondary intents) — collapsed by default on mobile

On signal tap:
1. PATCH `connections` table: `{ interest_signal: "WARM_LEAD", interest_signal_at: now }`
2. POST to `user_feedback`: `{ feedback_type: "interest_signal", connection_id, extra_data: { signal, previous_signal } }`
3. If WARM_LEAD: also PATCH `outreach_queue` status to "approved" → navigate to contact for draft
4. If ARCHIVE: also PATCH `connections.user_priority = "never"` → remove card from queue
5. Otherwise: remove card from queue (no status change needed unless NURTURE/etc. needs scheduling)

### Cadence Re-queuing Logic

In `queue_generator.py`, `is_contact_excluded()` already has the cooldown pattern. Extend it:

```python
SIGNAL_CADENCE_DAYS = {
    "WARM_LEAD": 7,
    "NURTURE": 21,
    "VALUE_DROP": 14,
    "SYNERGY": 30,
    "RECONNECT": 45,
    "FUTURE_PIVOT": 60,
    "ARCHIVE": None,  # Never re-queued
}
```

If `connection.interest_signal` is set and `connection.interest_signal_at` is within `SIGNAL_CADENCE_DAYS[signal]` days ago → exclude. If beyond cadence window → include (eligible to re-surface).

ARCHIVE signal → always excluded (same as `user_priority = "never"`).

### Draft Tone Adaptation

In `prose.py`, `generate_outreach_message()` currently ends with:
```python
"- {"Use casual tone for LinkedIn DM" if channel == "linkedin" else "Use professional but warm tone for email"}"
```

Add signal → tone mapping:
```python
SIGNAL_TONE_INSTRUCTIONS = {
    "WARM_LEAD": "Be direct and energized. You have a specific reason to connect. Make a clear soft ask.",
    "NURTURE": "Be warm but light-touch. No ask. Share value or check in briefly.",
    "VALUE_DROP": "Lead with something genuinely useful to them. Make it about them, not you.",
    "SYNERGY": "Peer-to-peer tone. Collaborative framing. Reference mutual interests or overlapping work.",
    "RECONNECT": "Reference shared history. Nostalgic, personal. Reconnect on something you had in common.",
    "FUTURE_PIVOT": "Exploratory tone. You're thinking about this space. Ask a curious question.",
}
```

Inject as an additional guideline in the prompt. No new LLM model or call pattern needed.

### Signal-Informed Rescoring Extension

In `feedback_processor.py`, add after existing skip/approval analysis:
```python
def _analyze_signal_patterns() -> dict:
    """Analyze which signal types dominate and which dimensions to reweight."""
    # Query UserFeedback where feedback_type = "interest_signal", last 60 days
    # Count WARM_LEAD signals per industry → boost goal_alignment for that industry
    # Count ARCHIVE signals per role keyword → reduce goal_alignment for that role
    # Return dimension adjustments: {"goal_alignment": 1.15, ...}
```

Conservative adjustments only (max ±20%). Requires minimum 5 signal actions before any adjustment fires (avoids thrash from a single session).

### Queue Card Enrichment Data Points

Three additions to the queue card HTML in `queue.js`:
1. **Industry chip:** `raw_enrichment.data.company_industry || raw_enrichment.companyIndustry` — already extracted in client-side filter logic; just render it as a pill
2. **First key factor:** `score_reasoning.key_factors[0]` — already in the connections join; truncate to 60 chars
3. **Last interaction:** `conn.last_message_date || conn.last_contacted_at` — format as "Last contacted: 3 months ago"

No new API calls. All data in the existing `outreach_queue + connections` join query.

---

## Sources

- Codebase direct analysis (HIGH confidence): `src/database/models.py`, `src/pipeline/queue_generator.py`, `src/pipeline/feedback_processor.py`, `src/llm/scoring.py`, `src/llm/prose.py`, `src/integrations/email_digest.py`, `pwa/js/queue.js`, `pwa/js/contact.js`
- `.planning/PROJECT.md` — v1.2 requirements, constraints, out-of-scope list (HIGH confidence)
- Personal CRM ecosystem patterns (MEDIUM confidence — WebSearch verified against multiple tools): Clay, Folk, Covve, Cloze cadence patterns; 14-21 day follow-up cadence as industry norm
- Intent signal taxonomy: domain-derived from the 7 named signals in PROJECT.md, behavior patterns from CRM triage research (MEDIUM confidence)

---

*Feature research for: Reconnect v1.2 Intent-Driven Triage milestone*
*Researched: 2026-03-11*
