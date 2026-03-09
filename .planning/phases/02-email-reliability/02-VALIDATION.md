---
phase: 2
slug: email-reliability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4+ with pytest-mock |
| **Config file** | `pyproject.toml` (run from project root) |
| **Quick run command** | `pytest tests/test_phase2_email.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_phase2_email.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | EMAIL-02 | unit | `pytest tests/test_phase2_email.py::test_card_layout_uses_table -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | EMAIL-03 | unit | `pytest tests/test_phase2_email.py::test_button_tap_targets -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | EMAIL-04 | unit | `pytest tests/test_phase2_email.py::test_profile_link_uses_query_params -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | EMAIL-05 | unit | `pytest tests/test_phase2_email.py::test_linkedin_button_in_card -x` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | EMAIL-06 | manual | Deploy and tap "Yes" | n/a | ⬜ pending |
| 02-01-06 | 01 | 1 | EMAIL-07 | manual (code review + browser) | Manual: visit action URL, see confirmation form | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase2_email.py` — covers EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05
  - Needs: `_build_digest_html()` callable with mock contacts (no DB)
  - Pattern: similar to existing `test_phase1_infra.py` with monkeypatching

*Existing infrastructure (pytest, pytest-mock, conftest fixtures) covers all Python test needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Edge Function approve sets `status: "approved"` | EMAIL-06 | Requires live Supabase deployment | Tap "Yes" in email, verify DB row updated |
| GET handler returns confirmation form, not execution | EMAIL-07 | Deno TypeScript not covered by pytest | Visit action URL in browser, verify `<form method="POST">` shown |
| Gmail mobile card layout renders correctly | EMAIL-02 | Requires real Gmail client | Send test digest, open on mobile Gmail |
| Gmail mobile tap targets are usable | EMAIL-03 | Requires real device interaction | Tap buttons on mobile, verify 44px+ targets |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
