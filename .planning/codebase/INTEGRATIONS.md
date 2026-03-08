# External Integrations

**Analysis Date:** 2025-02-03

## APIs & External Services

**LinkedIn Enrichment:**
- RapidAPI (fresh-linkedin-profile-data) - LinkedIn profile scraping with skills, role, company data
  - SDK/Client: requests library
  - Auth: `RAPIDAPI_KEY` env var
  - Implementation: `src/ingestion/rapidapi_linkedin.py`
  - Replaces deprecated Apify actor (2SyF0bVxmgGr8IVCZ)

**Email Finding & B2B Enrichment:**
- Hunter.io - Email address finder, domain verification
  - SDK/Client: requests library
  - Auth: `HUNTER_API_KEY` env var
  - Implementation: `src/ingestion/hunter.py`
  - Features: Email Finder API, domain-based email search, confidence scoring

**AI & LLM:**
- OpenAI - Text generation for scoring, outreach drafting, diagnostics
  - SDK/Client: openai 1.10+
  - Auth: `OPENAI_API_KEY` env var
  - Model: `gpt-4o-mini` (cost-optimized)
  - Implementation: `src/llm/scoring.py`, `src/llm/prose.py`, `src/llm/prescoring.py`
  - Uses: Batch scoring (50 contacts per request), individual scoring post-enrichment, prose generation for outreach

**Telegram Bot:**
- Telegram Bot API - Daily pipeline digest notifications (optional)
  - SDK/Client: Manual urllib + JSON (no SDK)
  - Auth: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` env vars
  - Implementation: `src/integrations/telegram.py`
  - Features: Pipeline failure alerts, daily digest with metrics, LLM-generated action briefs

## Data Storage

**Databases:**
- Primary: SQLite (local development)
  - Location: `data/reconnect.db` (local mode)
  - Client: SQLModel (ORM) + SQLAlchemy
  - Use: All data - connections, queue, feedback, dashboard snapshots

- Secondary: Supabase PostgreSQL (cloud production)
  - Connection: `SUPABASE_DB_URL` env var
  - Client: SQLModel + SQLAlchemy + psycopg2-binary
  - Sync: `src/sync/push.py` (local → cloud daily), `src/sync/pull.py` (cloud → local queries)

**File Storage:**
- Supabase Storage - PWA assets and data exports
  - Public bucket: `pwa` - Serves PWA (HTML/JS/CSS/icons)
  - Auth method: Public (anonymous read access)
  - Use: PWA distribution via CDN, manifest, service worker

**Caching:**
- IndexedDB (browser-only) - PWA offline queue persistence
- Streamlit session state (in-memory) - UI state management
- No server-side caching (Supabase connection pooling handles DB query caching)

## Authentication & Identity

**Email Authentication:**
- Gmail OAuth2 (Google)
  - Client ID/Secret: `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` env vars
  - Scopes: `gmail.send`, `gmail.readonly`
  - Implementation: `src/integrations/gmail.py`
  - Flow: User authorizes → token stored in `GmailCredentials` table → send email
  - Status: Not currently configured in most deployments (missing OAuth app credentials)

**Supabase Auth (PWA):**
- Built-in auth for future PWA user accounts
  - Config: `supabase/config.toml` [auth] section
  - Currently disabled - app is single-user (no multi-tenancy)
  - Can be enabled for multi-user scenarios

## Monitoring & Observability

**Error Tracking:**
- None detected - errors logged to console and file logs only

**Logs:**
- File-based logging to `logs/` directory
- Python logging module throughout
- Streamlit web UI shows logs in real-time
- Pipeline execution tracked in `pipeline_runs` table

**Email Digest Tracking:**
- `user_feedback` table captures user ratings and reactions
- `outreach_log` tracks attempts, outcomes, responses
- `dashboard_snapshots` stores computed metrics daily

## CI/CD & Deployment

**Hosting:**
- Supabase Cloud - Database, Auth, PostgREST, Edge Functions, Storage
- Project URL: `https://dxaewlecrkcttfziguer.supabase.co`
- PWA: Served from Supabase Storage public bucket (`pwa`)
- Local pipeline: macOS LaunchAgent runs daily @ 8AM

**CI Pipeline:**
- None detected (manual deployment)
- Development: Local testing, manual `supabase functions deploy`
- Edge Functions deployment: `supabase functions deploy action`, `feedback`, `draft`

**Local Development:**
- Supabase CLI: `supabase start` (Docker-based local emulation)
- Local PostgREST: http://127.0.0.1:54321
- Local Studio: http://127.0.0.1:54323
- Database mode: Toggle via `DATABASE_MODE=local|cloud` env var

## Environment Configuration

**Required env vars (all):**
- `OPENAI_API_KEY` - LLM integration (required for scoring)
- `SUPABASE_PROJECT_URL`, `SUPABASE_ANON_KEY` - PWA PostgREST access
- `SUPABASE_DB_URL` - Cloud database connection (cloud mode only)

**Recommended env vars:**
- `RAPIDAPI_KEY` - LinkedIn enrichment
- `HUNTER_API_KEY` - Email finding
- `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` - Email digest sending
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` - Notifications

**Secrets location:**
- `.env` file (local development) - Never commit
- Streamlit Cloud secrets (production Streamlit)
- Supabase secrets (for Edge Functions via `supabase secrets set`)
- Environment variables at deployment

**Data paths:**
- Local DB: `data/reconnect.db`
- LinkedIn imports: `~/Downloads` (scans for LinkedIn CSV exports)
- Logs: `logs/` directory (timestamped per day)

## Webhooks & Callbacks

**Incoming:**
- Email action links - Edge Function handlers
  - `/functions/action` - Handles approve/skip/snooze/feedback actions from email digest
  - `/functions/draft` - Generates outreach draft on demand
  - `/functions/feedback` - Records user feedback from digest

**Outgoing:**
- Gmail SMTP webhook (future) - Currently uses Gmail API direct send
- Telegram Bot API (polling via scheduled task)
- No webhook handlers for inbound email or external triggers

## Integration Flow

**Daily Pipeline:**
1. Local machine: `daily_pipeline.py` runs @ 8AM via LaunchAgent
2. Import → Pre-score → Enrich (RapidAPI + Hunter) → Score (OpenAI)
3. Generate queue → Generate email digest (HTML)
4. Attempt Gmail send (if configured) → Push to Supabase
5. Send Telegram notification with metrics

**Email Digest:**
- Generated as HTML in memory
- Sent via Gmail API (if credentials available)
- Contains action links with signed tokens (JWT-like tokens in `action_tokens` table)
- Links trigger Edge Functions with 48-hour expiry

**PWA Flow:**
1. User accesses PWA from Supabase Storage (`/pwa/index.html`)
2. Service Worker caches assets for offline use
3. JS app fetches data via PostgREST using `SUPABASE_ANON_KEY`
4. User actions (approve/skip) call Edge Functions or update queue locally
5. Sync: PWA offline actions merged on reconnection (IndexedDB → Supabase)

**Enrichment Pipeline:**
1. New contacts imported from LinkedIn CSV or manual entry
2. Pre-score via rule-based + batch LLM (free tier estimation)
3. Top candidates sent to RapidAPI for LinkedIn profile scraping
4. Hunter.io used for email finding if available
5. Full scoring via OpenAI (rubric-based dimension scoring)
6. Results cached in `Connection.raw_enrichment` (JSON)

---

*Integration audit: 2025-02-03*
