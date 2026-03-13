# Requirements: Reconnect

**Defined:** 2026-03-11
**Core Value:** When I get my morning email, I can quickly decide who to reconnect with, take action right there, and dig deeper into anyone who interests me — all without friction.

## v1.2 Requirements

Requirements for Intent-Driven Triage milestone. Each maps to roadmap phases.

### Email & Notifications

- [x] **EMAIL-01**: User receives daily email digest with contact recommendations via Gmail
- [x] **EMAIL-02**: Email digest includes "Review in App" CTA linking to PWA queue for signal assignment
- [x] **EMAIL-03**: Email action buttons use signal-aligned vocabulary (not legacy approve/skip/snooze)
- [x] **EMAIL-04**: Telegram notifications retained as backup for pipeline failure alerts

### Signal System

- [x] **SIG-01**: User can assign one of 7 intent signals to any queue contact (WARM_LEAD, NURTURE, VALUE_DROP, SYNERGY, RECONNECT, FUTURE_PIVOT, ARCHIVE)
- [x] **SIG-02**: Signal picker replaces legacy Reach Out / Skip / Snooze buttons on queue cards
- [x] **SIG-03**: Each signal assignment is stored with timestamp and persisted to Supabase
- [x] **SIG-04**: User can view signal history for a contact on their profile page
- [x] **SIG-05**: User can filter queue by assigned signal type
- [x] **SIG-06**: ARCHIVE signal hides contact from queue and dashboard (data preserved)

### Cadence & Re-queuing

- [x] **CAD-01**: Each signal defines a default cadence (days until contact reappears in queue)
- [x] **CAD-02**: Contacts with expired cadence automatically re-enter the daily queue
- [x] **CAD-03**: Re-queuing uses age-based eligibility to prevent cohort saturation

### Profile & Content

- [x] **PROF-01**: Profile key factors shows meaningful fallback content when enrichment data is sparse
- [x] **PROF-02**: Conversation starters generated from enrichment data and scoring rationale when activity_log is empty
- [x] **PROF-03**: User can add and edit free-form notes on any contact's profile
- [x] **PROF-04**: Contact notes visible on queue cards

### Personalization

- [x] **PERS-01**: User can define current projects and interests via a goals profile
- [x] **PERS-02**: User goals included in LLM scoring prompt for more relevant WARM_LEAD identification
- [x] **PERS-03**: Signal triage patterns adjust scoring dimension weights over time
- [x] **PERS-04**: Rescoring has safety guards (25-action minimum, ±40% multiplier cap, drift logging)
- [x] **PERS-05**: AI-generated draft messages adapt tone based on the assigned signal

### Queue UX

- [x] **QUX-01**: Queue cards show industry, first key factor, and last interaction date
- [x] **QUX-02**: Signal picker updates card in-place without removing it from the list

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
| EMAIL-01 | Phase 8 | Complete |
| EMAIL-02 | Phase 8 | Complete |
| EMAIL-03 | Phase 8 | Complete |
| EMAIL-04 | Phase 8 | Complete |
| SIG-01 | Phase 8 | Complete |
| SIG-02 | Phase 8 | Complete |
| SIG-03 | Phase 8 | Complete |
| SIG-04 | Phase 8 | Complete |
| SIG-05 | Phase 8 | Complete |
| SIG-06 | Phase 8 | Complete |
| CAD-01 | Phase 7 | Complete |
| CAD-02 | Phase 11 | Complete |
| CAD-03 | Phase 9 | Complete |
| PROF-01 | Phase 8 | Complete |
| PROF-02 | Phase 8 | Complete |
| PROF-03 | Phase 8 | Complete |
| PROF-04 | Phase 8 | Complete |
| PERS-01 | Phase 9 | Complete |
| PERS-02 | Phase 9 | Complete |
| PERS-03 | Phase 9 | Complete |
| PERS-04 | Phase 9 | Complete |
| PERS-05 | Phase 11 | Complete |
| QUX-01 | Phase 8 | Complete |
| QUX-02 | Phase 8 | Complete |

**Coverage:**
- v1.2 requirements: 24 total
- Satisfied: 22
- Pending (gap closure): 2 (PERS-05, CAD-02 → Phase 11)
- Unmapped: 0

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-13 — gap closure phase 11 added for PERS-05, CAD-02*
