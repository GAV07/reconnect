#!/usr/bin/env python3
"""Initialize the Reconnect database."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reconnect.database.engine import init_db


def main():
    """Initialize the database and create all tables."""
    print("Initializing database...")
    init_db()
    print("Database initialized successfully!")


if __name__ == "__main__":
    main()
