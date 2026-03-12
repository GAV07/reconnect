---
phase: 7
slug: signal-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (already installed) |
| **Config file** | `pyproject.toml` (ruff config exists; pytest section to add in Wave 0 if missing) |
| **Quick run command** | `python -m pytest tests/test_signal_foundation.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_signal_foundation.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | SIG-03 | unit | `pytest tests/test_signal_foundation.py::test_contact_signals_model` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | SIG-03 | unit | `pytest tests/test_signal_foundation.py::test_contact_notes_model` | ❌ W0 | ⬜ pending |
| 07-01-03 | 01 | 1 | SIG-03 | unit | `pytest tests/test_signal_foundation.py::test_connection_new_fields` | ❌ W0 | ⬜ pending |
| 07-01-04 | 01 | 1 | SIG-03 | unit | `pytest tests/test_signal_foundation.py::test_outreach_queue_new_fields` | ❌ W0 | ⬜ pending |
| 07-01-05 | 01 | 1 | SIG-03 | unit | `pytest tests/test_signal_foundation.py::test_user_profile_new_fields` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 1 | CAD-01 | unit | `pytest tests/test_signal_foundation.py::test_signal_actions_map` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 1 | CAD-01 | unit | `pytest tests/test_signal_foundation.py::test_apply_signal` | ❌ W0 | ⬜ pending |
| 07-02-03 | 02 | 1 | CAD-01 | unit | `pytest tests/test_signal_foundation.py::test_cadence_values` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 2 | SIG-03 | integration | `pytest tests/test_signal_foundation.py::test_backfill_skipped` | ❌ W0 | ⬜ pending |
| 07-03-02 | 03 | 2 | SIG-03 | integration | `pytest tests/test_signal_foundation.py::test_push_sync_new_fields` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_signal_foundation.py` — stubs for all phase test cases
- [ ] `tests/conftest.py` — shared fixtures (in-memory SQLite engine, test session)

*If test infrastructure already exists, Wave 0 verifies it covers new models.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PostgreSQL migration runs cleanly | SIG-03 | Requires live Supabase connection | Run `psql` with migration SQL against Supabase; verify tables created with `\d contact_signals` |
| Anon role grants work for PostgREST | SIG-03 | Requires live Supabase + PostgREST | `curl` the PostgREST endpoint for `contact_signals` with anon key; expect 200 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
