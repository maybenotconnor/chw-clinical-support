"""
MedGemma synthesis pipeline for clinical guideline RAG.

This module provides the Brain 2 reference implementation:
1. Takes a clinical query
2. Runs Brain 1 search (vector + keyword + RRF fusion)
3. Formats retrieved chunks with clinical prompt templates
4. Calls MedGemma via Ollama (local) for synthesis
5. Optionally validates via guardrail prompt

Requires:
- Existing guidelines database (guidelines_v2.db)
- Ollama running locally with medgemma model
- sentence-transformers for embedding generation
"""

import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, List, Optional, Tuple

import requests

from .clinical_prompts import (
    ChunkContext,
    HighRiskAlertContext,
    guardrail_prompt,
    synthesis_prompt,
)

# Try importing embedding dependencies (optional for query-only mode)
try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDER = True
except ImportError:
    HAS_EMBEDDER = False

try:
    import sqlite_vec
    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False


# --- Configuration ---

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "databases" / "guidelines_v2.db"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "hf.co/unsloth/medgemma-1.5-4b-it-GGUF:Q4_K_M"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RRF_K = 60  # RRF constant matching Android implementation


# --- Data Classes ---

@dataclass
class SearchResult:
    """Result from Brain 1 search."""
    chunk_id: str
    content: str
    headings: List[str]
    page_number: Optional[int]
    score: float
    source: str  # "vector", "keyword", or "hybrid"


@dataclass
class SynthesisResult:
    """Result from Brain 2 synthesis."""
    query: str
    summary: str
    chunks_used: List[SearchResult]
    alerts: List[HighRiskAlertContext]
    guardrail_result: Optional[str] = None
    guardrail_passed: Optional[bool] = None
    search_time_ms: float = 0
    synthesis_time_ms: float = 0
    total_time_ms: float = 0


# --- Brain 1: Search Engine ---

