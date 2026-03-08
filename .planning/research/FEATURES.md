# Feature Landscape

**Domain:** Personal CRM PWA + Actionable Email Digest (networking / outreach tool)
**Researched:** 2026-03-08
**Confidence:** HIGH (existing codebase audited; findings corroborated by multiple 2025-2026 sources)

---

## Context: What Already Exists

The pipeline, scoring, and Supabase backend are fully operational. The PWA code exists
(queue, contact, dashboard, preferences pages) but is not deployable from Supabase Storage.
The email digest generates correct HTML with token-based action buttons but cannot send
because Gmail OAuth is unconfigured.

This document focuses on what the **deployed milestone** needs — features that make
the product usable end-to-end — not on rebuilding what already works.

---

## Table Stakes

Features users expect in this category of product. Missing any of these means the daily
workflow breaks.

| Feature | Why Expected | Complexity | Status | Notes |
|---------|-------------|------------|--------|-------|
| Daily queue of prioritized contacts to review | Core loop — without this the tool has no daily value | Low | Exists | Deployed on Supabase Storage, not functional PWA |
| Approve / Skip / Snooze per contact | Action triage — the tool's primary verb set | Low | Exists | Implemented in PWA + Edge Functions |
| Optimistic UI on triage actions | Mobile feel — card must respond instantly, not wait for network | Low | Exists | Implemented with fade-out pattern |
| Contact profile page with enriched data | Users need context before acting | Med | Partial | Score breakdown done; full enrichment fields not surfaced |
| AI scoring rationale visible on profile | Transparency — "why is this person suggested today?" | Med | Partial | `score_reasoning` parsed and displayed, but not the full enrichment context |
| Conversation starters / hooks per contact | Reduces friction — user needs a reason to reach out | Low | Exists | Pulled from `conversation_hooks` in score_reasoning |
| One-tap LinkedIn deep link per contact | Every networking tool provides this | Low | Exists | Present in queue cards and profile page |
| Email digest arriving in inbox each morning | Daily habit driver — without the email the PWA is never opened | Med | Partial | HTML generates correctly; Gmail OAuth missing |
| Token-based action buttons in email (Reach Out / Skip / Snooze) | Email as zero-friction triage surface | Med | Exists | Tokens generate; email cannot send yet |
| Mobile-responsive email layout | >60% of email is opened on mobile in 2026 | Low | Partial | Single-column inline CSS present; needs audit for 44px buttons and 16px+ fonts |
| Empty-state messaging ("Queue is clear, check back tomorrow") | Sets correct expectations | Low | Exists | Implemented |
| Offline detection banner | PWA expectation | Low | Exists | Banner implemented |
| "Never Suggest" / "Always Suggest" per contact | User control over the algorithm | Low | Exists | Implemented on profile page and preferences view |
| Network health dashboard (scored, enriched, pipeline stats) | Accountability — tells you if the system is working | Med | Exists | dashboard_snapshots table; rendered in dashboard.js |
| Feedback history view (past approve/skip patterns) | Closing the loop — learning from past decisions | Low | Exists | Preferences page shows recent feedback |
| Proper SPA deployment (not static file host) | Hash routing must work; reload must not 404 | Low | Missing | Netlify with `_redirects` file needed |
| "View full queue" link in email → opens PWA | Bridge between email triage and deep review | Low | Partial | Link exists but points at Supabase Storage URL, not Netlify |

---

## Differentiators

Features that set this product apart from generic personal CRM tools. Not expected, but
highly valued when present — these are where the tool earns trust.

