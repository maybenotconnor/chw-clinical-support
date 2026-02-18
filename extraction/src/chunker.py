"""
Document chunking for clinical guidelines.

This module splits Docling documents into searchable chunks while
preserving structure and metadata like headings and page numbers.

Uses Docling's HybridChunker with token-aware chunking aligned to
the embedding model's tokenizer for optimal RAG performance.
"""

import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

# Default embedding model - must match the model used in embedder.py
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Default max tokens per chunk
# Set higher than model's 512 limit to allow larger clinical context chunks.
# Embeddings will capture semantic essence from first 512 tokens, but full
# chunk text is returned to users for complete clinical information.
DEFAULT_MAX_TOKENS = 1024

# Chunk categories
CHUNK_CATEGORY_CONTENT = "content"      # Clinical guidelines, treatments, symptoms
CHUNK_CATEGORY_METADATA = "metadata"    # TOC, abbreviations, foreword, credits

# Headings that indicate metadata sections (case-insensitive matching)
# These sections typically don't contain clinical guidance and should be
# deprioritized or filtered in search results
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
class ChunkResult:
    """Result of document chunking."""
    chunk_id: str
    content: str
    contextualized_text: str
    chunk_type: str
    page_number: Optional[int]
    headings: List[str] = field(default_factory=list)
    bbox: Optional[dict] = None
    element_label: str = ""
    category: str = CHUNK_CATEGORY_CONTENT  # 'content' or 'metadata'


