# Reconnect: Actionable PWA + Rich Email Reports

## What This Is

A personal networking tool that imports, enriches, and scores professional contacts, then surfaces the best reconnection opportunities via a daily email digest and a web app. The system runs a daily pipeline (CLI @ 8AM via LaunchAgent) that scores contacts, computes dashboard intelligence, generates an actionable email digest, and syncs data to a PWA where you can triage, review profiles, explore network demographics, and track your outreach pipeline.

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

### Active

<!-- v1.2 Intent-Driven Triage — see REQUIREMENTS.md for full REQ-IDs -->

- [ ] Email digest actually sends (fix config gap, keep Telegram as backup)
- [ ] Profile key factors show meaningful content with fallbacks when enrichment is sparse
- [ ] Conversation starters populated from alternative data sources (not just activity_log)
- [ ] 7 interest signals (WARM_LEAD, NURTURE, VALUE_DROP, SYNERGY, RECONNECT, FUTURE_PIVOT, ARCHIVE) replace Reach Out / Skip / Snooze
- [ ] Signal-driven system actions: cadence re-queuing, resource prompts, tone matching, tagging, archive
- [ ] User goals profile (current projects/interests inform WARM_LEAD identification)
- [ ] Contact notes (free-form, visible on queue cards + profile)
- [ ] Signal-informed rescoring (triage patterns improve future scoring)
- [ ] Draft tone adaptation (signal drives AI message tone)
- [ ] Queue card enrichment (mini key-factors, industry, last interaction for informed triage)

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

## Context

## Current Milestone: v1.2 Intent-Driven Triage

**Goal:** Replace score-only queue decisions with a qualitative signal system that captures *why* you'd reach out, drives messaging tone, schedules follow-ups, and learns from your patterns — while fixing email delivery and enriching sparse profiles.

**Target features:**
- Email digest fix + Telegram backup
- Profile enrichment (key factors fallbacks, conversation starters from alternative sources)
- 7 interest signals replacing Reach Out / Skip / Snooze
- Full signal system actions (cadence re-queuing, resource prompts, tone matching, archive, tags)
- User goals profile (current projects/interests inform matching)
- Contact notes (free-form, visible on queue + profile)
- Signal-informed rescoring (learning from triage patterns)
- Queue card enrichment (more context for informed signal choices)

**Current State (post v1.1):**
- ~12,800 LOC across Python (10,687 — pipeline, CLI, sync, services), JavaScript/CSS/HTML (2,131 — PWA)
- Tech stack: Python + SQLModel + SQLite (local), Supabase PostgreSQL + PostgREST + Edge Functions (cloud), Vanilla JS PWA on Netlify, Click CLI
- 35 v1.0+v1.1 requirements shipped and verified across 6 phases
- Pipeline runs daily via LaunchAgent → `reconnect pipeline run`, email digest via Gmail OAuth, PWA live on Netlify
- Streamlit admin UI fully replaced by `reconnect` CLI (5 command groups, 9 commands)

**Known Tech Debt:**
- `datetime.utcnow()` deprecated in Python 3.12+ (pre-existing, several files)
- Pydantic v2 `class Config` style deprecated in src/config.py
- Stale fallback URL `http://localhost:8501` in email_digest.py line 289 (never reached in production)
- Gmail OAuth GCP consent screen must be published (or add test user) before tokens work beyond 7 days
- Edge Function uses relative path `/functions/v1/action` (works but brittle)

**Potential v1.2+ Features:**
- AI contact search ("Who in my network knows about X?")
- Geographic distribution of contacts
- Company size tier distribution
- Pipeline controls in PWA admin panel

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

---
*Last updated: 2026-03-11 after v1.2 milestone started*
