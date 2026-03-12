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
| **Quick run commands** | `pytest tests/test_phase9_goals_scoring.py tests/test_phase9_cadence.py tests/test_phase9_feedback.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run the test file for that plan (see per-task map below)
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | PERS-02 | unit | `pytest tests/test_phase9_goals_scoring.py::TestScoringPrompt -x` | W0 | pending |
| 09-01-02 | 01 | 1 | PERS-01 | unit | `pytest tests/test_phase9_goals_scoring.py::TestPullSyncGoals -x` | W0 | pending |
| 09-01-03 | 01 | 1 | PERS-01 | grep | `grep -q "goals-input" pwa/js/preferences.js` | N/A | pending |
| 09-01-04 | 01 | 1 | PERS-02 | unit | `pytest tests/test_phase9_goals_scoring.py::TestRescoreTrigger -x` | W0 | pending |
| 09-02-01 | 02 | 1 | CAD-02 | unit | `pytest tests/test_phase9_cadence.py::TestCadenceRequeue -x` | W0 | pending |
| 09-02-02 | 02 | 1 | CAD-03 | unit | `pytest tests/test_phase9_cadence.py::TestCadenceRequeue::test_archive_never_requeued -x` | W0 | pending |
| 09-02-03 | 02 | 1 | CAD-03 | unit | `pytest tests/test_phase9_cadence.py::TestCadenceRequeue::test_uses_cadence_due_at -x` | W0 | pending |
| 09-03-01 | 03 | 2 | PERS-03 | unit | `pytest tests/test_phase9_feedback.py::TestSignalAnalysis -x` | W0 | pending |
| 09-03-02 | 03 | 2 | PERS-04 | unit | `pytest tests/test_phase9_feedback.py::TestSafetyGuards -x` | W0 | pending |
| 09-03-03 | 03 | 2 | PERS-04 | unit | `pytest tests/test_phase9_feedback.py::TestSafetyGuards::test_clamps_to_0_6_floor -x` | W0 | pending |
| 09-03-04 | 03 | 2 | PERS-04 | unit | `pytest tests/test_phase9_feedback.py::TestWeightHistory -x` | W0 | pending |
| 09-03-05 | 03 | 2 | PERS-04 | grep | `grep -q "weight_history" pwa/js/preferences.js` | N/A | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase9_goals_scoring.py` — stubs for PERS-01, PERS-02 (scoring prompt, pull sync, rescore trigger)
- [ ] `tests/test_phase9_cadence.py` — stubs for CAD-02, CAD-03 (cadence re-queuing)
- [ ] `tests/test_phase9_feedback.py` — stubs for PERS-03, PERS-04 (signal feedback, safety guards, weight history)
- [ ] `tests/conftest.py` — shared fixtures (already present, no change needed)

*Existing infrastructure covers framework installation — pytest, pytest-mock already in pyproject.toml `[dev]` dependencies.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Goals text area renders on Preferences page | PERS-01 | PWA vanilla JS UI, no test runner | Open PWA -> Preferences -> verify goals text area at top |
| Weight history section renders on Preferences page | PERS-04 | PWA vanilla JS UI, no test runner | Open PWA -> Preferences -> verify weight history table in collapsed section |
| Goals save triggers toast notification | PERS-01 | UI feedback, no backend test | Type goals text -> click Save -> verify toast appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
