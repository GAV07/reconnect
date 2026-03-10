# Phase 6: CLI + Gmail OAuth + Streamlit Removal - Research

**Researched:** 2026-03-09
**Domain:** Click CLI framework, Python console_scripts entry points, LaunchAgent configuration, Streamlit/Plotly removal
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use **click** as the CLI framework (not argparse or typer)
- **Nested command groups**: `reconnect pipeline run`, `reconnect queue stats`, `reconnect contacts import`, `reconnect sync push`, etc.
- Install via **console_scripts** entry point in pyproject.toml: `reconnect = "src.cli:main"`
- Commands per success criteria: `pipeline run`, `queue reset`, `queue stats`, `contacts import`, `contacts score`, `gmail auth`, `gmail status`, `sync push`, `sync pull`
- Stick to listed commands only — no extras beyond `gmail status` (added for debugging scheduled runs)
- **Plain text with section headers** — similar to existing scripts/run_pipeline.py output style
- No colored output or extra formatting dependencies
- `pipeline run` shows each step as it runs (step name on start, result on complete) — real-time progress
- Support `--json` flag on commands like `queue stats` for machine-readable output
- Errors in pipeline steps: **continue with warning**, don't fail fast. Non-fatal try-except matches existing behavior. Exit code 0 if pipeline finishes.
- **Delete `scripts/` directory entirely** — CLI replaces all script functionality
- **Update LaunchAgent plist** to call `reconnect pipeline run` directly (no shell wrapper)
- **Delete `src/ui/` entirely** — Streamlit is broken, PWA covers all user-facing needs, nothing to preserve
- **Full Streamlit cleanup** — remove all streamlit/plotly imports, try/except blocks, and references across the entire codebase (config.py, etc.)
- Remove `streamlit` and `plotly` from both `pyproject.toml` dependencies and `requirements.txt`
- `reconnect gmail auth` — browser-based OAuth flow: opens browser for Google consent, stores token in local GmailCredentials table
- After successful auth, **prompt to send a test email** for quick validation
- `reconnect gmail status` — check if OAuth is configured and token is valid/expired
- **Auto-refresh silently** on token expiry during unattended LaunchAgent runs. Only fail if refresh token itself is revoked

### Claude's Discretion
- Click group and command organization within src/cli.py (single file vs package)
- Exact help text wording for commands
- How to resolve the `reconnect` binary path in LaunchAgent plist (may need absolute path from pip install)
- Whether to add `click` as a required dependency or optional

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CLI-01 | User can run pipeline operations via CLI (pipeline run, queue reset, queue stats, contacts import, contacts score, gmail auth, sync push/pull) | Click group/command structure; existing functions in daily_pipeline.py, queue_generator.py, ingestion, sync modules are all directly wrappable |
| CLI-02 | Streamlit UI and dependencies fully removed after CLI parity confirmed | Streamlit imports isolated to src/ui/ (all files) + src/config.py try/except block; plotly only in src/ui/views/dashboard.py; clean deletion path is clear |
</phase_requirements>

---

## Summary

Phase 6 is primarily a refactoring phase: wrap existing pipeline functions in a Click CLI, delete the broken Streamlit UI, and update the LaunchAgent to call the `reconnect` binary directly. All the business logic already exists — this phase wires it to a `reconnect` command.

Click 8.3.1 is already installed in the project venv (pulled in transitively). The entry point pattern `[project.scripts]` in pyproject.toml creates the `reconnect` binary at `.venv/bin/reconnect` when installed with `pip install -e .`. The LaunchAgent plist must use the absolute path to this venv binary.

Streamlit references are entirely contained within `src/ui/` (8 files) plus a single try/except block in `src/config.py`. The `get_streamlit_secrets()` function in config.py and its try/except import are the only non-UI streamlit references. Deletion of `src/ui/` plus removal of that config block completes the cleanup. The `scripts/` directory (4 Python files + 2 shell scripts) is fully replaced by CLI commands.

