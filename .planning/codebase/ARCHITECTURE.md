# Architecture

**Analysis Date:** 2026-03-08

## Pattern Overview

**Overall:** Multi-tier data processing pipeline architecture with local batch processing, cloud synchronization, and distributed UI layers.

**Key Characteristics:**
- Local-first SQLite database → daily batch pipeline → cloud PostgreSQL sync
- Decoupled LLM scoring layer (OpenAI GPT-4o-mini) plugged into pipeline
- Bidirectional sync: push pipeline results (connections, queue) → pull user actions
- API-driven PWA (Vanilla JS) backed by Supabase PostgREST + Edge Functions
- Admin UI (Streamlit) for configuration and monitoring

## Layers

**Data Layer:**
- Purpose: Persistent storage for contacts, relationships, enrichment data
- Location: `src/database/models.py`, `src/database/engine.py`
- Contains: SQLModel definitions (Connection, OutreachQueueItem, UserProfile, etc.), session management
- Depends on: SQLAlchemy, SQLModel, sqlite3 (local) or psycopg2 (cloud)
- Used by: All pipeline steps, UI, sync operations

**Ingestion Layer:**
- Purpose: Import contact data from external sources
- Location: `src/ingestion/`
- Contains: LinkedIn dump parser, CSV importers, RapidAPI/Hunter.io enrichment clients, profile inference
- Key files: `linkedin_dump.py`, `rapidapi_linkedin.py`, `hunter.py`, `apify_client.py`
- Depends on: Data layer, thefuzz (fuzzy matching), zipfile, CSV parsing
- Used by: Daily pipeline step 1 (import)

**LLM/Scoring Layer:**
- Purpose: AI-powered contact prioritization and content generation
- Location: `src/llm/`
- Contains: Scoring rubric implementation, prose generation, prescoring, opportunity matching
- Key files: `scoring.py`, `prescoring.py`, `prose.py`, `opportunity_match.py`, `data_analyzer.py`
- Depends on: OpenAI API, data layer
- Used by: Pipeline steps 3, 5 (scoring); Queue generation; Email digest

**Pipeline Orchestration:**
- Purpose: Coordinate all data processing steps daily
- Location: `src/pipeline/daily_pipeline.py`
- Contains: 10-step workflow runner, state management via PipelineRun model
- Entry point: `run_daily_pipeline()` — invoked at 8AM via LaunchAgent
- Depends on: All layers (ingestion, LLM, queue, sync, integrations)
- Step flow: Import → Prescore → Enrich → Score → Queue → Sync → Data completeness → Feedback processing → Enrichment planning → Dashboard snapshot

**Queue Management:**
- Purpose: Generate and manage outreach candidates with exclusion rules
- Location: `src/pipeline/queue_generator.py`
- Contains: Exclusion logic (active conversations, recent contact, already queued), channel selection
- Depends on: Data layer, config
- Used by: Pipeline step 6

**Sync Layer:**
- Purpose: Bidirectional synchronization between local SQLite and cloud PostgreSQL
- Location: `src/sync/`
- Key files: `push.py`, `pull.py`, `runner.py`, `engines.py`
- Push direction: Connections, queue items, dashboard snapshots
- Pull direction: User feedback, approved actions from PWA
- Depends on: SQLAlchemy, psycopg2, connection pooling
- Used by: Pipeline step 7

**Integration Layer:**
- Purpose: External service clients for email and notifications
- Location: `src/integrations/`
- Contains: Gmail OAuth integration, email digest builder, Telegram bot client
- Key files: `gmail.py`, `email_digest.py`, `telegram.py`
- Depends on: OpenAI (for prose), config, data layer
- Used by: Pipeline final steps

**Services Layer:**
- Purpose: Shared business logic accessed by pipeline and UI
- Location: `src/services/`
- Contains: Dashboard computation, metric aggregation
- Key files: `dashboard_service.py`
- Depends on: Data layer, LLM layer
- Used by: Pipeline step 10, Streamlit dashboard view

**Admin UI (Streamlit):**
- Purpose: Local configuration, monitoring, manual triggers
- Location: `src/ui/`
- Views: `app.py` (main), `views/dashboard.py`, `views/review.py`, `views/opportunities.py`, `views/ask.py`
- Components: Search filters, connection detail renderer, action buttons
- Depends on: Data layer, Streamlit framework
- Entry point: `streamlit run src/ui/app.py`

