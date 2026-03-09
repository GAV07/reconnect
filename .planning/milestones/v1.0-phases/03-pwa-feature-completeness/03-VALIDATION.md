---
phase: 3
slug: pwa-feature-completeness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-mock (already installed in `.venv`) |
| **Config file** | `pyproject.toml` or none (pytest discovers `tests/`) |
| **Quick run command** | `source .venv/bin/activate && pytest tests/test_phase3_pwa.py -x -q` |
| **Full suite command** | `source .venv/bin/activate && pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `source .venv/bin/activate && pytest tests/test_phase3_pwa.py -x -q`
- **After every plan wave:** Run `source .venv/bin/activate && pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | PROFILE-01 | unit | `pytest tests/test_phase3_pwa.py::test_score_reasoning_has_all_dimensions -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | PROFILE-02 | unit | `pytest tests/test_phase3_pwa.py::test_professional_context_fields -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | PROFILE-03 | unit | `pytest tests/test_phase3_pwa.py::test_connection_strength_fields -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | PROFILE-04 | unit | `pytest tests/test_phase3_pwa.py::test_enrichment_fields -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | VIEW-01 | unit | `pytest tests/test_phase3_pwa.py::test_funnel_counts_in_snapshot -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | VIEW-02 | unit | `pytest tests/test_phase3_pwa.py::test_enrichment_status_counts -x` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 1 | VIEW-03 | unit | `pytest tests/test_phase3_pwa.py::test_feedback_history_rows -x` | ❌ W0 | ⬜ pending |
| 03-02-04 | 02 | 1 | VIEW-04 | smoke | Manual browser verify | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase3_pwa.py` — stubs for PROFILE-01 through VIEW-03 (7 tests)
- [ ] `src/services/dashboard_service.py` update — `compute_data_quality()` must include `reviewed`, `reached_out`, `connected` keys

*Existing conftest.py and test infrastructure are sufficient; no new fixtures needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Deep link bridge converts ?view=contact&id=X to #/contact/{id} | VIEW-04 | Requires browser environment with window.location | Load `https://eg-connect.netlify.app/?view=contact&id=test-id` → URL bar should show `#/contact/test-id` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