**Primary recommendation:** Create `src/cli.py` as a single file with Click groups; register via `[project.scripts]` in pyproject.toml; delete `src/ui/`, `scripts/`, and strip streamlit/plotly from both dependency files; update the LaunchAgent plist to use the absolute venv binary path.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| click | 8.3.1 (already in venv) | CLI framework — groups, commands, options, arguments | Project decision; already transitively installed; de facto Python CLI standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| click.testing.CliRunner | (bundled with click) | Test CLI commands in unit tests | All CLI tests |
| json (stdlib) | N/A | `--json` flag output serialization | `queue stats --json` |
| sys (stdlib) | N/A | Exit codes | On fatal errors only |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| click | typer | typer is built on click; user locked to click — no change needed |
| click | argparse | argparse is stdlib but more verbose; user locked to click |

**Installation:** click is already installed. To add it explicitly to pyproject.toml:
```bash
# No install needed — click 8.3.1 already present
# Just add to pyproject.toml [project] dependencies:
# "click>=8.0.0",
# Then reinstall editable:
pip install -e /Users/gavin/Developer/reconnect
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/
├── cli.py               # Single file: all Click groups and commands
├── pipeline/
│   └── daily_pipeline.py    # run_daily_pipeline() — unchanged
├── pipeline/
│   └── queue_generator.py   # get_queue_stats(), generate_daily_queue(), expire_stale_queue_items()
├── ingestion/
│   └── csv_import.py        # import_linkedin_csv()
├── llm/
│   └── scoring.py           # rescore_missing_dimensions()
├── sync/
│   ├── push.py              # push_to_cloud()
│   └── pull.py              # pull_from_cloud()
└── integrations/
    └── gmail.py             # authorize_gmail_oauth(), is_oauth_configured()
```

Deleted:
```
scripts/            # DELETED — all replaced by CLI commands
src/ui/             # DELETED — Streamlit UI fully removed
```

### Pattern 1: Click Group Nesting

**What:** Top-level `main` group with subgroups (`pipeline`, `queue`, `contacts`, `gmail`, `sync`), each with commands.
**When to use:** When commands share a natural namespace (e.g., all `pipeline` operations).

```python
# Source: click.palletsprojects.com/en/latest/commands/
import click

@click.group()
def main():
    """Reconnect CLI — personal networking pipeline."""
    pass

@main.group()
def pipeline():
    """Pipeline operations."""
    pass

@pipeline.command("run")
@click.option("--dump", "-d", type=click.Path(exists=True), help="LinkedIn export ZIP path")
@click.option("--skip-enrich", is_flag=True, help="Skip enrichment step")
def pipeline_run(dump, skip_enrich):
    """Run the daily Reconnect pipeline."""
    from src.database.engine import init_db
    from src.pipeline.daily_pipeline import run_daily_pipeline
    init_db()
    # ... (see Code Examples section)
```

**pyproject.toml entry point:**
```toml
[project.scripts]
reconnect = "src.cli:main"
```

After `pip install -e .`, the binary lives at:
```
/Users/gavin/Developer/reconnect/.venv/bin/reconnect
```

### Pattern 2: Real-Time Pipeline Step Output

**What:** Print step header before calling the function, then print result after — matches existing `scripts/run_pipeline.py` style.

```python
@pipeline.command("run")
def pipeline_run(...):
    print("----------------------------------------")
    print("[Pipeline] Starting Reconnect pipeline...")
    print("----------------------------------------")

    print("\n[Import] Checking for LinkedIn dump...", flush=True)
    # call function
    print(f"  Imported: {result['import']['imported']} contacts")

    print("\n[Pre-scoring] Running...", flush=True)
    # etc.
```

`flush=True` ensures output appears immediately in LaunchAgent log files (stdout is line-buffered by default; flush forces it through).

### Pattern 3: Queue Reset (No Existing Function — Port from UI)

**What:** `_reset_stale_queue()` exists in `src/ui/app.py` (lines 927-948) but nowhere in pipeline modules. Must be extracted to `src/pipeline/queue_generator.py` or implemented inline in CLI.

**Recommendation:** Add `reset_queue()` function to `src/pipeline/queue_generator.py` — keeps business logic in the right module, makes it testable independently of CLI.

```python
# Add to src/pipeline/queue_generator.py
def reset_queue() -> dict:
    """Mark all pending_review and approved items as skipped."""
    from datetime import datetime
    with get_session() as session:
        items = session.exec(
            select(OutreachQueueItem)
            .where(OutreachQueueItem.status.in_(["pending_review", "approved"]))
        ).all()
        count = 0
        for item in items:
            item.status = "skipped"
            item.skip_reason = "Queue reset via CLI"
            item.reviewed_at = datetime.utcnow()
            session.add(item)
            count += 1
    return {"reset": count}
```

