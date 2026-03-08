# Technology Stack

**Analysis Date:** 2025-02-03

## Languages

**Primary:**
- Python 3.11+ - Backend pipeline, data processing, LLM orchestration
- TypeScript (Deno 2) - Edge Functions (serverless handlers)
- JavaScript (ES6+) - PWA frontend, service worker

**Secondary:**
- SQL - Database migrations, Supabase functions
- HTML/CSS - PWA pages and styling

## Runtime

**Environment:**
- Python 3.11+ (local pipeline execution)
- Deno 2 (Edge Functions runtime via Supabase)
- Node.js (PWA dev tooling only, not required at runtime)

**Package Manager:**
- pip (Python)
- npm (JavaScript dependencies, minimal usage)
- Deno modules (TypeScript via ESM imports from https://esm.sh/)

**Lockfile:**
- `requirements.txt` (Python)
- `package-lock.json` (present but minimal usage)

## Frameworks

**Core:**
- SQLModel 0.0.14 - ORM/data validation layer (built on SQLAlchemy + Pydantic)
- SQLAlchemy 2.0+ - Database abstraction
- Streamlit 1.30+ - Admin UI (localhost:8501)

**API/Backend:**
- Supabase - Backend-as-a-Service (PostgREST API, Edge Functions, Auth, Storage)
- Google API Python Client 2.100+ - Gmail OAuth2 and email sending

**Frontend:**
- Supabase JS Client 2.x (PWA via CDN) - REST/realtime database access
- Vanilla JavaScript - No framework (custom router, state management)
- PWA APIs (Service Worker, IndexedDB for offline queue)

**Testing:**
- pytest 7.4+ - Unit testing framework
- pytest-cov 4.1+ - Code coverage

**Build/Dev:**
- ruff 0.1+ - Python linting and code formatting
- Hatchling - Python package building
- pydantic-settings 2.1+ - Environment configuration

## Key Dependencies

**Critical:**
- openai 1.10+ - LLM integration (GPT-4o-mini for scoring and outreach generation)
- apify-client 1.6+ - LinkedIn profile scraping (deprecated, replaced by RapidAPI)
- requests 2.31+ - HTTP client for API calls
- psycopg2-binary 2.9+ - PostgreSQL connector (for Supabase cloud sync)

**Infrastructure:**
- pydantic 2.5+ - Data validation and settings management
- python-dotenv 1.0+ - Environment variable loading
- plotly 5.18+ - Dashboard visualization
- google-auth-oauthlib 1.1+ - Gmail OAuth2 flow
- thefuzz 0.22+ - Fuzzy string matching for LinkedIn CSV deduplication

**Email/Notifications:**
- smtplib (stdlib) - Plain text email sending
- email.mime (stdlib) - HTML email composition (used by Gmail API integration)

## Configuration

**Environment:**
- Loaded via `src/config.py` using pydantic-settings (reads `.env` file)
- Two database modes: `local` (SQLite) and `cloud` (Supabase PostgreSQL)
- Secrets via environment variables or Streamlit Cloud secrets

**Key Env Vars:**
- `OPENAI_API_KEY` - Required for LLM scoring and prose generation
- `SUPABASE_PROJECT_URL`, `SUPABASE_ANON_KEY` - Cloud sync and PostgREST
- `SUPABASE_DB_URL` - PostgreSQL connection string (cloud mode)
- `RAPIDAPI_KEY` - LinkedIn profile enrichment (replaces deprecated Apify)
- `HUNTER_API_KEY` - Email finding and enrichment
- `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` - OAuth2 for email digest
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` - Pipeline notifications (optional)

**Build:**
- `.streamlit/config.toml` - Streamlit server and theme settings
- `supabase/config.toml` - Local Supabase emulation (Docker-based dev environment)
- `pyproject.toml` - Python project metadata and dependencies
- `pwa/manifest.json` - PWA manifest for installable app

## Platform Requirements

**Development:**
- macOS (or Linux/Windows with Bash)
- Python 3.11+
- SQLite3 (local dev database)
- Docker (optional, for local Supabase emulation)
- LaunchAgent script (scheduled daily pipeline @ 8AM on macOS)

**Production:**
- Supabase Cloud - Hosted PostgreSQL, PostgREST, Auth, Edge Functions, Storage
- Vercel or Netlify (PWA hosting, though Supabase Storage bucket also works)
- Local scheduler - macOS LaunchAgent runs `daily_pipeline.py` daily
- Email sending via Gmail API (SMTP alternative available but not configured)

**Deployment Target:**
- PWA: Supabase Storage public bucket (`pwa`) served via HTTPS
- Backend: Hybrid - local SQLite for dev, Supabase PostgreSQL for cloud sync
- Edge Functions: Deployed via Supabase CLI (`supabase functions deploy`)
- Streamlit: localhost only (not exposed to internet)

## Performance Configuration

**Database:**
- SQLite busy timeout: 30 seconds (local mode)
- PostgreSQL connection pooling via Supabase
- Max PostgREST rows: 1000 (Supabase config)

**LLM:**
- OpenAI model: `gpt-4o-mini` (cost-optimized)
- Max tokens per request: 500 (configurable)
- Temperature: 0.7 (default)
- Batch scoring: Pre-score 50 contacts per LLM call

**Cache:**
- TTL for enrichment data: 7 days (configurable)
- Streamlit in-memory session state for UI state
- PWA: IndexedDB for offline queue persistence

---

*Stack analysis: 2025-02-03*
