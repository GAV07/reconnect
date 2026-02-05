#!/usr/bin/env python3
"""CLI script to import LinkedIn CSV into Reconnect."""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.database.engine import init_db
from src.ingestion.csv_import import import_linkedin_csv


def main():
    """Import LinkedIn CSV file."""
    parser = argparse.ArgumentParser(description="Import LinkedIn connections CSV")
    parser.add_argument("csv_file", type=Path, help="Path to LinkedIn export CSV file")
    args = parser.parse_args()

    if not args.csv_file.exists():
        print(f"Error: File not found: {args.csv_file}")
        sys.exit(1)

    # Initialize database first
    print("Initializing database...")
    init_db()

    print(f"Importing from {args.csv_file}...")
    result = import_linkedin_csv(args.csv_file)

    print(f"\nImport complete:")
    print(f"  Total rows: {result.total_rows}")
    print(f"  Imported: {result.imported}")
    print(f"  Updated: {result.updated}")
    print(f"  Skipped: {result.skipped}")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for error in result.errors[:10]:  # Show first 10
            print(f"  - {error}")
        if len(result.errors) > 10:
            print(f"  ... and {len(result.errors) - 10} more")


if __name__ == "__main__":
    main()