### Pattern 4: LaunchAgent Plist Update

**What:** Replace shell wrapper with direct CLI binary call.

**Current plist ProgramArguments:**
```xml
<array>
    <string>/Users/gavin/Developer/reconnect/scripts/run_scheduled.sh</string>
</array>
```

**New plist ProgramArguments:**
```xml
<array>
    <string>/Users/gavin/Developer/reconnect/.venv/bin/reconnect</string>
    <string>pipeline</string>
    <string>run</string>
</array>
```

**WorkingDirectory stays the same** — `reconnect` binary needs the project root as CWD because pydantic-settings loads `.env` from the CWD.

**PATH in EnvironmentVariables** — can simplify or keep as-is; the binary path is absolute so PATH doesn't matter for finding it.

**Reload plist after editing:**
```bash
launchctl unload ~/Library/LaunchAgents/com.reconnect.daily-pipeline.plist
launchctl load ~/Library/LaunchAgents/com.reconnect.daily-pipeline.plist
```

### Pattern 5: `--json` Flag Output

**What:** Emit JSON to stdout for machine-readable output on supported commands.

```python
@queue.command("stats")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def queue_stats(as_json):
    """Show current queue statistics."""
    from src.pipeline.queue_generator import get_queue_stats
    stats = get_queue_stats()
    if as_json:
        import json
        click.echo(json.dumps(stats))
    else:
        print("\n[Queue Stats]")
        for status, count in stats.items():
            print(f"  {status}: {count}")
```

### Anti-Patterns to Avoid

- **Importing streamlit anywhere in src/cli.py:** The CLI must have zero streamlit/plotly imports. Verify with grep after cleanup.
- **Using `sys.exit(1)` in pipeline step errors:** Pipeline uses non-fatal try-except; CLI should mirror this — only `sys.exit(1)` if the entire pipeline setup fails (e.g., DB init fails).
- **Shell wrapper for LaunchAgent:** The decision is direct binary invocation. No new `.sh` wrapper.
- **Using relative paths in plist:** LaunchAgent does not activate venv or know about project paths — always use absolute path to the venv binary.
- **Forgetting `flush=True` on progress prints:** Without explicit flush, LaunchAgent log files may show output only after the process exits.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | Custom argparse wrapper | click groups/commands | Already in venv, nested groups are first-class |
| `--help` generation | Manual help text assembly | click's built-in help | Click generates `--help` from docstrings and option definitions |
| JSON output serialization | Custom formatter | stdlib `json.dumps()` | Zero complexity; stats dicts are already JSON-serializable |
| Test invocation | subprocess calls to CLI binary | `click.testing.CliRunner` | Sandboxed, captures output, no subprocess overhead |
| Token auto-refresh | Custom refresh loop | `_load_oauth_credentials()` in `src/integrations/gmail.py` | Already implemented — calls `creds.refresh(Request())` automatically |

**Key insight:** All business logic exists. This phase is exclusively wiring and deletion.

---

## Common Pitfalls

### Pitfall 1: Binary Not on PATH After pip install -e .
**What goes wrong:** Running `reconnect` from terminal says "command not found" even after install.
**Why it happens:** The venv isn't activated; the binary is at `.venv/bin/reconnect` but `~/.local/bin` or the venv bin isn't on PATH.
**How to avoid:** For the LaunchAgent, always use the absolute binary path. For manual use, activate venv first or use `.venv/bin/reconnect` directly. Document this in help output or README.
**Warning signs:** `which reconnect` returns nothing; `reconnect --help` fails.

### Pitfall 2: config.py get_streamlit_secrets() Left Behind
**What goes wrong:** Streamlit import try/except in config.py silently succeeds (if streamlit is still installed during transition) or raises ImportError after removal.
**Why it happens:** The `get_streamlit_secrets()` function in `src/config.py` imports streamlit at call time. It's never called from CLI paths, but it's still dead code that pollutes the module.
**How to avoid:** Delete the entire `get_streamlit_secrets()` function from config.py — it has no callers outside src/ui/ and is completely unused in the CLI + PWA architecture.
**Warning signs:** `grep -r "streamlit" src/` still shows hits after cleanup.

