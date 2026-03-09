# Roadmap: Reconnect

## Milestones

- ✅ **v1.0 Actionable PWA + Rich Email Digests** — Phases 1-3 (shipped 2026-03-09)
- 🚧 **v1.1 Network Intelligence** — Phases 4-6 (in progress)

## Phases

<details>
<summary>✅ v1.0 Actionable PWA + Rich Email Digests (Phases 1-3) — SHIPPED 2026-03-09</summary>

- [x] Phase 1: Infrastructure Foundations (2/2 plans) — completed 2026-03-08
- [x] Phase 2: Email Reliability (2/2 plans) — completed 2026-03-09
- [x] Phase 3: PWA Feature Completeness (3/3 plans) — completed 2026-03-09

See: `.planning/milestones/v1.0-ROADMAP.md` for full details.

</details>

### 🚧 v1.1 Network Intelligence (In Progress)

**Milestone Goal:** Make the tool smarter about surfacing network insights, give users control over queue prioritization, and add AI-powered contact search — while fixing infra gaps and removing Streamlit.

- [x] **Phase 4: Foundation Fixes + Queue UX** - Fix score breakdown bug and add queue sort/filter controls (completed 2026-03-09)
- [ ] **Phase 5: Dashboard Intelligence** - Health score insights and demographic charts across enriched contacts
- [ ] **Phase 6: CLI + Gmail OAuth + Streamlit Removal** - Full CLI parity, Gmail OAuth send path, delete Streamlit

## Phase Details

### Phase 4: Foundation Fixes + Queue UX
**Goal**: Users can trust scoring data and efficiently filter their outreach queue
**Depends on**: Phase 3 (v1.0 complete)
**Requirements**: INFRA-01, INFRA-02, QUEUE-01, QUEUE-02, QUEUE-03
**Success Criteria** (what must be TRUE):
  1. User can sort queue contacts by composite score (ascending/descending) without full page reload
  2. User can filter queue to show only pending, approved, or sent contacts
  3. User can filter queue by industry to narrow to a specific sector
  4. Contact profile pages show real values (not 0) in all 5 scoring dimension bars
  5. Daily email digest sends successfully via Gmail OAuth using GCP JSON credentials
**Plans**: 3 plans
Plans:
- [ ] 04-01-PLAN.md — Fix score breakdown bug (rescore contacts with missing dimension_scores)
- [ ] 04-02-PLAN.md — Add queue sort/filter controls (sort by score, filter by status and industry)
- [ ] 04-03-PLAN.md — Add Gmail OAuth send path with App Password fallback

### Phase 5: Dashboard Intelligence
**Goal**: Users can see what drives their network health score and understand their network composition
**Depends on**: Phase 4
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04
**Success Criteria** (what must be TRUE):
  1. Dashboard shows health score breakdown with per-component values and actionable insight text (e.g., "Add more contacts in tech" or "Your enrichment rate is strong")
  2. Dashboard shows a visual industry distribution chart across enriched contacts
  3. Dashboard shows role and seniority mix across enriched contacts
  4. Dashboard shows score tier distribution (e.g., how many contacts in high/medium/low tiers)
**Plans**: TBD

### Phase 6: CLI + Gmail OAuth + Streamlit Removal
**Goal**: Users can operate the pipeline entirely from the CLI and the broken Streamlit UI is fully removed
**Depends on**: Phase 5
**Requirements**: CLI-01, CLI-02
**Success Criteria** (what must be TRUE):
  1. User can run all pipeline operations via `reconnect` CLI commands (pipeline run, queue reset, queue stats, contacts import, contacts score, gmail auth, sync push/pull)
  2. `streamlit` and `plotly` are removed from requirements.txt and `src/ui/` is deleted
  3. Running `reconnect --help` shows all available subcommands with descriptions
  4. LaunchAgent runs daily pipeline via `reconnect pipeline run` without Streamlit dependency
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure Foundations | v1.0 | 2/2 | Complete | 2026-03-08 |
| 2. Email Reliability | v1.0 | 2/2 | Complete | 2026-03-09 |
| 3. PWA Feature Completeness | v1.0 | 3/3 | Complete | 2026-03-09 |
| 4. Foundation Fixes + Queue UX | 3/3 | Complete   | 2026-03-09 | - |
| 5. Dashboard Intelligence | v1.1 | 0/? | Not started | - |
| 6. CLI + Gmail OAuth + Streamlit Removal | v1.1 | 0/? | Not started | - |
