---
phase: 10
slug: draft-tone-adaptation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4+ |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/test_phase10_draft_tone.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_phase10_draft_tone.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | PERS-05 | unit | `pytest tests/test_phase10_draft_tone.py::TestDraftTonePrompt::test_warm_lead_includes_goals -x` | Wave 0 | pending |
| 10-01-02 | 01 | 1 | PERS-05 | unit | `pytest tests/test_phase10_draft_tone.py::TestDraftTonePrompt::test_nurture_excludes_goals -x` | Wave 0 | pending |
| 10-01-03 | 01 | 1 | PERS-05 | unit | `pytest tests/test_phase10_draft_tone.py::TestDraftTonePrompt::test_value_drop_references_enrichment -x` | Wave 0 | pending |
| 10-01-04 | 01 | 1 | PERS-05 | unit | `pytest tests/test_phase10_draft_tone.py::TestArchiveGuard::test_archive_returns_400 -x` | Wave 0 | pending |
| 10-01-05 | 01 | 1 | PERS-05 | unit | `pytest tests/test_phase10_draft_tone.py::TestDraftTonePrompt::test_all_signals_produce_distinct_prompts -x` | Wave 0 | pending |
| 10-01-06 | 01 | 1 | PERS-05 | unit | `pytest tests/test_phase10_draft_tone.py::TestPWAGate::test_no_signal_nudge_html -x` | Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase10_draft_tone.py` — stubs for PERS-05 (all 6 test cases)
- No conftest changes needed — existing `conftest.py` with `mock_settings` fixture is sufficient

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Edge Function deploys and responds correctly | PERS-05 | Requires Supabase deploy + live HTTP call | Deploy via `supabase functions deploy draft`, then call with signal param and verify response tone |
| Signal badge renders with correct color | PERS-05 | Visual UI check | Generate draft for WARM_LEAD contact, verify green badge appears above textarea |
| ARCHIVE contacts show no draft section | PERS-05 | Visual UI check | Navigate to ARCHIVE contact profile, verify no draft area is visible |
| No-signal nudge appears correctly | PERS-05 | Visual UI check | Navigate to contact without signal, verify "Assign a signal" nudge shows |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
