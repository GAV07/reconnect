# Reconnect

Personal networking CRM that intelligently identifies and prioritizes contacts to reconnect with. Uses LinkedIn data, AI-powered scoring, and automated outreach to help maintain your professional network.

## Features

- **LinkedIn Data Import** -- Import connections from LinkedIn export ZIPs (connections, messages, profile data) or plain CSV files
- **Two-Stage AI Scoring** -- Rule-based pre-scoring triages contacts into tiers before expensive enrichment; full LLM scoring runs after Apify profile enrichment
- **Automated Pipeline** -- Daily pipeline orchestrates import, scoring, enrichment, and outreach queue generation with configurable budgets
- **Outreach Queue** -- Smart queue generation with exclusion rules (active conversations, recently contacted, missing contact info) and draft message generation
- **Gmail Integration** -- OAuth2-based email sending directly from the app
- **Mobile-First Review UI** -- Card-based PWA interface for reviewing and approving outreach on mobile
- **Profile Inference** -- Auto-infers your seniority, expertise, industry, and interests from your LinkedIn data to improve scoring relevance

## Project Structure

```
reconnect/
├── src/
│   ├── config.py                  # Configuration via environment variables
│   ├── database/
│   │   ├── engine.py              # SQLAlchemy engine & session management
│   │   └── models.py             # SQLModel table definitions
│   ├── ingestion/
│   │   ├── apify_client.py        # Apify LinkedIn profile scraping
│   │   ├── hunter.py              # Hunter.io email finding & enrichment
│   │   ├── csv_import.py          # CSV import
│   │   ├── linkedin_dump.py       # LinkedIn export ZIP parser (connections, messages, profile)
│   │   └── profile_inference.py   # Auto-infer user profile from LinkedIn data
│   ├── integrations/
│   │   └── gmail.py               # Gmail OAuth2 & email sending
│   ├── llm/
│   │   ├── prescoring.py          # Pre-enrichment scoring (rule-based + LLM batch)
│   │   ├── prompts.py             # LLM prompt templates
│   │   ├── prose.py               # Outreach message generation
│   │   └── scoring.py             # Full reconnection scoring (post-enrichment)
│   ├── pipeline/
│   │   ├── daily_pipeline.py      # Pipeline orchestrator
│   │   └── queue_generator.py     # Outreach queue generation with exclusion rules
│   ├── sync/                       # Cloud sync with Supabase
│   │   ├── push.py                # Push local data to cloud
│   │   ├── pull.py                # Pull cloud changes to local
│   │   └── runner.py              # Sync orchestrator
│   └── ui/
│       ├── app.py                 # Main Streamlit app (routing, settings, pipeline)
│       ├── components/
│       │   ├── actions.py         # Action buttons (enrich, draft, etc.)
│       │   ├── detail.py          # Contact detail modal
│       │   └── search.py          # Search & filter interface
│       └── pages/
│           └── review.py          # Mobile-first queue review interface
├── scripts/
│   ├── import_csv.py              # CLI: import contacts from CSV
│   ├── init_db.py                 # CLI: initialize database
│   ├── run_pipeline.py            # CLI: run the daily pipeline
│   └── run_sync.py                # CLI: sync with Supabase cloud
├── static/
│   ├── manifest.json              # PWA web app manifest
│   ├── service-worker.js          # Offline caching & push notifications
│   └── offline.html               # Offline fallback page
├── supabase/
│   ├── config.toml                # Supabase local dev configuration
│   ├── migrations/                # Database schema migrations
│   └── seed.sql                   # Seed data for local dev
└── pyproject.toml
```

## Requirements

- Python >= 3.11
- API keys: OpenAI, Apify (for LinkedIn enrichment), Hunter.io (for email finding)
- Gmail OAuth2 credentials (optional, for email sending)

## Setup

1. **Install dependencies:**
   ```bash
   pip install -e .
   ```

2. **Configure environment variables** by creating a `.env` file:
   ```env
   # Required
   OPENAI_API_KEY=sk-...

   # For LinkedIn profile enrichment
   APIFY_API_KEY=apify_api_...

   # For email finding (Hunter.io)
   HUNTER_API_KEY=...

   # For Gmail integration (optional)
   GMAIL_CLIENT_ID=...
   GMAIL_CLIENT_SECRET=...
   ```

3. **Initialize the database:**
   ```bash
   python scripts/init_db.py
   ```

4. **Run the app:**
   ```bash
   streamlit run src/ui/app.py
   ```

## Usage

### Importing Contacts

**Via UI:** Upload a LinkedIn export ZIP or CSV through the Streamlit interface.

**Via CLI:**
```bash
python scripts/import_csv.py path/to/connections.csv
```

### Running the Pipeline

The pipeline orchestrates the full workflow: import, pre-score, enrich, full-score, and queue generation.

**Via UI:** Use the Pipeline page in the Streamlit app.

**Via CLI:**
```bash
# Full pipeline with LinkedIn dump
python scripts/run_pipeline.py --dump path/to/linkedin-export.zip --user-name "Your Name"

# Skip enrichment (scoring only)
python scripts/run_pipeline.py --skip-enrich

# Custom budget
python scripts/run_pipeline.py --enrich-budget 5 --queue-size 15
```

