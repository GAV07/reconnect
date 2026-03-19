---
phase: 14
slug: search-bar
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | implicit (no explicit pytest.ini) |
| **Quick run command** | `python -m pytest tests/test_phase14_search.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_phase14_search.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | SEARCH-01 | unit | `python -m pytest tests/test_phase14_search.py::test_search_query_state -x` | ❌ W0 | ⬜ pending |
| 14-01-02 | 01 | 1 | SEARCH-01 | unit | `python -m pytest tests/test_phase14_search.py::test_textsearch_call -x` | ❌ W0 | ⬜ pending |
| 14-01-03 | 01 | 1 | SEARCH-01 | unit | `python -m pytest tests/test_phase14_search.py::test_ilike_fallback_pattern -x` | ❌ W0 | ⬜ pending |
| 14-01-04 | 01 | 1 | SEARCH-01 | unit | `python -m pytest tests/test_phase14_search.py::test_migration_has_fts_column -x` | ❌ W0 | ⬜ pending |
| 14-01-05 | 01 | 1 | SEARCH-01 | unit | `python -m pytest tests/test_phase14_search.py::test_migration_has_gin_index -x` | ❌ W0 | ⬜ pending |
| 14-02-01 | 01 | 1 | SEARCH-02 | unit | `python -m pytest tests/test_phase14_search.py::test_search_debounce_pattern -x` | ❌ W0 | ⬜ pending |
| 14-02-02 | 01 | 1 | SEARCH-02 | unit | `python -m pytest tests/test_phase14_search.py::test_count_banner_search_format -x` | ❌ W0 | ⬜ pending |
| 14-03-01 | 01 | 1 | SEARCH-01/02 | unit | `python -m pytest tests/test_phase14_search.py::test_search_placeholder -x` | ❌ W0 | ⬜ pending |
| 14-03-02 | 01 | 1 | SEARCH-01/02 | unit | `python -m pytest tests/test_phase14_search.py::test_clear_filters_resets_search -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase14_search.py` — stubs for SEARCH-01, SEARCH-02 via PWA static file analysis
- [ ] Update `tests/test_phase13_contacts.py` — adjust `test_role_filter_exists()` and `test_contact_filters_shape()` for roleQuery → searchQuery rename

*Existing infrastructure covers framework install — pytest already in use.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Search icon visually appears inside input | SEARCH-01 | CSS layout rendering | Open Contacts page, verify magnifying glass icon left of input |
| Debounce "feels right" at 300ms | SEARCH-02 | UX perception | Type quickly, verify no flicker; pause, verify results update |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
