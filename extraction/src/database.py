"""
SQLite database operations with sqlite-vec for vector storage.

This module manages the clinical guidelines database schema and provides
CRUD operations for documents, chunks, and embeddings.
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import sqlite_vec


@dataclass
class DocumentMetadata:
    """Metadata for an extracted document."""
    filename: str
    title: str
    version: Optional[str] = None
    extraction_date: str = field(default_factory=lambda: datetime.now().isoformat())
    page_count: int = 0


@dataclass
class DocumentRecord:
    """Full document record from database."""
    doc_id: str
    filename: str
    title: str
    version: Optional[str]
    extraction_date: str
    approval_status: str
    docling_json: Optional[str]
    page_count: int = 0


# Chunk categories for filtering/ranking
CHUNK_CATEGORY_CONTENT = "content"      # Clinical guidelines, treatments, symptoms
CHUNK_CATEGORY_METADATA = "metadata"    # TOC, abbreviations, foreword, credits

# Headings that indicate metadata sections (case-insensitive matching)
METADATA_HEADING_PATTERNS = [
    "contents",
    "table of contents",
    "abbreviations",
    "acronyms",
    "foreword",
    "preface",
    "acknowledgements",
    "acknowledgments",
    "credits",
    "contributors",
    "editorial",
    "index",
    "glossary",
    "references",
    "bibliography",
]


@dataclass
class ChunkData:
    """Data for a document chunk."""
    chunk_id: str
    content: str
    contextualized_text: str
    chunk_type: str
    page_number: Optional[int]
    headings: List[str] = field(default_factory=list)
    bbox: Optional[dict] = None
    element_label: str = ""
    category: str = CHUNK_CATEGORY_CONTENT  # 'content' or 'metadata'


@dataclass
class SearchResult:
    """Result from vector similarity search."""
    chunk_id: str
    doc_id: str
    content: str
    page_number: Optional[int]
    distance: float
    headings: List[str] = field(default_factory=list)
    category: str = CHUNK_CATEGORY_CONTENT


class GuidelineDatabase:
    """SQLite database operations for clinical guidelines with sqlite-vec."""

    SCHEMA_SQL = """
    -- Document tracking
    CREATE TABLE IF NOT EXISTS documents (
        doc_id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        title TEXT,
        version TEXT,
        extraction_date TEXT NOT NULL,
        approval_status TEXT DEFAULT 'pending',
        docling_json TEXT,
        page_count INTEGER DEFAULT 0
    );

    -- Core content
    CREATE TABLE IF NOT EXISTS chunks (
        chunk_id TEXT PRIMARY KEY,
        doc_id TEXT NOT NULL,
        content TEXT NOT NULL,
        contextualized_text TEXT NOT NULL,
        chunk_type TEXT NOT NULL,
        page_number INTEGER,
        category TEXT DEFAULT 'content',
        FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
    );

    -- Index for filtering by category (enables efficient content-only searches)
    CREATE INDEX IF NOT EXISTS idx_chunks_category ON chunks(category);

    -- Chunk metadata (separate table for flexibility)
    CREATE TABLE IF NOT EXISTS chunk_metadata (
        chunk_id TEXT PRIMARY KEY,
        headings_json TEXT,
        bbox_json TEXT,
        element_label TEXT,
        FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
    );

    -- High-risk term detection (Phase 2 but schema created now)
    CREATE TABLE IF NOT EXISTS high_risk_terms (
        term_id INTEGER PRIMARY KEY AUTOINCREMENT,
        term TEXT NOT NULL UNIQUE,
        category TEXT,
        severity TEXT DEFAULT 'High'
    );

    -- Create indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
    CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(approval_status);
    """

    EMBEDDINGS_TABLE_SQL = """
    CREATE VIRTUAL TABLE IF NOT EXISTS embeddings USING vec0(
        chunk_id TEXT PRIMARY KEY,
        embedding float[384]
    );
    """

    FTS5_TABLE_SQL = """
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        chunk_id UNINDEXED,
        content,
        tokenize='porter unicode61'
    );
    """

    # Clinically-curated high-risk terms for Phase 2
    HIGH_RISK_TERMS = [
        # General danger signs
        ("danger sign", "General", "High"),
        ("danger signs", "General", "High"),
        ("life-threatening", "General", "High"),
        ("life threatening", "General", "High"),
        ("severe", "General", "Medium"),
        # Referral indicators
        ("refer immediately", "Referral", "High"),
        ("emergency referral", "Referral", "High"),
        ("refer to health facility", "Referral", "Medium"),
        ("refer to hospital", "Referral", "High"),
        ("urgent referral", "Referral", "High"),
        # Neurological
        ("convulsions", "Neurological", "High"),
        ("convulsion", "Neurological", "High"),
        ("unconscious", "Neurological", "High"),
        ("loss of consciousness", "Neurological", "High"),
        ("severe headache", "Neurological", "Medium"),
        ("altered consciousness", "Neurological", "High"),
        ("coma", "Neurological", "High"),
        # Pediatric
        ("not able to drink", "Pediatric", "High"),
        ("unable to drink", "Pediatric", "High"),
        ("not able to breastfeed", "Pediatric", "High"),
        ("unable to breastfeed", "Pediatric", "High"),
        ("severe malnutrition", "Pediatric", "High"),
        # Respiratory
        ("severe pneumonia", "Respiratory", "High"),
        ("chest indrawing", "Respiratory", "High"),
        ("difficulty breathing", "Respiratory", "High"),
        ("respiratory distress", "Respiratory", "High"),
        ("stridor", "Respiratory", "High"),
        # Maternal
        ("vaginal bleeding", "Maternal", "High"),
        ("fits in pregnancy", "Maternal", "High"),
        ("severe headache in pregnancy", "Maternal", "High"),
        ("blurred vision in pregnancy", "Maternal", "High"),
        ("eclampsia", "Maternal", "High"),
        ("pre-eclampsia", "Maternal", "High"),
        ("postpartum hemorrhage", "Maternal", "High"),
        # Dehydration
        ("severe dehydration", "Dehydration", "High"),
        ("signs of dehydration", "Dehydration", "Medium"),
        # Hematologic
        ("severe anaemia", "Hematologic", "High"),
        ("severe anemia", "Hematologic", "High"),
        # Gastrointestinal
        ("persistent vomiting", "Gastrointestinal", "High"),
        ("bloody diarrhoea", "Gastrointestinal", "High"),
        ("bloody diarrhea", "Gastrointestinal", "High"),
        # Additional pediatric
        ("not able to eat", "Pediatric", "High"),
        ("high fever", "General", "Medium"),
        # Scope limitations
        ("do not treat", "Scope", "High"),
        ("beyond scope", "Scope", "Medium"),
        ("requires specialist", "Scope", "Medium"),
    ]

    def __init__(self, db_path: str):
        """Initialize database connection with sqlite-vec.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._load_sqlite_vec()

    def _load_sqlite_vec(self):
        """Load the sqlite-vec extension."""
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)

    def create_schema(self):
        """Create all tables and virtual tables."""
        self.conn.executescript(self.SCHEMA_SQL)
        self.conn.execute(self.EMBEDDINGS_TABLE_SQL)
        self.conn.execute(self.FTS5_TABLE_SQL)
        self.conn.commit()

    def populate_fts5(self):
        """Populate FTS5 table from existing chunks.

        Call this after all chunks have been inserted to enable keyword search.
        """
        # Clear existing FTS5 data
        self.conn.execute("DELETE FROM chunks_fts")
        # Populate from chunks table
        self.conn.execute("""
            INSERT INTO chunks_fts(chunk_id, content)
            SELECT chunk_id, content FROM chunks
        """)
        self.conn.commit()

    def populate_high_risk_terms(self):
        """Populate high_risk_terms table with curated danger signs.

        Call this once during database setup.
        """
        # Clear existing terms
        self.conn.execute("DELETE FROM high_risk_terms")
        # Insert curated terms
        self.conn.executemany(
            "INSERT INTO high_risk_terms (term, category, severity) VALUES (?, ?, ?)",
            self.HIGH_RISK_TERMS
        )
        self.conn.commit()

    def get_high_risk_terms(self) -> List[tuple]:
        """Get all high-risk terms from database.

        Returns:
            List of (term, category, severity) tuples
        """
        rows = self.conn.execute(
            "SELECT term, category, severity FROM high_risk_terms"
        ).fetchall()
        return [(row['term'], row['category'], row['severity']) for row in rows]

    def insert_document(
        self,
        metadata: DocumentMetadata,
        docling_json: Optional[str] = None
    ) -> str:
        """Insert a new document record.

        Args:
            metadata: Document metadata
            docling_json: Optional serialized Docling output

        Returns:
            Generated document ID
        """
        doc_id = str(uuid.uuid4())
        self.conn.execute(
            """
            INSERT INTO documents (
                doc_id, filename, title, version,
                extraction_date, approval_status, docling_json, page_count
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                doc_id,
                metadata.filename,
                metadata.title,
                metadata.version,
                metadata.extraction_date,
                docling_json,
                metadata.page_count
            )
        )
        self.conn.commit()
        return doc_id

    def insert_chunk(self, doc_id: str, chunk: ChunkData):
        """Insert a chunk and its metadata.

        Args:
            doc_id: Parent document ID
            chunk: Chunk data to insert
        """
        # Insert main chunk record
        self.conn.execute(
            """
            INSERT INTO chunks (
                chunk_id, doc_id, content, contextualized_text,
                chunk_type, page_number, category
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk.chunk_id,
                doc_id,
                chunk.content,
                chunk.contextualized_text,
                chunk.chunk_type,
                chunk.page_number,
                chunk.category
            )
        )

        # Insert metadata
        self.conn.execute(
            """
            INSERT INTO chunk_metadata (
                chunk_id, headings_json, bbox_json, element_label
            ) VALUES (?, ?, ?, ?)
            """,
            (
                chunk.chunk_id,
                json.dumps(chunk.headings),
                json.dumps(chunk.bbox) if chunk.bbox else None,
                chunk.element_label
            )
        )
        self.conn.commit()

    def insert_embedding(self, chunk_id: str, embedding: List[float]):
        """Insert embedding into vec0 virtual table.

        Args:
            chunk_id: Associated chunk ID
            embedding: 384-dimensional float vector
        """
        # sqlite-vec accepts JSON array format
        embedding_json = json.dumps(embedding)
        self.conn.execute(
            "INSERT INTO embeddings(chunk_id, embedding) VALUES (?, ?)",
            (chunk_id, embedding_json)
        )
        self.conn.commit()

    def insert_embeddings_batch(self, embeddings: List[tuple]):
        """Insert multiple embeddings efficiently.

        Args:
            embeddings: List of (chunk_id, embedding_list) tuples
        """
        for chunk_id, embedding in embeddings:
            embedding_json = json.dumps(embedding)
            self.conn.execute(
                "INSERT INTO embeddings(chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, embedding_json)
            )
        self.conn.commit()

    def update_approval_status(self, doc_id: str, status: str):
        """Update document approval status.

        Args:
            doc_id: Document ID
            status: New status ('pending', 'approved', 'rejected')
        """
        self.conn.execute(
            "UPDATE documents SET approval_status = ? WHERE doc_id = ?",
            (status, doc_id)
        )
        self.conn.commit()

    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        """Retrieve a document by ID.

        Args:
            doc_id: Document ID

        Returns:
            DocumentRecord or None if not found
        """
        row = self.conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?",
            (doc_id,)
        ).fetchone()

        if row is None:
            return None

        return DocumentRecord(
            doc_id=row['doc_id'],
            filename=row['filename'],
            title=row['title'],
            version=row['version'],
            extraction_date=row['extraction_date'],
            approval_status=row['approval_status'],
            docling_json=row['docling_json'],
            page_count=row['page_count']
        )

    def get_documents_by_status(self, status: str = None) -> List[DocumentRecord]:
        """Get documents filtered by approval status.

        Args:
            status: Filter by status, or None for all

        Returns:
            List of DocumentRecord objects
        """
        if status and status != 'all':
            rows = self.conn.execute(
                "SELECT * FROM documents WHERE approval_status = ? ORDER BY extraction_date DESC",
                (status,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM documents ORDER BY extraction_date DESC"
            ).fetchall()

        return [
            DocumentRecord(
                doc_id=row['doc_id'],
                filename=row['filename'],
                title=row['title'],
                version=row['version'],
                extraction_date=row['extraction_date'],
                approval_status=row['approval_status'],
                docling_json=row['docling_json'],
                page_count=row['page_count']
            )
            for row in rows
        ]

    def get_chunks(self, doc_id: str, category: Optional[str] = None) -> List[ChunkData]:
        """Get all chunks for a document.

        Args:
            doc_id: Document ID
            category: Optional filter by category ('content' or 'metadata')

        Returns:
            List of ChunkData objects
        """
        if category:
            rows = self.conn.execute(
                """
                SELECT c.*, m.headings_json, m.bbox_json, m.element_label
                FROM chunks c
                LEFT JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
                WHERE c.doc_id = ? AND c.category = ?
                ORDER BY c.page_number, c.chunk_id
                """,
                (doc_id, category)
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT c.*, m.headings_json, m.bbox_json, m.element_label
                FROM chunks c
                LEFT JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
                WHERE c.doc_id = ?
                ORDER BY c.page_number, c.chunk_id
                """,
                (doc_id,)
            ).fetchall()

        return [
            ChunkData(
                chunk_id=row['chunk_id'],
                content=row['content'],
                contextualized_text=row['contextualized_text'],
                chunk_type=row['chunk_type'],
                page_number=row['page_number'],
                headings=json.loads(row['headings_json']) if row['headings_json'] else [],
                bbox=json.loads(row['bbox_json']) if row['bbox_json'] else None,
                element_label=row['element_label'] or "",
                category=row['category'] or CHUNK_CATEGORY_CONTENT
            )
            for row in rows
        ]

    def get_chunk_count(self, doc_id: str) -> int:
        """Get count of chunks for a document.

        Args:
            doc_id: Document ID

        Returns:
            Number of chunks
        """
        result = self.conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE doc_id = ?",
            (doc_id,)
        ).fetchone()
        return result[0]

    def search_similar(
        self,
        query_embedding: List[float],
        k: int = 10,
        content_only: bool = True
    ) -> List[SearchResult]:
        """Vector similarity search using sqlite-vec.

        Args:
            query_embedding: 384-dimensional query vector
            k: Number of results to return
            content_only: If True, exclude metadata chunks (TOC, abbreviations, etc.)

        Returns:
            List of SearchResult objects ordered by similarity
        """
        embedding_json = json.dumps(query_embedding)

        # Note: sqlite-vec doesn't support WHERE clauses in the MATCH query,
        # so we fetch more results and filter in Python if content_only is True
        fetch_k = k * 3 if content_only else k

        rows = self.conn.execute(
            """
            SELECT
                e.chunk_id,
                e.distance,
                c.doc_id,
                c.content,
                c.page_number,
                c.category,
                m.headings_json
            FROM embeddings e
            INNER JOIN chunks c ON c.chunk_id = e.chunk_id
            LEFT JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
            WHERE e.embedding MATCH ?
                AND k = ?
            ORDER BY e.distance
            """,
            (embedding_json, fetch_k)
        ).fetchall()

        results = []
        for row in rows:
            category = row['category'] or CHUNK_CATEGORY_CONTENT
            # Filter out metadata if content_only
            if content_only and category == CHUNK_CATEGORY_METADATA:
                continue
            results.append(SearchResult(
                chunk_id=row['chunk_id'],
                doc_id=row['doc_id'],
                content=row['content'],
                page_number=row['page_number'],
                distance=row['distance'],
                headings=json.loads(row['headings_json']) if row['headings_json'] else [],
                category=category
            ))
            if len(results) >= k:
                break

        return results

    def search_keyword(
        self,
        query: str,
        k: int = 10,
        content_only: bool = True
    ) -> List[SearchResult]:
        """Keyword/BM25 search using FTS5.

        Args:
            query: Search query text
            k: Number of results to return
            content_only: If True, exclude metadata chunks (TOC, abbreviations, etc.)

        Returns:
            List of SearchResult objects ordered by BM25 relevance
        """
        # Escape special FTS5 characters and format query
        # FTS5 uses quotes for phrase search, we use OR for term matching
        terms = query.strip().split()
        if not terms:
            return []

        # Join terms with OR for broader matching
        fts_query = " OR ".join(f'"{term}"' for term in terms)

        # Use category filter in SQL for FTS5 (unlike vec0, FTS5 supports JOINs with WHERE)
        if content_only:
            rows = self.conn.execute(
                """
                SELECT
                    c.chunk_id,
                    c.doc_id,
                    c.content,
                    c.page_number,
                    c.category,
                    m.headings_json,
                    bm25(chunks_fts) as bm25_score
                FROM chunks_fts fts
                JOIN chunks c ON fts.chunk_id = c.chunk_id
                LEFT JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
                WHERE chunks_fts MATCH ?
                    AND c.category = 'content'
                ORDER BY bm25(chunks_fts)
                LIMIT ?
                """,
                (fts_query, k)
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT
                    c.chunk_id,
                    c.doc_id,
                    c.content,
                    c.page_number,
                    c.category,
                    m.headings_json,
                    bm25(chunks_fts) as bm25_score
                FROM chunks_fts fts
                JOIN chunks c ON fts.chunk_id = c.chunk_id
                LEFT JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
                WHERE chunks_fts MATCH ?
                ORDER BY bm25(chunks_fts)
                LIMIT ?
                """,
                (fts_query, k)
            ).fetchall()

        return [
            SearchResult(
                chunk_id=row['chunk_id'],
                doc_id=row['doc_id'],
                content=row['content'],
                page_number=row['page_number'],
                distance=abs(row['bm25_score']),  # BM25 returns negative scores
                headings=json.loads(row['headings_json']) if row['headings_json'] else [],
                category=row['category'] or CHUNK_CATEGORY_CONTENT
            )
            for row in rows
        ]

    def close(self):
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