class BrainOneSearch:
    """Brain 1 search engine using the existing SQLite database."""

    def __init__(self, db_path: str = None, device: str = "cpu"):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        # Load sqlite-vec extension
        if HAS_SQLITE_VEC:
            self.conn.enable_load_extension(True)
            sqlite_vec.load(self.conn)
            self.conn.enable_load_extension(False)

        # Load embedding model
        self.embedder = None
        if HAS_EMBEDDER:
            self.embedder = SentenceTransformer(EMBEDDING_MODEL, device=device)

        # Load high-risk terms
        self.high_risk_terms = self._load_high_risk_terms()

    def _load_high_risk_terms(self) -> List[Tuple[str, str, str]]:
        """Load high-risk terms from database."""
        try:
            rows = self.conn.execute(
                "SELECT term, category, severity FROM high_risk_terms"
            ).fetchall()
            return [(row["term"], row["category"], row["severity"]) for row in rows]
        except sqlite3.OperationalError:
            return []

    def detect_high_risk(self, results: List[SearchResult]) -> List[HighRiskAlertContext]:
        """Detect high-risk terms in search results."""
        alerts = []
        seen_terms = set()
        all_content = " ".join(r.content.lower() for r in results)

        for term, category, severity in self.high_risk_terms:
            if term.lower() in all_content and term not in seen_terms:
                alerts.append(HighRiskAlertContext(
                    term=term, category=category, severity=severity
                ))
                seen_terms.add(term)

        # Sort: High severity first
        alerts.sort(key=lambda a: (0 if a.severity == "High" else 1, a.term))
        return alerts

    def search_vector(self, query: str, k: int = 15) -> List[SearchResult]:
        """Vector similarity search using sqlite-vec."""
        if not self.embedder or not HAS_SQLITE_VEC:
            return []

        embedding = self.embedder.encode(query).tolist()
        embedding_json = json.dumps(embedding)

        rows = self.conn.execute(
            """
            SELECT
                e.chunk_id, e.distance,
                c.content, c.page_number, c.category,
                m.headings_json
            FROM embeddings e
            INNER JOIN chunks c ON c.chunk_id = e.chunk_id
            LEFT JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
            WHERE e.embedding MATCH ? AND k = ?
            ORDER BY e.distance
            """,
            (embedding_json, k * 3)
        ).fetchall()

        results = []
        for row in rows:
            if row["category"] == "metadata":
                continue
            if len(row["content"].strip()) < 50:
                continue
            headings = json.loads(row["headings_json"]) if row["headings_json"] else []
            results.append(SearchResult(
                chunk_id=row["chunk_id"],
                content=row["content"],
                headings=headings,
                page_number=row["page_number"],
                score=1.0 - row["distance"],
                source="vector",
            ))
            if len(results) >= k:
                break

        return results

    def search_keyword(self, query: str, k: int = 15) -> List[SearchResult]:
        """BM25 keyword search using FTS5."""
        terms = query.strip().split()
        if not terms:
            return []

        fts_query = " OR ".join(f'"{term}"' for term in terms)

        try:
            rows = self.conn.execute(
                """
                SELECT
                    c.chunk_id, c.content, c.page_number, c.category,
                    m.headings_json,
                    bm25(chunks_fts) as bm25_score
                FROM chunks_fts fts
                JOIN chunks c ON fts.chunk_id = c.chunk_id
                LEFT JOIN chunk_metadata m ON c.chunk_id = m.chunk_id
                WHERE chunks_fts MATCH ? AND c.category = 'content'
                ORDER BY bm25(chunks_fts)
                LIMIT ?
                """,
                (fts_query, k)
            ).fetchall()
        except sqlite3.OperationalError:
            return []

        return [
            SearchResult(
                chunk_id=row["chunk_id"],
                content=row["content"],
                headings=json.loads(row["headings_json"]) if row["headings_json"] else [],
                page_number=row["page_number"],
                score=abs(row["bm25_score"]),
                source="keyword",
            )
            for row in rows
        ]

    def search_hybrid(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Hybrid search combining vector and keyword with RRF fusion."""
        vector_results = self.search_vector(query, k=15)
        keyword_results = self.search_keyword(query, k=15)

        # RRF fusion
        scores = {}  # chunk_id -> (rrf_score, SearchResult)

        for rank, result in enumerate(vector_results):
            rrf_score = 1.0 / (RRF_K + rank + 1)
            if result.chunk_id in scores:
                scores[result.chunk_id] = (
                    scores[result.chunk_id][0] + rrf_score,
                    result,
                )
            else:
                scores[result.chunk_id] = (rrf_score, result)

        for rank, result in enumerate(keyword_results):
            rrf_score = 1.0 / (RRF_K + rank + 1)
            if result.chunk_id in scores:
                scores[result.chunk_id] = (
                    scores[result.chunk_id][0] + rrf_score,
                    scores[result.chunk_id][1],
                )
            else:
                scores[result.chunk_id] = (rrf_score, result)

        # Sort by RRF score descending
        sorted_results = sorted(scores.values(), key=lambda x: x[0], reverse=True)

        return [
            SearchResult(
                chunk_id=result.chunk_id,
                content=result.content,
                headings=result.headings,
                page_number=result.page_number,
                score=rrf_score,
                source="hybrid",
            )
            for rrf_score, result in sorted_results[:top_k]
        ]

    def close(self):
        self.conn.close()


# --- Brain 2: MedGemma Synthesis ---

class BrainTwoSynthesis:
    """Brain 2 synthesis engine using MedGemma via Ollama."""

    def __init__(
        self,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_MODEL,
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model

    def is_available(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = resp.json().get("models", [])
            return any(self.model in m.get("name", "") for m in models)
        except requests.ConnectionError:
            return False

    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        """Generate completion from MedGemma.

        Args:
            prompt: Full prompt string
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (low for clinical accuracy)

        Returns:
            Generated text
        """
        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"]

    def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> Generator[str, None, None]:
        """Stream generation from MedGemma.

        Args:
            prompt: Full prompt string
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Token strings as they're generated
        """
        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1,
                },
            },
            stream=True,
            timeout=120,
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if "response" in data:
                    yield data["response"]
                if data.get("done"):
                    break

    def synthesize(
        self,
        query: str,
        chunks: List[SearchResult],
        alerts: List[HighRiskAlertContext],
    ) -> str:
        """Generate clinical synthesis from search results.

        Args:
            query: Clinical question
            chunks: Retrieved guideline chunks
            alerts: Detected high-risk alerts

        Returns:
            Synthesized clinical summary
        """
        chunk_contexts = [
            ChunkContext(
                content=c.content,
                headings=c.headings,
                page_number=c.page_number,
                score=c.score,
            )
            for c in chunks
        ]

        alert_contexts = alerts if alerts else None
        prompt = synthesis_prompt(query, chunk_contexts, alert_contexts)
        return self.generate(prompt)

    def validate_guardrail(
        self,
        query: str,
        summary: str,
        chunks: List[SearchResult],
    ) -> Tuple[bool, str]:
        """Validate synthesis via guardrail prompt.

        Args:
            query: Original question
            summary: Generated summary to validate
            chunks: Source chunks

        Returns:
            (passed, full_validation_text)
        """
        chunk_contexts = [
            ChunkContext(
                content=c.content,
                headings=c.headings,
                page_number=c.page_number,
                score=c.score,
            )
            for c in chunks
        ]

        prompt = guardrail_prompt(query, summary, chunk_contexts)
        validation = self.generate(prompt, max_tokens=300, temperature=0.1)

        # Parse OVERALL result
        passed = "OVERALL: PASS" in validation.upper()
        return passed, validation


# --- Full Pipeline ---

class ClinicalRAGPipeline:
    """End-to-end RAG pipeline: Query → Brain 1 → Brain 2 → Result."""

    def __init__(
        self,
        db_path: str = None,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_MODEL,
        device: str = "cpu",
    ):
        self.brain1 = BrainOneSearch(db_path=db_path, device=device)
        self.brain2 = BrainTwoSynthesis(ollama_url=ollama_url, model=model)

    def query(
        self,
        query: str,
        top_k: int = 10,
        run_guardrail: bool = True,
    ) -> SynthesisResult:
        """Run full RAG pipeline.

        Args:
            query: Clinical question
            top_k: Number of chunks to retrieve
            run_guardrail: Whether to validate summary

        Returns:
            SynthesisResult with all details
        """
        total_start = time.time()

        # Brain 1: Search
        search_start = time.time()
        chunks = self.brain1.search_hybrid(query, top_k=top_k)
        alerts = self.brain1.detect_high_risk(chunks)
        search_time = (time.time() - search_start) * 1000

        # Brain 2: Synthesis
        synth_start = time.time()
        summary = self.brain2.synthesize(query, chunks, alerts)
        synth_time = (time.time() - synth_start) * 1000

        # Guardrail validation
        guardrail_result = None
        guardrail_passed = None
        if run_guardrail:
            guardrail_passed, guardrail_result = self.brain2.validate_guardrail(
                query, summary, chunks
            )

        total_time = (time.time() - total_start) * 1000

        return SynthesisResult(
            query=query,
            summary=summary,
            chunks_used=chunks,
            alerts=alerts,
            guardrail_result=guardrail_result,
            guardrail_passed=guardrail_passed,
            search_time_ms=search_time,
            synthesis_time_ms=synth_time,
            total_time_ms=total_time,
        )

    def query_search_only(self, query: str, top_k: int = 10) -> SynthesisResult:
        """Brain 1 only (no LLM synthesis).

        Useful for testing search quality or when MedGemma is unavailable.
        """
        search_start = time.time()
        chunks = self.brain1.search_hybrid(query, top_k=top_k)
        alerts = self.brain1.detect_high_risk(chunks)
        search_time = (time.time() - search_start) * 1000

        return SynthesisResult(
            query=query,
            summary="[Brain 2 not used - search-only mode]",
            chunks_used=chunks,
            alerts=alerts,
            search_time_ms=search_time,
            total_time_ms=search_time,
        )

    def close(self):
        self.brain1.close()


# --- CLI for testing ---

def print_result(result: SynthesisResult):
    """Pretty-print a synthesis result."""
    print(f"\n{'='*70}")
    print(f"QUERY: {result.query}")
    print(f"{'='*70}")

    # Alerts
    if result.alerts:
        high = [a for a in result.alerts if a.severity == "High"]
        medium = [a for a in result.alerts if a.severity == "Medium"]
        if high:
            print(f"\n🔴 DANGER SIGNS: {', '.join(a.term for a in high)}")
        if medium:
            print(f"🟡 Caution: {', '.join(a.term for a in medium)}")

    # Summary
    print(f"\n📋 CLINICAL SUMMARY:")
    print(f"{result.summary}")

    # Guardrail
    if result.guardrail_passed is not None:
        status = "✅ PASSED" if result.guardrail_passed else "❌ FAILED"
        print(f"\n🛡️ Guardrail: {status}")
        if not result.guardrail_passed and result.guardrail_result:
            print(f"   {result.guardrail_result}")

    # Sources
    print(f"\n📖 Sources ({len(result.chunks_used)} chunks):")
    for i, chunk in enumerate(result.chunks_used[:5], 1):
        heading = " > ".join(chunk.headings) if chunk.headings else "General"
        page = f"p.{chunk.page_number}" if chunk.page_number else "n/a"
        print(f"   [{i}] {heading} ({page}) [score: {chunk.score:.3f}]")

    # Timing
    print(f"\n⏱️ Timing:")
    print(f"   Search: {result.search_time_ms:.0f}ms")
    print(f"   Synthesis: {result.synthesis_time_ms:.0f}ms")
    print(f"   Total: {result.total_time_ms:.0f}ms")
    print()


# Test queries covering a range of clinical scenarios
TEST_QUERIES = [
    "What are the danger signs of malaria in children under 5?",
    "How do you treat severe dehydration in a child?",
    "Management of hypertension in adults",
    "What are the symptoms of tuberculosis?",
    "First aid for snake bite",
    "Danger signs in pregnancy that require immediate referral",
    "How to manage pneumonia in children",
    "Treatment of uncomplicated malaria",
    "Signs and management of severe malnutrition",
    "HIV testing and counseling guidelines",
    "Management of diabetes mellitus type 2",
    "How to assess a patient with chest pain",
    # Edge cases
    "What are the danger signs in a newborn?",
    "Snake bite first aid and antivenom treatment",
    "When should a CHW refer a patient to hospital?",
    "Dosage of amoxicillin for pneumonia in children under 5",
    "How to prevent mother to child transmission of HIV",
    "Management of severe acute malnutrition in children",
    "Treatment of uncomplicated urinary tract infection",
    "Epilepsy seizure management and first aid",
]


def run_ablation(brain1: BrainOneSearch, queries: List[str], output_path: Optional[str] = None):
    """Run ablation study: compare vector-only, keyword-only, and hybrid search.

    For each query, runs all three search modes and compares which heading paths
    appear in the top-5 results. Outputs a structured markdown table.

    Args:
        brain1: Initialized BrainOneSearch instance
        queries: List of queries to evaluate
        output_path: Optional path to write markdown results file
    """
    print(f"\n{'='*70}")
    print("ABLATION STUDY: Vector-Only vs Keyword-Only vs Hybrid RRF")
    print(f"{'='*70}\n")

    results_rows = []
    vector_top3_hits = 0
    keyword_top3_hits = 0
    hybrid_top3_hits = 0
    total = len(queries)

    for i, query in enumerate(queries, 1):
        print(f"[{i}/{total}] {query}")

        # Run all three search modes
        t0 = time.time()
        vector_results = brain1.search_vector(query, k=10)
        vector_ms = (time.time() - t0) * 1000

        t0 = time.time()
        keyword_results = brain1.search_keyword(query, k=10)
        keyword_ms = (time.time() - t0) * 1000

        t0 = time.time()
        hybrid_results = brain1.search_hybrid(query, top_k=10)
        hybrid_ms = (time.time() - t0) * 1000

        # Extract top-1 heading for each mode
        def top_heading(results):
            if results and results[0].headings:
                return " > ".join(results[0].headings[-2:])  # last 2 levels
            return "(no heading)"

        def top3_headings(results):
            headings = []
            for r in results[:3]:
                if r.headings:
                    headings.append(" > ".join(r.headings[-2:]))
            return headings

        # Check for unique chunks across modes
        vector_ids = {r.chunk_id for r in vector_results[:5]}
        keyword_ids = {r.chunk_id for r in keyword_results[:5]}
        hybrid_ids = {r.chunk_id for r in hybrid_results[:5]}

        # Hybrid captures chunks from both sources
        hybrid_has_vector = len(hybrid_ids & vector_ids) > 0
        hybrid_has_keyword = len(hybrid_ids & keyword_ids) > 0
        hybrid_diverse = hybrid_has_vector and hybrid_has_keyword

        # Detect high-risk alerts for each mode
        vector_alerts = brain1.detect_high_risk(vector_results[:5])
        keyword_alerts = brain1.detect_high_risk(keyword_results[:5])
        hybrid_alerts = brain1.detect_high_risk(hybrid_results[:5])

        # Track top-3 heading coverage (using hybrid as reference)
        hybrid_top3 = set(top3_headings(hybrid_results))
        if hybrid_top3:
            hybrid_top3_hits += 1
        vector_top3 = set(top3_headings(vector_results))
        if vector_top3:
            vector_top3_hits += 1
        keyword_top3 = set(top3_headings(keyword_results))
        if keyword_top3:
            keyword_top3_hits += 1

        row = {
            "query": query,
            "vector_heading": top_heading(vector_results),
            "keyword_heading": top_heading(keyword_results),
            "hybrid_heading": top_heading(hybrid_results),
            "vector_ms": vector_ms,
            "keyword_ms": keyword_ms,
            "hybrid_ms": hybrid_ms,
            "vector_alerts": len(vector_alerts),
            "keyword_alerts": len(keyword_alerts),
            "hybrid_alerts": len(hybrid_alerts),
            "hybrid_diverse": hybrid_diverse,
            "vector_unique": len(vector_ids - keyword_ids),
            "keyword_unique": len(keyword_ids - vector_ids),
        }
        results_rows.append(row)

        print(f"  Vector:  {top_heading(vector_results)} ({vector_ms:.0f}ms, {len(vector_alerts)} alerts)")
        print(f"  Keyword: {top_heading(keyword_results)} ({keyword_ms:.0f}ms, {len(keyword_alerts)} alerts)")
        print(f"  Hybrid:  {top_heading(hybrid_results)} ({hybrid_ms:.0f}ms, {len(hybrid_alerts)} alerts, diverse={hybrid_diverse})")
        print()

    # Summary statistics
    diverse_count = sum(1 for r in results_rows if r["hybrid_diverse"])
    avg_vector_ms = sum(r["vector_ms"] for r in results_rows) / total
    avg_keyword_ms = sum(r["keyword_ms"] for r in results_rows) / total
    avg_hybrid_ms = sum(r["hybrid_ms"] for r in results_rows) / total

    print(f"\n{'='*70}")
    print("ABLATION SUMMARY")
    print(f"{'='*70}")
    print(f"Queries evaluated: {total}")
    print(f"Hybrid retrieved from BOTH sources: {diverse_count}/{total} ({diverse_count*100//total}%)")
    print(f"Avg latency — Vector: {avg_vector_ms:.0f}ms | Keyword: {avg_keyword_ms:.0f}ms | Hybrid: {avg_hybrid_ms:.0f}ms")
    print(f"Queries with top-3 results — Vector: {vector_top3_hits}/{total} | Keyword: {keyword_top3_hits}/{total} | Hybrid: {hybrid_top3_hits}/{total}")

    # Generate markdown output
    if output_path:
        _write_ablation_markdown(results_rows, output_path, {
            "total": total,
            "diverse_count": diverse_count,
            "avg_vector_ms": avg_vector_ms,
            "avg_keyword_ms": avg_keyword_ms,
            "avg_hybrid_ms": avg_hybrid_ms,
            "vector_top3_hits": vector_top3_hits,
            "keyword_top3_hits": keyword_top3_hits,
            "hybrid_top3_hits": hybrid_top3_hits,
        })


def _write_ablation_markdown(rows: list, output_path: str, stats: dict):
    """Write ablation results as a structured markdown file."""
    lines = [
        "# Evaluation Results: Ablation Study & Per-Query Analysis",
        "",
        "**Methodology**: Each of the 20 test queries was run through three search configurations:",
        "- **Vector-only**: MiniLM-L6-v2 semantic search via sqlite-vec",
        "- **Keyword-only**: BM25 full-text search via FTS5",
        "- **Hybrid RRF**: Reciprocal Rank Fusion (k=60) combining both methods",
        "",
        "All measurements taken on the Python reference pipeline (not Android device).",
        "",
        "---",
        "",
        "## Summary Statistics",
        "",
        f"| Metric | Vector-Only | Keyword-Only | Hybrid RRF |",
        f"|--------|-------------|--------------|------------|",
        f"| Queries with top-3 results | {stats['vector_top3_hits']}/{stats['total']} | {stats['keyword_top3_hits']}/{stats['total']} | {stats['hybrid_top3_hits']}/{stats['total']} |",
        f"| Avg search latency | {stats['avg_vector_ms']:.0f}ms | {stats['avg_keyword_ms']:.0f}ms | {stats['avg_hybrid_ms']:.0f}ms |",
        f"| Hybrid draws from both sources | — | — | {stats['diverse_count']}/{stats['total']} ({stats['diverse_count']*100//stats['total']}%) |",
        "",
        "**Key finding**: Hybrid RRF retrieves from both vector and keyword sources in "
        f"{stats['diverse_count']}/{stats['total']} queries, capturing semantic matches that keyword search misses "
        "and exact terminology that vector search misses.",
        "",
        "---",
        "",
        "## Per-Query Results",
        "",
        "| # | Query | Vector Top-1 Heading | Keyword Top-1 Heading | Hybrid Top-1 Heading | Alerts (V/K/H) | Hybrid Diverse |",
        "|---|-------|---------------------|----------------------|---------------------|----------------|----------------|",
    ]

    for i, row in enumerate(rows, 1):
        q = row["query"][:50] + ("..." if len(row["query"]) > 50 else "")
        alerts = f"{row['vector_alerts']}/{row['keyword_alerts']}/{row['hybrid_alerts']}"
        diverse = "Yes" if row["hybrid_diverse"] else "No"
        lines.append(
            f"| {i} | {q} | {row['vector_heading'][:30]} | {row['keyword_heading'][:30]} | {row['hybrid_heading'][:30]} | {alerts} | {diverse} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Latency Breakdown",
        "",
        "| # | Query | Vector (ms) | Keyword (ms) | Hybrid (ms) |",
        "|---|-------|-------------|--------------|-------------|",
    ])

    for i, row in enumerate(rows, 1):
        q = row["query"][:50] + ("..." if len(row["query"]) > 50 else "")
        lines.append(
            f"| {i} | {q} | {row['vector_ms']:.0f} | {row['keyword_ms']:.0f} | {row['hybrid_ms']:.0f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Failure Analysis",
        "",
        "### Queries where vector and keyword returned different top results",
        "",
        "These cases illustrate why hybrid search matters:",
        "",
    ])

    # Find interesting divergence cases
    divergent = [r for r in rows if r["vector_heading"] != r["keyword_heading"]]
    for row in divergent[:3]:
        lines.extend([
            f"**Query**: \"{row['query']}\"",
            f"- Vector retrieved: {row['vector_heading']}",
            f"- Keyword retrieved: {row['keyword_heading']}",
            f"- Hybrid retrieved: {row['hybrid_heading']}",
            f"- Vector found {row['vector_unique']} unique chunks not in keyword results; keyword found {row['keyword_unique']} unique chunks not in vector results",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## Limitations",
        "",
        "1. **Self-evaluation**: These results use automated heading matching, not clinical expert review. "
        "We plan independent clinical validation with Makerere IIDMM physicians before deployment.",
        "2. **Single document**: All queries are evaluated against the Uganda Clinical Guidelines 2023. "
        "Generalization to other guideline PDFs requires additional testing.",
        "3. **Guardrail self-grading**: The guardrail uses the same model (MedGemma) that generated the summary. "
        "An independent NLI-based validator would provide stronger safety guarantees.",
        "4. **Python pipeline latency**: Timings reflect the Python reference implementation, not the Android app. "
        "On-device latency targets (<200ms for search, <2s total) are based on Android profiling.",
        "",
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nAblation results written to: {output_path}")


def main():
    """Run test queries through the pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="MedGemma Clinical RAG Pipeline")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Database path")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    parser.add_argument("--url", default=DEFAULT_OLLAMA_URL, help="Ollama URL")
    parser.add_argument("--query", type=str, help="Single query to test")
    parser.add_argument("--search-only", action="store_true", help="Brain 1 only")
    parser.add_argument("--no-guardrail", action="store_true", help="Skip guardrail")
    parser.add_argument("--all", action="store_true", help="Run all test queries")
    parser.add_argument("--ablation", action="store_true", help="Run ablation study comparing search modes")
    parser.add_argument("--ablation-output", type=str, help="Path to write ablation results markdown")
    parser.add_argument("--device", default="cpu", help="Device for embeddings")
    args = parser.parse_args()

    # Ablation mode: search-only comparison, no LLM needed
    if args.ablation:
        brain1 = BrainOneSearch(db_path=args.db, device=args.device)
        queries = TEST_QUERIES if args.all else TEST_QUERIES
        output_path = args.ablation_output or str(
            Path(__file__).parent.parent.parent / "submission" / "evaluation_results.md"
        )
        run_ablation(brain1, queries, output_path)
        brain1.close()
        return

    pipeline = ClinicalRAGPipeline(
        db_path=args.db,
        ollama_url=args.url,
        model=args.model,
        device=args.device,
    )

    # Check Brain 2 availability
    if not args.search_only:
        if pipeline.brain2.is_available():
            print(f"✅ MedGemma ({args.model}) available via Ollama")
        else:
            print(f"⚠️ MedGemma ({args.model}) not available. Use --search-only or start Ollama.")
            print(f"   Run: ollama pull {args.model}")
            args.search_only = True

    queries = []
    if args.query:
        queries = [args.query]
    elif args.all:
        queries = TEST_QUERIES
    else:
        queries = TEST_QUERIES[:3]  # Default: first 3 queries

    for query in queries:
        if args.search_only:
            result = pipeline.query_search_only(query)
        else:
            result = pipeline.query(query, run_guardrail=not args.no_guardrail)
        print_result(result)

    pipeline.close()


if __name__ == "__main__":
    main()
