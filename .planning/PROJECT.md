# Reconnect: Actionable PWA + Rich Email Reports

## What This Is

A personal networking tool that imports, enriches, and scores professional contacts, then surfaces the best reconnection opportunities via a daily email digest and a web app. The system runs a daily pipeline (CLI @ 8AM via LaunchAgent) that scores contacts, computes dashboard intelligence, generates an actionable email digest, and syncs data to a PWA where you can triage contacts with intent signals, review enriched profiles, explore network demographics, and track your outreach pipeline. Signal assignments drive messaging tone, schedule follow-ups via cadence, and improve future scoring through feedback loops.

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
- ✓ Accurate score breakdowns (all 5 dimensions show real values) — v1.1
- ✓ Gmail OAuth send path with GCP credentials + App Password fallback — v1.1
- ✓ Queue sort by composite score (ascending/descending) — v1.1
- ✓ Queue filter by status (pending/approved/sent) — v1.1
- ✓ Queue filter by industry — v1.1
- ✓ Dashboard health score breakdown with actionable insights — v1.1
- ✓ Dashboard industry distribution chart — v1.1
- ✓ Dashboard role/seniority mix — v1.1
- ✓ Dashboard score tier distribution — v1.1
- ✓ `reconnect` CLI with Click (pipeline, queue, contacts, gmail, sync) — v1.1
- ✓ Streamlit UI + plotly dependencies fully removed — v1.1
- ✓ Email digest sends with "Review in App" CTA and signal-aligned vocabulary — v1.2
- ✓ Profile key factors show meaningful content with enrichment fallbacks — v1.2
- ✓ Conversation starters populated from enrichment data and scoring rationale — v1.2
- ✓ 7 intent signals (WARM_LEAD, NURTURE, VALUE_DROP, SYNERGY, RECONNECT, FUTURE_PIVOT, ARCHIVE) replace legacy triage — v1.2
- ✓ Signal-driven cadence re-queuing with age-based eligibility — v1.2
- ✓ User goals profile informing LLM scoring for WARM_LEAD identification — v1.2
- ✓ Contact notes (free-form, visible on queue cards + profile) — v1.2
- ✓ Signal-informed rescoring with safety guards (25-action min, ±40% cap, audit trail) — v1.2
- ✓ Draft tone adaptation (signal drives AI message tone via Edge Function) — v1.2
- ✓ Queue card enrichment (industry chip, key factor, last interaction, notes) — v1.2

### Active

(None — define next milestone requirements via `/gsd:new-milestone`)

### Out of Scope

- Native mobile app — PWA covers mobile use case via add-to-home-screen
- Real-time chat or messaging — not a communication tool, surfaces who to reach out to
- OAuth/social login for PWA — single-user tool, anon key + action tokens sufficient
- Draft outreach from email — email is for triage only; drafts handled in PWA contact page
- Bulk actions — let "Never Suggest" per contact handle this
- Push notifications — redundant with email (daily email IS the push notification)
- Calendar integration — daily email is the reminder mechanism
- Social graph visualization — impressive to demo, not useful in daily workflow
- Broader AI questions (life/personal) — start with professional enriched data only
- Multi-signal assignment per contact — one signal at a time keeps mental model simple
- Real-time signal processing — daily batch pipeline sufficient for single-user tool
- Signal-based auto-outreach — always human-in-the-loop

## Context

**Current State (post v1.2):**
- ~36,800 LOC across Python (13,550), JavaScript (20,922), TypeScript (718), CSS (1,068), HTML (524)
- Tech stack: Python + SQLModel + SQLite (local), Supabase PostgreSQL + PostgREST + Edge Functions (cloud), Vanilla JS PWA on Netlify, Click CLI
- 45 v1.0+v1.1+v1.2 requirements shipped and verified across 11 phases (3 milestones)
- Pipeline runs daily via LaunchAgent → `reconnect pipeline run`, email digest via Gmail OAuth, PWA live on Netlify
- Signal system: 7 intent signals with cadence re-queuing, draft tone adaptation, feedback-based rescoring
- 169 tests passed, 9 skipped, 0 failures

**Known Tech Debt:**
- `datetime.utcnow()` deprecated in Python 3.12+ (pre-existing, several files)
- Pydantic v2 `class Config` style deprecated in src/config.py
- `apply_signal()` and `backfill_skipped_signals()` orphaned in signal_service.py (PWA writes directly to PostgREST)
- `_get_data_health_stats()` and `_get_skip_pattern_insight()` uncalled in email_digest.py post-rebuild
- `tests/test_phase10_draft_tone.py` planned but never created (6 tests for PERS-05)
- Gmail OAuth GCP consent screen must be published (or add test user) before tokens work beyond 7 days
- outreach_queue.signal UPDATE permission unverified for anon role (table-level grant likely inherited)

