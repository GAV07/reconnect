# Phase 6: CLI + Gmail OAuth + Streamlit Removal - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace Streamlit admin UI with a unified `reconnect` CLI that covers all pipeline operations. Delete Streamlit, plotly, and all references. Update LaunchAgent to use the CLI directly. Gmail OAuth (already implemented in Phase 4) gets a CLI auth flow and status check.

</domain>

<decisions>
## Implementation Decisions

### CLI Framework & Structure
- Use **click** as the CLI framework (not argparse or typer)
- **Nested command groups**: `reconnect pipeline run`, `reconnect queue stats`, `reconnect contacts import`, `reconnect sync push`, etc.
- Install via **console_scripts** entry point in pyproject.toml: `reconnect = "src.cli:main"`
- Commands per success criteria: `pipeline run`, `queue reset`, `queue stats`, `contacts import`, `contacts score`, `gmail auth`, `gmail status`, `sync push`, `sync pull`
- Stick to listed commands only — no extras beyond `gmail status` (added for debugging scheduled runs)

### Output & Feedback Style
- **Plain text with section headers** — similar to existing scripts/run_pipeline.py output style
- No colored output or extra formatting dependencies
- `pipeline run` shows each step as it runs (step name on start, result on complete) — real-time progress
- Support `--json` flag on commands like `queue stats` for machine-readable output
- Errors in pipeline steps: **continue with warning**, don't fail fast. Non-fatal try-except matches existing behavior. Exit code 0 if pipeline finishes.

### Migration & Cleanup
- **Delete `scripts/` directory entirely** — CLI replaces all script functionality
- **Update LaunchAgent plist** to call `reconnect pipeline run` directly (no shell wrapper)
- **Delete `src/ui/` entirely** — Streamlit is broken, PWA covers all user-facing needs, nothing to preserve
- **Full Streamlit cleanup** — remove all streamlit/plotly imports, try/except blocks, and references across the entire codebase (config.py, etc.)
- Remove `streamlit` and `plotly` from both `pyproject.toml` dependencies and `requirements.txt`

### Gmail Auth CLI Flow
- `reconnect gmail auth` — browser-based OAuth flow: opens browser for Google consent, stores token in local GmailCredentials table
- After successful auth, **prompt to send a test email** for quick validation
- `reconnect gmail status` — check if OAuth is configured and token is valid/expired
- **Auto-refresh silently** on token expiry during unattended LaunchAgent runs. Only fail if refresh token itself is revoked, with message to re-run `reconnect gmail auth`

### Claude's Discretion
- Click group and command organization within src/cli.py (single file vs package)
- Exact help text wording for commands
- How to resolve the `reconnect` binary path in LaunchAgent plist (may need absolute path from pip install)
- Whether to add `click` as a required dependency or optional

</decisions>

<specifics>
## Specific Ideas

- Output style matches existing scripts/run_pipeline.py: section headers in brackets, indented details, dashed separators
- LaunchAgent should call the CLI binary directly without a shell wrapper
- Gmail auth flow: "Opening browser for Google authorization..." → consent → "Authorization successful! Token stored locally." → "Test sending? (y/n)"

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/run_pipeline.py`: Output formatting patterns for pipeline results — can be ported directly to CLI
- `scripts/run_sync.py`: Argparse structure for sync push/pull — logic reusable, just rewrap in click
- `scripts/import_csv.py`: CSV import argument handling — port to click command
- `src/integrations/gmail.py`: Full OAuth2 flow already implemented (Phase 4) — CLI just needs to call it
- `src/pipeline/daily_pipeline.py`: `run_daily_pipeline()` is the core function CLI wraps

### Established Patterns
- Pipeline functions return dicts with step results — CLI formats these for display
- `get_session()` context manager for all database access
- `from src.config import settings` for configuration
- `init_db()` called before pipeline operations
- Try-except per pipeline step with results dict aggregation

### Integration Points
- `pyproject.toml` [project.scripts] — new entry point for `reconnect` command
- LaunchAgent plist `ProgramArguments` — update to CLI binary path
- `requirements.txt` + `pyproject.toml` dependencies — remove streamlit/plotly, add click
- `src/config.py` — remove streamlit try/except import block
- All files importing from `src.ui` — none expected outside src/ui/ itself

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-cli-gmail-oauth-streamlit-removal*
*Context gathered: 2026-03-09*
