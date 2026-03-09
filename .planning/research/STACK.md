# Stack Research

**Domain:** Personal networking PWA + Python pipeline — v1.1 additions
**Researched:** 2026-03-09
**Confidence:** HIGH (verified with official docs and PyPI)
**Scope:** NEW capabilities only — dashboard charts, AI search, Gmail OAuth, queue filtering, CLI

---

## Context

This is additive research on top of a working v1.0 system. The existing stack is locked:
Python + SQLModel + SQLite, Supabase PostgreSQL + PostgREST + Edge Functions (Deno),
Vanilla JS PWA on Netlify, OpenAI `gpt-4o-mini`, Gmail App Password + smtplib.

**This document covers only what needs to change or be added for v1.1.**

---

## Recommended Stack

### Core Technologies — New Additions

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Chart.js | 4.5.1 | PWA dashboard charts (bar, pie, doughnut) | Most popular vanilla-JS-compatible charting library (2M+ weekly npm downloads). Zero-dependency, 48KB gzipped (tree-shakes to ~14KB for single chart types). Works via CDN script tag — no build step. Integrates by calling `new Chart(canvas, config)`. V4 API is stable with no breaking changes since 4.0. |
| click | 8.3.1 | Python CLI commands to replace Streamlit admin | Best CLI framework for subcommand-based tools (like `git`). Decorator-based, composable groups, automatic `--help` generation. Significantly less boilerplate than argparse for multi-command tools. Already in ecosystem — no conflict with existing deps. |
| google-api-python-client | 2.192.0 | Gmail API (OAuth2 send mail) | Official Google-maintained library. Required to call the Gmail `messages.send` endpoint. Works with the standard `InstalledAppFlow` → `token.json` pattern. Pinned to `>=2.100.0` is fine — semver minor bumps are backward-compatible. |
| google-auth-oauthlib | 1.3.0 | OAuth2 browser flow for Gmail credential setup | Provides `InstalledAppFlow` used for the one-time browser auth dance. Stores refresh token in `token.json`. After initial setup, `creds.refresh(Request())` handles silent renewal — no browser interaction needed on subsequent pipeline runs. |
| google-auth | 2.49.0 | OAuth2 credential management and token refresh | Core credential plumbing used by both `google-auth-oauthlib` and `google-api-python-client`. Handles token refresh via `creds.refresh(Request())`. Installed transitively — list explicitly in requirements.txt for version pinning. |

### Supporting Libraries — New Additions

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| google-auth-httplib2 | 0.2.0 | HTTP transport adapter for google-api-python-client | Required by `googleapiclient.discovery.build()`. Installed as a transitive dep but pin explicitly. |
| pgvector (Supabase extension) | built-in on Supabase | Vector similarity search for AI contact search | No Python package needed — enable via SQL migration: `CREATE EXTENSION IF NOT EXISTS vector;`. Already available on all Supabase hosted plans. |
| openai (existing) | >=1.10.0 | Generate embeddings via `text-embedding-3-small` | Already in requirements.txt. The existing `openai.OpenAI` client handles both completions (scoring) and embeddings (search). No new package. |

### Development Tools — Unchanged

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Test pipeline logic | Existing. Add tests for CLI commands via Click's `CliRunner`. |
| python-dotenv | .env loading | Existing. No change. |
| LaunchAgent plist | Daily scheduling | Existing. No change. |

---

## Feature-by-Feature Stack Decisions

### 1. Dashboard Charts (PWA — Vanilla JS)

**Technology:** Chart.js 4.5.1 via CDN

