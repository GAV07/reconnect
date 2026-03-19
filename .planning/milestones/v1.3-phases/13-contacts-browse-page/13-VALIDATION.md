---
phase: 13
slug: contacts-browse-page
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, `tests/` directory) |
| **Config file** | none — pytest auto-discovers `tests/test_*.py` |
| **Quick run command** | `python -m pytest tests/test_phase13_contacts.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_phase13_contacts.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | BROWSE-01 | unit (static) | `pytest tests/test_phase13_contacts.py::test_contacts_js_exists -x` | ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 1 | BROWSE-01 | unit (static) | `pytest tests/test_phase13_contacts.py::test_contacts_route_registered -x` | ❌ W0 | ⬜ pending |
| 13-01-03 | 01 | 1 | BROWSE-01 | unit (static) | `pytest tests/test_phase13_contacts.py::test_nav_has_contacts_tab -x` | ❌ W0 | ⬜ pending |
| 13-02-01 | 02 | 1 | BROWSE-02 | unit (static) | `pytest tests/test_phase13_contacts.py::test_browse_select_excludes_raw_enrichment -x` | ❌ W0 | ⬜ pending |
| 13-03-01 | 03 | 1 | BROWSE-03/04 | unit (static) | `pytest tests/test_phase13_contacts.py::test_contact_filters_shape -x` | ❌ W0 | ⬜ pending |
| 13-05-01 | 05 | 1 | BROWSE-05 | unit (static) | `pytest tests/test_phase13_contacts.py::test_page_size_is_50 -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase13_contacts.py` — stubs for BROWSE-01 through BROWSE-05 via static file analysis

*Uses Python `open()` + string matching to verify PWA static files contain expected patterns — same pattern as `tests/test_phase3_pwa.py`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual card layout matches spec | BROWSE-01 | CSS/visual rendering | Open PWA → Contacts tab, verify compact row format with name/role/company line and industry chip + city + score line |
| Filter dropdowns populate correctly | BROWSE-03/04 | Dynamic Supabase data | Open PWA → Contacts tab, verify industry and city dropdowns show distinct values from database |
| Load More pagination works | BROWSE-05 | End-to-end server round-trip | Open PWA → Contacts tab, click "Load More", verify new contacts appended without duplicates |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
