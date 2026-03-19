---
phase: 13
plan: "01"
subsystem: pwa
tags: [navigation, routing, css, testing]
dependency_graph:
  requires: []
  provides: [contacts-nav-tab, contacts-route, contacts-css-classes, contacts-test-suite]
  affects: [pwa/index.html, pwa/js/app.js, pwa/css/app.css]
tech_stack:
  added: []
  patterns: [hash-router, bottom-nav-tab, css-custom-properties]
key_files:
  created: [tests/test_phase13_contacts.py]
  modified: [pwa/index.html, pwa/js/app.js, pwa/css/app.css]
decisions:
  - "Active state logic uses startsWith('#/contact/') (trailing slash) so #/contacts does not falsely activate Queue tab"
  - "contacts.js script tag inserted between contact.js and dashboard.js — correct load order for router dependency"
  - ".filter-group class is standalone (not a descendant selector) — does not conflict with existing .queue-filters .filter-group"
metrics:
  duration: 2min
  completed_date: "2026-03-18"
  tasks_completed: 2
  files_changed: 3
  files_created: 1
---

# Phase 13 Plan 01: Contacts Page Infrastructure Summary

**One-liner:** 4-tab bottom nav with Contacts as 2nd tab, /contacts route wired in app.js, 13 CSS classes added to app.css, and 12 static analysis tests created (2 passing now, 10 passing after Plan 02).

## What Was Built

Plan 01 establishes the navigation, routing, and visual shell that Plan 02 (contacts.js module) will plug into.

### Changes Made

**pwa/index.html**
- Added Contacts tab as 2nd position in 4-tab bottom nav (Queue | Contacts | Dashboard | Settings)
- Used two-person SVG icon (`viewBox="0 0 24 24"`, stroke-based, matches existing nav icon style)
- Added `<script src="js/contacts.js">` between contact.js and dashboard.js in script loading order

**pwa/js/app.js**
- Added `/contacts` route to `routes` object (after `/queue`, before `/contact`)
- Added `case 'contacts': await renderContacts(content); break;` to render() switch
- Fixed active state logic: changed `startsWith('#/contact')` to `startsWith('#/contact/')` so that navigating to `#/contacts` does not falsely activate the Queue tab

**pwa/css/app.css**
- Added 13 new CSS classes before the `/* Responsive */` media query:
  - Contact row: `.contact-row`, `.contact-row:active`, `.contact-row-header`, `.contact-row-name`, `.contact-row-role`, `.contact-row-meta`, `.contact-row-city`
  - Filter bar: `.contacts-filter-bar`, `.contacts-filter-row`, `.filter-group`, `.filter-group-full`, `.filter-input`, `.filter-input:focus`
  - Utility: `.contacts-count-banner`, `.btn-sm`, `.load-more-container`

**tests/test_phase13_contacts.py** (new file)
- 12 static analysis tests covering BROWSE-01 through BROWSE-05
- 2 tests pass immediately: `test_nav_has_contacts_tab`, `test_contacts_route_registered`
- 10 tests are intentionally failing (Wave 0 RED state) until Plan 02 creates contacts.js

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 44cd150 | feat(13-01): add Contacts nav tab, script tag, and router wiring |
| Task 2 | fa5e37a | feat(13-01): add contacts CSS classes and static analysis tests |

## Verification Results

```
pytest tests/test_phase13_contacts.py::test_nav_has_contacts_tab tests/test_phase13_contacts.py::test_contacts_route_registered -x -q
2 passed, 1 warning in 0.01s
```

All 13 CSS classes confirmed present. No new test failures introduced in existing test suite (pre-existing Gmail OAuth failure in test_phase1_infra.py is out of scope).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files exist:
- pwa/index.html: FOUND
- pwa/js/app.js: FOUND
- pwa/css/app.css: FOUND
- tests/test_phase13_contacts.py: FOUND

Commits exist:
- 44cd150: FOUND
- fa5e37a: FOUND
