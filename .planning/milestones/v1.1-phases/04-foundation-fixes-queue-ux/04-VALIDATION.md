---
phase: 4
slug: foundation-fixes-queue-ux
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4.0+ (already in pyproject.toml dev deps) |
| **Config file** | pyproject.toml (no [tool.pytest] section yet — runs with defaults) |
| **Quick run command** | `python -m pytest tests/test_phase4_foundation.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_phase4_foundation.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | INFRA-02 | unit | `python -m pytest tests/test_phase4_foundation.py::test_dimension_scores_populated -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | INFRA-02 | unit | `python -m pytest tests/test_phase4_foundation.py::test_find_missing_dimension_scores -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | QUEUE-01 | unit | `python -m pytest tests/test_phase4_foundation.py::test_queue_sort_toggle -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 1 | QUEUE-02 | unit | `python -m pytest tests/test_phase4_foundation.py::test_queue_status_filter -x` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 1 | QUEUE-03 | unit | `python -m pytest tests/test_phase4_foundation.py::test_industry_dual_path -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | INFRA-01 | unit | `python -m pytest tests/test_phase4_foundation.py::test_oauth_not_configured -x` | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 2 | INFRA-01 | unit (mock) | `python -m pytest tests/test_phase4_foundation.py::test_oauth_send_email_mock -x` | ❌ W0 | ⬜ pending |
| 04-03-03 | 03 | 2 | INFRA-01 | unit | `python -m pytest tests/test_phase4_foundation.py::test_no_gmail_creds_in_push -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase4_foundation.py` — stubs for all 8 automated test cases above
- [ ] No new conftest.py needed — existing fixtures pattern applies

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Gmail OAuth send integration (actual token + API call) | INFRA-01 | Requires real GCP credentials and browser OAuth consent flow | Run `python -c "from src.integrations.gmail import oauth_send_html_email; ..."` with valid token |
| Queue filter controls render and update card list | QUEUE-01, QUEUE-02, QUEUE-03 | Vanilla JS DOM rendering in PWA | Open PWA in browser, verify sort toggle, status dropdown, industry dropdown appear and update displayed contacts |
| Contact profile dimension bars show real values | INFRA-02 | PWA renders from Supabase data | Open any contact profile after re-score, verify all 5 dimension bars show non-zero values |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
