#!/usr/bin/env python3
"""
Update existing guidelines.db for Phase 2 features.

Adds:
- FTS5 full-text search table (chunks_fts)
- High-risk terms data

Run this after Phase 1 pipeline has generated the database.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import GuidelineDatabase


def update_database(db_path: str):
    """Update database with Phase 2 features."""
    print(f"Opening database: {db_path}")
    db = GuidelineDatabase(db_path)

    # Check current state
    chunk_count = db.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"Found {chunk_count} chunks in database")

    # Create FTS5 table if needed
    print("Creating FTS5 table...")
    db.conn.execute(db.FTS5_TABLE_SQL)
    db.conn.commit()

    # Populate FTS5
    print("Populating FTS5 from chunks...")
    db.populate_fts5()
    fts_count = db.conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    print(f"FTS5 table now has {fts_count} rows")

    # Populate high-risk terms
    print("Populating high-risk terms...")
    db.populate_high_risk_terms()
    term_count = db.conn.execute("SELECT COUNT(*) FROM high_risk_terms").fetchone()[0]
    print(f"High-risk terms table now has {term_count} terms")

    # Test FTS5 search
    print("\nTesting FTS5 search for 'malaria'...")
    results = db.search_keyword("malaria", k=3)
    for i, r in enumerate(results, 1):
        print(f"  {i}. [Page {r.page_number}] {r.content[:80]}...")

    # Show some high-risk terms
    print("\nSample high-risk terms:")
    terms = db.get_high_risk_terms()[:5]
    for term, category, severity in terms:
        print(f"  - {term} ({category}, {severity})")

    db.close()
    print(f"\nDatabase updated successfully: {db_path}")


if __name__ == "__main__":
    # Default paths
    data_db = Path(__file__).parent.parent.parent / "data" / "databases" / "guidelines.db"
    android_db = Path(__file__).parent.parent.parent / "android" / "app" / "src" / "main" / "assets" / "databases" / "guidelines.db"

    # Update both copies if they exist
    for db_path in [data_db, android_db]:
        if db_path.exists():
            print(f"\n{'='*60}")
            update_database(str(db_path))
        else:
            print(f"Database not found: {db_path}")