### Pitfall 3: Forgetting to Reload LaunchAgent After Plist Edit
**What goes wrong:** Pipeline still runs via old shell wrapper even after plist is updated.
**Why it happens:** LaunchAgent reads plist at load time; changes to the file on disk don't take effect until the agent is reloaded.
**How to avoid:** Always run `launchctl unload` then `launchctl load` after editing the plist. Verify with `launchctl list | grep reconnect`.
**Warning signs:** `launchctl list com.reconnect.daily-pipeline` shows old ProgramArguments.

### Pitfall 4: CWD Not Set for reconnect Binary in LaunchAgent
**What goes wrong:** `settings.database_path` resolves to a relative path from `/` (root) instead of the project root; `.env` file not found; database not found.
**Why it happens:** LaunchAgent sets CWD to `/` by default unless `WorkingDirectory` is specified.
**How to avoid:** Keep `WorkingDirectory` key in plist pointing to `/Users/gavin/Developer/reconnect`. The plist already has this — don't remove it when updating ProgramArguments.
**Warning signs:** Database path errors in pipeline log; "no such file" for `.env`.

### Pitfall 5: CliRunner + mock.patch Ordering Issues in Tests
**What goes wrong:** Mocked functions appear to not apply when using `CliRunner.invoke()`.
**Why it happens:** `mock.patch` as a decorator on the test function patches after Click resolves the command. The patch must be active when `invoke()` runs.
**How to avoid:** Use `with patch("src.pipeline.daily_pipeline.run_daily_pipeline") as mock_run:` inside the test body, then call `runner.invoke()` inside the `with` block.
**Warning signs:** Test passes without the mock being called; mock.called is False.

### Pitfall 6: Missing queue reset Function in Pipeline Module
**What goes wrong:** `reconnect queue reset` command has no function to call — the only implementation is buried in `src/ui/app.py`'s `_reset_stale_queue()`.
**Why it happens:** Queue reset was implemented as a UI-only action in Streamlit app.
**How to avoid:** Extract reset logic to `src/pipeline/queue_generator.py` as `reset_queue()` before implementing the CLI command. This also makes it testable.

---

## Code Examples

Verified patterns from project codebase and click documentation:

