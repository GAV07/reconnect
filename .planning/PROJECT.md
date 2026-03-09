# Reconnect: Actionable PWA + Rich Email Reports

## What This Is

A personal networking tool that imports, enriches, and scores professional contacts, then surfaces the best reconnection opportunities via a daily email digest and a web app. The system runs a daily pipeline (LaunchAgent @ 8AM) that scores contacts, generates an actionable email digest, and syncs data to a PWA where you can triage, review profiles, and track your outreach pipeline.

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
- ✓ PWA deployed on Netlify with SPA routing — v1.0
- ✓ Service worker with root-relative paths for Netlify — v1.0
- ✓ pwa_url config + all references updated to Netlify domain — v1.0
- ✓ Gmail App Password + smtplib email sending — v1.0
- ✓ Table-based email HTML for Gmail mobile compatibility — v1.0
- ✓ 44px+ tap targets, 16px+ font in email — v1.0
- ✓ Query parameter deep links surviving Gmail redirect chain — v1.0
- ✓ LinkedIn direct link in email digest — v1.0
- ✓ Yes auto-queues contact for outreach — v1.0
- ✓ GET/POST split prevents Gmail scanner token consumption — v1.0
- ✓ Contact profile with AI scoring rationale (5 dimensions) — v1.0
- ✓ Professional context, connection strength, enrichment fields on profile — v1.0
- ✓ Pipeline funnel view (imported → scored → reviewed → reached out → connected) — v1.0
- ✓ Enrichment status view — v1.0
- ✓ Feedback history view — v1.0
- ✓ Deep link bridge (query params → hash route) — v1.0

### Active

(None — next milestone requirements TBD via `/gsd:new-milestone`)

### Out of Scope

- Native mobile app — PWA covers mobile use case via add-to-home-screen
- Real-time chat or messaging — not a communication tool, surfaces who to reach out to
- OAuth/social login for PWA — single-user tool, anon key + action tokens sufficient
- Draft outreach from email — email is for triage only; drafts handled in PWA contact page
- Contact import in PWA — import is a pipeline concern; keep in Python pipeline / Streamlit
- Bulk actions — let "Never Suggest" per contact handle this
- Push notifications — redundant with email (daily email IS the push notification)
- Calendar integration — daily email is the reminder mechanism
- Social graph visualization — impressive to demo, not useful in daily workflow

## Context

**Current State (post v1.0):**
- ~6,200 LOC across Python (pipeline, sync, services), JavaScript (PWA), TypeScript (Edge Functions)
- Tech stack: Python + SQLModel + SQLite (local), Supabase PostgreSQL + PostgREST + Edge Functions (cloud), Vanilla JS PWA on Netlify
- All 18 v1.0 requirements shipped and verified
- Pipeline runs daily via LaunchAgent, email digest lands in Gmail, PWA live on Netlify

**Known Tech Debt:**
- `src/ui/views/review.py` references removed OAuth functions — Streamlit admin UI crashes on import
- `test_netlify_toml` test asserts no `command` but commit added echo build command
- Edge Function uses relative path `/functions/v1/action` (works but brittle)
- RLS status of Supabase tables unverified for public exposure

## Constraints

- **Hosting**: PWA on Netlify, backend on Supabase — no additional infra
- **Email**: Must work in Gmail (mobile + desktop) — table-based HTML, no CSS flexbox
- **Auth**: Single-user tool — anon key + action tokens, no multi-tenant auth
- **Pipeline**: Daily batch (not real-time) — LaunchAgent @ 8AM
- **Budget**: Minimal — free tiers of Netlify + Supabase

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Netlify for PWA hosting | Proper SPA deployment, custom domain, CI/CD — Supabase Storage can't do SPA routing | ✓ Good — clean deploy, SPA redirect works |
| Gmail App Password + smtplib | Replaces unconfigured OAuth flow — 330 lines → 60 lines, no client ID needed | ✓ Good — email sending works reliably |
| GET/POST split on action Edge Function | Gmail scanners pre-fetch GET URLs — showing confirmation page on GET prevents token consumption | ✓ Good — scanner-safe, no false triggers |
| Query parameter deep links (not hash fragments) | Hash fragments stripped by Gmail redirect chain — query params survive | ✓ Good — email → PWA profile navigation works |
| Table-based email HTML | Gmail strips CSS flexbox on mobile — table role=presentation is bulletproof | ✓ Good — renders correctly on all clients |
| Email Yes auto-queues for outreach | Reduces friction — one tap to act, no extra steps | ✓ Good — streamlines daily triage |
| No draft outreach from email | Keep email simple (triage only), handle drafts in PWA | ✓ Good — clear separation of concerns |
| Profile page shows AI rationale | Transparency builds trust in scoring — user wants to know why | ✓ Good — 5-dimension breakdown is actionable |
| get_settings() at call time | Module-level singleton breaks monkeypatching — call-time pattern enables testing | ✓ Good — adopted across gmail.py and email_digest.py |
| raw_enrichment dual-key unwrap | Enrichment pipeline returns nested `data` wrapper or flat object — handle both | ✓ Good — defensive, no crashes on either shape |

---
*Last updated: 2026-03-09 after v1.0 milestone*
