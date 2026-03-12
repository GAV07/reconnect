---
phase: 9
slug: goals-sync-and-pipeline-intelligence
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4+ with pytest-mock 3.12+ |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `pytest tests/test_phase9_goals_pipeline.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_phase9_goals_pipeline.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | PERS-01 | unit | `pytest tests/test_phase9_goals_pipeline.py::TestGoalsModel -x` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | PERS-02 | unit | `pytest tests/test_phase9_goals_pipeline.py::TestScoringPrompt -x` | ❌ W0 | ⬜ pending |
| 09-01-03 | 01 | 1 | PERS-01 | unit | `pytest tests/test_phase9_goals_pipeline.py::TestGoalsPullSync -x` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 1 | CAD-02 | unit | `pytest tests/test_phase9_goals_pipeline.py::TestCadenceRequeue -x` | ❌ W0 | ⬜ pending |
| 09-02-02 | 02 | 1 | CAD-03 | unit | `pytest tests/test_phase9_goals_pipeline.py::TestCadenceRequeue::test_archive_never_requeued -x` | ❌ W0 | ⬜ pending |
| 09-02-03 | 02 | 1 | CAD-03 | unit | `pytest tests/test_phase9_goals_pipeline.py::TestCadenceRequeue::test_uses_cadence_due_at -x` | ❌ W0 | ⬜ pending |
| 09-03-01 | 03 | 2 | PERS-03 | unit | `pytest tests/test_phase9_goals_pipeline.py::TestSignalFeedback -x` | ❌ W0 | ⬜ pending |
| 09-03-02 | 03 | 2 | PERS-04 | unit | `pytest tests/test_phase9_goals_pipeline.py::TestSafetyGuards -x` | ❌ W0 | ⬜ pending |
| 09-03-03 | 03 | 2 | PERS-04 | unit | `pytest tests/test_phase9_goals_pipeline.py::TestSafetyGuards::test_clamp_multiplier -x` | ❌ W0 | ⬜ pending |
| 09-03-04 | 03 | 2 | PERS-04 | unit | `pytest tests/test_phase9_goals_pipeline.py::TestWeightHistory -x` | ❌ W0 | ⬜ pending |
| 09-04-01 | 04 | 2 | PERS-04 | manual | PWA preferences page shows weight history | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase9_goals_pipeline.py` — stubs for PERS-01, PERS-02, PERS-03, PERS-04, CAD-02, CAD-03
- [ ] `tests/conftest.py` — shared fixtures (already present, no change needed)

*Existing infrastructure covers framework installation — pytest, pytest-mock already in pyproject.toml `[dev]` dependencies.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Goals text area renders on Preferences page | PERS-01 | PWA vanilla JS UI, no test runner | Open PWA → Preferences → verify goals text area at top |
| Weight history section renders on Preferences page | PERS-04 | PWA vanilla JS UI, no test runner | Open PWA → Preferences → verify weight history table in collapsed section |
| Goals save triggers toast notification | PERS-01 | UI feedback, no backend test | Type goals text → click Save → verify toast appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
