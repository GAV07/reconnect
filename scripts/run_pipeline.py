#!/usr/bin/env python
"""CLI script to run the Reconnect daily pipeline.

Usage:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --dump ~/Downloads/linkedin-export.zip
    python scripts/run_pipeline.py --skip-enrich --skip-queue
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.engine import init_db
from src.pipeline.daily_pipeline import run_daily_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Run the Reconnect daily pipeline"
    )

    parser.add_argument(
        "--dump", "-d",
        type=Path,
        help="Path to LinkedIn data export ZIP file",
    )

    parser.add_argument(
        "--user-name", "-u",
        type=str,
        help="Your name (for message direction detection)",
    )

    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help="Skip Apify enrichment step",
    )

    parser.add_argument(
        "--skip-queue",
        action="store_true",
        help="Skip queue generation step",
    )

    parser.add_argument(
        "--enrich-budget", "-e",
        type=int,
        help="Max contacts to enrich (default: from settings)",
    )

    parser.add_argument(
        "--queue-size", "-q",
        type=int,
        help="Max queue items to generate (default: from settings)",
    )

    args = parser.parse_args()

    # Validate dump path if provided
    if args.dump and not args.dump.exists():
        print(f"Error: LinkedIn dump not found: {args.dump}")
        sys.exit(1)

    # Initialize database
    print("Initializing database...")
    init_db()

    # Run pipeline
    print("\nRunning pipeline...")
    print("-" * 40)

    results = run_daily_pipeline(
        linkedin_dump_path=args.dump,
        user_name=args.user_name,
        skip_enrichment=args.skip_enrich,
        skip_queue_generation=args.skip_queue,
        enrich_budget=args.enrich_budget,
        queue_size=args.queue_size,
    )

    # Print results
    print("\nPipeline Results:")
    print("-" * 40)

    if "import" in results:
        imp = results["import"]
        print(f"\n[Import]")
        print(f"  Imported: {imp.get('imported', 0)} new contacts")
        print(f"  Updated: {imp.get('updated', 0)} existing contacts")
        print(f"  Messages processed: {imp.get('messages_processed', 0)}")
        print(f"  Conversations summarized: {imp.get('conversations_summarized', 0)}")

    if "prescore" in results:
        ps = results["prescore"]
        print(f"\n[Pre-scoring]")
        print(f"  Scored: {ps.get('scored', 0)} contacts")
        print(f"  Tier 1 (enrich): {ps.get('tier1', 0)}")
        print(f"  Tier 2 (maybe): {ps.get('tier2', 0)}")
        print(f"  Tier 3 (skip): {ps.get('tier3', 0)}")

    if "enrich" in results:
        en = results["enrich"]
        print(f"\n[Enrichment]")
        print(f"  Success: {en.get('success', 0)}")
        print(f"  Failed: {en.get('failed', 0)}")
        if en.get("errors"):
            print(f"  Errors:")
            for err in en["errors"][:5]:
                print(f"    - {err}")

    if "score" in results:
        sc = results["score"]
        print(f"\n[Full Scoring]")
        print(f"  Scored: {sc.get('scored', 0)}")
        print(f"  Failed: {sc.get('failed', 0)}")

    if "queue" in results:
        q = results["queue"]
        print(f"\n[Queue Generation]")
        print(f"  Added: {q.get('added', 0)}")
        print(f"  Excluded: {q.get('excluded', 0)}")
        if q.get("exclusion_reasons"):
            print(f"  Exclusion reasons:")
            for reason, count in q["exclusion_reasons"].items():
                print(f"    - {reason}: {count}")

    if "error" in results:
        err = results["error"]
        print(f"\n[ERROR]")
        print(f"  Step: {err.get('step', 'unknown')}")
        print(f"  Message: {err.get('message', 'Unknown error')}")
        sys.exit(1)

    print("\n" + "-" * 40)
    print("Pipeline completed successfully!")


if __name__ == "__main__":
    main()
