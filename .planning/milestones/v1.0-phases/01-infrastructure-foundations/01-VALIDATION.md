---
phase: 1
slug: infrastructure-foundations
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (>=7.4.0, in pyproject.toml dev deps) |
| **Config file** | None present — Wave 0 installs |
| **Quick run command** | `pytest tests/test_phase1_infra.py -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_phase1_infra.py -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | DEPLOY-01 | smoke (file content check) | `pytest tests/test_phase1_infra.py::test_netlify_toml -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | DEPLOY-02 | smoke (file content check) | `pytest tests/test_phase1_infra.py::test_service_worker_paths -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | DEPLOY-03 | unit | `pytest tests/test_phase1_infra.py::test_pwa_url_config -x` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 1 | EMAIL-01 | unit (mock SMTP) | `pytest tests/test_phase1_infra.py::test_gmail_smtplib -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — package marker
- [ ] `tests/test_phase1_infra.py` — covers DEPLOY-01, DEPLOY-02, DEPLOY-03, EMAIL-01
- [ ] `tests/conftest.py` — shared fixtures (mock settings with test env vars)
- [ ] pytest install: already in pyproject.toml dev deps (`pip install -e ".[dev]"`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Netlify URL loads PWA and deep links resolve | DEPLOY-01 | Requires live Netlify deployment | Navigate to `https://eg-connect.netlify.app` and `/#/contact/123` |
| Email lands in inbox (not spam) | EMAIL-01 | Requires live Gmail delivery | Run pipeline, check inbox within 5 minutes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