**PWA Layer:**
- Purpose: Production user-facing queue review interface
- Location: `pwa/`
- Architecture: Hash-based router (no backend routing), vanilla JS + Supabase JS SDK
- Entry point: `index.html` served from Supabase Storage bucket `pwa`
- Pages: /queue (main), /contact/[id], /dashboard, /preferences
- Depends on: Supabase PostgREST API, Edge Functions
- Service Worker: Offline support and sync

**API/Functions Layer:**
- Purpose: Serverless handlers for user actions and webhooks
- Location: `supabase/functions/`
- Edge Functions: `action/index.ts` (approve/skip/snooze/feedback), `draft/index.ts` (prose gen), `feedback/index.ts` (ratings)
- Auth: Token-based (one-time action tokens), no JWT required for action function
- Depends on: Deno TypeScript runtime, Supabase client
- Used by: PWA (via email links and direct calls)

## Data Flow

**Daily Pipeline Execution:**

1. LaunchAgent triggers `python -m src.pipeline.daily_pipeline` at 8AM
2. LinkedIn dump import (if available in ~/Downloads)
3. Prescore all unscored contacts via OpenAI batch
4. Enrich top tier-1 and tier-2 contacts via RapidAPI LinkedIn
5. Score enriched contacts using LLM rubric
6. Generate outreach queue with exclusion rules
7. Compute data completeness metrics
8. Process user feedback → update scoring weights
9. Plan next enrichment budget
10. Compute and save dashboard snapshot
11. Push to Supabase cloud (if configured)
12. Send email digest with action tokens
13. Send Telegram notification

**User Action Flow (Email-Driven):**

1. User receives digest email with action links
2. Clicks approve/skip/snooze button
3. Browser follows link to Supabase Edge Function: `/functions/v1/action?token=UUID`
4. Edge Function validates token expiry, marks as used, updates queue item status
5. Pipeline's next pull phase retrieves updated status
6. Next digest reflects user's previous actions

**PWA Interaction Flow:**

1. PWA loads from Supabase Storage, initializes Supabase client
2. User navigates to /queue route (hash-based)
3. PWA fetches queue items via PostgREST: `GET /rest/v1/outreach_queue`
4. User reviews, approves/skips contacts
5. Actions call Edge Functions directly or update locally (offline mode)
6. Service Worker syncs when online
7. PWA fetches updated connection details via PostgREST

**State Management:**

- **Local state:** SQLite Connection, OutreachQueueItem tables (source of truth for pipeline)
- **Cloud state:** PostgreSQL mirrored tables + action changes
- **Pipeline state:** PipelineRun record with step tracking
- **Sync state:** SyncMetadata singleton (last push/pull timestamps)

## Key Abstractions

**Connection (Data Model):**
- Purpose: Represents a professional contact with scoring, enrichment, and engagement data
- Examples: `src/database/models.py` lines 62-140
- Pattern: SQLModel with composite indexes for search, scoring, and engagement queries; JSON columns for flexible enrichment data storage
- Nested enrichment: `get_enrichment_data()` helper unwraps RapidAPI response structure

**OutreachQueueItem (Workflow):**
- Purpose: Queue entry with draft message, status, and action tokens
- States: pending_review → approved/skipped → sent
- Pattern: Immutable history via timestamps (created_at, reviewed_at, sent_at)

**PipelineRun (Audit Trail):**
- Purpose: Track execution history for monitoring
- Pattern: Records steps_completed and step_results as JSON for flexible schema evolution
- Used for: Debugging, billing, SLO monitoring

**ActionToken (Security):**
- Purpose: One-time-use links for email actions
- Pattern: UUID tokens with expiry, marks used after one click
- Maps to: Edge Functions via URL parameter `?token=UUID`

**Scoring Rubric:**
- Purpose: Consistent, explainable prioritization logic
- Dimensions: Goal Alignment (0-25), Industry Overlap (0-20), Mutual Value (0-20), Conversation Hooks (0-20), Network Reach (0-15)
- Implementation: `src/llm/scoring.py` SCORING_SYSTEM_PROMPT lines 15-140
- Outputs: reconnect_score (0-100), score_reasoning (text)

**Exclusion Rules (Queue Logic):**
- Purpose: Prevent irrelevant outreach
- Rules: Active conversation (< N days), recently contacted, already in queue, no contact info
- Pattern: `is_contact_excluded()` returns ExclusionResult with reason
- Configuration: Settings `active_conversation_days`, `recently_contacted_days`, etc.