**CDN script tag** (add to `pwa/index.html`):
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js"></script>
```

**Why Chart.js over alternatives:**
- Works with a `<canvas>` element — no DOM framework needed
- Bar charts for industry distribution, doughnut/pie for score tiers, all via same API
- CDN UMD bundle works without `import` statements — compatible with existing non-module JS
- Chart.js 4.x requires a `<canvas>` container div with explicit dimensions for mobile — critical for PWA

**Usage pattern** (in `dashboard.js`):
```javascript
function buildIndustryChart(data) {
  const canvas = document.getElementById('industry-chart');
  // Destroy existing chart instance to avoid "Canvas is already in use" error
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();

  new Chart(canvas, {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [{ data: data.values, backgroundColor: '#0a66c2' }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } }
    }
  });
}
```

**Data source:** `dashboard_snapshots.snapshot_data` JSONB field. The Python pipeline
(daily_pipeline.py Step 7 / dashboard snapshot) needs to compute and store `industry_distribution`,
`role_distribution`, and `score_tier_distribution` arrays. No new Supabase API calls needed —
data already flows through the snapshot mechanism.

**HTML container pattern** (required for Chart.js responsive behavior):
```html
<div style="position:relative; height:180px;">
  <canvas id="industry-chart"></canvas>
</div>
```

### 2. AI-Powered Contact Search

**Architecture decision:** Edge Function handles embedding + search, NOT the PWA directly.

**Why Edge Function (not PWA → OpenAI directly):**
- The PWA's anon key cannot safely call OpenAI API (key would be exposed in browser JS)
- Supabase Edge Functions already have `OPENAI_API_KEY` as a secret — reuse this
- The Edge Function can generate the embedding and call `match_connections` RPC in one hop

**Architecture:**
```
PWA (query text)
  → POST /functions/v1/search (Supabase Edge Function, --no-verify-jwt)
    → OpenAI text-embedding-3-small API (generates query embedding)
    → Supabase RPC: match_connections(query_embedding, threshold, count)
      → pgvector cosine similarity against connections.embedding column
    → Returns ranked contacts to PWA
```

**Python pipeline responsibility:** Generate and store embeddings for all enriched connections
during the daily pipeline run (new pipeline step). Use existing `openai.OpenAI` client:

```python
from openai import OpenAI

client = OpenAI(api_key=settings.openai_api_key)

def embed_connection(text: str) -> list[float]:
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small",
        dimensions=512  # Reduce from 1536 — same pricing, ~3x faster search, negligible accuracy loss
    )
    return response.data[0].embedding
```

**Embedding text composition** (concatenate enriched fields into a single string for embedding):
```python
def build_search_text(conn: Connection) -> str:
    parts = [
        conn.name or "",
        conn.current_role or "",
        conn.current_company or "",
        conn.headline or "",
        conn.about_summary or "",
        " ".join(conn.skills or []),
        conn.industry or "",
    ]
    return " | ".join(p for p in parts if p)