### Complete CLI Structure (src/cli.py)
```python
# Source: click.palletsprojects.com/en/latest/commands/ + project patterns
import sys
import click

@click.group()
def main():
    """Reconnect — personal networking pipeline CLI."""
    pass

# ── pipeline ─────────────────────────────────────────────────────────────────

@main.group()
def pipeline():
    """Pipeline operations."""
    pass

@pipeline.command("run")
@click.option("--dump", "-d", type=click.Path(exists=True),
              help="Path to LinkedIn export ZIP")
@click.option("--skip-enrich", is_flag=True, help="Skip enrichment step")
@click.option("--skip-queue", is_flag=True, help="Skip queue generation step")
def pipeline_run(dump, skip_enrich, skip_queue):
    """Run the daily Reconnect pipeline."""
    from pathlib import Path
    from src.database.engine import init_db
    from src.pipeline.daily_pipeline import run_daily_pipeline

    print("----------------------------------------")
    print("[Pipeline] Starting Reconnect pipeline...")
    print("----------------------------------------")

    try:
        init_db()
    except Exception as e:
        print(f"[ERROR] Database init failed: {e}")
        sys.exit(1)

    results = run_daily_pipeline(
        linkedin_dump_path=Path(dump) if dump else None,
        skip_enrichment=skip_enrich,
        skip_queue_generation=skip_queue,
    )

    _print_pipeline_results(results)
    # Exit 0 even if individual steps had errors — matches existing behavior


def _print_pipeline_results(results: dict) -> None:
    """Format and print pipeline results to stdout."""
    if "import" in results:
        imp = results["import"]
        print(f"\n[Import]")
        print(f"  Imported: {imp.get('imported', 0)} new contacts")
        print(f"  Updated: {imp.get('updated', 0)} existing contacts")

    if "prescore" in results:
        ps = results["prescore"]
        print(f"\n[Pre-scoring]")
        print(f"  Scored: {ps.get('scored', 0)} contacts")

    if "enrich" in results:
        en = results["enrich"]
        print(f"\n[Enrichment]")
        print(f"  Success: {en.get('success', 0)}")
        print(f"  Failed: {en.get('failed', 0)}")

    if "score" in results:
        sc = results["score"]
        print(f"\n[Full Scoring]")
        print(f"  Scored: {sc.get('scored', 0)}")

    if "queue" in results:
        q = results["queue"]
        print(f"\n[Queue Generation]")
        print(f"  Added: {q.get('added', 0)}")
        print(f"  Excluded: {q.get('excluded', 0)}")

    print("\n----------------------------------------")
    print("Pipeline complete.")

# ── queue ────────────────────────────────────────────────────────────────────

@main.group()
def queue():
    """Queue operations."""
    pass

@queue.command("stats")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def queue_stats(as_json):
    """Show current queue statistics."""
    import json as _json
    from src.pipeline.queue_generator import get_queue_stats
    stats = get_queue_stats()
    if as_json:
        click.echo(_json.dumps(stats))
    else:
        print("\n[Queue Stats]")
        for status, count in stats.items():
            print(f"  {status}: {count}")

@queue.command("reset")
def queue_reset():
    """Reset all pending/approved queue items to skipped."""
    from src.pipeline.queue_generator import reset_queue
    result = reset_queue()
    print(f"[Queue Reset] {result['reset']} items reset to skipped.")

# ── contacts ─────────────────────────────────────────────────────────────────

@main.group()
def contacts():
    """Contact operations."""
    pass

@contacts.command("import")
@click.argument("csv_file", type=click.Path(exists=True))
def contacts_import(csv_file):
    """Import LinkedIn connections CSV."""
    from pathlib import Path
    from src.database.engine import init_db
    from src.ingestion.csv_import import import_linkedin_csv
    init_db()
    result = import_linkedin_csv(Path(csv_file))
    print(f"\n[Import]")
    print(f"  Imported: {result.imported}")
    print(f"  Updated: {result.updated}")
    print(f"  Skipped: {result.skipped}")

@contacts.command("score")
def contacts_score():
    """Re-score contacts that are missing dimension scores."""
    from src.database.engine import init_db
    from src.llm.scoring import rescore_missing_dimensions
    init_db()
    result = rescore_missing_dimensions()
    print(f"\n[Scoring]")
    print(f"  Rescored: {result.get('rescored', 0)}")
    print(f"  Failed: {result.get('failed', 0)}")

# ── gmail ────────────────────────────────────────────────────────────────────

@main.group()
def gmail():
    """Gmail OAuth operations."""
    pass

@gmail.command("auth")
@click.argument("client_secrets", type=click.Path(exists=True))
def gmail_auth(client_secrets):
    """Authorize Gmail OAuth. Requires credentials.json from GCP Console."""
    from src.database.engine import init_db
    from src.integrations.gmail import authorize_gmail_oauth, is_oauth_configured

    init_db()
    print("Opening browser for Google authorization...")
    authorize_gmail_oauth(client_secrets)
    print("Authorization successful! Token stored locally.")

    if click.confirm("Send a test email to verify?"):
        _send_test_email()

def _send_test_email():
    """Send a test email via Gmail OAuth to verify auth works."""
    from src.integrations.gmail import oauth_send_html_email, get_user_email
    email = get_user_email() or click.prompt("Enter recipient email")
    try:
        oauth_send_html_email(email, "Reconnect test email",
                              "<p>Gmail OAuth is configured correctly.</p>")
        print(f"Test email sent to {email}.")
    except Exception as e:
        print(f"Test email failed: {e}")

@gmail.command("status")
def gmail_status():
    """Check Gmail OAuth configuration status."""
    from src.integrations.gmail import is_oauth_configured, is_gmail_configured
    oauth_ok = is_oauth_configured()
    app_pw_ok = is_gmail_configured()

    print("\n[Gmail Status]")
    print(f"  OAuth configured: {'yes' if oauth_ok else 'no'}")
    print(f"  App Password configured: {'yes' if app_pw_ok else 'no'}")
    if not oauth_ok and not app_pw_ok:
        print("  Run 'reconnect gmail auth <credentials.json>' to configure OAuth.")

# ── sync ─────────────────────────────────────────────────────────────────────

@main.group()
def sync():
    """Sync operations."""
    pass

@sync.command("push")
def sync_push():
    """Push local data to Supabase cloud."""
    from src.sync.push import push_to_cloud
    print("[Sync] Pushing to cloud...")
    stats = push_to_cloud()
    print(f"  {stats}")

@sync.command("pull")
def sync_pull():
    """Pull actions from Supabase cloud to local."""
    from src.sync.pull import pull_from_cloud
    print("[Sync] Pulling from cloud...")
    stats = pull_from_cloud()
    print(f"  {stats}")
```