## Entry Points

**Scheduled Pipeline:**
- Location: `src/pipeline/daily_pipeline.py` function `run_daily_pipeline()`
- Triggers: 8AM via macOS LaunchAgent (or manual CLI invocation)
- Responsibilities: Orchestrate all 10 processing steps, manage PipelineRun state, handle errors
- Returns: Dict with results from each step

**Streamlit Admin UI:**
- Location: `src/ui/app.py` function `render_sidebar_nav()`
- Triggers: User runs `streamlit run src/ui/app.py`
- Responsibilities: View/search contacts, run manual pipeline, review queue, dashboard
- Pages: Contacts (main), Dashboard, Ask My Network, Review, Opportunities

**PWA Frontend:**
- Location: `pwa/index.html`, `pwa/js/app.js` function `render()`
- Triggers: User visits PWA URL from Supabase Storage
- Responsibilities: Route-based UI for queue, contact details, preferences
- Data source: PostgREST API + Edge Functions

**Email Action Endpoint:**
- Location: `supabase/functions/action/index.ts` (Deno)
- Triggers: User clicks approve/skip/snooze link in digest email
- Responsibilities: Validate token, mark used, update queue status
- Auth: Service role key (--no-verify-jwt)

**Pull from Cloud:**
- Location: `src/sync/pull.py` function `pull_from_cloud()`
- Triggers: Pipeline step 11, after push completes
- Responsibilities: Fetch user-approved actions, merge into local queue
- Pattern: SELECT WHERE action_status = 'approved' on cloud, upsert locally

## Error Handling

**Strategy:** Non-fatal failures are logged and reported, critical steps block pipeline

**Patterns:**

- **Try-except by step:** Each pipeline step wrapped in try-except (lines 89-375 in `daily_pipeline.py`)
- **Error aggregation:** Results dict includes `{"error": {"message": str, "step": str}}`
- **Failure notification:** Telegram bot sends alert with step name if configured
- **Partial completion:** Pipeline continues after non-critical steps fail (data completeness, feedback, enrichment planning)
- **PipelineRun state:** `status = "failed"` recorded with `error_step` and `error_message` for audit

**Common Failures:**

- OpenAI API rate limit → Caught by `prescoring`, `scoring` functions
- RapidAPI quota exhausted → Caught in enrichment loop with retry count
- Supabase sync network error → Caught by sync runner, recorded in SyncMetadata.last_error
- Email send failure → Caught, logged non-fatal if Gmail not configured

## Cross-Cutting Concerns

**Logging:**
- Tool: Python `logging` module + Telegram alerts
- Pattern: Get logger via `logging.getLogger(__name__)` in each module
- Levels: DEBUG for SQL echo, INFO for step transitions, WARNING for non-fatal failures, ERROR for critical failures
- Telegram: `src/integrations/telegram.py` sends notifications on pipeline start/success/failure

**Validation:**
- Configuration: Pydantic Settings in `src/config.py` validates env vars at import time
- Database: SQLModel enforces field types; indexes on frequently queried columns (name, email, reconnect_score)
- Token generation: ActionToken validates expiry before use in Edge Function
- Queue exclusion: Multi-rule check in `is_contact_excluded()` before queueing

**Authentication:**
- Supabase PWA: Anon key (PostgREST read-only for public tables)
- Edge Functions: Service role key in Deno runtime (no JWT requirement for /action endpoint)
- Gmail OAuth: Stored in GmailCredentials table, refreshed on send attempt
- Local Streamlit: No auth (assumes localhost-only or Streamlit Cloud auth)

**Rate Limiting:**
- OpenAI: Prescore uses batch mode, reduces API calls; prescore_batch_size config (default 50)
- RapidAPI: enrich_budget config (default 30 per day) controls LinkedIn enrichment calls
- Supabase: Pull frequency (once per pipeline run) minimizes DB traffic

**Caching:**
- Settings: `@lru_cache()` on `get_settings()` (single instance per process)
- Enrichment data: Stored in raw_enrichment JSON column, reused in scoring
- Connection summaries: cached_summary field with timestamp, TTL in config (cache_ttl_days)
- PWA offline: Service Worker caches queue and contact data locally

**Timestamps:**
- Pattern: All tables use `created_at` (immutable), `updated_at` (mutable), optional step-specific times
- UTC: All times stored in UTC, no timezone conversions
- Freshness queries: Index on `enriched_at`, `last_message_date` for queue generation exclusion