```

**Database changes required:**
```sql
-- Enable pgvector (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- Add embedding column to connections table
ALTER TABLE connections ADD COLUMN IF NOT EXISTS embedding extensions.vector(512);

-- HNSW index for fast cosine similarity
CREATE INDEX IF NOT EXISTS connections_embedding_hnsw
  ON connections USING hnsw (embedding extensions.vector_cosine_ops);

-- RPC function for search
CREATE OR REPLACE FUNCTION match_connections(
  query_embedding extensions.vector(512),
  match_threshold float DEFAULT 0.5,
  match_count int DEFAULT 10
)
RETURNS TABLE(
  id uuid,
  name text,
  current_role text,
  current_company text,
  reconnect_score int,
  similarity float
)
LANGUAGE sql
AS $$
  SELECT
    id, name, current_role, current_company, reconnect_score,
    1 - (embedding <=> query_embedding) AS similarity
  FROM connections
  WHERE embedding IS NOT NULL
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY embedding <=> query_embedding ASC
  LIMIT match_count;
$$;
```

**Edge Function (Deno TypeScript):**
```typescript
// supabase/functions/search/index.ts
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import OpenAI from 'https://esm.sh/openai@4'

Deno.serve(async (req) => {
  const { query } = await req.json()
  const openai = new OpenAI({ apiKey: Deno.env.get('OPENAI_API_KEY') })

  const embRes = await openai.embeddings.create({
    input: query,
    model: 'text-embedding-3-small',
    dimensions: 512,
  })
  const embedding = embRes.data[0].embedding

  const sb = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )
  const { data, error } = await sb.rpc('match_connections', {
    query_embedding: embedding,
    match_threshold: 0.5,
    match_count: 10,
  })

  return Response.json({ results: data, error })
})
```

**PWA fetch call** (in a new `search.js` or inside `app.js`):
```javascript
async function searchContacts(query) {
  const res = await fetch(`${SUPABASE_URL}/functions/v1/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  })
  return res.json()
}
```

**Note:** No API key needed in the PWA request because the Edge Function is deployed with
`--no-verify-jwt`. The query text is the only sensitive data and is acceptable to transmit
over HTTPS.

**Embedding dimensions:** Use 512 (not the 1536 default). Pricing is identical per OpenAI docs
($0.02/1M tokens regardless of dimensions). 512d vectors search ~3x faster with pgvector HNSW
indexing. Accuracy difference is negligible for contact name/role/skill matching.

### 3. Gmail OAuth (Replace App Password)

**Technology:** `google-api-python-client` + `google-auth-oauthlib` + `google-auth`

**When the one-time browser flow runs:** First pipeline execution after adding credentials.
The `InstalledAppFlow.run_local_server(port=0)` opens a browser tab, completes OAuth, and
saves `token.json`. All subsequent runs call `creds.refresh(Request())` silently.

**Standard pattern** (HIGH confidence — from Google official quickstart, verified 2026):
```python
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
TOKEN_PATH = Path("data/gmail_token.json")
CREDS_PATH = Path("data/gmail_credentials.json")  # GCP OAuth client secret


def get_gmail_service():
    """Get authenticated Gmail API service, refreshing token if needed."""
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def send_html_email(to: str, subject: str, html_body: str) -> dict:
    """Send HTML email via Gmail API OAuth."""
    service = get_gmail_service()
    msg = MIMEMultipart('alternative')
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()
    return {'message_id': result.get('id', '')}
```

**GCP setup required (one-time):**
1. Google Cloud Console → APIs & Services → Enable Gmail API
2. Create OAuth 2.0 Client ID (Desktop application type)
3. Download JSON → save as `data/gmail_credentials.json`
4. Add `data/gmail_token.json` and `data/gmail_credentials.json` to `.gitignore`

**Config changes to `src/config.py`:**
```python
gmail_credentials_path: str = "data/gmail_credentials.json"
gmail_token_path: str = "data/gmail_token.json"
# Keep existing gmail_app_password as fallback until OAuth confirmed working
```

**Scope needed:** `https://www.googleapis.com/auth/gmail.send` — narrowest scope that
permits sending. Do NOT use `https://mail.google.com/` (full mailbox access, triggers
Google security warnings).

### 4. Queue Filtering/Sorting (PWA — Vanilla JS)

**Technology:** Pure vanilla JS — no library needed.

**Pattern:** Fetch all pending items once, store in a module-level array, re-render on
filter/sort change. Do NOT re-fetch from Supabase on every filter change — the queue is
≤50 items.

```javascript
// In queue.js — store items at module scope
let _queueItems = []

async function renderQueue(container) {
  // Fetch once
  const { data } = await db.from('outreach_queue')
    .select('*, connections(*)')
    .in('status', ['pending_review'])
    .order('priority_score', { ascending: false })
  _queueItems = data || []
  renderFilteredQueue(container)
}

function renderFilteredQueue(container) {
  const sortBy = document.getElementById('queue-sort')?.value || 'score'
  const filterIndustry = document.getElementById('queue-filter-industry')?.value || 'all'

  let items = [..._queueItems]

  // Filter
  if (filterIndustry !== 'all') {
    items = items.filter(i => i.connections?.industry === filterIndustry)
  }

  // Sort
  if (sortBy === 'score') {
    items.sort((a, b) => (b.priority_score || 0) - (a.priority_score || 0))
  } else if (sortBy === 'name') {
    items.sort((a, b) => (a.connections?.name || '').localeCompare(b.connections?.name || ''))
  }

  // Re-render cards
  container.innerHTML = items.map(renderQueueCard).join('')
}
```

**UI controls pattern** (add above queue card list in `renderQueue`):
```javascript
const controls = `
  <div class="queue-controls">
    <select id="queue-sort" onchange="renderFilteredQueue(document.getElementById('app-content'))">
      <option value="score">Sort: Score</option>
      <option value="name">Sort: Name</option>
    </select>
    <select id="queue-filter-industry" onchange="renderFilteredQueue(document.getElementById('app-content'))">
      <option value="all">All Industries</option>
      ${industries.map(i => `<option value="${i}">${i}</option>`).join('')}
    </select>
  </div>`
```

**Industry values for filter:** Derive from `_queueItems` at render time — `[...new Set(_queueItems.map(i => i.connections?.industry).filter(Boolean))]`.

**No library needed** — Array `.filter()`, `.sort()`, and `.localeCompare()` cover all requirements. Adding List.js or similar would be over-engineering for a ≤50-item list.

### 5. CLI Commands (Replace Streamlit Admin)

**Technology:** Click 8.3.1

**Why Click over argparse:** The pipeline already has natural subcommand grouping (`pipeline run`, `pipeline status`, `contacts list`, `contacts score`). Click's `@click.group()` / `@click.command()` decorator pattern maps exactly to this structure with automatic `--help` generation. Argparse requires manual `add_subparsers()` scaffolding for the same result. Typer is also reasonable but adds a pyproject.toml dependency; Click is more widely known in the Python ecosystem.

**Proposed CLI structure:**
```
reconnect
├── pipeline run          # Run full daily pipeline
├── pipeline status       # Show last run results
├── contacts list         # List top-scored contacts
├── contacts score        # Re-score specific contacts
├── contacts search       # Run embedding search (Python-side, useful for debugging)
├── sync push             # Manual push to Supabase
├── sync pull             # Manual pull from Supabase
└── email test            # Send test digest email
```

**Entry point pattern** (create `src/cli.py`):
```python
import click
from src.pipeline.daily_pipeline import run_daily_pipeline
from src.sync.push import push_to_supabase

@click.group()
def cli():
    """Reconnect networking pipeline CLI."""

@cli.group()
def pipeline():
    """Pipeline operations."""

@pipeline.command()
@click.option('--skip-enrichment', is_flag=True, help='Skip Apify enrichment step')
@click.option('--skip-email', is_flag=True, help='Skip digest email')
def run(skip_enrichment, skip_email):
    """Run the full daily pipeline."""
    result = run_daily_pipeline(skip_enrichment=skip_enrichment)
    click.echo(f"Pipeline completed: {result['status']}")

@cli.group()
def sync():
    """Sync operations."""

@sync.command('push')
def sync_push():
    """Push local SQLite changes to Supabase."""
    result = push_to_supabase()
    click.echo(f"Pushed {result.get('pushed', 0)} records")
```

**Invocation after `pip install -e .`:**
```bash
reconnect pipeline run
reconnect pipeline run --skip-enrichment
reconnect sync push
reconnect email test
```

**pyproject.toml entry point:**
```toml
[project.scripts]
reconnect = "src.cli:cli"
```

**Streamlit removal:** Delete `src/ui/` directory entirely after CLI covers:
- Manual pipeline trigger
- Sync status
- Contact list/score review (can use PWA instead)

The v1.1 PWA covers all contact review/feedback use cases. The Streamlit UI is the only thing
requiring `streamlit>=1.30.0` and `plotly>=5.18.0` — both can be dropped from requirements.txt.

---

## Installation Changes

### Python — Add to requirements.txt

```
# Gmail OAuth (replacing App Password)
google-api-python-client>=2.192.0
google-auth-oauthlib>=1.3.0
google-auth>=2.49.0
google-auth-httplib2>=0.2.0

# CLI (replacing Streamlit)
click>=8.3.1
```

### Python — Remove from requirements.txt

```
# Remove after Streamlit deletion confirmed working
streamlit>=1.30.0
plotly>=5.18.0
```

### PWA — Add to pwa/index.html

```html
<!-- Add before app scripts, after existing Supabase CDN script -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js"></script>
```

### Supabase — New SQL Migration

```sql
-- supabase/migrations/[timestamp]_embeddings.sql
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

ALTER TABLE connections ADD COLUMN IF NOT EXISTS embedding extensions.vector(512);

CREATE INDEX IF NOT EXISTS connections_embedding_hnsw
  ON connections USING hnsw (embedding extensions.vector_cosine_ops);

CREATE OR REPLACE FUNCTION match_connections(
  query_embedding extensions.vector(512),
  match_threshold float DEFAULT 0.5,
  match_count int DEFAULT 10
)
RETURNS TABLE(id uuid, name text, current_role text, current_company text, reconnect_score int, similarity float)
LANGUAGE sql AS $$
  SELECT id, name, current_role, current_company, reconnect_score,
         1 - (embedding <=> query_embedding) AS similarity
  FROM connections
  WHERE embedding IS NOT NULL
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY embedding <=> query_embedding ASC
  LIMIT match_count;
$$;
```

### New Supabase Edge Function

```
supabase/functions/search/index.ts
```
Deploy with: `supabase functions deploy search --no-verify-jwt`

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Chart.js 4.x via CDN | D3.js | D3 when you need fully custom SVG visualizations with complex transitions. For bar/pie/doughnut charts from JSON data, D3 is 10x more code for the same result. |
| Chart.js 4.x via CDN | Highcharts | Highcharts when the project is commercial and needs IE11 support. Free for non-commercial but requires attribution. Chart.js is MIT with no restrictions. |
| Chart.js 4.x via CDN | uPlot | uPlot when rendering time-series data with thousands of points at 60fps. For distributions of ≤50 categories, Chart.js is simpler. |
| Click 8.x | argparse (stdlib) | argparse when adding any external dependency is prohibited (e.g., locked corporate environments). Click requires one `pip install` but saves significant boilerplate for multi-subcommand CLIs. |
| Click 8.x | Typer | Typer if the codebase already uses Pydantic models everywhere and type-hint-driven CLI generation is preferred. Typer is essentially Click with type hints — either works fine. Click is more widely documented. |
| Edge Function for search | PWA calls OpenAI directly | Only if the OpenAI key can be safely exposed (never for browser-accessible apps). Embedding in an Edge Function keeps the key server-side. |
| pgvector + RPC | Supabase full-text search (tsvector) | Full-text search when queries are keyword-based (e.g., `WHERE name ILIKE '%smith%'`). For semantic queries like "who works in fintech AI" where the words don't literally appear in the data, pgvector is necessary. Consider offering both: keyword search falls back to `ILIKE`, semantic search uses the embedding RPC. |
| InstalledAppFlow token.json | Service Account | Service accounts for server-to-server scenarios where no human user is involved. Gmail send on behalf of a personal Gmail account requires a user OAuth flow — service accounts only work with Google Workspace (GSuite) accounts. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| React/Vue/Svelte in PWA | Requires a build pipeline (Vite/Webpack), breaks the zero-build Netlify deploy, adds framework-specific syntax overhead for a single-user app with 4 pages | Continue with vanilla JS + `innerHTML` templating |
| LangChain for embeddings | Adds 20+ transitive dependencies for a feature that's 5 lines with `openai` directly | `openai.OpenAI().embeddings.create()` directly |
| Streamlit after v1.1 | `src/ui/views/review.py` already crashes on import (OAuth functions removed). Adding Streamlit complexity when the CLI + PWA covers all use cases. | Click CLI for pipeline ops, PWA for contact review |
| `text-embedding-ada-002` | Older, more expensive, lower quality than `text-embedding-3-small`. Being deprecated. | `text-embedding-3-small` |
| 1536 dimensions for pgvector | Default dimension but unnecessary for contact search. Increases storage and query time with no accuracy benefit at this dataset size (≤10K contacts). | 512 dimensions — same pricing, 3x faster HNSW search |
| Full mailbox OAuth scope | `https://mail.google.com/` triggers Google's "This app wants access to your Google Account" security warning. Excessive permission for send-only use case. | `https://www.googleapis.com/auth/gmail.send` |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Chart.js@4.5.1 | All modern browsers, Supabase JS@2 CDN | UMD bundle works without ES modules. Chart.js 4.x dropped IE11 support — acceptable for a modern PWA. |
| google-api-python-client@2.192.0 | google-auth>=2.14.1, google-auth-oauthlib>=0.5.0 | All three must be updated together — mixing very old google-auth with new google-api-python-client causes import errors. Pin all three. |
| click@8.3.1 | Python 3.8+, pydantic-settings 2.x | No conflicts with existing dependencies. Click does not interact with Pydantic. |
| openai>=1.10.0 (existing) | embeddings API (text-embedding-3-small) | Already installed. The embeddings endpoint has been stable since openai v1.0. No version change needed. |
| pgvector (Supabase hosted) | Supabase hosted plans (free and pro) | pgvector is pre-installed on all Supabase hosted instances. Only `CREATE EXTENSION` needed, no server access. |

---

## Confidence Assessment

| Area | Confidence | Source |
|------|------------|--------|
| Chart.js 4.5.1 CDN pattern | HIGH | jsDelivr CDN listing + Chart.js official docs |
| Gmail OAuth Python pattern | HIGH | Google official quickstart (verified 2026), PyPI package versions confirmed |
| google-auth package versions | HIGH | PyPI: google-auth 2.49.0 (Mar 6, 2026), google-auth-oauthlib 1.3.0 (Feb 27, 2026), google-api-python-client 2.192.0 (Mar 5, 2026) |
| pgvector Supabase availability | HIGH | Supabase official docs, pre-installed on all hosted plans |
| text-embedding-3-small 512 dimensions | HIGH | OpenAI docs confirm `dimensions` parameter, pricing identical, no accuracy penalty at this scale |
| RPC via supabase-js rpc() for vector search | HIGH | Supabase official semantic search docs + OpenAI cookbook |
| Click 8.3.1 | HIGH | PyPI confirmed, released Nov 15, 2025 |
| Edge Function search architecture | MEDIUM | Supabase Edge Functions docs + pgvector RPC pattern — confirmed working pattern but specific integration not tested against this codebase |
| 512 vs 1536 dimensions tradeoff | MEDIUM | OpenAI community forum + multiple blog sources — no official benchmark for contact-scale datasets |

---

## Sources

- [Chart.js Installation Docs](https://www.chartjs.org/docs/latest/getting-started/installation.html) — CDN installation pattern, Canvas API
- [Chart.js on jsDelivr](https://www.jsdelivr.com/package/npm/chart.js?path=dist) — Version 4.5.1 confirmed current
- [google-auth-oauthlib on PyPI](https://pypi.org/project/google-auth-oauthlib/) — Version 1.3.0, released 2026-02-27
- [google-auth on PyPI](https://pypi.org/project/google-auth/) — Version 2.49.0, released 2026-03-06
- [google-api-python-client on PyPI](https://pypi.org/project/google-api-python-client/) — Version 2.192.0, released 2026-03-05
- [Gmail API Python Quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) — InstalledAppFlow token.json pattern
- [Supabase pgvector Docs](https://supabase.com/docs/guides/database/extensions/pgvector) — Extension setup, HNSW indexing
- [Supabase Semantic Search Docs](https://supabase.com/docs/guides/ai/semantic-search) — match_documents RPC pattern, supabase-js rpc() usage
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings) — text-embedding-3-small, dimensions parameter
- [OpenAI text-embedding-3-small Model Page](https://platform.openai.com/docs/models/text-embedding-3-small) — 1536 default, pricing $0.02/1M tokens
- [OpenAI Embeddings Pricing](https://costgoat.com/pricing/openai-embeddings) — Confirmed dimension-independent pricing
- [Click 8.3.1 on PyPI](https://pypi.org/project/click/) — Version 8.3.1, released 2025-11-15
- [Click Entry Points Docs](https://click.palletsprojects.com/en/stable/entry-points/) — pyproject.toml scripts pattern

---

*Stack research for: Reconnect v1.1 — dashboard charts, AI search, Gmail OAuth, queue filtering, CLI*
*Researched: 2026-03-09*