### Testing CLI Commands with CliRunner
```python
# Source: click.palletsprojects.com/en/stable/testing/
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from src.cli import main

def test_queue_stats():
    runner = CliRunner()
    with patch("src.pipeline.queue_generator.get_queue_stats") as mock_stats:
        mock_stats.return_value = {"pending_review": 3, "approved": 1, "sent": 10}
        result = runner.invoke(main, ["queue", "stats"])
    assert result.exit_code == 0
    assert "pending_review: 3" in result.output

def test_queue_stats_json():
    runner = CliRunner()
    with patch("src.pipeline.queue_generator.get_queue_stats") as mock_stats:
        mock_stats.return_value = {"pending_review": 3}
        result = runner.invoke(main, ["queue", "stats", "--json"])
    import json
    data = json.loads(result.output)
    assert data["pending_review"] == 3

def test_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "pipeline" in result.output
```

### pyproject.toml Changes
```toml
[project]
dependencies = [
    # REMOVE: "streamlit>=1.30.0",
    # REMOVE: "plotly>=5.18.0",
    "click>=8.0.0",    # ADD
    "sqlmodel>=0.0.14",
    # ... rest unchanged
]

[project.scripts]
reconnect = "src.cli:main"    # ADD this entire section
```

### Streamlit Cleanup in src/config.py
```python
# BEFORE (lines 10-18):
def get_streamlit_secrets() -> dict[str, Any]:
    """Get secrets from Streamlit Cloud if available."""
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            return dict(st.secrets)
    except Exception:
        pass
    return {}

# AFTER: Delete this entire function — it has no callers outside src/ui/
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `scripts/run_pipeline.py` (argparse) | `reconnect pipeline run` (click) | Phase 6 | Single installed binary replaces multiple scripts |
| `scripts/run_sync.py` | `reconnect sync push/pull` | Phase 6 | Consistent UX |
| `scripts/import_csv.py` | `reconnect contacts import` | Phase 6 | Consistent UX |
| Streamlit admin UI | Deleted — PWA covers user-facing | Phase 6 | Remove broken/unused code |
| Shell wrapper LaunchAgent | Direct venv binary in ProgramArguments | Phase 6 | Fewer moving parts |

**Deprecated/outdated:**
- `scripts/` directory: All 6 files (`run_pipeline.py`, `run_sync.py`, `import_csv.py`, `init_db.py`, `run_scheduled.sh`, `scheduler.sh`) — fully replaced by CLI commands
- `src/ui/` directory: All 8+ files — deleted entirely, no preservation needed
- `streamlit` and `plotly` packages: Remove from `requirements.txt` and `pyproject.toml`

---

## Open Questions

1. **`init_db.py` script replacement**
   - What we know: `scripts/init_db.py` exists; it initializes the database. Not listed in success criteria commands.
   - What's unclear: Should `reconnect` have an `init` or `db init` command, or does `pipeline run` always call `init_db()` first (it does)?
   - Recommendation: Since `init_db()` is called at the start of `pipeline run` and `contacts import`, no separate `reconnect db init` command is needed. The script is redundant.

2. **`reconnect contacts score` — which function to call**
   - What we know: `rescore_missing_dimensions()` in `src/llm/scoring.py` rescores contacts without dimension scores. `prescore_unscored_connections()` in `src/llm/prescoring.py` handles un-scored contacts.
   - What's unclear: "contacts score" in the success criteria — does it mean rescore all, or just rescore missing?
   - Recommendation: Map `contacts score` to `rescore_missing_dimensions()` (dimension score fix) since that's the established repair function from Phase 4. Add `--all` flag if needed.

3. **gmail_auth credential path convention**
   - What we know: `authorize_gmail_oauth(client_secrets_path: str)` expects a path to GCP credentials.json.
   - What's unclear: Should the path be a required argument or should it default to a well-known location (e.g., `~/credentials.json`)?
   - Recommendation: Require it as a positional argument (`reconnect gmail auth ./credentials.json`) — makes the path explicit, avoids silent path resolution errors.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ (installed in venv at `/Users/gavin/Developer/reconnect/.venv/bin/pytest`) |
| Config file | none — `pyproject.toml` has no `[tool.pytest]` section |
| Quick run command | `pytest tests/test_phase6_cli.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-01 | `reconnect --help` lists all subcommand groups | unit | `pytest tests/test_phase6_cli.py::test_help -x` | Wave 0 |
| CLI-01 | `reconnect pipeline run` calls `run_daily_pipeline()` | unit | `pytest tests/test_phase6_cli.py::test_pipeline_run -x` | Wave 0 |
| CLI-01 | `reconnect queue stats` outputs status counts | unit | `pytest tests/test_phase6_cli.py::test_queue_stats -x` | Wave 0 |
| CLI-01 | `reconnect queue stats --json` outputs valid JSON | unit | `pytest tests/test_phase6_cli.py::test_queue_stats_json -x` | Wave 0 |
| CLI-01 | `reconnect queue reset` calls reset_queue() | unit | `pytest tests/test_phase6_cli.py::test_queue_reset -x` | Wave 0 |
| CLI-01 | `reconnect contacts import <csv>` calls import_linkedin_csv() | unit | `pytest tests/test_phase6_cli.py::test_contacts_import -x` | Wave 0 |
| CLI-01 | `reconnect contacts score` calls rescore_missing_dimensions() | unit | `pytest tests/test_phase6_cli.py::test_contacts_score -x` | Wave 0 |
| CLI-01 | `reconnect gmail status` reports OAuth configured/not | unit | `pytest tests/test_phase6_cli.py::test_gmail_status -x` | Wave 0 |
| CLI-01 | `reconnect sync push` calls push_to_cloud() | unit | `pytest tests/test_phase6_cli.py::test_sync_push -x` | Wave 0 |
| CLI-01 | `reconnect sync pull` calls pull_from_cloud() | unit | `pytest tests/test_phase6_cli.py::test_sync_pull -x` | Wave 0 |
| CLI-02 | No streamlit import anywhere in src/ (excluding src/ui/) | static | `pytest tests/test_phase6_cli.py::test_no_streamlit_imports -x` | Wave 0 |
| CLI-02 | No plotly import anywhere in src/ | static | `pytest tests/test_phase6_cli.py::test_no_plotly_imports -x` | Wave 0 |
| CLI-02 | src/ui/ directory does not exist | static | `pytest tests/test_phase6_cli.py::test_ui_deleted -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_phase6_cli.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase6_cli.py` — covers all CLI-01/CLI-02 behaviors above
- [ ] `reset_queue()` function in `src/pipeline/queue_generator.py` — needed before CLI test can mock it

