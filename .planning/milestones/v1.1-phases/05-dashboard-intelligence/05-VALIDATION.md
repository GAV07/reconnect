---
phase: 5
slug: dashboard-intelligence
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4.0+ (already in pyproject.toml dev deps) |
| **Config file** | pyproject.toml (uses defaults — no [tool.pytest] section needed) |
| **Quick run command** | `python -m pytest tests/test_phase5_dashboard.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_phase5_dashboard.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 0 | DASH-01–04 | unit | `python -m pytest tests/test_phase5_dashboard.py -x -q` | ❌ W0 | ⬜ pending |
| 5-02-01 | 02 | 1 | DASH-01 | unit | `python -m pytest tests/test_phase5_dashboard.py::test_health_breakdown_low_values -x` | ❌ W0 | ⬜ pending |
| 5-02-02 | 02 | 1 | DASH-01 | unit | `python -m pytest tests/test_phase5_dashboard.py::test_health_breakdown_high_values -x` | ❌ W0 | ⬜ pending |
| 5-02-03 | 02 | 1 | DASH-02 | unit | `python -m pytest tests/test_phase5_dashboard.py::test_industry_distribution_sorted -x` | ❌ W0 | ⬜ pending |
| 5-02-04 | 02 | 1 | DASH-02 | unit | `python -m pytest tests/test_phase5_dashboard.py::test_industry_dual_key -x` | ❌ W0 | ⬜ pending |
| 5-02-05 | 02 | 1 | DASH-02 | unit | `python -m pytest tests/test_phase5_dashboard.py::test_industry_no_enriched -x` | ❌ W0 | ⬜ pending |
| 5-02-06 | 02 | 1 | DASH-03 | unit | `python -m pytest tests/test_phase5_dashboard.py::test_seniority_classification -x` | ❌ W0 | ⬜ pending |
| 5-02-07 | 02 | 1 | DASH-03 | unit | `python -m pytest tests/test_phase5_dashboard.py::test_role_seniority_structure -x` | ❌ W0 | ⬜ pending |
| 5-02-08 | 02 | 1 | DASH-04 | unit | `python -m pytest tests/test_phase5_dashboard.py::test_score_tier_buckets -x` | ❌ W0 | ⬜ pending |
| 5-02-09 | 02 | 1 | DASH-04 | unit | `python -m pytest tests/test_phase5_dashboard.py::test_score_tier_excludes_unscored -x` | ❌ W0 | ⬜ pending |
| 5-02-10 | 02 | 1 | DASH-04 | unit | `python -m pytest tests/test_phase5_dashboard.py::test_score_tier_pct_sums -x` | ❌ W0 | ⬜ pending |
| 5-02-11 | 02 | 1 | DASH-01–04 | unit | `python -m pytest tests/test_phase5_dashboard.py::test_snapshot_includes_new_keys -x` | ❌ W0 | ⬜ pending |
| 5-03-01 | 03 | 2 | DASH-01–04 | manual smoke | Open dashboard in browser after deploy | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase5_dashboard.py` — stubs for all 11 automated test cases (DASH-01 through DASH-04)
- [ ] No new conftest.py needed — existing `conftest.py` fixtures apply; mock Connection pattern from `test_phase4_foundation.py` is reusable

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PWA renders new sections without crash when keys are missing from snapshot (stale snapshot guard) | DASH-01–04 | Requires browser rendering with stale snapshot data | Open dashboard in browser before pipeline runs; verify no console errors and sections gracefully omitted |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
