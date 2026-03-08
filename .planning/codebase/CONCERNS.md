# Codebase Concerns

**Analysis Date:** 2025-02-08

## Tech Debt

**Gmail OAuth Not Configured:**
- Issue: Email digest generates HTML but cannot send without Gmail OAuth setup
- Files: `src/integrations/gmail.py`, `src/pipeline/daily_pipeline.py` (lines 315-331)
- Impact: Daily digest emails fail silently. Users don't receive reconnection reminders. Feature is implemented but disabled.
- Fix approach: Document Gmail OAuth setup steps in README. Add UI flow to `src/ui/app.py` to guide users through credential exchange. The infrastructure is there; needs frontend integration.

**RapidAPI Enrichment Falls Back to Mock Data:**
- Issue: When `rapidapi_key` is not configured, `fetch_linkedin_profile()` silently returns mock profile data instead of error
- Files: `src/ingestion/rapidapi_linkedin.py` (lines 27-29)
- Impact: Enrichment silently degrades to dummy data, corrupting scoring decisions. Users may not realize enrichment is fake.
- Fix approach: Log a warning and skip enrichment rather than mock it. Ensure `update_connection_from_profile()` returns False when data is mock.

**SQLModel Metadata Reserved Name Workaround:**
- Issue: SQLAlchemy reserves "metadata" as a column name. UserFeedback works around this with `sa_column=Column("metadata", JSON)`
- Files: `src/database/models.py` (line 356)
- Impact: Non-obvious code; fragile if refactored. Future developers may not understand the mapping.
- Fix approach: Rename field to `extra_data` in code but keep database column as `metadata` (already done correctly). Document in model docstring.

**Large Complex Files:**
- Issue: Several Python files exceed 1000 lines, mixing responsibilities
- Files: `src/ingestion/linkedin_dump.py` (1395 lines), `src/ui/app.py` (1061 lines)
- Impact: Hard to test, maintain, and reason about. Risk of bugs in complex logic.
- Fix approach: Split LinkedIn dump parser into: CSV parsing, conversation summarization, engagement signal extraction. Split UI app into page modules (contacts, dashboard, queue, preferences).

**Bare Exception Handlers:**
- Issue: Many `except Exception:` blocks without context, especially in pipeline non-fatal steps
- Files: `src/pipeline/daily_pipeline.py` (lines 238, 252, 266, 284, 307, 325, 342), `src/sync/push.py` (line 255)
- Impact: Errors are swallowed silently. Difficult to debug failures. Critical information lost.
- Fix approach: Replace bare except with specific exception types. Log with full traceback. Consider whether "non-fatal" steps should actually continue or halt the pipeline.

**Limited Error Context in API Ingestion:**
- Issue: RapidAPI and Hunter.io failures only print to console, no structured logging
- Files: `src/ingestion/rapidapi_linkedin.py` (lines 71-73), `src/ingestion/hunter.py`
- Impact: No audit trail. Difficult to track which enrichments failed and why. Can't retroactively diagnose data quality issues.
- Fix approach: Implement structured logging with enrichment failure tracking. Store failure reasons in database.

---

## Known Bugs

**Date Format Ambiguity:**
- Symptoms: Dates from LinkedIn may be parsed incorrectly in dual-format scenarios (MM/DD/YYYY vs DD/MM/YYYY)
- Files: `src/ingestion/linkedin_dump.py` (lines 136-156)
- Trigger: Import LinkedIn dump with inconsistent date formats across records
- Workaround: Currently tries multiple formats. Risk of wrong interpretation if both interpretations are valid (e.g., "01/05/2024").

**Edge Function Token Security:**
- Symptoms: Action tokens are one-time-use but only verified in Edge Functions, not in database
- Files: `supabase/functions/action/index.ts` (lines 41-48)
- Trigger: Token marked used in cloud DB; local DB may not sync immediately
- Workaround: TTL of 48 hours provides expiry fallback. If sync fails, tokens could theoretically be reused.

