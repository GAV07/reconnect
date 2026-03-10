"""Tests for Phase 6 CLI — Click-based reconnect command.

Tests verify CLI wiring only. All business logic is mocked.
Uses CliRunner to invoke commands without subprocess overhead.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli import main


# ── Help / Structure Tests ────────────────────────────────────────────────────


def test_help():
    """reconnect --help exits 0 and lists all 5 command groups."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "pipeline" in result.output
    assert "queue" in result.output
    assert "contacts" in result.output
    assert "gmail" in result.output
    assert "sync" in result.output


# ── pipeline commands ─────────────────────────────────────────────────────────


def test_pipeline_run():
    """reconnect pipeline run calls run_daily_pipeline() and prints step results."""
    runner = CliRunner()
    mock_result = {
        "import": {"imported": 5, "updated": 2},
        "prescore": {"scored": 10},
        "enrich": {"success": 3, "failed": 1},
        "score": {"scored": 8},
        "queue": {"added": 4, "excluded": 2},
    }
    with patch("src.database.engine.init_db") as mock_init, \
         patch("src.pipeline.daily_pipeline.run_daily_pipeline") as mock_run:
        mock_run.return_value = mock_result
        result = runner.invoke(main, ["pipeline", "run"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert "Pipeline" in result.output


def test_pipeline_run_db_init_failure():
    """reconnect pipeline run exits 1 if init_db raises."""
    runner = CliRunner()
    with patch("src.database.engine.init_db") as mock_init:
        mock_init.side_effect = Exception("DB connection failed")
        result = runner.invoke(main, ["pipeline", "run"])
    assert result.exit_code == 1
    assert "ERROR" in result.output or "error" in result.output.lower()


def test_pipeline_run_with_flags():
    """reconnect pipeline run accepts --skip-enrich and --skip-queue flags."""
    runner = CliRunner()
    with patch("src.database.engine.init_db"), \
         patch("src.pipeline.daily_pipeline.run_daily_pipeline") as mock_run:
        mock_run.return_value = {}
        result = runner.invoke(main, ["pipeline", "run", "--skip-enrich", "--skip-queue"])
    assert result.exit_code == 0
    call_kwargs = mock_run.call_args
    assert call_kwargs.kwargs.get("skip_enrichment") is True or \
           (call_kwargs.args and True in call_kwargs.args)


# ── queue commands ────────────────────────────────────────────────────────────


def test_queue_stats():
    """reconnect queue stats calls get_queue_stats() and prints status counts."""
    runner = CliRunner()
    with patch("src.pipeline.queue_generator.get_queue_stats") as mock_stats:
        mock_stats.return_value = {
            "pending_review": 3,
            "approved": 1,
            "skipped": 10,
            "sent": 25,
            "failed": 0,
        }
        result = runner.invoke(main, ["queue", "stats"])
    assert result.exit_code == 0
    mock_stats.assert_called_once()
    assert "pending_review" in result.output
    assert "3" in result.output


def test_queue_stats_json():
    """reconnect queue stats --json outputs valid JSON with status keys."""
    runner = CliRunner()
    with patch("src.pipeline.queue_generator.get_queue_stats") as mock_stats:
        mock_stats.return_value = {
            "pending_review": 3,
            "approved": 1,
            "skipped": 10,
            "sent": 25,
            "failed": 0,
        }
        result = runner.invoke(main, ["queue", "stats", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["pending_review"] == 3
    assert "approved" in data


def test_queue_reset():
    """reconnect queue reset calls reset_queue() and prints count."""
    runner = CliRunner()
    with patch("src.pipeline.queue_generator.reset_queue") as mock_reset:
        mock_reset.return_value = {"reset": 7}
        result = runner.invoke(main, ["queue", "reset"])
    assert result.exit_code == 0
    mock_reset.assert_called_once()
    assert "7" in result.output


# ── contacts commands ─────────────────────────────────────────────────────────


def test_contacts_import(tmp_path):
    """reconnect contacts import <csv> calls import_linkedin_csv() with Path argument."""
    # Create a real temp file so click.Path(exists=True) passes
    csv_file = tmp_path / "connections.csv"
    csv_file.write_text("First Name,Last Name,Email\nJohn,Doe,john@example.com\n")

    runner = CliRunner()
    mock_result = MagicMock()
    mock_result.imported = 1
    mock_result.updated = 0
    mock_result.skipped = 0

    with patch("src.database.engine.init_db"), \
         patch("src.ingestion.csv_import.import_linkedin_csv") as mock_import:
        mock_import.return_value = mock_result
        result = runner.invoke(main, ["contacts", "import", str(csv_file)])

    assert result.exit_code == 0
    mock_import.assert_called_once()
    # Verify the Path argument was passed
    call_args = mock_import.call_args
    assert isinstance(call_args.args[0], Path)


def test_contacts_score():
    """reconnect contacts score calls rescore_missing_dimensions()."""
    runner = CliRunner()
    with patch("src.database.engine.init_db"), \
         patch("src.llm.scoring.rescore_missing_dimensions") as mock_score:
        mock_score.return_value = {"rescored": 15, "failed": 2}
        result = runner.invoke(main, ["contacts", "score"])
    assert result.exit_code == 0
    mock_score.assert_called_once()
    assert "15" in result.output


# ── gmail commands ────────────────────────────────────────────────────────────


def test_gmail_auth(tmp_path):
    """reconnect gmail auth <file> calls authorize_gmail_oauth() (test email skipped)."""
    # Create a real temp file so click.Path(exists=True) passes
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text('{"installed": {}}')

    runner = CliRunner()
    with patch("src.database.engine.init_db"), \
         patch("src.integrations.gmail.authorize_gmail_oauth") as mock_auth, \
         patch("click.confirm", return_value=False):
        result = runner.invoke(main, ["gmail", "auth", str(creds_file)])

    assert result.exit_code == 0
    mock_auth.assert_called_once_with(str(creds_file))


def test_gmail_status():
    """reconnect gmail status calls is_oauth_configured() and is_gmail_configured()."""
    runner = CliRunner()
    with patch("src.integrations.gmail.is_oauth_configured", return_value=True) as mock_oauth, \
         patch("src.integrations.gmail.is_gmail_configured", return_value=False) as mock_app:
        result = runner.invoke(main, ["gmail", "status"])
    assert result.exit_code == 0
    mock_oauth.assert_called_once()
    mock_app.assert_called_once()
    assert "yes" in result.output  # OAuth configured
    assert "no" in result.output   # App Password not configured


# ── sync commands ─────────────────────────────────────────────────────────────


def test_sync_push():
    """reconnect sync push calls push_to_cloud()."""
    runner = CliRunner()
    with patch("src.sync.push.push_to_cloud") as mock_push:
        mock_push.return_value = {"pushed": 50, "failed": 0}
        result = runner.invoke(main, ["sync", "push"])
    assert result.exit_code == 0
    mock_push.assert_called_once()


def test_sync_pull():
    """reconnect sync pull calls pull_from_cloud()."""
    runner = CliRunner()
    with patch("src.sync.pull.pull_from_cloud") as mock_pull:
        mock_pull.return_value = {"pulled": 5, "errors": 0}
        result = runner.invoke(main, ["sync", "pull"])
    assert result.exit_code == 0
    mock_pull.assert_called_once()


# ── reset_queue function ──────────────────────────────────────────────────────


def test_reset_queue_function():
    """reset_queue() marks all pending_review and approved items as skipped, returns {"reset": N}."""
    from src.pipeline.queue_generator import reset_queue

    # Create mock session and items
    mock_item_1 = MagicMock()
    mock_item_1.status = "pending_review"
    mock_item_2 = MagicMock()
    mock_item_2.status = "approved"

    mock_session = MagicMock()
    mock_session.exec.return_value.all.return_value = [mock_item_1, mock_item_2]
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)

    with patch("src.pipeline.queue_generator.get_session", return_value=mock_session):
        result = reset_queue()

    assert result == {"reset": 2}
    assert mock_item_1.status == "skipped"
    assert mock_item_2.status == "skipped"
    assert mock_item_1.skip_reason == "Queue reset via CLI"
    assert mock_item_2.skip_reason == "Queue reset via CLI"
