"""Daily pipeline for Reconnect.

Orchestrates the full daily workflow:
1. Import LinkedIn dump (if provided)
2. Auto-update UserProfile from LinkedIn data
3. Pre-score un-scored contacts
4. Enrich top N from tier 1 via Apify (budgeted)
5. Full-score enriched contacts
6. Generate outreach queue
7. Sync to cloud (if Supabase configured)

Note: Email finding via Hunter.io is available as a separate manual step in the UI.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlmodel import select

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection, PipelineRun, UserProfile


@dataclass
class PipelineResult:
    """Result of a pipeline run."""

    run_id: str
    status: str  # "completed" | "failed"
    steps_completed: list[str] = field(default_factory=list)
    step_results: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    error_step: Optional[str] = None


def run_daily_pipeline(
    linkedin_dump_path: Optional[Path] = None,
    user_name: Optional[str] = None,
    skip_enrichment: bool = False,
    skip_queue_generation: bool = False,
    enrich_budget: Optional[int] = None,
    queue_size: Optional[int] = None,
) -> dict:
    """
    Run the daily pipeline.

    Args:
        linkedin_dump_path: Optional path to LinkedIn export ZIP
        user_name: User's name for message direction detection
        skip_enrichment: Skip Apify enrichment step
        skip_queue_generation: Skip queue generation step
        enrich_budget: Max contacts to enrich (default: settings.daily_enrich_budget)
        queue_size: Max queue items to generate (default: settings.daily_queue_size)

    Returns:
        Dict with results from each step
    """
    if enrich_budget is None:
        enrich_budget = settings.daily_enrich_budget
    if queue_size is None:
        queue_size = settings.daily_queue_size

    # Create pipeline run record
    run_id = None
    with get_session() as session:
        run = PipelineRun(
            run_type="daily",
            status="running",
            input_params={
                "linkedin_dump": str(linkedin_dump_path) if linkedin_dump_path else None,
                "skip_enrichment": skip_enrichment,
                "skip_queue_generation": skip_queue_generation,
                "enrich_budget": enrich_budget,
                "queue_size": queue_size,
            },
        )
        session.add(run)
        session.flush()
        run_id = run.id

    results = {}
    steps_completed = []
    error_message = None
    error_step = None

    try:
        # Step 1: Import LinkedIn dump
        # Priority: explicit path > auto-detect from Downloads
        from src.ingestion.linkedin_dump import (
            auto_import_linkedin_dump,
            extract_linkedin_dump,
            import_linkedin_dump,
        )

        # Get user name from profile if not provided
        if not user_name:
            with get_session() as session:
                profile = session.get(UserProfile, 1)
                if profile:
                    user_name = profile.name

        import_result = None

        if linkedin_dump_path and linkedin_dump_path.exists():
            # Explicit path provided
            import_result = import_linkedin_dump(
                linkedin_dump_path,
                user_name=user_name,
                summarize_conversations=True,
            )
        else:
            # Try auto-import from default location (Downloads)
            import_result = auto_import_linkedin_dump(
                user_name=user_name,
                summarize_conversations=False,  # Skip LLM for auto-import
            )

        if import_result:
            results["import"] = {
                "batch_id": import_result.batch_id,
                "imported": import_result.connections_imported,
                "updated": import_result.connections_updated,
                "new_ids": import_result.new_connection_ids,
                "messages_processed": import_result.messages_processed,
                "conversations_summarized": import_result.conversations_summarized,
                "source": "explicit" if linkedin_dump_path else "auto",
            }
            steps_completed.append("import")

            # Step 2: Update user profile from dump (only if explicit path)
            if linkedin_dump_path:
                from src.ingestion.profile_inference import update_user_profile_from_dump

                dump = extract_linkedin_dump(linkedin_dump_path)
                update_user_profile_from_dump(dump)
                steps_completed.append("profile_update")

        # Step 2b: Check for goals rescore trigger
        # When user changes goals in the PWA, a UserPreference row with
        # pref_type="rescore_trigger" is written. We batch-clear scored_at
        # on up to 10 contacts per run so they get rescored with the new goals.
        # The trigger row is deleted once all affected contacts are rescored.
        try:
            from src.database.models import UserPreference
            with get_session() as session:
                trigger = session.exec(
                    select(UserPreference)
                    .where(UserPreference.pref_type == "rescore_trigger")
                    .where(UserPreference.pref_key == "goals_updated_at")
                ).first()

                if trigger and trigger.pref_value:
                    from datetime import datetime as dt
                    trigger_ts = dt.fromisoformat(trigger.pref_value.replace("Z", "+00:00"))

                    # Find contacts scored before goals changed
                    stale = session.exec(
                        select(Connection)
                        .where(Connection.scored_at.isnot(None))
                        .where(Connection.scored_at < trigger_ts)
                        .limit(10)
                    ).all()

                    if stale:
                        for conn in stale:
                            conn.scored_at = None
                        session.commit()
                        results["rescore_cleared"] = len(stale)
                        import logging as _log
                        _log.getLogger(__name__).info(
                            "Goals rescore: cleared scored_at on %d contacts (batch)", len(stale)
                        )
                    else:
                        # All contacts rescored — remove trigger
                        session.delete(trigger)
                        session.commit()
                        results["rescore_trigger_cleared"] = True
                        import logging as _log
                        _log.getLogger(__name__).info(
                            "Goals rescore: all contacts rescored, trigger removed"
                        )

                    steps_completed.append("rescore_trigger")
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning("Goals rescore trigger check failed: %s", e)

        # Step 3: Pre-score un-scored contacts
        from src.llm.prescoring import prescore_unscored_connections

        prescore_result = prescore_unscored_connections(use_llm=True)
        results["prescore"] = prescore_result
        steps_completed.append("prescore")

        # Step 4: Enrich top tier-1 contacts (unless skipped)
        if not skip_enrichment:
            from src.ingestion.rapidapi_linkedin import update_connection_from_profile
            from src.llm.prescoring import get_tier1_connections

            tier1 = get_tier1_connections(limit=enrich_budget)
            enrich_results = {"success": 0, "failed": 0, "errors": []}

            for conn in tier1:
                try:
                    if update_connection_from_profile(conn.id):
                        enrich_results["success"] += 1
                    else:
                        enrich_results["failed"] += 1
                except Exception as e:
                    enrich_results["failed"] += 1
                    enrich_results["errors"].append(f"{conn.name}: {str(e)[:50]}")

            # Step 4b: If budget remains, enrich top tier-2 contacts
            remaining_budget = enrich_budget - len(tier1)
            tier2_enriched = []
            if remaining_budget > 0:
                tier2 = _get_tier2_connections(limit=remaining_budget)
                for conn in tier2:
                    try:
                        if update_connection_from_profile(conn.id):
                            enrich_results["success"] += 1
                            tier2_enriched.append(conn)
                        else:
                            enrich_results["failed"] += 1
                    except Exception as e:
                        enrich_results["failed"] += 1
                        enrich_results["errors"].append(f"{conn.name}: {str(e)[:50]}")

            results["enrich"] = enrich_results
            steps_completed.append("enrich")

        # Step 5: Full-score enriched contacts that need scoring
        # Runs even when enrichment is skipped — picks up enriched-but-unscored contacts
        from src.llm.scoring import score_connection

        score_results = {"scored": 0, "failed": 0, "skipped": 0}

        with get_session() as session:
            # Find all enriched contacts that either have no score or no rubric
            unscored = session.exec(
                select(Connection)
                .where(Connection.enriched_at.isnot(None))
                .where(Connection.reconnect_score.is_(None))
            ).all()
            to_score = [(c.id, c.name) for c in unscored]

        for conn_id, conn_name in to_score:
            try:
                result = score_connection(conn_id)
                if result:
                    score_results["scored"] += 1
                else:
                    score_results["failed"] += 1
            except Exception:
                score_results["failed"] += 1

        results["score"] = score_results
        steps_completed.append("score")

        # Note: cadence re-queuing (CAD-02, CAD-03) is integrated directly into
        # generate_daily_queue() rather than being a separate pipeline step.
        # Contacts with expired cadence_due_at are queried inside queue generation
        # and compete for slots alongside fresh scored candidates (capped at 50%).
        # One-day delay for goals changes is expected behavior (goals are stable
        # networking objectives, not urgent requests) — pull sync runs at end of
        # pipeline, so new goals take effect on the NEXT day's scoring run.

        # Step 6: Generate outreach queue (unless skipped)
        if not skip_queue_generation:
            from src.pipeline.queue_generator import generate_daily_queue

            queue_result = generate_daily_queue(limit=queue_size)
            results["queue"] = queue_result
            steps_completed.append("queue")

        # Mark run as completed
        with get_session() as session:
            run = session.get(PipelineRun, run_id)
            if run:
                run.status = "completed"
                run.steps_completed = steps_completed
                run.step_results = results
                run.completed_at = datetime.utcnow()
                session.add(run)

        # Step 7: Compute data completeness scores
        try:
            from src.llm.data_analyzer import analyze_all_connections

            completeness_result = analyze_all_connections()
            results["data_completeness"] = completeness_result
            steps_completed.append("data_completeness")
        except Exception as dc_error:
            import logging
            logging.getLogger(__name__).warning(
                "Data completeness analysis failed (non-fatal): %s", dc_error
            )
            results["data_completeness"] = {"error": str(dc_error)}

        # Step 8: Process feedback signals → update scoring weights
        try:
            from src.pipeline.feedback_processor import process_feedback

            feedback_result = process_feedback()
            results["feedback"] = feedback_result
            steps_completed.append("feedback")
        except Exception as fb_error:
            import logging
            logging.getLogger(__name__).warning(
                "Feedback processing failed (non-fatal): %s", fb_error
            )
            results["feedback"] = {"error": str(fb_error)}

        # Step 9: Plan tomorrow's enrichment budget
        try:
            from src.pipeline.enrichment_planner import plan_enrichment

            enrichment_plan = plan_enrichment()
            results["enrichment_plan"] = enrichment_plan
            steps_completed.append("enrichment_plan")
        except Exception as ep_error:
            import logging
            logging.getLogger(__name__).warning(
                "Enrichment planning failed (non-fatal): %s", ep_error
            )
            results["enrichment_plan"] = {"error": str(ep_error)}

        # Step 10: Compute and save dashboard snapshot
        try:
            from src.services.dashboard_service import (
                compute_dashboard_snapshot,
                save_dashboard_snapshot,
            )

            snapshot = compute_dashboard_snapshot()
            save_dashboard_snapshot(snapshot)
            results["dashboard_snapshot"] = {"computed": True}
            steps_completed.append("dashboard_snapshot")
        except Exception as ds_error:
            import logging
            logging.getLogger(__name__).warning(
                "Dashboard snapshot failed (non-fatal): %s", ds_error
            )
            results["dashboard_snapshot"] = {"error": str(ds_error)}

        # Optional: sync to cloud if Supabase is configured
        if settings.supabase_db_url:
            try:
                from src.sync.runner import run_sync

                sync_result = run_sync()
                results["sync"] = sync_result
                steps_completed.append("sync")

                # Update the pipeline run with sync step
                with get_session() as session:
                    run = session.get(PipelineRun, run_id)
                    if run:
                        run.steps_completed = steps_completed
                        run.step_results = results
                        session.add(run)
            except Exception as sync_error:
                import logging

                logging.getLogger(__name__).warning(
                    "Cloud sync failed (non-fatal): %s", sync_error
                )
                results["sync"] = {"error": str(sync_error)}

        # Send email digest (non-fatal) -- OAuth first, App Password fallback
        from src.integrations.email_digest import send_digest_email
        from src.integrations.gmail import is_gmail_configured, is_oauth_configured

        email_configured = is_oauth_configured() or is_gmail_configured()
        if email_configured:
            try:
                digest_result = send_digest_email(results)
                results["email_digest"] = digest_result
                if digest_result.get("sent"):
                    steps_completed.append("email_digest")
            except Exception as digest_error:
                import logging
                logging.getLogger(__name__).warning(
                    "Email digest failed (non-fatal): %s", digest_error
                )
                results["email_digest"] = {"error": str(digest_error)}

        # Send Telegram notification (non-fatal)
        from src.integrations.telegram import is_telegram_configured, send_pipeline_notification

        if is_telegram_configured():
            try:
                tg_ok = send_pipeline_notification(results)
                results["telegram"] = {"sent": tg_ok}
                if tg_ok:
                    steps_completed.append("telegram")
            except Exception as tg_error:
                import logging

                logging.getLogger(__name__).warning(
                    "Telegram notification failed (non-fatal): %s", tg_error
                )
                results["telegram"] = {"error": str(tg_error)}

    except Exception as e:
        error_message = str(e)
        error_step = steps_completed[-1] if steps_completed else "init"

        # Mark run as failed
        with get_session() as session:
            run = session.get(PipelineRun, run_id)
            if run:
                run.status = "failed"
                run.steps_completed = steps_completed
                run.step_results = results
                run.error_message = error_message
                run.error_step = error_step
                run.completed_at = datetime.utcnow()
                session.add(run)

        results["error"] = {"message": error_message, "step": error_step}

        # Send failure alert via Telegram (non-fatal)
        from src.integrations.telegram import is_telegram_configured, send_failure_notification

        if is_telegram_configured():
            try:
                send_failure_notification(error_step, error_message)
            except Exception:
                pass  # Don't mask the original error

    return results


def get_recent_pipeline_runs(limit: int = 10) -> list[PipelineRun]:
    """
    Get recent pipeline run history.

    Args:
        limit: Max runs to return

    Returns:
        List of PipelineRun records, most recent first
    """
    with get_session() as session:
        runs = session.exec(
            select(PipelineRun)
            .order_by(PipelineRun.started_at.desc())
            .limit(limit)
        ).all()

        # Detach from session
        result = []
        for run in runs:
            _ = run.id, run.status, run.step_results
            result.append(run)

        return result


def get_pipeline_stats() -> dict:
    """
    Get aggregate pipeline statistics.

    Returns:
        Dict with run counts, success rate, etc.
    """
    with get_session() as session:
        from sqlmodel import func

        total = session.exec(
            select(func.count(PipelineRun.id))
        ).one()

        completed = session.exec(
            select(func.count(PipelineRun.id))
            .where(PipelineRun.status == "completed")
        ).one()

        failed = session.exec(
            select(func.count(PipelineRun.id))
            .where(PipelineRun.status == "failed")
        ).one()

        # Get last run
        last_run = session.exec(
            select(PipelineRun)
            .order_by(PipelineRun.started_at.desc())
            .limit(1)
        ).first()

        return {
            "total_runs": total,
            "completed": completed,
            "failed": failed,
            "success_rate": (completed / total * 100) if total > 0 else 0,
            "last_run": last_run.started_at if last_run else None,
            "last_status": last_run.status if last_run else None,
        }


def _get_tier2_connections(limit: int = 20) -> list[Connection]:
    """
    Get top tier-2 connections for overflow enrichment when tier-1 budget remains.

    Args:
        limit: Max number to return

    Returns:
        List of tier-2 connections sorted by pre_score descending
    """
    with get_session() as session:
        connections = session.exec(
            select(Connection)
            .where(Connection.pre_score_tier == 2)
            .where(Connection.enriched_at.is_(None))
            .where(Connection.linkedin_url.isnot(None))
            .order_by(Connection.pre_score.desc())
            .limit(limit)
        ).all()

        result = []
        for conn in connections:
            _ = conn.id, conn.name, conn.pre_score
            result.append(conn)

        return result