---

## Security Considerations

**Gmail Credentials Stored in SQLite:**
- Risk: OAuth tokens stored unencrypted in local SQLite database
- Files: `src/database/models.py` (lines 259-278), `src/integrations/gmail.py` (entire file)
- Current mitigation: SQLite is local-only. Access token refreshes limit token lifetime exposure.
- Recommendations: Encrypt credentials at rest using `cryptography` library. Consider storing only refresh token, not access token.

**RapidAPI Key in Environment:**
- Risk: RapidAPI key could be leaked if .env is accidentally committed or exposed
- Files: `src/config.py` (lines 46-47), `.env` file (forbidden read)
- Current mitigation: .gitignore protects .env file
- Recommendations: Add secret scanning hook to pre-commit. Use .env template file in repo. Document in SECURITY.md.

**Edge Functions Disable JWT on Public Actions:**
- Risk: `supabase/functions/action` and `supabase/functions/feedback` have `--no-verify-jwt` for email link clicks to work
- Files: `supabase/functions/action/index.ts`, `supabase/functions/feedback/index.ts`
- Current mitigation: Token UUID is cryptographically random; tokens expire; tokens are single-use
- Recommendations: Implement rate limiting per IP. Monitor for suspicious token usage patterns. Consider token signing with HMAC.

**Supabase Anon Key in PWA:**
- Risk: Anon key is embedded in client-side JavaScript; attacker can use it to query database
- Files: `pwa/js/app.js` (lines 4-5)
- Current mitigation: Anon key has restricted Row-Level Security (RLS) policies (assumed)
- Recommendations: Verify RLS policies are strict. Consider PostgREST request signing. Document scope of anon key.

---

## Performance Bottlenecks

**LLM Batch Calls Without Caching:**
- Problem: Prescoring, scoring, and opportunity matching make synchronous LLM calls for every contact
- Files: `src/llm/prescoring.py` (entire file), `src/llm/scoring.py` (entire file)
- Cause: No caching layer; no batch inference. Each contact = one API call.
- Improvement path: Implement `cached_summary` for scored contacts. Batch multiple scoring requests into single GPT-4 call. Cache embedding vectors. Skip re-scoring contacts that haven't changed.

**Daily Pipeline Sequential Steps:**
- Problem: Pipeline runs 10 steps sequentially, blocking on slow enrichment calls
- Files: `src/pipeline/daily_pipeline.py` (lines 89-349)
- Cause: Tier 1 enrichment (lines 149-183) makes individual RapidAPI calls. Each takes ~1-3 seconds.
- Improvement path: Parallelize enrichment using ThreadPoolExecutor or asyncio. Set per-step timeouts to fail fast. Implement partial pipeline recovery (skip failed step, continue).

**Search and Filtering on Full Load:**
- Problem: UI views load all connections into memory, then filter in Python
- Files: `src/ui/app.py`, `src/ui/views/` (all files)
- Cause: No pagination, no server-side filtering
- Improvement path: Implement limit/offset queries. Add full-text search indexes on PostgreSQL. Use lazy loading in PWA.

**Engagement Signal Processing Inefficient:**
- Problem: Parsing endorsements/recommendations creates individual database records without batching
- Files: `src/ingestion/linkedin_dump.py` (endorsements/recommendations parsing)
- Cause: Multiple session.add() calls in loop instead of batch insert
- Improvement path: Batch create engagement signals in groups of 100. Use bulk_insert_mappings if available.

---

## Fragile Areas

**LinkedIn Dump Import Parsing:**
- Files: `src/ingestion/linkedin_dump.py` (entire file)
- Why fragile: Parsing is tightly coupled to CSV column names and ordering. LinkedIn changes their export format periodically.
- Safe modification: Add schema validation before parsing. Test with multiple LinkedIn export samples. Add migration layer if columns change.
- Test coverage: No unit tests for CSV parsing. Manual testing only.

