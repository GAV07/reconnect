# Codebase Structure

**Analysis Date:** 2026-03-08

## Directory Layout

```
reconnect/
├── src/                           # Python backend code
│   ├── __init__.py
│   ├── config.py                  # Pydantic settings from environment variables
│   ├── api/                       # Supabase integration API layer
│   │   ├── __init__.py
│   │   └── tokens.py              # Action token generation for email links
│   ├── database/                  # ORM and persistence
│   │   ├── __init__.py
│   │   ├── engine.py              # SQLAlchemy engine factory (local/cloud modes)
│   │   └── models.py              # SQLModel table definitions
│   ├── ingestion/                 # External data importers
│   │   ├── __init__.py
│   │   ├── linkedin_dump.py       # ZIP parser for full LinkedIn data exports
│   │   ├── profile_inference.py   # User profile extraction from dump
│   │   ├── rapidapi_linkedin.py   # RapidAPI client for LinkedIn enrichment
│   │   ├── hunter.py              # Hunter.io email finder
│   │   ├── apify_client.py        # Apify scraper client (deprecated)
│   │   └── csv_import.py          # CSV batch import utility
│   ├── llm/                       # AI/LLM integrations
│   │   ├── __init__.py
│   │   ├── scoring.py             # OpenAI rubric-based connection scoring
│   │   ├── prescoring.py          # Fast pre-enrichment prioritization
│   │   ├── prose.py               # Outreach message generation
│   │   ├── opportunity_match.py   # Goal-to-contact matching
│   │   ├── data_analyzer.py       # Data completeness analysis
│   │   └── prompts.py             # Shared prompt templates
│   ├── pipeline/                  # Daily workflow orchestration
│   │   ├── __init__.py
│   │   ├── daily_pipeline.py      # Main 10-step pipeline runner
│   │   ├── queue_generator.py     # Outreach queue creation with rules
│   │   ├── feedback_processor.py  # User feedback → scoring adjustments
│   │   └── enrichment_planner.py  # Next-day enrichment budget planning
│   ├── sync/                      # Cloud synchronization
│   │   ├── __init__.py
│   │   ├── engines.py             # Local/cloud engine factory methods
│   │   ├── runner.py              # Sync orchestrator (push then pull)
│   │   ├── push.py                # Push connections/queue to Supabase
│   │   └── pull.py                # Pull user actions from Supabase
│   ├── integrations/              # External services
│   │   ├── __init__.py
│   │   ├── gmail.py               # OAuth2 client and message sender
│   │   ├── email_digest.py        # HTML email builder with action tokens
│   │   └── telegram.py            # Bot client for notifications
│   ├── services/                  # Shared business logic
│   │   ├── __init__.py
│   │   └── dashboard_service.py   # Metric computation and snapshots
│   └── ui/                        # Streamlit admin interface
│       ├── __init__.py
│       ├── app.py                 # Main app shell and router
│       ├── components/            # Reusable UI building blocks
│       │   ├── __init__.py
│       │   ├── actions.py         # Approve/skip/snooze buttons
│       │   ├── detail.py          # Connection detail card
│       │   └── search.py          # Filter and search bar
│       └── views/                 # Page implementations
│           ├── __init__.py
│           ├── dashboard.py       # Network health and metrics
│           ├── review.py          # Queue review interface
│           ├── opportunities.py   # Contact browser
│           └── ask.py             # Network search tool
│
├── pwa/                           # Progressive Web App (Vanilla JS)
│   ├── index.html                 # App shell with manifest injection
│   ├── manifest.json              # PWA metadata
│   ├── service-worker.js          # Offline support and sync
│   ├── css/                       # Stylesheets
│   │   └── *.css                  # Utility and component styles
│   ├── js/                        # Application code
│   │   ├── app.js                 # Router and Supabase client init
│   │   ├── queue.js               # Queue view (main page)
│   │   ├── contact.js             # Individual contact details
│   │   ├── dashboard.js           # Metrics dashboard
│   │   ├── preferences.js         # User preferences editor
│   │   ├── offline.js             # Offline sync manager
│   │   └── push.js                # Push notification handler
│   └── icons/                     # App icons
│       └── *.png                  # favicon and app icons
│
├── supabase/                      # Cloud infrastructure
│   ├── migrations/                # SQL schema versions
│   │   ├── 20240207000000_initial_schema.sql
│   │   ├── 20240208000000_enhanced_linkedin_ingestion.sql
│   │   └── 20260305000000_pwa_overhaul.sql
│   ├── seed.sql                   # Test data (unused in production)
│   └── functions/                 # Serverless edge functions (Deno)
│       ├── action/index.ts        # Email action handler (approve/skip/snooze/feedback)
│       ├── draft/index.ts         # Prose generation endpoint
│       └── feedback/index.ts      # Feedback submission handler
│
├── .planning/                     # GSD documentation (this file)
│   └── codebase/                  # Auto-generated architecture docs
│
├── pyproject.toml                 # Python dependencies and metadata
├── package.json                   # Node deps for PWA build (if any)
├── .env.example                   # Template environment variables
└── README.md                       # Project overview
```

