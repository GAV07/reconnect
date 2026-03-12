# Requirements: Reconnect

**Defined:** 2026-03-11
**Core Value:** When I get my morning email, I can quickly decide who to reconnect with, take action right there, and dig deeper into anyone who interests me — all without friction.

## v1.2 Requirements

Requirements for Intent-Driven Triage milestone. Each maps to roadmap phases.

### Email & Notifications

- [ ] **EMAIL-01**: User receives daily email digest with contact recommendations via Gmail
- [ ] **EMAIL-02**: Email digest includes "Review in App" CTA linking to PWA queue for signal assignment
- [ ] **EMAIL-03**: Email action buttons use signal-aligned vocabulary (not legacy approve/skip/snooze)
- [ ] **EMAIL-04**: Telegram notifications retained as backup for pipeline failure alerts

### Signal System

- [ ] **SIG-01**: User can assign one of 7 intent signals to any queue contact (WARM_LEAD, NURTURE, VALUE_DROP, SYNERGY, RECONNECT, FUTURE_PIVOT, ARCHIVE)
- [ ] **SIG-02**: Signal picker replaces legacy Reach Out / Skip / Snooze buttons on queue cards
- [ ] **SIG-03**: Each signal assignment is stored with timestamp and persisted to Supabase
- [ ] **SIG-04**: User can view signal history for a contact on their profile page
- [ ] **SIG-05**: User can filter queue by assigned signal type
- [ ] **SIG-06**: ARCHIVE signal hides contact from queue and dashboard (data preserved)

### Cadence & Re-queuing

- [ ] **CAD-01**: Each signal defines a default cadence (days until contact reappears in queue)
- [ ] **CAD-02**: Contacts with expired cadence automatically re-enter the daily queue
- [ ] **CAD-03**: Re-queuing uses age-based eligibility to prevent cohort saturation

### Profile & Content

- [ ] **PROF-01**: Profile key factors shows meaningful fallback content when enrichment data is sparse
- [ ] **PROF-02**: Conversation starters generated from enrichment data and scoring rationale when activity_log is empty
- [ ] **PROF-03**: User can add and edit free-form notes on any contact's profile
- [ ] **PROF-04**: Contact notes visible on queue cards

### Personalization

- [ ] **PERS-01**: User can define current projects and interests via a goals profile
- [ ] **PERS-02**: User goals included in LLM scoring prompt for more relevant WARM_LEAD identification
- [ ] **PERS-03**: Signal triage patterns adjust scoring dimension weights over time
- [ ] **PERS-04**: Rescoring has safety guards (25-action minimum, ±40% multiplier cap, drift logging)
- [ ] **PERS-05**: AI-generated draft messages adapt tone based on the assigned signal

### Queue UX

- [ ] **QUX-01**: Queue cards show industry, first key factor, and last interaction date
- [ ] **QUX-02**: Signal picker updates card in-place without removing it from the list

## Future Requirements

Deferred to v1.3+. Tracked but not in current roadmap.

### Signal Extensions

- **SIG-07**: VALUE_DROP signal prompts user to attach a resource/link before outreach
- **SIG-08**: Signal-driven email digest bucketing (group contacts by signal in digest)
- **SIG-09**: Signal analytics on dashboard (signal distribution, trends over time)

### Cadence Extensions

- **CAD-04**: Configurable cadence per signal via CLI
- **CAD-05**: Per-contact cadence override

### Personalization Extensions

- **PERS-06**: Signal-based queue filtering in CLI (`reconnect contacts list --signal WARM_LEAD`)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Multi-signal assignment per contact | One signal at a time keeps the mental model simple; latest signal is authoritative |
| 7 signal buttons in email digest | Token model limitation — email stays as triage notification, signals assigned in PWA |
| Real-time signal processing | Daily batch pipeline is sufficient for single-user tool |
| Signal-based auto-outreach | Always human-in-the-loop — signals inform, never auto-send |
| Native mobile app | PWA covers mobile use case |
| React/Vue rewrite for signal picker | 7 buttons in Vanilla JS, not a UI framework migration |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| EMAIL-01 | — | Pending |
| EMAIL-02 | — | Pending |
| EMAIL-03 | — | Pending |
| EMAIL-04 | — | Pending |
| SIG-01 | — | Pending |
| SIG-02 | — | Pending |
| SIG-03 | — | Pending |
| SIG-04 | — | Pending |
| SIG-05 | — | Pending |
| SIG-06 | — | Pending |
| CAD-01 | — | Pending |
| CAD-02 | — | Pending |
| CAD-03 | — | Pending |
| PROF-01 | — | Pending |
| PROF-02 | — | Pending |
| PROF-03 | — | Pending |
| PROF-04 | — | Pending |
| PERS-01 | — | Pending |
| PERS-02 | — | Pending |
| PERS-03 | — | Pending |
| PERS-04 | — | Pending |
| PERS-05 | — | Pending |
| QUX-01 | — | Pending |
| QUX-02 | — | Pending |

**Coverage:**
- v1.2 requirements: 24 total
- Mapped to phases: 0
- Unmapped: 24

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-11 after initial definition*