### Reviewing Outreach

Open the **Review Queue** page for a mobile-optimized card interface where you can:
- Review AI-drafted messages
- Edit subject lines and message bodies
- Send emails via Gmail or copy messages for LinkedIn
- Skip contacts you don't want to reach out to

## How Scoring Works

### Stage 1: Pre-Scoring (before enrichment)

Rule-based scoring assigns points based on:
- Job title signals (Founder/CEO +30, VP +20, Director +15, Student -30)
- Company recognition (Big Tech +10, top consulting +12)
- Profile completeness (LinkedIn URL, email, message history)
- Match with your profile (industry, goals)

Contacts are assigned to tiers:
- **Tier 1** (score >= 70): Enriched via Apify
- **Tier 2** (40-70): May be enriched
- **Tier 3** (< 40): Skipped

### Stage 2: Full Scoring (after enrichment)

Uses the enriched profile data with LLM analysis for deeper reconnection relevance scoring.

## Configuration

All settings are configurable via environment variables or `.env`:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_PATH` | `data/reconnect.db` | SQLite database path |
| `DATABASE_MODE` | `local` | `local` (SQLite) or `cloud` (PostgreSQL) |
| `SUPABASE_DB_URL` | - | PostgreSQL connection string for cloud sync |
| `OPENAI_MODEL` | `gpt-4o-mini` | LLM model for scoring/generation |
| `DAILY_ENRICH_BUDGET` | `10` | Max contacts to enrich per pipeline run |
| `DAILY_QUEUE_SIZE` | `10` | Max outreach queue items to generate |
| `PRESCORE_BATCH_SIZE` | `50` | Contacts per LLM batch scoring call |
| `ACTIVE_CONVERSATION_DAYS` | `30` | Days to consider a conversation active (excluded from queue) |
| `RECENTLY_CONTACTED_DAYS` | `30` | Days to exclude after contacting someone |

## Cloud Sync with Supabase

The app supports syncing data to Supabase PostgreSQL for cloud storage and mobile access.

### Setting Up Supabase

**Option 1: Hosted Supabase (recommended for production)**

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **Settings > Database > Connection string** and copy the URI
3. Add to your `.env`:
   ```env
   DATABASE_MODE=local
   SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
4. Initialize the cloud schema:
   ```bash
   python -c "from src.database.engine import get_engine, init_db; init_db(get_engine('cloud'))"
   ```

**Option 2: Local Supabase (for development)**

1. Install the [Supabase CLI](https://supabase.com/docs/guides/cli)
2. Start local Supabase:
   ```bash
   supabase start
   ```
3. Use the local database URL from the output:
   ```env
   SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
   ```

### Running Sync

The sync pushes local pipeline results to cloud and pulls user actions back:

```bash
# Full sync (push + pull)
python scripts/run_sync.py

# Push only (local -> cloud)
python scripts/run_sync.py --push-only

# Pull only (cloud -> local)
python scripts/run_sync.py --pull-only
```

The daily pipeline automatically syncs to cloud after completion if `SUPABASE_DB_URL` is configured.

### How Sync Works

- **Push:** Sends enriched/scored connections, outreach queue items, and user profile to cloud
- **Pull:** Retrieves queue item status changes and outreach log entries from cloud
- **Conflict resolution:** Cloud wins for user review actions; most-recent timestamp wins otherwise

## Scheduled Automation (macOS)

The pipeline can run automatically on a daily schedule using macOS LaunchAgent.

### Quick Start

```bash
# Install and start the scheduler (runs daily at 8 AM)
./scripts/scheduler.sh install

# Check status
./scripts/scheduler.sh status

# View logs
./scripts/scheduler.sh logs
```

### Scheduler Commands

| Command | Description |
|---------|-------------|
| `install` | Install and start the daily scheduler |
| `uninstall` | Stop and remove the scheduler |
| `start` | Start the scheduler (if installed) |
| `stop` | Stop the scheduler temporarily |
| `status` | Show scheduler status and recent output |
| `run` | Run the pipeline manually now |
| `logs` | Show today's pipeline log |

### Configuration

The scheduler runs at **8:00 AM daily**. To change the time, edit `com.reconnect.daily-pipeline.plist`:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>8</integer>  <!-- Change this (0-23) -->
    <key>Minute</key>
    <integer>0</integer>  <!-- Change this (0-59) -->
</dict>
```

Then reinstall: `./scripts/scheduler.sh uninstall && ./scripts/scheduler.sh install`

### Logs

Pipeline logs are stored in `logs/` with daily rotation:
- `logs/pipeline-YYYY-MM-DD.log` - Daily pipeline output
- `logs/launchd-stdout.log` - LaunchAgent stdout
- `logs/launchd-stderr.log` - LaunchAgent stderr

Logs older than 30 days are automatically deleted.

## Development

```bash
pip install -e ".[dev]"
ruff check src/
pytest
```
