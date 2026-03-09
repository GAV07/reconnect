# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Actionable PWA + Rich Email Digests

**Shipped:** 2026-03-09
**Phases:** 3 | **Plans:** 7

### What Was Built
- Gmail App Password + smtplib email sending (replaced 330-line OAuth with 60-line smtplib)
- Netlify PWA deployment with SPA routing and service worker
- Table-based email cards with 44px tap targets, LinkedIn buttons, profile deep links
- GET/POST split on action Edge Function preventing Gmail scanner token consumption
- Contact profile page with 5-dimension AI scoring rationale, professional context, enrichment status
- Dashboard pipeline funnel, enrichment status views, and feedback history

### What Worked
- Phase-level planning with 2-3 focused plans per phase kept scope tight
- get_settings() call-time pattern enabled test monkeypatching across all modules consistently
- Table-based HTML for email was the right call — no Gmail rendering surprises
- Query parameter deep links (not hash fragments) survived Gmail redirect chain as designed

### What Was Inefficient
- ROADMAP.md checkbox tracking fell behind — plan completion didn't auto-update checkboxes
- SUMMARY.md frontmatter lacked `requirements_completed` field across all plans — required manual backfill
- Streamlit admin UI (`review.py`) wasn't updated when OAuth functions were removed — tech debt carried forward

### Patterns Established
- get_settings() at call time (not module-level singleton) for all config access in testable modules
- Table role=presentation for email card layouts (Gmail-safe)
- raw_enrichment dual-key unwrap (`?.data || obj || {}`) for defensive enrichment data access
- event.target.closest() guard for card click vs button click disambiguation in PWA
- buildXxxSection() helper pattern returning HTML strings for composable PWA views

### Key Lessons
1. Gmail strips CSS flexbox on mobile — always use table-based layouts for email HTML
2. Hash fragments are stripped by Gmail redirect chain — use query parameters for email deep links
3. Gmail pre-fetch scanners will consume action tokens — GET must be side-effect-free
4. Keep ROADMAP.md checkboxes updated during plan execution, not as a post-hoc fix

### Cost Observations
- Sessions: ~6 (research + plan + execute per phase)
- Notable: Entire milestone completed in 2 days with consistent ~3 min/plan execution time

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 3 | 7 | Initial milestone — established planning/execution workflow |

### Top Lessons (Verified Across Milestones)

1. (Pending — need multiple milestones to verify patterns)
