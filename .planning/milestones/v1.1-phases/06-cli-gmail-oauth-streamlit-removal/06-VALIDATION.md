---
phase: 6
slug: cli-gmail-oauth-streamlit-removal
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4+ (installed in venv) |
| **Config file** | none — pyproject.toml has no `[tool.pytest]` section |
| **Quick run command** | `pytest tests/test_phase6_cli.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_phase6_cli.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | CLI-01 | unit | `pytest tests/test_phase6_cli.py::test_help -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 0 | CLI-01 | unit | `pytest tests/test_phase6_cli.py::test_pipeline_run -x` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 0 | CLI-01 | unit | `pytest tests/test_phase6_cli.py::test_queue_stats -x` | ❌ W0 | ⬜ pending |
| 06-01-04 | 01 | 0 | CLI-01 | unit | `pytest tests/test_phase6_cli.py::test_queue_stats_json -x` | ❌ W0 | ⬜ pending |
| 06-01-05 | 01 | 0 | CLI-01 | unit | `pytest tests/test_phase6_cli.py::test_queue_reset -x` | ❌ W0 | ⬜ pending |
| 06-01-06 | 01 | 0 | CLI-01 | unit | `pytest tests/test_phase6_cli.py::test_contacts_import -x` | ❌ W0 | ⬜ pending |
| 06-01-07 | 01 | 0 | CLI-01 | unit | `pytest tests/test_phase6_cli.py::test_contacts_score -x` | ❌ W0 | ⬜ pending |
| 06-01-08 | 01 | 0 | CLI-01 | unit | `pytest tests/test_phase6_cli.py::test_gmail_status -x` | ❌ W0 | ⬜ pending |
| 06-01-09 | 01 | 0 | CLI-01 | unit | `pytest tests/test_phase6_cli.py::test_sync_push -x` | ❌ W0 | ⬜ pending |
| 06-01-10 | 01 | 0 | CLI-01 | unit | `pytest tests/test_phase6_cli.py::test_sync_pull -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 0 | CLI-02 | static | `pytest tests/test_phase6_cli.py::test_no_streamlit_imports -x` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 0 | CLI-02 | static | `pytest tests/test_phase6_cli.py::test_no_plotly_imports -x` | ❌ W0 | ⬜ pending |
| 06-02-03 | 02 | 0 | CLI-02 | static | `pytest tests/test_phase6_cli.py::test_ui_deleted -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase6_cli.py` — stubs for all CLI-01/CLI-02 behaviors above
- [ ] `reset_queue()` function in `src/pipeline/queue_generator.py` — needed before CLI test can mock it

*Existing `conftest.py` with `mock_settings` fixture is sufficient.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LaunchAgent runs `reconnect pipeline run` | CLI-01 | Requires macOS launchd runtime | 1. Update plist 2. `launchctl unload && load` 3. Check log output |
| Gmail OAuth browser flow | CLI-01 | Requires interactive browser | 1. Run `reconnect gmail auth <creds.json>` 2. Complete OAuth consent 3. Verify token stored |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