## Directory Purposes

**src/:** All Python backend code. Entry point depends on context:
- Scheduled: `python -m src.pipeline.daily_pipeline` (runs at 8AM)
- Admin UI: `streamlit run src/ui/app.py` (localhost:8501)
- Import/manual: Direct function calls via CLI or Streamlit

**src/database/:** ORM definitions and session management. `engine.py` is the factory:
- `get_engine(mode)` returns SQLAlchemy Engine for "local" (SQLite) or "cloud" (PostgreSQL)
- `init_db()` creates all tables via SQLModel.metadata.create_all()
- `get_session()` provides context manager for transactional access
- All modules use `get_session()` context manager for queries

**src/ingestion/:** Import and enrichment clients. Entry points:
- LinkedIn: `linkedin_dump.import_linkedin_dump()` processes ZIP files
- RapidAPI: `rapidapi_linkedin.update_connection_from_profile()` enriches individual contact
- Hunter: `hunter.find_email()` does email lookups

**src/llm/:** OpenAI integration. Key functions:
- `prescoring.prescore_unscored_connections()` batches contacts, assigns pre_score and pre_score_tier
- `scoring.score_connection()` applies full rubric to enriched contact, sets reconnect_score
- `prose.generate_outreach_message()` creates draft email/DM text

**src/pipeline/:** Daily workflow. Central entry:
- `daily_pipeline.run_daily_pipeline()` is the orchestrator
- Runs 10 steps sequentially, captures results in PipelineRun record
- Returns dict with all step outputs

**src/sync/:** Bidirectional cloud sync. Flow:
- `runner.run_sync()` → `push.push_to_cloud()` → `pull.pull_from_cloud()`
- Push: SELECT from local, UPSERT to cloud for Connections, OutreachQueueItems, DashboardSnapshots
- Pull: SELECT changed actions from cloud, merge into local queue status

**src/ui/:** Streamlit admin dashboard. Hierarchical:
- `app.py` is entry point, manages session state and page routing
- `components/` are reusable; `views/` are full pages
- Pages access database directly via `get_session()`

