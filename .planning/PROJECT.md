# Reconnect v2: Actionable PWA + Rich Email Reports

## What This Is

A personal networking tool that imports, enriches, and scores professional contacts, then surfaces the best reconnection opportunities via a daily email digest and a web app. Currently the pipeline, scoring, and data sync work — but the PWA is broken (hosted as static files on Supabase Storage, not deployed as a real site) and the email digest is read-only. This milestone makes the whole system usable end-to-end: a real PWA on Netlify for daily triage and deeper exploration, plus actionable email reports that let you act without leaving your inbox.

## Core Value

When I get my morning email, I can quickly decide who to reconnect with, take action right there, and dig deeper into anyone who interests me — all without friction.

## Requirements

### Validated

- ✓ LinkedIn contact import and deduplication — existing
- ✓ RapidAPI/Hunter enrichment pipeline — existing
- ✓ LLM scoring rubric (goal alignment, industry overlap, mutual value, hooks, reach) — existing
- ✓ Outreach queue generation with exclusion rules — existing
- ✓ Daily pipeline orchestration (10 steps, LaunchAgent @ 8AM) — existing
- ✓ Bidirectional sync (local SQLite → Supabase PostgreSQL) — existing
- ✓ Edge Functions for action tokens (approve/skip/snooze) — existing
- ✓ Email digest HTML generation — existing
- ✓ Streamlit admin UI (contacts, dashboard, review, opportunities) — existing
- ✓ PWA code with hash-based router and offline support — existing (but not deployed)

### Active

- [ ] PWA properly deployed on Netlify with custom domain/subdomain
- [ ] PWA daily action hub: review today's queue, approve/skip/snooze contacts
- [ ] PWA contact profile page showing enriched data, AI scoring rationale, and connection strength
- [ ] PWA pipeline funnel view (imported → scored → reviewed → reached out → connected)
- [ ] PWA enrichment status view (which contacts have full data vs. need enrichment)
- [ ] PWA feedback history (past yes/no decisions, scoring accuracy over time)
- [ ] Email digest with Yes/No/Skip action buttons per contact
- [ ] Email "View full profile" links that open PWA contact detail page
- [ ] Email "Open LinkedIn" direct links per contact
- [ ] Email actions: "Yes" queues contact for outreach automatically
- [ ] Email mobile-responsive design (triage on phone, follow up on desktop)
- [ ] Netlify deployment configured correctly (pointing at `pwa/` directory from eg-connect repo)

### Out of Scope

- Native mobile app — PWA covers mobile use case
- Real-time chat or messaging — not a communication tool
- OAuth/social login for PWA — single-user tool, anon key is fine
- Draft outreach from email — action hub handles drafts, email is for triage
- Telegram notifications — email is the primary channel now

## Context

- Existing Netlify account linked to `eg-connect` repo but pointing at wrong directory — needs reconfiguration to serve `pwa/`
- PWA code exists in `pwa/` with hash-based routing, Supabase JS SDK, service worker — needs proper deployment and feature buildout
- Email digest generates HTML but Gmail OAuth not configured — need to either configure Gmail or find alternative send method
- Edge Functions already handle action tokens — email buttons can leverage existing `/functions/v1/action?token=UUID` pattern
- User consumes email on both mobile and desktop — responsive design is critical
- Scoring rationale (`score_reasoning` field) already exists on Connection model — needs surfacing in PWA and email
- Data like enrichment status, connection strength, professional context already stored — needs proper UI presentation

## Constraints

- **Hosting**: PWA on Netlify (not Supabase Storage) — needs proper SPA routing and deployment
- **Backend**: Keep Supabase for API/database/Edge Functions — Netlify is frontend only
- **Email**: Must work in Gmail (mobile + desktop) — HTML email compatibility constraints
- **Auth**: Single-user tool — no multi-tenant auth needed, anon key + action tokens sufficient
- **Pipeline**: Don't break existing daily pipeline — additive changes only

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Netlify for PWA hosting | Proper SPA deployment, custom domain, CI/CD — Supabase Storage can't do this | — Pending |
| Email Yes auto-queues for outreach | Reduces friction — one tap to act, no extra steps | — Pending |
| No draft outreach from email | Keep email simple (triage only), handle drafts in PWA | — Pending |
| Profile page shows AI rationale | Transparency builds trust in scoring — user wants to know why | — Pending |

---
*Last updated: 2026-03-08 after initialization*
