"""
Main extraction pipeline for clinical guidelines.

This script orchestrates the full extraction process:
1. Convert PDF using Docling
2. Chunk the document
3. Generate embeddings
4. Store in SQLite with sqlite-vec
"""

import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from .chunker import GuidelineChunker, DEFAULT_MAX_TOKENS, DEFAULT_EMBED_MODEL
from .converter import GuidelineConverter
from .database import ChunkData, DocumentMetadata, GuidelineDatabase
from .embedder import GuidelineEmbedder


def run_pipeline(
    pdf_path: str,
    db_path: str,
    enable_ocr: bool = True,
    batch_size: int = 32,
    device: str = "cpu",
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """Run the full extraction pipeline.

    Args:
        pdf_path: Path to input PDF file
        db_path: Path for output SQLite database
        enable_ocr: Whether to enable OCR during extraction
        batch_size: Batch size for embedding generation
        device: Device for embedding model ('cpu', 'cuda', 'mps')
        max_tokens: Maximum tokens per chunk (default 1024 for clinical context)

    Returns:
        Dictionary with pipeline statistics
    """
    stats = {
        'pdf_path': pdf_path,
        'db_path': db_path,
        'pages': 0,
        'chunks': 0,
        'embeddings': 0
    }

    print(f"\n{'='*60}")
    print("CHW Clinical Guidelines Extraction Pipeline")
    print(f"{'='*60}\n")

    # Step 1: Initialize database
    print("[1/5] Initializing database...")
    db = GuidelineDatabase(db_path)
    db.create_schema()
    print(f"      Database created at: {db_path}")

    # Step 2: Convert PDF
    print("\n[2/5] Converting PDF with Docling...")
    print(f"      Source: {pdf_path}")
    converter = GuidelineConverter(enable_ocr=enable_ocr)
    result = converter.convert(pdf_path)
    stats['pages'] = result.metadata.get('page_count', 0)
    print(f"      Extracted {stats['pages']} pages")

    # Step 3: Insert document record
    print("\n[3/5] Storing document record...")
    metadata = DocumentMetadata(
        filename=result.metadata['filename'],
        title=result.metadata['title'],
        version=result.metadata.get('version'),
        extraction_date=result.metadata['extraction_date'],
        page_count=stats['pages']
    )
    doc_id = db.insert_document(metadata, result.docling_json)
    print(f"      Document ID: {doc_id}")

    # Step 4: Chunk document
    print("\n[4/5] Chunking document...")
    print(f"      Max tokens per chunk: {max_tokens}")
    chunker = GuidelineChunker(max_tokens=max_tokens)
    chunks = chunker.chunk(result.document)
    stats['chunks'] = len(chunks)
    print(f"      Created {stats['chunks']} chunks")

    # Insert chunks
    print("      Inserting chunks into database...")
    for chunk in tqdm(chunks, desc="      Chunks"):
        chunk_data = ChunkData(
            chunk_id=chunk.chunk_id,
            content=chunk.content,
            contextualized_text=chunk.contextualized_text,
            chunk_type=chunk.chunk_type,
            page_number=chunk.page_number,
            headings=chunk.headings,
            bbox=chunk.bbox,
            element_label=chunk.element_label,
            category=chunk.category
        )
        db.insert_chunk(doc_id, chunk_data)

    # Step 5: Generate and store embeddings
    print("\n[5/5] Generating embeddings...")
    embedder = GuidelineEmbedder(device=device)
    embedding_results = embedder.embed_chunks(chunks, batch_size=batch_size)
    stats['embeddings'] = len(embedding_results)

    print("      Inserting embeddings into database...")
    embeddings_batch = [
        (emb.chunk_id, emb.embedding)
        for emb in embedding_results
    ]
    db.insert_embeddings_batch(embeddings_batch)
    print(f"      Stored {stats['embeddings']} embeddings")

    # Step 6: Populate FTS5 for keyword search
    print("\n[6/6] Populating FTS5 index for keyword search...")
    db.populate_fts5()
    print("      FTS5 index populated")

    # Close database
    db.close()

    # Summary
    print(f"\n{'='*60}")
    print("Pipeline Complete!")
    print(f"{'='*60}")
    print(f"  Pages:      {stats['pages']}")
    print(f"  Chunks:     {stats['chunks']}")
    print(f"  Embeddings: {stats['embeddings']}")
    print(f"  Database:   {db_path}")
    print(f"{'='*60}\n")

    return stats


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Extract clinical guidelines from PDF to searchable database"
    )
    parser.add_argument(
        "pdf_path",
        help="Path to input PDF file"
    )
    parser.add_argument(
        "--output", "-o",
        default="data/databases/guidelines.db",
        help="Output database path (default: data/databases/guidelines.db)"
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable OCR (faster but may miss scanned content)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding generation (default: 32)"
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda", "mps"],
        default="cpu",
        help="Device for embedding model (default: cpu)"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Maximum tokens per chunk (default: {DEFAULT_MAX_TOKENS}). "
             "Larger values provide more clinical context per chunk."
    )

    args = parser.parse_args()

    # Validate input
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Run pipeline
    try:
        stats = run_pipeline(
            pdf_path=str(pdf_path),
            db_path=args.output,
            enable_ocr=not args.no_ocr,
            batch_size=args.batch_size,
            device=args.device,
            max_tokens=args.max_tokens,
        )
    except Exception as e:
        print(f"Error: Pipeline failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
