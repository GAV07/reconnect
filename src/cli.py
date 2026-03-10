"""Reconnect CLI — Click-based command interface for the networking pipeline.

Usage:
    reconnect --help
    reconnect pipeline run [--dump <path>] [--skip-enrich] [--skip-queue]
    reconnect queue stats [--json]
    reconnect queue reset
    reconnect contacts import <csv_file>
    reconnect contacts score
    reconnect gmail auth <client_secrets>
    reconnect gmail status
    reconnect sync push
    reconnect sync pull
"""

import sys

import click


@click.group()
def main():
    """Reconnect -- personal networking pipeline CLI."""
    pass


# ── pipeline ─────────────────────────────────────────────────────────────────


@main.group()
def pipeline():
    """Pipeline operations."""
    pass


@pipeline.command("run")
@click.option("--dump", "-d", type=click.Path(exists=True), help="Path to LinkedIn export ZIP")
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


# ── queue ─────────────────────────────────────────────────────────────────────


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


# ── contacts ──────────────────────────────────────────────────────────────────


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


# ── gmail ─────────────────────────────────────────────────────────────────────


@main.group()
def gmail():
    """Gmail OAuth operations."""
    pass


@gmail.command("auth")
@click.argument("client_secrets", type=click.Path(exists=True))
def gmail_auth(client_secrets):
    """Authorize Gmail OAuth. Requires credentials.json from GCP Console."""
    from src.database.engine import init_db
    from src.integrations.gmail import authorize_gmail_oauth

    init_db()
    print("Opening browser for Google authorization...")
    authorize_gmail_oauth(client_secrets)
    print("Authorization successful! Token stored locally.")

    if click.confirm("Send a test email to verify?"):
        _send_test_email()


def _send_test_email():
    """Send a test email via Gmail OAuth to verify auth works."""
    from src.integrations.gmail import get_user_email, oauth_send_html_email

    email = get_user_email() or click.prompt("Enter recipient email")
    try:
        oauth_send_html_email(
            email,
            "Reconnect test email",
            "<p>Gmail OAuth is configured correctly.</p>",
        )
        print(f"Test email sent to {email}.")
    except Exception as e:
        print(f"Test email failed: {e}")


@gmail.command("status")
def gmail_status():
    """Check Gmail OAuth configuration status."""
    from src.integrations.gmail import is_gmail_configured, is_oauth_configured

    oauth_ok = is_oauth_configured()
    app_pw_ok = is_gmail_configured()

    print("\n[Gmail Status]")
    print(f"  OAuth configured: {'yes' if oauth_ok else 'no'}")
    print(f"  App Password configured: {'yes' if app_pw_ok else 'no'}")
    if not oauth_ok and not app_pw_ok:
        print("  Run 'reconnect gmail auth <credentials.json>' to configure OAuth.")


# ── sync ──────────────────────────────────────────────────────────────────────


@main.group()
def sync():
    """Sync operations."""
    pass


@sync.command("push")
def sync_push():
    """Push local data to Supabase cloud."""
    from src.sync.push import push_to_cloud

    print("[Sync] Pushing to cloud...", flush=True)
    stats = push_to_cloud()
    print(f"  {stats}")


@sync.command("pull")
def sync_pull():
    """Pull actions from Supabase cloud to local."""
    from src.sync.pull import pull_from_cloud

    print("[Sync] Pulling from cloud...", flush=True)
    stats = pull_from_cloud()
    print(f"  {stats}")
