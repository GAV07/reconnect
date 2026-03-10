# Milestones

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

