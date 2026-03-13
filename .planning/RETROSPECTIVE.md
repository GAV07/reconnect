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

## Milestone: v1.1 — Network Intelligence

**Shipped:** 2026-03-10
**Phases:** 3 | **Plans:** 7

### What Was Built
- Score breakdown fix — rescored 139 contacts with accurate 5-dimension scores
- Queue sort/filter controls — sort by score, filter by status and industry in PWA
- Gmail OAuth send path with App Password fallback for daily email digests
- Dashboard intelligence — health breakdown with insights, industry distribution, role/seniority mix, score tiers
- `reconnect` CLI with Click — 5 command groups (pipeline, queue, contacts, gmail, sync), 9 commands
- Streamlit removal — 23 files deleted, LaunchAgent updated to call CLI directly

### What Worked
- TDD approach (RED/GREEN commits) caught bugs early and provided clear verification evidence
- Client-side sort/filter for queue was simpler and more accurate than server-side PostgREST approach (reconnect_score is in joined row)
- Lazy imports in CLI commands kept `reconnect --help` startup instant
- Phase verification (gsd-verifier) caught stale .pyc files that would have broken grep checks
- 3-source cross-reference (VERIFICATION + SUMMARY + REQUIREMENTS) gave high confidence in audit

### What Was Inefficient
- SUMMARY.md frontmatter `one_liner` field missing from all plans — summary-extract returns None
- ROADMAP.md Progress table format inconsistency (Phase 5/6 rows had misaligned columns)
- Phase 04 VERIFICATION had `human_needed` status but all code was verified — the 4 human items were about live browser testing that's hard to avoid

### Patterns Established
- reconnect_score (not priority_score) as the canonical composite score field
- OAuth-first with App Password fallback — check is_oauth_configured() before is_gmail_configured()
- OAuth tokens local-only — never sync GmailCredentials to Supabase (security boundary)
- Client-side filtering on raw_enrichment JSON with dual-key extraction (company_industry || companyIndustry)
- Lazy imports inside Click command bodies for fast CLI startup
- import json as _json to avoid name collision with Click option aliases
- buildXxxSection() functions with null-guard early return for graceful degradation on stale snapshots

### Key Lessons
1. Client-side sort/filter beats server-side when the data comes from joins (PostgREST .order() on stale columns is wrong)
2. Dual-key extraction is necessary when enrichment data has inconsistent field naming across providers
3. Streamlit should have been removed earlier — the broken admin UI was tech debt from v1.0
4. SUMMARY.md frontmatter needs consistent `one_liner` field for milestone-level reporting
5. Nyquist validation (VALIDATION.md) was created but never completed — need to either commit to it or skip

### Cost Observations
- Sessions: ~4 (research + plan + execute per phase, milestone audit + completion)
- Notable: Entire milestone completed in 1 day; ~3 min average per plan execution
- Model mix: Sonnet for executors/verifier/integration-checker, orchestrator context stayed lean (~10-15%)

---

## Milestone: v1.2 — Intent-Driven Triage

**Shipped:** 2026-03-13
**Phases:** 5 | **Plans:** 12

### What Was Built
- Signal foundation — 7 intent signals with schema, canonical service, migration, and bidirectional sync
- Email digest rebuilt — "Review in App" CTA with signal-aligned vocabulary and industry chips
- Profile enrichment — key factors/conversation starters fallbacks, contact notes, signal history UI
- User goals profile — current projects/interests inform LLM scoring for better WARM_LEAD identification
- Cadence re-queuing — automatic contact re-appearance based on signal cadence with age-based eligibility
- Signal-informed rescoring — triage patterns adjust scoring weights with safety guards (25-action min, ±40% cap, audit trail)
- Draft tone adaptation — Edge Function produces signal-aware AI messages (7 tone branches + ARCHIVE guard)

### What Worked
- Gap closure phase (Phase 11) caught integration issues that audit identified — assignSignalFromCard() wasn't writing to outreach_queue.signal or connections.cadence_due_at
- PostgREST direct writes pattern (no new Edge Functions) kept architecture simple — same pattern for signals, notes, goals, and feedback
- Canonical SIGNAL_ACTIONS defined once in Python, mirrored in JS — consistent behavior across stack
- TDD with in-memory SQLite databases (test_phase9_cadence.py, test_phase11_signal_write.py) provided fast, reliable verification
- Audit → gap closure → completion flow proved effective: audit found real integration gaps, Phase 11 fixed them

### What Was Inefficient
- SUMMARY.md frontmatter `requirements_completed` missing from most plans — 13/24 requirements had gaps in SUMMARY.md tracking (all confirmed via VERIFICATION.md)
- `one_liner` field still missing from all SUMMARYs — summary-extract returns empty, forcing manual accomplishment extraction
- Nyquist validation (VALIDATION.md) created for all 5 phases but none reached compliant status — overhead without benefit
- `apply_signal()` and `backfill_skipped_signals()` in signal_service.py are orphaned — PWA writes directly to PostgREST, bypassing Python service
- `test_phase10_draft_tone.py` planned (6 tests) but never created — PERS-05 lacks automated regression coverage

### Patterns Established
- SIGNAL_ACTIONS as canonical const in both Python (signal_service.py) and JS (queue.js) — single source of truth
- PostgREST direct writes for all PWA data mutations (signals, notes, goals, feedback, queue status)
- typeof SIGNAL_ACTIONS !== 'undefined' guard for cross-module JS const access
- Three-way signal gate: ARCHIVE=hidden, null=nudge, valid=generate (draft section)
- Insert-only audit log pattern (weight_history) — never upsert, full audit trail
- Cadence re-queuing as inline integration in generate_daily_queue() — not a separate pipeline step
- SIGNAL_TONE_CONFIG map pattern for signal-to-behavior mapping in Edge Functions

### Key Lessons
1. Milestone audit before completion catches real integration gaps — Phase 11 exists because the audit found missing writes
2. SUMMARY.md frontmatter needs enforcement — `requirements_completed` and `one_liner` missing from most plans across all 3 milestones
3. Nyquist validation adds overhead without clear benefit for this project — consider removing or simplifying
4. Orphaned code (apply_signal, backfill, data_health_stats) accumulates when Python service patterns are bypassed by PWA direct writes
5. outreach_queue.signal UPDATE permission needs human verification — table-level grants may cover it but it's unconfirmed

### Cost Observations
- Sessions: ~8 (research + plan + execute × 5 phases, audit + gap closure + completion)
- Notable: 5 phases in 3 days; largest milestone yet (12 plans vs 7 each for v1.0/v1.1)
- Model mix: Balanced profile (sonnet for executors/verifier, opus for orchestration)

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 3 | 7 | Initial milestone — established planning/execution workflow |
| v1.1 | 3 | 7 | TDD commits, 3-source requirement cross-reference, CLI replaces Streamlit |
| v1.2 | 5 | 12 | Milestone audit → gap closure flow, PostgREST direct writes, signal system architecture |

### Top Lessons (Verified Across Milestones)

1. buildXxxSection() composable HTML pattern works well for email (v1.0), dashboard (v1.1), and profile (v1.2)
2. get_settings() call-time pattern continues to enable clean testing — adopted across all modules
3. raw_enrichment dual-key unwrap needed in every consumer — defensive pattern is essential
4. SUMMARY.md frontmatter needs to be consistent from the start — missing across all 3 milestones
5. ~3 min/plan execution time is stable across all milestones — good velocity benchmark
6. Milestone audit catches integration gaps that phase-level verification misses — verified in v1.2
7. PostgREST direct writes from PWA are simpler than Edge Functions — use Edge Functions only when server-side secrets needed
