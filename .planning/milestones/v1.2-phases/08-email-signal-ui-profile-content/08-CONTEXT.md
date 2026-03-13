# Phase 8: Email + Signal UI + Profile Content - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can triage contacts via 7 intent signals in the PWA, receive a daily email that directs them to the app, and see meaningful content on every profile regardless of enrichment completeness. This phase replaces the legacy Approve/Skip/Snooze interaction model with the signal system built in Phase 7.

</domain>

<decisions>
## Implementation Decisions

### Email digest redesign
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

### Signal picker interaction
- Queue cards show a single "Assign Signal" tap area (collapsed by default)
- Tapping expands an inline picker with 7 color-coded chips with short labels
- Chips fit 3-4 per row on mobile (e.g. green "Warm Lead", blue "Nurture")
- After assigning a signal: signal badge appears on the card, card stays in place (no removal, no dimming)
- User can reassign by tapping again to change signal
- ARCHIVE signal hides contact from queue and dashboard (per spec, sets user_priority "never")
- PostgREST direct write to contact_signals + connection update (no new Edge Function — decided in Phase 7)

### Queue filtering and default view
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

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/integrations/email_digest.py`: Full HTML email generation with `_build_digest_html()`, `_extract_why_today()` — needs modification to remove action buttons and add signal vocabulary
- `src/integrations/gmail.py`: `send_html_email()` + `oauth_send_html_email()` — ready to use
- `src/services/signal_service.py`: `SIGNAL_ACTIONS` dict with all 7 signals, `apply_signal()` function — canonical source, PWA mirrors as JS const
- `src/api/tokens.py`: `create_action_tokens()` — will no longer be called for email (action buttons removed)
- `pwa/js/queue.js`: Queue card rendering with `queueAction()`, status filters, industry filter, realtime subscription
- `pwa/js/contact.js`: Profile page with score breakdown, key factors, conversation starters, draft generation
- `pwa/css/app.css`: `.queue-card`, `.btn-primary`, `.score-badge`, `.why-today`, `.card-actions` classes

### Established Patterns
- Supabase PostgREST: `db.from('table').select('*').eq('field', val)` for reads, `.update()` / `.insert()` for writes
- Optimistic UI: card opacity reduction → API call → restore on success/error
- Realtime: `db.channel().on('postgres_changes', ...)` for live updates
- HTML escaping: `escapeHtml()` function in PWA for XSS prevention
- Email HTML: table-based layout with `role="presentation"`, 44px+ tap targets, 16px+ font

### Integration Points
- `pwa/js/queue.js`: Replace 3 action buttons with signal picker expand/collapse
- `pwa/js/contact.js`: Add contact notes display, signal history, notes editing
- `src/integrations/email_digest.py`: Rebuild HTML template — remove action buttons, add Review in App CTA, add industry to cards
- `src/pipeline/daily_pipeline.py`: Ensure `send_digest_email()` is called in pipeline
- `supabase/functions/action/index.ts`: Email action Edge Function may need vocabulary update for confirmation page
- `contact_signals` table: PWA reads via PostgREST, writes via PostgREST (anon grants exist from Phase 7 migration)
- `contact_notes` table: PWA reads/writes via PostgREST (anon grants exist from Phase 7 migration)

</code_context>

<specifics>
## Specific Ideas

- Email should feel like a morning briefing — "here's who you should look at today" — not a decision surface
- Signal chips should be immediately recognizable by color — user builds muscle memory over time
- Queue default to untriaged keeps daily triage focused — "work through these, then you're done"

</specifics>

<deferred>
## Deferred Ideas

- Signal-based email digest bucketing (group contacts by signal in email) — v1.3+ (SIG-08)
- Signal analytics on dashboard (distribution, trends) — v1.3+ (SIG-09)
- Per-contact cadence override — v1.3+ (CAD-05)
- Separate "signaled contacts" page/view beyond queue filter — future consideration

</deferred>

---

*Phase: 08-email-signal-ui-profile-content*
*Context gathered: 2026-03-11*