**Email Digest Token Generation:**
- Files: `src/integrations/email_digest.py` (lines 154-196), `src/api/tokens.py`
- Why fragile: Token creation happens in email builder; failures are silently caught. If token creation fails, digest still sends without action buttons.
- Safe modification: Move token creation outside email building. Pre-create tokens before rendering HTML. Add explicit error on token creation failure.
- Test coverage: No unit tests. Manual testing required.

**Scoring Prompt Engineering:**
- Files: `src/llm/scoring.py` (lines 15-69, 87-150)
- Why fragile: Scoring logic depends on exact prompt structure and LLM model. Changes to prompt can drastically alter score distribution.
- Safe modification: Version prompts in code. Test score distribution on sample contact set. A/B test prompt changes. Store rubric scores separately for analysis.
- Test coverage: No automated scoring tests. No regression suite.

**Sync Between Local and Cloud:**
- Files: `src/sync/push.py`, `src/sync/pull.py`, `src/sync/runner.py`
- Why fragile: Bidirectional sync with implicit ordering assumptions. Cloud and local schemas must match.
- Safe modification: Add sync versioning. Explicitly handle schema mismatches. Add pre-sync validation. Test offline scenarios.
- Test coverage: No sync integration tests. Requires working Supabase instance.

---

## Scaling Limits

**SQLite Concurrency:**
- Current capacity: Single-threaded access via `check_same_thread=False` workaround
- Limit: Will fail under concurrent write load (e.g., multiple Streamlit users or parallel enrichment workers)
- Scaling path: Migrate to PostgreSQL locally or use Supabase exclusively. Implement connection pooling.

**LLM API Rate Limits:**
- Current capacity: ~30 enrichments/day × 2 LLM calls per = ~60 API calls/day at $0.15 per 1M tokens
- Limit: If daily queue size increases to 100+, will hit OpenAI rate limits (3000 rpm on free tier)
- Scaling path: Batch scoring requests. Implement exponential backoff. Consider cheaper models for low-confidence cases. Add queue prioritization.

**RapidAPI Monthly Quota:**
- Current capacity: Unknown (depends on tier; free tier has daily limits)
- Limit: Enriching 30 contacts/day = 900/month. Free tier is typically 50-100/month.
- Scaling path: Document actual quota. Implement monthly quota tracking. Skip enrichment if quota exhausted. Offer paid tier fallback.

**Supabase Edge Function Concurrency:**
- Current capacity: Default limits per Supabase plan
- Limit: If many users click email links simultaneously, functions may timeout or queue
- Scaling path: Monitor function execution times. Implement request queuing in the function. Add retry logic client-side.

---

## Dependencies at Risk

**OpenAI API Dependency:**
- Risk: Critical for prescoring, full scoring, prose generation, and opportunity matching. All LLM functionality requires OPENAI_API_KEY.
- Impact: If OpenAI is down or API changes, scoring pipeline halts. No fallback LLM.
- Migration plan: Implement adapter pattern for LLM providers. Add Anthropic or local LLM fallback. Cache LLM outputs more aggressively.

**RapidAPI LinkedIn Profile Data:**
- Risk: Enrichment API may be deprecated or data quality may degrade as LinkedIn changes their API.
- Impact: Enrichment step fails silently (returns mock data). Scores degrade without visibility.
- Migration plan: Add Hunter.io or clearbit as fallback enrichment. Implement enrichment provider abstraction. Monitor enrichment data freshness.

**Gmail API OAuth:**
- Risk: Gmail API OAuth flow may change. User's refresh tokens may expire or be revoked.
- Impact: Email digest stops working with no user visibility. Requires credential re-authentication.
- Migration plan: Implement token refresh monitoring. Add warning if token is expiring soon. Document Gmail API deprecation timeline.

**Supabase Project Stability:**
- Risk: If Supabase project is deleted or data is lost, all cloud data is gone.
- Impact: PWA cannot load queue or dashboard. Sync fails.
- Migration plan: Implement database backups. Automate periodic exports. Test disaster recovery procedure.

