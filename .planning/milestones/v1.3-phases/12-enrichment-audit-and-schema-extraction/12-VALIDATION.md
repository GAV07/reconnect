---
phase: 12
slug: enrichment-audit-and-schema-extraction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/test_phase12_enrichment.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_phase12_enrichment.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | ENRICH-03 | unit | `python -m pytest tests/test_phase12_enrichment.py::TestFieldExtraction -x` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | ENRICH-03 | unit | `python -m pytest tests/test_phase12_enrichment.py::TestFieldExtraction -x` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 1 | ENRICH-04 | unit | `python -m pytest tests/test_phase12_enrichment.py::TestBackfill -x` | ❌ W0 | ⬜ pending |
| 12-03-01 | 03 | 2 | ENRICH-01 | unit | `python -m pytest tests/test_phase12_enrichment.py::TestEnrichmentCoverage -x` | ❌ W0 | ⬜ pending |
| 12-04-01 | 04 | 2 | ENRICH-02 | unit | `python -m pytest tests/test_phase12_enrichment.py::TestFieldExtraction::test_education_text_extracted -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase12_enrichment.py` — stubs for ENRICH-01, ENRICH-02, ENRICH-03, ENRICH-04
- [ ] Test fixtures for mock Connection with raw_enrichment data

*Existing infrastructure covers pytest framework — no install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Supabase migration adds 7 columns | ENRICH-03 | Requires live Supabase connection | Run migration via `supabase db push` or psycopg2 and verify with `\d connections` |
| `push_to_cloud` syncs backfilled rows | ENRICH-04 | Requires Supabase connection | Run pipeline, check Supabase dashboard for populated columns |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