| Feature | Value Proposition | Complexity | Notes |
|---------|-----------------|------------|-------|
| Score dimension breakdown bars on profile (Goal Alignment, Industry Fit, Mutual Value, Conv. Hooks, Network Reach) | Transparency in AI scoring builds trust; users know exactly why someone ranked high | Med | Implemented in contact.js; needs visual polish |
| "Why Today" hook shown on queue card and in email | Contextual relevance — not just who, but why now (job change, timing, etc.) | Low | Exists — `why_today` field from queue_generator |
| Skip pattern insight in email footer ("You've skipped 60% of Acme Corp contacts this week") | Self-awareness — surfaces patterns the user can't see themselves | Med | Implemented in email_digest.py `_get_skip_pattern_insight()` |
| Feedback CTA in email (1-5 rating) | Closes the loop on digest quality; feeds algorithm improvement | Low | Implemented with feedback tokens |
| Pipeline funnel view (Imported → Scored → Reviewed → Reached Out) | Operational visibility — tells you where contacts fall out | High | Not yet built; data exists to compute it |
| Enrichment status view (which contacts need more data) | Actionable data quality — shows what to fix | Med | Data quality stats in dashboard snapshot; not a dedicated view |
| Adaptive scoring weights that learn from approve/skip patterns | Algorithm that improves as you use it | High | `user_preferences` scoring_weight prefs are written by pipeline; visible in preferences view |
| Draft message generation with LinkedIn DM deep link | Removes the blank-page problem when reaching out | Med | Implemented in contact.js via `/draft` Edge Function |
| Regenerate draft option | Recovery from bad AI output without leaving the app | Low | Implemented (btn becomes "Regenerate") |
| Remaining contacts compact list in email (+N more in queue) | Full picture without overwhelming primary CTAs | Low | Implemented in email_digest.py |
| Realtime queue updates via Supabase channels | Queue refreshes automatically when pipeline adds new contacts | Med | Implemented in setupQueueRealtime() |
| Email subject line with first-name preview ("Reconnect Mar 4: Sarah, Mike, Lisa + 12 more") | Inbox scanning habit — first names in subject drive open rates | Low | Implemented |

---

## Anti-Features

Things to deliberately NOT build in this milestone. Each one represents a scope trap.

| Anti-Feature | Why Avoid | What to Do Instead |
|-------------|-----------|-------------------|
| Draft outreach from email | Complexity in email clients (form fields, AMP) would break Gmail compatibility; email is triage only | Handle draft generation in PWA contact profile page only |
| OAuth / multi-user auth for PWA | Single-user tool; adding auth adds login friction and deployment complexity | Anon key + action tokens is sufficient security for personal tool |
| Native mobile app (iOS / Android) | Duplicates the PWA; maintenance burden doubles | PWA covers all mobile use cases — add-to-home-screen is good enough |
| Real-time chat or in-app messaging | Not a communication tool; Reconnect surfaces who to reach out to, not how | Link to LinkedIn DM or email client |
| Contact import inside the PWA | Import from LinkedIn CSV is a pipeline concern; the PWA is for review and action | Keep import in the Python pipeline / Streamlit admin |
| Bulk actions ("skip all from Acme Corp") | Adds UI complexity for a task users do a few times total | Let "Never Suggest" per contact handle this; skip pattern insight surfaces it |
| Calendar integration / reminder scheduling | Out of scope; adds OAuth complexity and external dependency | The daily email IS the reminder mechanism |
| Read receipts / tracking pixels | Privacy-hostile for a personal tool; also technically complex with email clients blocking tracking | Not needed — user knows they read their own digest |
| Pagination inside email digest | Email truncation at 102KB (Gmail) is the real constraint; keep to top 5-7 contacts with compact overflow list | Cap featured contacts at 5; show compact overflow list |
| Push notifications to phone | Redundant with email — the daily email digest IS the push notification | Email handles morning habit; PWA is for deeper work |
| Social graph visualization | Impressive to demo, not useful in daily workflow | Pipeline funnel view covers what matters operationally |
| Sentiment analysis on contacts | Adds LLM cost; score_reasoning already captures what matters | Trust the existing rubric scoring (goal alignment, mutual value, etc.) |
| Contact deduplication UI | Already handled in the Python pipeline's import step | Don't expose this complexity in the PWA |

---

## Feature Dependencies

