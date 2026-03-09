# Requirements: Reconnect v1.1

**Defined:** 2026-03-09
**Core Value:** When I get my morning email, I can quickly decide who to reconnect with, take action right there, and dig deeper into anyone who interests me — all without friction.

## v1.1 Requirements

Requirements for v1.1 Network Intelligence milestone. Each maps to roadmap phases.

### Infrastructure

- [ ] **INFRA-01**: User can send daily email digest via Gmail OAuth using GCP JSON credentials
- [x] **INFRA-02**: User can see accurate score breakdowns on contact profiles (all 5 dimensions show real values, not 0)

### Queue UX

- [x] **QUEUE-01**: User can sort queue contacts by composite score (ascending/descending)
- [x] **QUEUE-02**: User can filter queue by status (pending, approved, sent)
- [x] **QUEUE-03**: User can filter queue by industry

### Dashboard Intelligence

- [ ] **DASH-01**: User can see health score breakdown showing what drives the score with actionable insights
- [ ] **DASH-02**: User can see industry distribution across enriched contacts
- [ ] **DASH-03**: User can see role/seniority mix across enriched contacts
- [ ] **DASH-04**: User can see score tier distribution across contacts

### CLI + Streamlit Removal

- [ ] **CLI-01**: User can run pipeline operations via CLI (pipeline run, queue reset, queue stats, contacts import, contacts score, gmail auth, sync push/pull)
- [ ] **CLI-02**: Streamlit UI and dependencies fully removed after CLI parity confirmed

## v1.2+ Requirements

Deferred to future release. Tracked but not in current roadmap.

### AI Search

- **SEARCH-01**: User can ask natural language questions about their network ("Who knows about X?")
- **SEARCH-02**: Search results link to contact profiles with match reasoning

### Demographics

- **DEMO-01**: User can see geographic distribution of contacts
- **DEMO-02**: User can see company size tier distribution

### Pipeline Controls

- **PIPE-01**: User can trigger pipeline operations from PWA admin panel

## Out of Scope

| Feature | Reason |
|---------|--------|
| Native mobile app | PWA covers mobile use case via add-to-home-screen |
| Real-time chat/messaging | Not a communication tool, surfaces who to reach out to |
| OAuth/social login for PWA | Single-user tool, anon key + action tokens sufficient |
| Push notifications | Daily email IS the push notification |
| Calendar integration | Daily email is the reminder mechanism |
| Social graph visualization | Impressive to demo, not useful in daily workflow |
| Score weight tuning UI | Feedback processor handles weights; UI is cosmetic overhead |
| Broader AI questions (life/personal) | Start with professional enriched data only |
| Company size demographics | Not selected for v1.1 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 4 | Pending |
| INFRA-02 | Phase 4 | Complete |
| QUEUE-01 | Phase 4 | Complete |
| QUEUE-02 | Phase 4 | Complete |
| QUEUE-03 | Phase 4 | Complete |
| DASH-01 | Phase 5 | Pending |
| DASH-02 | Phase 5 | Pending |
| DASH-03 | Phase 5 | Pending |
| DASH-04 | Phase 5 | Pending |
| CLI-01 | Phase 6 | Pending |
| CLI-02 | Phase 6 | Pending |

**Coverage:**
- v1.1 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 after roadmap creation*
