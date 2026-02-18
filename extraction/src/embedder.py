"""
Embedding generation for clinical guideline chunks.

This module generates 384-dimensional embeddings using the
MiniLM-L6-v2 sentence transformer model.
"""

from dataclasses import dataclass
from typing import List

from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from .chunker import ChunkResult


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    chunk_id: str
    embedding: List[float]


class GuidelineEmbedder:
    """Generates embeddings for clinical guideline chunks."""

    MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384

    def __init__(self, model_id: str = None, device: str = "cpu"):
        """Initialize embedding model.

        Args:
            model_id: HuggingFace model ID (defaults to MiniLM-L6-v2)
            device: Device to run model on ('cpu', 'cuda', 'mps')
        """
        self.model_id = model_id or self.MODEL_ID
        self.device = device
        self.model = SentenceTransformer(self.model_id, device=device)

    def embed(self, text: str) -> List[float]:
        """Embed a single text string.

        Args:
            text: Text to embed

        Returns:
            384-dimensional embedding as list of floats
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> List[List[float]]:
        """Embed a batch of texts.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            show_progress: Whether to show progress bar

        Returns:
            List of embeddings
        """
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
        return embeddings.tolist()

    def embed_chunks(
        self,
        chunks: List[ChunkResult],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> List[EmbeddingResult]:
        """Generate embeddings for document chunks.

        Uses the contextualized_text field for embedding to include
        heading context for better semantic search.

        Args:
            chunks: List of ChunkResult objects
            batch_size: Batch size for processing
            show_progress: Whether to show progress bar

        Returns:
            List of EmbeddingResult objects
        """
        # Extract contextualized texts for embedding
        texts = [chunk.contextualized_text for chunk in chunks]

        # Generate embeddings
        embeddings = self.embed_batch(
            texts,
            batch_size=batch_size,
            show_progress=show_progress
        )

        # Combine with chunk IDs
        results = []
        for chunk, embedding in zip(chunks, embeddings):
            results.append(EmbeddingResult(
                chunk_id=chunk.chunk_id,
                embedding=embedding
            ))

        return results


def embed_chunks(
    chunks: List[ChunkResult],
    model_id: str = None,
    device: str = "cpu",
    batch_size: int = 32
) -> List[EmbeddingResult]:
    """Convenience function to embed document chunks.

    Args:
        chunks: List of ChunkResult objects
        model_id: Optional model ID override
        device: Device to run on
        batch_size: Batch size for processing

    Returns:
        List of EmbeddingResult objects
    """
    embedder = GuidelineEmbedder(model_id=model_id, device=device)
    return embedder.embed_chunks(chunks, batch_size=batch_size)
