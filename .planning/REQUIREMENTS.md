# Requirements: Reconnect v2

**Defined:** 2026-03-08
**Core Value:** When I get my morning email, I can quickly decide who to reconnect with, take action right there, and dig deeper into anyone who interests me — all without friction.

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Deployment

- [ ] **DEPLOY-01**: PWA deployed on Netlify with `publish = "pwa"` directory and SPA redirect rule (`/* → /index.html 200`)
- [ ] **DEPLOY-02**: Service worker BASE path fixed for Netlify (no longer computes path from Supabase Storage URL)
- [x] **DEPLOY-03**: `pwa_url` config variable added to `.env` and `src/config.py`, all email/Edge Function references updated from Supabase Storage URL to Netlify URL

### Email Delivery

- [x] **EMAIL-01**: Email digest sends via Gmail App Password + `smtplib` (replaces unconfigured OAuth flow)
- [ ] **EMAIL-02**: Email card layout uses table-based HTML (not Flexbox) for Gmail mobile compatibility
- [ ] **EMAIL-03**: Email action buttons are 44px+ tap targets with 600px max-width and 16px+ font
- [ ] **EMAIL-04**: "View full profile" links use query parameters (`?view=contact&id=123`) that survive Gmail's redirect chain
- [ ] **EMAIL-05**: "Open LinkedIn" direct link included per contact in email digest
- [ ] **EMAIL-06**: "Yes" action auto-queues contact for outreach (no extra step needed)
- [ ] **EMAIL-07**: Action Edge Function uses GET/POST split — GET shows confirmation page, POST executes action — preventing Gmail scanner token consumption

### PWA Profile

- [ ] **PROFILE-01**: Contact profile page displays AI scoring rationale with dimension breakdown (Goal Alignment, Industry Overlap, Mutual Value, Conversation Hooks, Network Reach)
- [ ] **PROFILE-02**: Contact profile page shows professional context (current role, company, industry, career trajectory)
- [ ] **PROFILE-03**: Contact profile page shows connection strength (how you know them, mutual connections, last interaction)
- [ ] **PROFILE-04**: Contact profile page surfaces full enrichment fields (location, headline, email status, LinkedIn URL)

### PWA Views

- [ ] **VIEW-01**: Pipeline funnel view showing contact flow: imported → scored → reviewed → reached out → connected
- [ ] **VIEW-02**: Enrichment status view showing which contacts have full data vs. need more enrichment
- [ ] **VIEW-03**: Feedback history view showing past yes/no decisions and scoring accuracy over time
- [ ] **VIEW-04**: PWA reads query parameters on load and navigates to correct hash route (email deep link bridge)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Security

- **SEC-01**: RLS audit on all Supabase tables — verify row-level security before public exposure
- **SEC-02**: Action token expiry validation hardened (multi-use safe or confirmation-protected)

### Polish

- **POLISH-01**: PWA manifest `start_url` and `scope` corrected for Netlify domain
- **POLISH-02**: Service worker cache versioning strategy for Netlify deploys
- **POLISH-03**: Score rationale preview (1-2 hooks) shown directly in email contact cards
- **POLISH-04**: "View full queue" link in email footer opens PWA queue page

## Out of Scope

| Feature | Reason |
|---------|--------|
| Draft outreach from email | Email is for triage only; drafts handled in PWA contact page |
| OAuth / multi-user auth for PWA | Single-user tool; anon key + action tokens sufficient |
| Native mobile app | PWA covers mobile use case via add-to-home-screen |
| Real-time chat / messaging | Not a communication tool — surfaces who to reach out to, not how |
| Contact import in PWA | Import is a pipeline concern; keep in Python pipeline / Streamlit |
| Bulk actions | Let "Never Suggest" per contact handle this; skip patterns surface it |
| Push notifications | Redundant with email — daily email IS the push notification |
| Calendar integration | Out of scope; daily email is the reminder mechanism |
| Social graph visualization | Impressive to demo, not useful in daily workflow |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEPLOY-01 | Phase 1 | Pending |
| DEPLOY-02 | Phase 1 | Pending |
| DEPLOY-03 | Phase 1 | Complete |
| EMAIL-01 | Phase 1 | Complete |
| EMAIL-02 | Phase 2 | Pending |
| EMAIL-03 | Phase 2 | Pending |
| EMAIL-04 | Phase 2 | Pending |
| EMAIL-05 | Phase 2 | Pending |
| EMAIL-06 | Phase 2 | Pending |
| EMAIL-07 | Phase 2 | Pending |
| PROFILE-01 | Phase 3 | Pending |
| PROFILE-02 | Phase 3 | Pending |
| PROFILE-03 | Phase 3 | Pending |
| PROFILE-04 | Phase 3 | Pending |
| VIEW-01 | Phase 3 | Pending |
| VIEW-02 | Phase 3 | Pending |
| VIEW-03 | Phase 3 | Pending |
| VIEW-04 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-08*
*Last updated: 2026-03-08 after roadmap creation*
