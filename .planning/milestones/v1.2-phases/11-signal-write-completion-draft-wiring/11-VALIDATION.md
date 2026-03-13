---
phase: 11
slug: signal-write-completion-draft-wiring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4+ |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/test_phase11_signal_write.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_phase11_signal_write.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 0 | PERS-05, CAD-02 | unit | `pytest tests/test_phase11_signal_write.py -x` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | PERS-05 | unit | `pytest tests/test_phase11_signal_write.py::TestAssignSignalWrites::test_outreach_queue_signal_written -x` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 1 | CAD-02 | unit | `pytest tests/test_phase11_signal_write.py::TestAssignSignalWrites::test_cadence_due_at_written -x` | ❌ W0 | ⬜ pending |
| 11-01-04 | 01 | 1 | CAD-02 | unit | `pytest tests/test_phase11_signal_write.py::TestAssignSignalWrites::test_archive_cadence_is_null -x` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 1 | PERS-05 | unit | `pytest tests/test_phase11_signal_write.py::TestDraftToneIntegration::test_signal_reaches_tone_config -x` | ❌ W0 | ⬜ pending |
| 11-02-02 | 02 | 1 | PERS-05 | unit | `pytest tests/test_phase11_signal_write.py::TestArchiveGuardWired::test_archive_guard_fires_when_signal_set -x` | ❌ W0 | ⬜ pending |
| 11-02-03 | 02 | 1 | CAD-02 | integration | `pytest tests/test_phase11_signal_write.py::TestCadenceEndToEnd::test_cadence_query_finds_written_contact -x` | ❌ W0 | ⬜ pending |
| 11-02-04 | 02 | 1 | PERS-05 | unit | `pytest tests/test_phase11_signal_write.py::TestDraftToneIntegration::test_all_non_archive_signals_reach_config -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase11_signal_write.py` — stubs for PERS-05 + CAD-02 (7 test cases)
- [ ] `tests/test_phase10_draft_tone.py` — SIGNAL_TONE_CONFIG prompt construction (audit tech debt)

*Existing `conftest.py` with `mock_settings` fixture is sufficient — no changes needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PostgREST UPDATE permission on `outreach_queue.signal` column | PERS-05 | Supabase permission model not reproducible in SQLite | Assign signal in PWA, check browser console for 403/permission errors |
| End-to-end draft tone in production | PERS-05 | Requires live Edge Function + OpenAI | Assign WARM_LEAD signal, trigger draft generation, verify tone matches config |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