**Potential v1.3+ Features:**
- Signal analytics on dashboard (distribution, trends over time)
- VALUE_DROP resource/link attachment before outreach
- Signal-driven email digest bucketing
- Configurable cadence per signal via CLI
- Per-contact cadence override
- AI contact search ("Who in my network knows about X?")
- Geographic distribution of contacts

## Constraints

- **Hosting**: PWA on Netlify, backend on Supabase — no additional infra
- **Email**: Must work in Gmail (mobile + desktop) — table-based HTML, no CSS flexbox
- **Auth**: Single-user tool — anon key + action tokens, no multi-tenant auth
- **Pipeline**: Daily batch (not real-time) — LaunchAgent @ 8AM via CLI
- **Budget**: Minimal — free tiers of Netlify + Supabase
- **Admin**: CLI-only — no web admin UI (Streamlit removed)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Netlify for PWA hosting | Proper SPA deployment, custom domain, CI/CD — Supabase Storage can't do SPA routing | ✓ Good — clean deploy, SPA redirect works |
| Gmail App Password + smtplib | Replaces unconfigured OAuth flow — 330 lines → 60 lines, no client ID needed | ✓ Good — email sending works reliably |
| GET/POST split on action Edge Function | Gmail scanners pre-fetch GET URLs — showing confirmation page on GET prevents token consumption | ✓ Good — scanner-safe, no false triggers |
| Query parameter deep links (not hash fragments) | Hash fragments stripped by Gmail redirect chain — query params survive | ✓ Good — email → PWA profile navigation works |
| Table-based email HTML | Gmail strips CSS flexbox on mobile — table role=presentation is bulletproof | ✓ Good — renders correctly on all clients |
| Email Yes auto-queues for outreach | Reduces friction — one tap to act, no extra steps | ✓ Good — streamlines daily triage |
| Profile page shows AI rationale | Transparency builds trust in scoring — user wants to know why | ✓ Good — 5-dimension breakdown is actionable |
| get_settings() at call time | Module-level singleton breaks monkeypatching — call-time pattern enables testing | ✓ Good — adopted across gmail.py and email_digest.py |
| raw_enrichment dual-key unwrap | Enrichment pipeline returns nested `data` wrapper or flat object — handle both | ✓ Good — defensive, no crashes on either shape |
| Client-side queue sort on reconnect_score | priority_score is stale/legacy; reconnect_score in joined connections row is the live composite | ✓ Good — accurate, no stale data |
| Client-side industry filter | raw_enrichment is JSON; PostgREST can't filter nested JSON without generated columns | ✓ Good — works for current data volume |
| OAuth tokens local-only | GmailCredentials never synced to Supabase — security boundary | ✓ Good — tokens stay on machine |
| OAuth-first with App Password fallback | is_oauth_configured() checked before is_gmail_configured() everywhere | ✓ Good — smooth migration path |
| Click CLI replacing Streamlit | Streamlit was broken (import crashes), CLI is lighter and automatable via LaunchAgent | ✓ Good — 9 commands cover all operations |
| Lazy imports in CLI commands | Heavy pipeline imports only loaded when command runs, keeps `reconnect --help` instant | ✓ Good — fast startup |
| Canonical SIGNAL_ACTIONS in signal_service.py | Single source of truth for 7 signals; PWA mirrors as JS const | ✓ Good — consistent behavior across Python/JS |
| PostgREST direct writes for signals/notes | No Edge Function needed — same pattern as user_feedback, anon grants sufficient | ✓ Good — simpler architecture |
| Cadence re-queuing via age-based eligibility | signal_assigned_at + cadence_days <= today — prevents cohort saturation | ✓ Good — distributed re-appearance |
| Feedback processor safety guards | 25-action min, ±40% cap, weight history logging — prevents runaway drift | ✓ Good — auditable, conservative |
| SIGNAL_TONE_CONFIG in Edge Function | Module-level const map keyed by signal name — readable, extensible, zero per-call allocation | ✓ Good — clean tone branching |
| ARCHIVE guard before DB reads | Early return avoids unnecessary profile/connection fetches for archived contacts | ✓ Good — efficient |
| Client-side signal filter | PostgREST cannot filter on embedded resource fields (connections.latest_signal) | ✓ Good — works for current volume |
| outreach_queue UPDATE keyed on itemId | Prevents multi-row update bug when connectionId matches multiple queue entries | ✓ Good — safe writes |

---
*Last updated: 2026-03-13 after v1.2 milestone*