```
Netlify deployment (SPA routing fixed)
  → All PWA pages actually reachable by URL
  → Email "View full profile" links → PWA contact page work correctly
  → Email "View Full Queue" link works correctly

Gmail OAuth configured (or SendGrid/Resend fallback)
  → Email digest sends
  → Token-based action buttons become live
  → Feedback rating CTA becomes live
  → Skip pattern insight reaches user

Contact profile page (PWA) fully built
  → Draft generation usable
  → Score breakdown visible
  → "Never/Always Suggest" buttons reachable from email

Email mobile layout audit (44px buttons, 600px max-width)
  → Mobile triage actually works without mis-taps
  → Opens reliably across Gmail iOS, Gmail Android, Apple Mail

Pipeline funnel view
  → Depends on: dashboard_snapshots with funnel-stage counts (not yet computed)
  → Requires: pipeline step to write stage-count snapshot data

Enrichment status view
  → Depends on: data quality stats already in dashboard snapshot
  → Low effort: surface existing quality.need_enrichment as a dedicated view
```

---

## MVP Recommendation

The milestone is "make the whole system usable end-to-end." Prioritize in this order:

**Must-ship (blocks daily usability):**
1. Netlify deployment with correct `pwa/` directory and `_redirects` for SPA routing
2. Gmail OAuth or alternative email sender (SendGrid / Resend are zero-config alternatives) — email is the entry point
3. Email mobile layout audit — buttons must be 44px+, 600px max-width, 16px+ font
4. Update PWA email link from Supabase Storage URL to Netlify URL

**Should-ship (completes the core loop):**
5. Contact profile page — surface enrichment fields (location, headline, email) that are stored but not yet shown
6. Pipeline funnel view — compute and display stage counts (the data exists, needs a snapshot step)
7. Enrichment status dedicated view (surface existing quality stats as a separate view, not just in dashboard)

**Can-defer (nice to have, not blocking):**
8. Feedback history with approve/skip pattern charts (data exists; visualization is cosmetic)
9. Scoring weight display improvements (already rendered in preferences; just needs polish)
10. Push notification setup (redundant with email in current single-user context)

---

## Sources

- [Best Personal CRM Software in 2026 - CRM.org](https://crm.org/crmland/personal-crm) — feature landscape survey (MEDIUM confidence)
- [Top Personal CRM Tools 2026 - Dex blog](https://getdex.com/blog/top-10-best-personal-crm-apps-in-2026-to-up-your-networking-game/) — competitive feature set (MEDIUM confidence)
- [Personal CRM Tools 2025 - Folk.app](https://www.folk.app/articles/best-personal-crm) — anti-feature insight on over-engineering (MEDIUM confidence)
- [Email CTA Best Practices 2025 - Moosend](https://moosend.com/blog/email-cta/) — button sizing, layout patterns (HIGH confidence, official)
- [Mobile Emails 2026 - Saturate Marketing](https://saturate.marketing/designing-emails-for-mobile-in-2026-structure-speed-and-what-still-works) — 600px, 44px buttons, 16px+ font minimums (MEDIUM confidence)
- [Responsive Email Design 2026 - Mailtrap](https://mailtrap.io/blog/responsive-email-design/) — Gmail 102KB truncation limit (HIGH confidence)
- [Capability URLs - W3C TAG](https://w3ctag.github.io/capability-urls/) — security pattern for token-based email actions (HIGH confidence, authoritative)
- [AI Lead Scoring Transparency 2026 - Warmly](https://www.warmly.ai/p/blog/ai-lead-scoring) — "why this is hot" driver cards in-context (MEDIUM confidence)
- [Predictive Scoring Transparency 2025 - Influencers Time](https://www.influencers-time.com/predictive-lead-scoring-platforms-built-on-first-party-data/) — feedback loops, scoring trust (MEDIUM confidence)
- [PWA Offline Patterns 2025 - LogRocket](https://blog.logrocket.com/nextjs-16-pwa-offline-support/) — stale-while-revalidate, offline queue patterns (HIGH confidence)
- Existing codebase audit: `pwa/js/{queue,contact,dashboard,preferences}.js`, `src/integrations/email_digest.py`, `src/database/models.py` (HIGH confidence — direct source)
