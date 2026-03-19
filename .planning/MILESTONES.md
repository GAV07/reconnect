# Milestones

## v1.3 Contact Discovery (Shipped: 2026-03-19)

**Phases completed:** 3 phases, 6 plans, 12 tasks
**Timeline:** 4 days (2026-03-16 → 2026-03-19)
**Code:** 40 files changed, +6,845 / -54 lines
**Git range:** feat(12-01) → feat(14-02)

**Key accomplishments:**
- Enrichment schema extraction — 7 queryable columns (industry, headline, city, country, school, seniority, education_text) with SQLite migration helper, extraction/backfill module, and Supabase migration
- Pipeline wiring — enrichment extraction at enrichment time, gap-fill step in daily pipeline, CLI stats and backfill commands, 19 tests
- Contacts browse page — 4-tab bottom nav, server-side PostgREST filtering (role/industry/city), 50-item pagination, contact cards with score/signal badges
- Full-text search — tsvector + GIN migration, multi-field search bar with textSearch primary path, ilike fallback, 300ms debounce, search-aware count banner and empty state

---

## v1.2 Intent-Driven Triage (Shipped: 2026-03-13)

**Phases completed:** 5 phases, 12 plans, 9 tasks

**Timeline:** 3 days (2026-03-11 → 2026-03-13)
**Code:** 78 files changed, +16,097 / -1,867 lines
**Git range:** feat(07-01) → feat(11-01)

**Key accomplishments:**
- Signal foundation — 7 intent signals (WARM_LEAD, NURTURE, VALUE_DROP, SYNERGY, RECONNECT, FUTURE_PIVOT, ARCHIVE) with schema, service, migration, and bidirectional sync
- Email digest rebuilt — "Review in App" CTA, signal-aligned vocabulary, industry chips, deep link to PWA queue
- Profile enrichment — key factors/conversation starters fallbacks from enrichment data, contact notes, signal history UI
- User goals profile — current projects/interests inform LLM scoring prompt for better WARM_LEAD identification
- Cadence re-queuing — automatic contact re-appearance based on signal cadence timing with age-based eligibility
- Signal-informed rescoring — triage patterns adjust scoring weights with safety guards (25-action min, +/-40% cap, audit trail)
- Draft tone adaptation — Edge Function produces signal-aware AI messages (7 tone branches + ARCHIVE guard)

---

## v1.1 Network Intelligence (Shipped: 2026-03-10)

**Phases completed:** 3 phases, 7 plans, 13 tasks
**Timeline:** 1 day (2026-03-09 → 2026-03-10)
**Code:** 58 files changed, +6,145 / -3,365 lines
**Git range:** feat(04-01) → feat(06-02)

**Key accomplishments:**
- Fixed score breakdown bug — rescored 139 contacts with accurate 5-dimension scores
- Queue sort/filter controls — sort by score, filter by status and industry in PWA
- Gmail OAuth send path with App Password fallback for daily digests
- Dashboard intelligence — health breakdown, industry distribution, role/seniority mix, score tiers
- `reconnect` CLI with Click — 5 command groups, 9 commands replacing Streamlit admin UI
- Streamlit fully removed — 23 files deleted, LaunchAgent calls CLI directly

---

## v1.0 Actionable PWA + Rich Email Digests (Shipped: 2026-03-09)

**Phases completed:** 3 phases, 7 plans
**Timeline:** 2 days (2026-03-08 → 2026-03-09)
**Code:** 19 files changed, +3,288 / -419 lines

**Key accomplishments:**
- Gmail App Password + smtplib integration (replaced 330-line OAuth with 60-line smtplib)
- Netlify PWA deployment with SPA routing and root-relative service worker
- Table-based email cards with 44px tap targets, LinkedIn buttons, and profile deep links
- GET/POST split on action Edge Function (prevents Gmail scanner token consumption)
- Contact profile page with AI scoring rationale, professional context, connection strength, enrichment status
- Dashboard pipeline funnel, enrichment status views, and feedback history

---