---

## Missing Critical Features

**No Offline Sync:**
- Problem: PWA has offline detection but no offline queue. Changes made offline are lost if not synced.
- Blocks: Using app without internet connection. Working on mobile networks with intermittent connectivity.

**No Undo/Rollback:**
- Problem: Once a contact is marked "approved" or "skipped", there's no easy way to reverse it.
- Blocks: Recovering from accidental actions. Reclassifying contacts.

**No Bulk Operations:**
- Problem: No way to bulk-tag, bulk-score, or bulk-export contacts.
- Blocks: Managing large contact lists (100+ contacts). Preparing outreach campaigns.

**No Draft History:**
- Problem: When user approves a contact, draft message is generated on-demand. If user doesn't send immediately, draft is lost.
- Blocks: Saving drafts for later. A/B testing message variants.

**No Engagement Metrics Dashboard:**
- Problem: Once outreach is sent, no tracking of replies or engagement.
- Blocks: Measuring reconnection success rate. Identifying which hooks/messages work best.

---

## Test Coverage Gaps

**No Unit Tests for LLM Scoring:**
- What's not tested: Scoring rubric calculation, dimension scoring logic, prompt building
- Files: `src/llm/scoring.py` (entire file), `src/llm/prescoring.py` (entire file)
- Risk: Score distribution could regress without detection. Prompt changes could break scoring silently.
- Priority: High

**No Integration Tests for Pipeline:**
- What's not tested: End-to-end daily pipeline with import + enrich + score + queue + digest
- Files: `src/pipeline/daily_pipeline.py` (entire file)
- Risk: Breaking changes to pipeline steps are only caught in production. Multi-step failures are hard to diagnose.
- Priority: High

**No Sync Tests:**
- What's not tested: Bidirectional sync between local and cloud. Conflict resolution. Schema migrations.
- Files: `src/sync/push.py`, `src/sync/pull.py`
- Risk: Sync corruption silently propagates to cloud. Users lose data without knowing.
- Priority: High

**No Email Digest Tests:**
- What's not tested: HTML rendering, token generation, action button links, feedback flow
- Files: `src/integrations/email_digest.py` (entire file), `supabase/functions/action/index.ts`, `supabase/functions/feedback/index.ts`
- Risk: Email digest breaks on minor HTML/template changes. Action links silently fail.
- Priority: Medium

**No PWA Component Tests:**
- What's not tested: Queue rendering, contact detail view, form validation, offline behavior
- Files: `pwa/js/queue.js`, `pwa/js/contact.js`, `pwa/js/dashboard.js`, `pwa/js/preferences.js`
- Risk: UI breaks silently in browser. Responsive design regressions undetected. Offline mode untested.
- Priority: Medium

**No CSV Import Tests:**
- What's not tested: Connection CSV parsing with edge cases (missing columns, special characters, duplicate names)
- Files: `src/ingestion/csv_import.py`, `src/ingestion/linkedin_dump.py`
- Risk: Bad imports corrupt database. Data loss from malformed CSVs not caught.
- Priority: Medium

---

## Technical Debt Summary by Impact

**Critical (blocks features):**
- No offline sync capability
- Gmail OAuth not configured (feature non-functional)
- RapidAPI mock data fallback (corrupts scoring)

**High (impacts reliability):**
- Bare exception handlers (errors swallowed)
- Large monolithic files (hard to maintain)
- No LLM caching (slow, expensive)
- Sequential pipeline (slow)
- No unit tests for scoring/pipeline

**Medium (impacts quality):**
- Fragile sync layer
- Edge function security assumptions
- Unencrypted Gmail credentials
- LinkedIn dump parser brittleness
- Missing engagement outcome tracking

**Low (nice-to-have):**
- Performance optimizations (batch LLM, pagination)
- Missing UI features (bulk ops, draft history)

---

*Concerns audit: 2025-02-08*