*(No conftest gaps — existing `conftest.py` with `mock_settings` fixture is sufficient)*

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — all existing scripts, pipeline functions, gmail integration, UI files, plist
- click 8.3.1 installed in project venv — version confirmed via `click.__version__`
- pyproject.toml and requirements.txt — dependency lists confirmed
- LaunchAgent plist at `~/Library/LaunchAgents/com.reconnect.daily-pipeline.plist` — current structure confirmed

### Secondary (MEDIUM confidence)
- [Click documentation — Entry Points](https://click.palletsprojects.com/en/latest/entry-points/) — console_scripts pattern
- [Click documentation — Testing](https://click.palletsprojects.com/en/stable/testing/) — CliRunner patterns
- [Python Packaging User Guide — pyproject.toml scripts](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) — [project.scripts] syntax

### Tertiary (LOW confidence)
- None — all claims backed by direct code inspection or official documentation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — click already installed in venv, version confirmed
- Architecture: HIGH — all existing functions directly inspected; clear wiring path
- Pitfalls: HIGH — derived from direct code inspection (config.py streamlit import, launchd CWD behavior, CliRunner mock ordering documented in click GitHub issues)

**Research date:** 2026-03-09
**Valid until:** 2026-06-09 (stable domain — Click 8.x, pyproject.toml, launchd are all stable)
