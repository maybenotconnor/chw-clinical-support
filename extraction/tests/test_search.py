"""Tests for Brain 1 search engine functionality."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from extraction.src.medgemma_synthesis import BrainOneSearch, SearchResult


# --- Fixtures ---

@pytest.fixture
def mock_db(tmp_path):
    """Create a minimal test database with chunks, FTS5, and high-risk terms."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))

    # Create schema
    conn.executescript("""
        CREATE TABLE documents (
            doc_id TEXT PRIMARY KEY,
            filename TEXT, title TEXT, version TEXT,
            extraction_date TEXT, approval_status TEXT, docling_json TEXT, page_count INTEGER
        );
        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY, doc_id TEXT, content TEXT,
            contextualized_text TEXT, chunk_type TEXT, page_number INTEGER, category TEXT
        );
        CREATE TABLE chunk_metadata (
            chunk_id TEXT PRIMARY KEY, headings_json TEXT, bbox_json TEXT, element_label TEXT
        );
        CREATE TABLE high_risk_terms (
            term_id INTEGER PRIMARY KEY AUTOINCREMENT,
            term TEXT NOT NULL UNIQUE, category TEXT, severity TEXT DEFAULT 'High'
        );
    """)

    # Insert test document
    conn.execute(
        "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("doc1", "test.pdf", "Test Guidelines", "1.0", "2024-01-01", "approved", None, 10)
    )

    # Insert test chunks covering clinical scenarios
    chunks = [
        ("c1", "doc1",
         "Malaria danger signs in children under 5: convulsions, inability to drink, severe vomiting, high fever above 39C. Refer immediately.",
         "", "text", 5, "content",
         '["Chapter 3", "Malaria", "Danger Signs"]'),
        ("c2", "doc1",
         "Treatment of uncomplicated malaria: Artemether-Lumefantrine (AL) is the first-line treatment. Dosage by weight.",
         "", "text", 6, "content",
         '["Chapter 3", "Malaria", "Treatment"]'),
        ("c3", "doc1",
         "Management of severe dehydration: Start IV fluids immediately. Ringer's Lactate or Normal Saline.",
         "", "text", 12, "content",
         '["Chapter 5", "Dehydration", "Management"]'),
        ("c4", "doc1",
         "Headache management: Paracetamol 500mg-1g every 4-6 hours. Maximum 4g per day.",
         "", "text", 20, "content",
         '["Chapter 8", "Neurological", "Headache"]'),
        ("c5", "doc1",
         "Table of Contents: Chapter 1 Introduction, Chapter 2 Emergencies, Chapter 3 Malaria",
         "", "text", 1, "metadata",
         '["Contents"]'),
    ]

    for c in chunks:
        conn.execute(
            "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?)",
            c[:7]
        )
        conn.execute(
            "INSERT INTO chunk_metadata VALUES (?, ?, NULL, NULL)",
            (c[0], c[7])
        )

    # Create and populate FTS5
    conn.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            chunk_id UNINDEXED, content, tokenize='porter unicode61'
        )
    """)
    conn.execute("""
        INSERT INTO chunks_fts(chunk_id, content)
        SELECT chunk_id, content FROM chunks
    """)

    # Insert high-risk terms
    terms = [
        ("convulsions", "Neurological", "High"),
        ("severe dehydration", "Dehydration", "High"),
        ("refer immediately", "Referral", "High"),
        ("headache", "Neurological", "Medium"),
    ]
    conn.executemany(
        "INSERT INTO high_risk_terms (term, category, severity) VALUES (?, ?, ?)",
        terms
    )
    conn.commit()
    conn.close()

    return str(db_path)


# --- Search Tests ---

@patch("extraction.src.medgemma_synthesis.HAS_EMBEDDER", False)
@patch("extraction.src.medgemma_synthesis.HAS_SQLITE_VEC", False)
class TestKeywordSearch:
    """Test keyword (BM25) search functionality."""

    def test_returns_results_for_known_query(self, mock_db):
        brain1 = BrainOneSearch(db_path=mock_db)
        results = brain1.search_keyword("malaria danger signs", k=5)
        assert len(results) > 0
        brain1.close()

    def test_malaria_query_finds_malaria_chunk(self, mock_db):
        brain1 = BrainOneSearch(db_path=mock_db)
        results = brain1.search_keyword("malaria", k=5)
        contents = [r.content for r in results]
        assert any("malaria" in c.lower() for c in contents)
        brain1.close()

    def test_dehydration_query_finds_dehydration_chunk(self, mock_db):
        brain1 = BrainOneSearch(db_path=mock_db)
        results = brain1.search_keyword("severe dehydration treatment", k=5)
        contents = [r.content for r in results]
        assert any("dehydration" in c.lower() for c in contents)
        brain1.close()

    def test_empty_query_returns_empty(self, mock_db):
        brain1 = BrainOneSearch(db_path=mock_db)
        results = brain1.search_keyword("", k=5)
        assert len(results) == 0
        brain1.close()

    def test_results_have_headings(self, mock_db):
        brain1 = BrainOneSearch(db_path=mock_db)
        results = brain1.search_keyword("malaria", k=5)
        assert len(results) > 0
        assert len(results[0].headings) > 0
        brain1.close()


# --- High-Risk Detection Tests ---

@patch("extraction.src.medgemma_synthesis.HAS_EMBEDDER", False)
@patch("extraction.src.medgemma_synthesis.HAS_SQLITE_VEC", False)
class TestHighRiskDetection:
    """Test high-risk term detection."""

    def test_detects_convulsions(self, mock_db):
        brain1 = BrainOneSearch(db_path=mock_db)
        results = [SearchResult(
            chunk_id="c1", content="Patient has convulsions and high fever",
            headings=[], page_number=1, score=1.0, source="keyword"
        )]
        alerts = brain1.detect_high_risk(results)
        terms = [a.term for a in alerts]
        assert "convulsions" in terms
        brain1.close()

    def test_does_not_fire_on_benign_content(self, mock_db):
        brain1 = BrainOneSearch(db_path=mock_db)
        results = [SearchResult(
            chunk_id="c1", content="The patient reported mild cough for two days",
            headings=[], page_number=1, score=1.0, source="keyword"
        )]
        alerts = brain1.detect_high_risk(results)
        high_alerts = [a for a in alerts if a.severity == "High"]
        assert len(high_alerts) == 0
        brain1.close()

    def test_high_severity_sorted_first(self, mock_db):
        brain1 = BrainOneSearch(db_path=mock_db)
        results = [SearchResult(
            chunk_id="c1",
            content="Headache with convulsions requires refer immediately",
            headings=[], page_number=1, score=1.0, source="keyword"
        )]
        alerts = brain1.detect_high_risk(results)
        if len(alerts) >= 2:
            assert alerts[0].severity == "High"
        brain1.close()

    def test_no_duplicate_alerts(self, mock_db):
        brain1 = BrainOneSearch(db_path=mock_db)
        results = [
            SearchResult(chunk_id="c1", content="convulsions noted",
                         headings=[], page_number=1, score=1.0, source="keyword"),
            SearchResult(chunk_id="c2", content="convulsions again",
                         headings=[], page_number=2, score=0.9, source="keyword"),
        ]
        alerts = brain1.detect_high_risk(results)
        terms = [a.term for a in alerts]
        assert terms.count("convulsions") == 1
        brain1.close()