class GuidelineChunker:
    """Chunks clinical guidelines while preserving structure.

    Uses Docling's HybridChunker with token-aware chunking to create
    appropriately-sized chunks for clinical RAG applications. Chunks
    are sized to provide sufficient clinical context while respecting
    embedding model constraints.
    """

    def __init__(
        self,
        merge_list_items: bool = True,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        embed_model_id: str = DEFAULT_EMBED_MODEL,
    ):
        """Initialize chunker with token-aware configuration.

        Args:
            merge_list_items: Whether to merge list items into single chunks
            max_tokens: Maximum tokens per chunk. Default 1024 allows larger
                clinical context. Chunks exceeding embedding model limit (512)
                will have embeddings generated from first 512 tokens, but full
                text is preserved for display.
            embed_model_id: HuggingFace model ID for tokenizer alignment.
                Must match the embedding model used for vector search.
        """
        # Initialize tokenizer aligned to the embedding model
        self.tokenizer = HuggingFaceTokenizer(
            tokenizer=AutoTokenizer.from_pretrained(embed_model_id),
            max_tokens=max_tokens,
        )

        # Initialize HybridChunker with token-aware settings
        # HybridChunker will:
        # - Split chunks that exceed max_tokens
        # - Merge small adjacent chunks (same heading) up to max_tokens
        # - Preserve document structure and heading hierarchy
        self.chunker = HybridChunker(
            tokenizer=self.tokenizer,
            merge_list_items=merge_list_items,
        )

        self.max_tokens = max_tokens
        self.embed_model_id = embed_model_id

    def chunk(self, document) -> List[ChunkResult]:
        """Chunk a Docling document into searchable segments.

        Args:
            document: Docling document object

        Returns:
            List of ChunkResult objects with content and metadata
        """
        chunks = []

        for doc_chunk in self.chunker.chunk(document):
            # Extract metadata from chunk
            headings = self._extract_headings(doc_chunk)
            page_number = self._extract_page_number(doc_chunk)
            chunk_type = self._determine_chunk_type(doc_chunk)
            bbox = self._extract_bbox(doc_chunk)
            element_label = self._extract_label(doc_chunk)

            # Determine category (content vs metadata)
            category = self._determine_category(headings)

            # Generate contextualized text for embedding
            contextualized = self._contextualize(doc_chunk, headings)

            chunks.append(ChunkResult(
                chunk_id=str(uuid.uuid4()),
                content=doc_chunk.text,
                contextualized_text=contextualized,
                chunk_type=chunk_type,
                page_number=page_number,
                headings=headings,
                bbox=bbox,
                element_label=element_label,
                category=category
            ))

        return chunks

    def _extract_headings(self, chunk) -> List[str]:
        """Extract heading hierarchy from chunk metadata.

        Args:
            chunk: Docling chunk object

        Returns:
            List of heading strings from root to leaf
        """
        headings = []

        if hasattr(chunk, 'meta') and chunk.meta:
            meta = chunk.meta
            # Try different metadata structures
            if hasattr(meta, 'headings'):
                headings = list(meta.headings) if meta.headings else []
            elif hasattr(meta, 'doc_items'):
                # Extract from document items
                for item in meta.doc_items:
                    if hasattr(item, 'label') and 'heading' in str(item.label).lower():
                        if hasattr(item, 'text'):
                            headings.append(item.text)

        return headings

    def _extract_page_number(self, chunk) -> Optional[int]:
        """Extract page number from chunk metadata.

        Args:
            chunk: Docling chunk object

        Returns:
            Page number or None
        """
        if hasattr(chunk, 'meta') and chunk.meta:
            meta = chunk.meta
            if hasattr(meta, 'doc_items') and meta.doc_items:
                for item in meta.doc_items:
                    if hasattr(item, 'prov') and item.prov:
                        for prov in item.prov:
                            if hasattr(prov, 'page_no'):
                                return prov.page_no
        return None

    def _determine_chunk_type(self, chunk) -> str:
        """Determine the type of content in the chunk.

        Args:
            chunk: Docling chunk object

        Returns:
            Chunk type string: 'text', 'table', 'list', 'figure'
        """
        if hasattr(chunk, 'meta') and chunk.meta:
            meta = chunk.meta
            if hasattr(meta, 'doc_items') and meta.doc_items:
                for item in meta.doc_items:
                    label = getattr(item, 'label', '')
                    if label:
                        label_str = str(label).lower()
                        if 'table' in label_str:
                            return 'table'
                        elif 'list' in label_str:
                            return 'list'
                        elif 'figure' in label_str or 'picture' in label_str:
                            return 'figure'
        return 'text'

    def _determine_category(self, headings: List[str]) -> str:
        """Determine if chunk is clinical content or document metadata.

        Checks if any heading in the hierarchy matches known metadata patterns
        (e.g., "Contents", "Abbreviations", "Foreword"). These sections typically
        don't contain clinical guidance and should be deprioritized in search.

        Args:
            headings: List of heading strings from root to leaf

        Returns:
            'content' for clinical guidelines, 'metadata' for non-clinical sections
        """
        for heading in headings:
            heading_lower = heading.lower().strip()
            for pattern in METADATA_HEADING_PATTERNS:
                if pattern in heading_lower:
                    return CHUNK_CATEGORY_METADATA
        return CHUNK_CATEGORY_CONTENT

    def _extract_bbox(self, chunk) -> Optional[dict]:
        """Extract bounding box from chunk metadata.

        Args:
            chunk: Docling chunk object

        Returns:
            Bounding box dict or None
        """
        if hasattr(chunk, 'meta') and chunk.meta:
            meta = chunk.meta
            if hasattr(meta, 'doc_items') and meta.doc_items:
                for item in meta.doc_items:
                    if hasattr(item, 'prov') and item.prov:
                        for prov in item.prov:
                            if hasattr(prov, 'bbox') and prov.bbox:
                                bbox = prov.bbox
                                return {
                                    'l': getattr(bbox, 'l', 0),
                                    't': getattr(bbox, 't', 0),
                                    'r': getattr(bbox, 'r', 0),
                                    'b': getattr(bbox, 'b', 0)
                                }
        return None

    def _extract_label(self, chunk) -> str:
        """Extract element label from chunk metadata.

        Args:
            chunk: Docling chunk object

        Returns:
            Element label string
        """
        if hasattr(chunk, 'meta') and chunk.meta:
            meta = chunk.meta
            if hasattr(meta, 'doc_items') and meta.doc_items:
                labels = []
                for item in meta.doc_items:
                    if hasattr(item, 'label') and item.label:
                        labels.append(str(item.label))
                return ', '.join(labels) if labels else ''
        return ''

    def _contextualize(self, chunk, headings: List[str]) -> str:
        """Generate contextualized text for embedding.

        Prepends heading hierarchy to chunk text to provide context
        for better semantic search.

        Args:
            chunk: Docling chunk object
            headings: List of heading strings

        Returns:
            Contextualized text string
        """
        parts = []

        # Add heading context
        if headings:
            heading_context = ' > '.join(headings)
            parts.append(f"[{heading_context}]")

        # Add main content
        parts.append(chunk.text)

        return ' '.join(parts)


def chunk_document(
    document,
    merge_list_items: bool = True,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    embed_model_id: str = DEFAULT_EMBED_MODEL,
) -> List[ChunkResult]:
    """Convenience function to chunk a document.

    Args:
        document: Docling document object
        merge_list_items: Whether to merge list items into single chunks
        max_tokens: Maximum tokens per chunk (default 1024 for clinical context)
        embed_model_id: HuggingFace model ID for tokenizer alignment

    Returns:
        List of ChunkResult objects
    """
    chunker = GuidelineChunker(
        merge_list_items=merge_list_items,
        max_tokens=max_tokens,
        embed_model_id=embed_model_id,
    )
    return chunker.chunk(document)
