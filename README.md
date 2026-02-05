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
│   │   ├── coresignal.py          # Coresignal API integration
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
│   └── run_pipeline.py            # CLI: run the daily pipeline
├── static/
│   ├── manifest.json              # PWA web app manifest
│   ├── service-worker.js          # Offline caching & push notifications
│   └── offline.html               # Offline fallback page
└── pyproject.toml
```

## Requirements

- Python >= 3.11
- API keys: OpenAI, Apify (for enrichment)
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

   # For LinkedIn enrichment
   APIFY_API_KEY=apify_api_...

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
| `OPENAI_MODEL` | `gpt-4o-mini` | LLM model for scoring/generation |
| `DAILY_ENRICH_BUDGET` | `10` | Max contacts to enrich per pipeline run |
| `DAILY_QUEUE_SIZE` | `10` | Max outreach queue items to generate |
| `PRESCORE_BATCH_SIZE` | `50` | Contacts per LLM batch scoring call |
| `ACTIVE_CONVERSATION_DAYS` | `30` | Days to consider a conversation active (excluded from queue) |
| `RECENTLY_CONTACTED_DAYS` | `30` | Days to exclude after contacting someone |

## Development

```bash
pip install -e ".[dev]"
ruff check src/
pytest
```