**pwa/:** User-facing queue review app. Architecture:
- `index.html` is sole entry point, loads all JS modules
- `app.js` initializes Supabase client, routes via hash (#/queue, #/contact/id, etc.)
- Each view (queue.js, contact.js, dashboard.js) fetches data from PostgREST API
- `service-worker.js` enables offline mode and sync

**supabase/functions/:** Serverless handlers invoked by PWA or email.
- `action/index.ts` receives ?token=UUID, validates, updates queue status
- `draft/index.ts` generates prose via OpenAI if triggered from PWA
- Deno TypeScript runtime; no build step required
- Deployed via `supabase functions deploy` or CI/CD

## Key File Locations

**Entry Points:**

- `src/pipeline/daily_pipeline.py`: Daily scheduled workflow (LaunchAgent @ 8AM)
- `src/ui/app.py`: Streamlit admin UI (localhost:8501)
- `pwa/index.html`: PWA user interface (Supabase Storage URL)
- `supabase/functions/action/index.ts`: Email action handler
- `src/api/tokens.py`: Token generation for email links

**Configuration:**

- `src/config.py`: Pydantic Settings, reads .env file
- `pyproject.toml`: Python dependencies and project metadata
- `.env`: Local environment variables (not committed, contains secrets)
- `supabase/functions/*.ts`: Edge Function secrets set via `supabase secrets set`

**Database:**

- `src/database/models.py`: SQLModel table definitions (35 tables/models)
- `src/database/engine.py`: SQLAlchemy engine factory and session manager
- `supabase/migrations/`: SQL schema versions (Postgres DDL)
- `data/reconnect.db`: Local SQLite database file (created on first run)

**Business Logic:**

- `src/llm/scoring.py`: Rubric-based scoring (main intelligence)
- `src/pipeline/queue_generator.py`: Exclusion rules and queue logic
- `src/integrations/email_digest.py`: Email template and token injection
- `src/services/dashboard_service.py`: Metric computation

**Testing & Debugging:**

- `src/pipeline/daily_pipeline.py` lines 380-444: Utility functions for run history and stats
- Streamlit pages in `src/ui/views/` include debug sections (e.g., connection count)

## Naming Conventions

**Files:**

- Python modules: `snake_case.py` (e.g., `daily_pipeline.py`, `email_digest.py`)
- Edge Functions: `index.ts` inside function directory (e.g., `supabase/functions/action/index.ts`)
- PWA modules: `snake_case.js` (e.g., `app.js`, `service-worker.js`)
- Configuration: `config.py` (Settings class), `.env` (secrets)
- Models: `models.py` (all SQLModel definitions in one file)

**Directories:**

- Python packages: `snake_case/` (e.g., `src/ingestion/`, `src/llm/`)
- Feature areas: Named after responsibility (e.g., `pipeline`, `sync`, `ui`)
- Type directories: `views/`, `components/` inside UI
- Cloud code: `functions/`, `migrations/` inside `supabase/`

**Functions & Classes:**

- Functions: `snake_case()` (e.g., `run_daily_pipeline()`, `is_contact_excluded()`)
- Classes (Models): `PascalCase` SQLModel (e.g., `Connection`, `OutreachQueueItem`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `SCORING_SYSTEM_PROMPT`, `CONNECTION_SYNC_FIELDS`)
- Helper functions: Underscore prefix `_private_function()` for internal utils

**Variables:**

- Local: `snake_case` (e.g., `enrich_budget`, `results`)
- Database fields: `snake_case` matching column names (e.g., `reconnect_score`, `last_contacted_at`)
- Config: All lowercase in .env, PascalCase in Settings class (e.g., `OPENAI_API_KEY` → `openai_api_key`)

## Where to Add New Code

**New Feature (end-to-end):**
1. Add database model fields to `src/database/models.py` (if needed)
2. Add processing logic as new function in relevant `src/` module
3. Integrate into pipeline by adding step to `src/pipeline/daily_pipeline.py` (between steps 1-10)
4. If cloud-visible: add sync logic to `src/sync/push.py` CONNECTION_SYNC_FIELDS or new table handler
5. If user-facing: add Streamlit view in `src/ui/views/` or PWA page in `pwa/js/`

**New LLM Integration:**
- Add to `src/llm/` folder as `new_feature.py`
- Import OpenAI client: `from openai import OpenAI`
- Get config: `from src.config import settings`
- Access database: `from src.database.engine import get_session`
- Return dict with results for pipeline aggregation

**New Ingestion Source:**
- Add to `src/ingestion/new_source.py`
- Function signature: `import_new_source(...) -> ImportResult` dataclass (see linkedin_dump.py for pattern)
- Call from pipeline step 1 alongside LinkedIn import
- Record in ImportBatch model for history

**New Pipeline Step:**
- Add function: `def compute_new_metric() -> dict` in appropriate module
- Add to pipeline: Insert between steps 1-10 in `src/pipeline/daily_pipeline.py`
- Try-except block: Wrap in try-except, add to results dict, append to steps_completed
- Non-fatal: Use warning log if can fail without blocking rest of pipeline

**New Admin UI Page:**
- Create `src/ui/views/new_feature.py` with `render_view()` function
- Import in `src/ui/app.py` at top
- Add route in `render_sidebar_nav()` with button that sets `st.session_state.page = "new_feature"`
- Add elif branch in main page render that calls `render_view()`

**New PWA Page:**
- Create `pwa/js/new_feature.js` with `async function renderView()` export
- Add route to `pwa/js/app.js` routes object: `'/new-feature': { module: 'new_feature', title: 'New Feature' }`
- Module exports async `renderView(contentDiv)` that populates the page
- Fetch data from PostgREST: `supabase.from('table_name').select()`

**New Edge Function:**
- Create `supabase/functions/new_function/index.ts`
- Deno.serve async handler receives Request, returns Response
- Access Supabase: `const supabase = createClient(supabaseUrl, serviceRoleKey)`
- Deploy: `supabase functions deploy new_function`
- Call from PWA: `fetch('https://PROJECT.supabase.co/functions/v1/new_function', { body: JSON.stringify(data) })`

**Utilities & Helpers:**
- Shared Python utilities: `src/utils/` (create if needed) or appropriate module
- Shared PWA utilities: `pwa/js/utils/` (create if needed)
- Cross-cutting concerns: Add to existing module (e.g., validation logic in `src/pipeline/queue_generator.py`)

## Special Directories

**src/reconnect/:** Legacy/archived code (not used in current pipeline, can be removed)
- Contains old implementation of database, ingestion, llm, ui modules
- Do not use; refer to `src/` instead

**data/:** Local data artifacts
- `reconnect.db`: SQLite database created on init_db()
- Location controlled by `settings.database_path` config (default "data/reconnect.db")
- Committed: No (git-ignored)

**supabase/functions/:** Edge Functions
- Generated: No (source code checked in)
- Committed: Yes (required for deployment)
- Local testing: `supabase functions serve` (requires Docker)

**pwa/js/, pwa/css/:** PWA assets
- Generated: No (vanilla JS, no build step)
- Committed: Yes
- Served from: Supabase Storage bucket `pwa` (public)
- Manifest injection: `index.html` includes <link rel="manifest" href="/static/manifest.json">

**.env:** Environment configuration
- Generated: No (user creates from .env.example)
- Committed: No (git-ignored, contains secrets)
- Required vars: OPENAI_API_KEY, SUPABASE_PROJECT_URL, SUPABASE_ANON_KEY (for PWA)
- Optional: Gmail*, Telegram*, RapidAPI*, Hunter* credentials

**.planning/codebase/:** Documentation
- Generated: Yes (by GSD /gsd:map-codebase)
- Committed: Yes
- Consumed by: /gsd:plan-phase and /gsd:execute-phase
- Update: Run /gsd:map-codebase whenever architecture changes significantly

---

## Path Reference Quick Index

| Purpose | Path |
|---------|------|
| Pipeline entry | `src/pipeline/daily_pipeline.py` |
| Database models | `src/database/models.py` |
| Configuration | `src/config.py` |
| LLM scoring | `src/llm/scoring.py` |
| Queue rules | `src/pipeline/queue_generator.py` |
| Sync push | `src/sync/push.py` |
| Sync pull | `src/sync/pull.py` |
| Email digest | `src/integrations/email_digest.py` |
| Streamlit admin | `src/ui/app.py` |
| PWA router | `pwa/js/app.js` |
| Email action handler | `supabase/functions/action/index.ts` |
| Local database | `data/reconnect.db` (generated) |
| Secrets | `.env` (local, not committed) |
| Schema migrations | `supabase/migrations/*.sql` |
