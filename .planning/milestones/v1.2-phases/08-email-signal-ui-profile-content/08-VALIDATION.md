---
phase: 8
slug: email-signal-ui-profile-content
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — runs via `pytest tests/` with no config file |
| **Quick run command** | `python -m pytest tests/test_phase8_email_signal_ui.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_phase8_email_signal_ui.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 8-01-01 | 01 | 0 | EMAIL-01 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_send_digest_email_returns_dict -x` | ❌ W0 | ⬜ pending |
| 8-01-02 | 01 | 0 | EMAIL-02 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_review_in_app_cta_present -x` | ❌ W0 | ⬜ pending |
| 8-01-03 | 01 | 0 | EMAIL-03 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_no_legacy_action_buttons -x` | ❌ W0 | ⬜ pending |
| 8-01-04 | 01 | 0 | EMAIL-03 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_no_token_generation -x` | ❌ W0 | ⬜ pending |
| 8-01-05 | 01 | 0 | EMAIL-04 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestPipelineWiring::test_telegram_wired -x` | ❌ W0 | ⬜ pending |
| 8-01-06 | 01 | 0 | EMAIL-02 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_industry_in_featured_cards -x` | ❌ W0 | ⬜ pending |
| 8-01-07 | 01 | 0 | EMAIL-01 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestDigestRebuild::test_digest_subject_format -x` | ❌ W0 | ⬜ pending |
| 8-02-01 | 02 | 0 | SIG-01 | manual | N/A — JS const verified by code review | - | ⬜ pending |
| 8-02-02 | 02 | 0 | SIG-06 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestSignalWrite::test_archive_sets_user_priority -x` | ❌ W0 | ⬜ pending |
| 8-02-03 | 02 | 0 | QUX-01 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestQueueCardContext::test_card_context_fields_populated -x` | ❌ W0 | ⬜ pending |
| 8-02-04 | 02 | 0 | QUX-02 | manual | N/A — DOM manipulation requires browser test | - | ⬜ pending |
| 8-03-01 | 03 | 0 | PROF-01 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestProfileFallback::test_key_factors_fallback_with_enrichment -x` | ❌ W0 | ⬜ pending |
| 8-03-02 | 03 | 0 | PROF-01 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestProfileFallback::test_key_factors_fallback_truly_empty -x` | ❌ W0 | ⬜ pending |
| 8-03-03 | 03 | 0 | PROF-02 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestProfileFallback::test_starters_fallback_uses_headline -x` | ❌ W0 | ⬜ pending |
| 8-03-04 | 03 | 0 | PROF-03 | unit | `pytest tests/test_phase8_email_signal_ui.py::TestNoteWrite::test_contact_note_insert_structure -x` | ❌ W0 | ⬜ pending |
| 8-04-01 | 04 | 0 | Pull sync | unit | `pytest tests/test_phase8_email_signal_ui.py::TestPullSync::test_pull_stats_has_signal_keys -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase8_email_signal_ui.py` — stubs for all automated requirements above
- [ ] Existing `tests/conftest.py` — shared fixtures (`mock_settings` with PWA_URL, GMAIL_APP_PASSWORD, GMAIL_SENDER_EMAIL)

*conftest.py and pytest framework already in place from prior phases.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Signal picker expand/collapse on queue card | SIG-01, SIG-02 | JS DOM manipulation requires browser | Open PWA → queue → tap "Assign Signal" → verify picker expands with 7 chips |
| Signal assignment keeps card in place | QUX-02 | DOM removal check requires browser | Assign any non-ARCHIVE signal → verify card stays visible in queue |
| ARCHIVE hides card from default view | SIG-06 | DOM removal + filter interaction | Assign ARCHIVE → card fades; switch to "All" filter → card visible |
| Signal filter tabs work | SIG-05 | JS filter UI requires browser | Select "Warm Lead" filter → only warm lead cards shown |
| Email renders in Gmail mobile/desktop | EMAIL-01 | Gmail rendering requires real email send | Send test digest → open in Gmail app and web |
| Notes textarea edit on profile page | PROF-03 | JS textarea interaction | Open profile → type note → save → verify persisted |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
