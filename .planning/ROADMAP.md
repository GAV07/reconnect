# Roadmap: Reconnect v2 — Actionable PWA + Rich Email Digests

## Overview

The pipeline, scoring, and data sync already work. Two blockers prevent end-to-end use: the PWA is stranded on Supabase Storage (no SPA routing), and the daily email digest generates correct HTML but cannot send. Phase 1 removes both blockers and makes the system live. Phase 2 hardens the email so token actions survive Gmail scanning and the layout holds on mobile. Phase 3 builds out the PWA surfaces that make daily triage and deeper contact review useful.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure Foundations** - Deploy PWA to Netlify, wire up Gmail sending, update config (completed 2026-03-08)
- [x] **Phase 2: Email Reliability** - Make email layout, actions, and deep links work correctly in Gmail (completed 2026-03-09)
- [ ] **Phase 3: PWA Feature Completeness** - Contact profiles, pipeline funnel, enrichment status, feedback history

## Phase Details

### Phase 1: Infrastructure Foundations
**Goal**: The PWA is live on Netlify and the daily email digest lands in the inbox
**Depends on**: Nothing (first phase)
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, EMAIL-01
**Success Criteria** (what must be TRUE):
  1. Navigating to the Netlify URL loads the PWA and deep links (e.g., `/#/contact/123`) resolve correctly
  2. The service worker registers without errors and pre-caches assets using correct Netlify-relative paths
  3. Running the daily pipeline sends an email digest to the inbox (visible in Gmail, not spam)
  4. All email links (View Profile, Open LinkedIn, action buttons) point to the Netlify domain, not Supabase Storage
**Plans:** 2/2 plans complete
Plans:
- [x] 01-01-PLAN.md — Config surgery + Gmail smtplib rewrite + test scaffold + package cleanup
- [x] 01-02-PLAN.md — Netlify deploy fix + service worker fix + email digest URL update + human verify

### Phase 2: Email Reliability
**Goal**: Email actions work correctly in Gmail on mobile and desktop without trust-breaking failures
**Depends on**: Phase 1
**Requirements**: EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05, EMAIL-06, EMAIL-07
**Success Criteria** (what must be TRUE):
  1. Opening the digest on Gmail mobile shows correct card layout (contact name and score badge side-by-side, not stacked)
  2. Tapping Yes/No/Skip buttons in Gmail on mobile triggers the correct action (44px+ tap targets, readable 16px+ font)
  3. Tapping "View full profile" from email opens the PWA on the correct contact page (not the homepage)
  4. Tapping "Open LinkedIn" goes directly to the contact's LinkedIn profile
  5. Tapping "Yes" in the email automatically queues the contact for outreach with no extra step required
  6. Gmail scanner pre-fetching the action URL does not consume the token or execute the action prematurely
**Plans:** 2/2 plans complete
Plans:
- [ ] 02-01-PLAN.md — Table-based email card HTML rewrite + tap targets + profile deep links + LinkedIn buttons
- [x] 02-02-PLAN.md — Edge Function GET/POST split + PWA deep link bridge + production deploy (deployed, awaiting human-verify)

### Phase 3: PWA Feature Completeness
**Goal**: The PWA surfaces the full enrichment and scoring data needed to review, triage, and track contacts
**Depends on**: Phase 2
**Requirements**: PROFILE-01, PROFILE-02, PROFILE-03, PROFILE-04, VIEW-01, VIEW-02, VIEW-03, VIEW-04
**Success Criteria** (what must be TRUE):
  1. Opening a contact profile page shows the AI scoring rationale broken down by dimension (Goal Alignment, Industry Overlap, Mutual Value, Conversation Hooks, Network Reach)
  2. The contact profile page shows professional context (role, company, industry), connection strength (how we know each other), and all enrichment fields (location, headline, email status, LinkedIn URL)
  3. The pipeline funnel view shows a count of contacts at each stage (imported → scored → reviewed → reached out → connected)
  4. The enrichment status view shows which contacts have full data and which need more enrichment
  5. Clicking an email deep link (e.g., `?view=contact&id=123`) opens the PWA and navigates to the correct contact page
**Plans:** 2/3 plans executed
Plans:
- [ ] 03-01-PLAN.md — Backend data layer update (funnel counts in dashboard snapshot) + test scaffold
- [ ] 03-02-PLAN.md — Contact profile sections (professional context, connection strength, enrichment status)
- [ ] 03-03-PLAN.md — Dashboard funnel + enrichment status views + feedback history + deploy + human verify

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure Foundations | 2/2 | Complete   | 2026-03-09 |
| 2. Email Reliability | 2/2 | Complete   | 2026-03-09 |
| 3. PWA Feature Completeness | 2/3 | In Progress|  |
