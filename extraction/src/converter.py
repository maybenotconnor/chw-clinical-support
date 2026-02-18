"""
Docling PDF extraction wrapper for clinical guidelines.

This module uses IBM's Docling library to extract structured content
from clinical guideline PDFs with layout analysis and table extraction.

Supports two modes:
1. Standard pipeline: Layout analysis + OCR + table extraction
2. VLM pipeline: Vision Language Model for superior extraction (requires API key)
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, VlmPipelineOptions
from docling.datamodel.pipeline_options_vlm_model import ApiVlmOptions, ResponseFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline
from pydantic import AnyUrl


# OpenAI API configuration
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

# Clinical document extraction prompt
VLM_EXTRACTION_PROMPT = """Convert this clinical guideline page to well-structured markdown.

Instructions:
- Preserve ALL text content exactly as written - this is medical information where accuracy is critical
- Maintain heading hierarchy (use # for main headings, ## for subheadings, etc.)
- Format tables using markdown table syntax with proper alignment
- Preserve numbered lists, bullet points, and indentation
- Keep medical dosages, measurements, and units exactly as shown
- Identify and preserve: treatment protocols, drug names, dosages, contraindications, warnings
- For flowcharts or diagrams, describe the decision flow in structured text
- Do not add any commentary or interpretation - only convert what is visible

Output only the markdown content, no explanations."""


@dataclass
class ConversionResult:
    """Result of PDF conversion."""
    document: object  # DoclingDocument
    metadata: dict
    docling_json: str
    markdown: str = field(default="")


class GuidelineConverterVLM:
    """Converts clinical guideline PDFs using Docling with VLM pipeline.

    Uses OpenAI GPT for superior document understanding, especially for:
    - Complex table structures
    - Multi-column layouts
    - Flowcharts and diagrams
    - Handwritten annotations (if present)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = OPENAI_MODEL,
        concurrency: int = 1,
        timeout: int = 120,
    ):
        """Initialize VLM-based converter.

        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: OpenAI model name (default: gpt-5.2-mini)
            concurrency: Number of concurrent API requests
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Pass api_key or set OPENAI_API_KEY env var."
            )

        # Configure VLM pipeline options for OpenAI
        vlm_options = ApiVlmOptions(
            url=AnyUrl(OPENAI_API_URL),
            params={
                "model": model,
                "temperature": 0.0,  # Deterministic for medical content
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
            },
            prompt=VLM_EXTRACTION_PROMPT,
            timeout=timeout,
            concurrency=concurrency,
            response_format=ResponseFormat.MARKDOWN,
        )

        pipeline_options = VlmPipelineOptions(
            vlm_options=vlm_options,
            enable_remote_services=True,
        )

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=VlmPipeline,
                    pipeline_options=pipeline_options,
                )
            }
        )

    def convert(self, pdf_path: str, output_markdown: bool = True) -> ConversionResult:
        """Convert PDF to structured document using VLM.

        Args:
            pdf_path: Path to the PDF file
            output_markdown: Whether to save markdown file alongside PDF

        Returns:
            ConversionResult with document, metadata, JSON, and markdown
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        print(f"Converting {pdf_path.name} with Gemini VLM pipeline...")
        result = self.converter.convert(str(pdf_path))

        # Export to markdown
        markdown = result.document.export_to_markdown()

        # Save markdown file for validation
        if output_markdown:
            md_path = pdf_path.with_suffix(".extracted.md")
            md_path.write_text(markdown, encoding="utf-8")
            print(f"Markdown saved to: {md_path}")

        # Extract metadata
        metadata = self._extract_metadata(result.document, pdf_path)

        # Export to JSON
        docling_json = self._export_to_json(result.document)

        return ConversionResult(
            document=result.document,
            metadata=metadata,
            docling_json=docling_json,
            markdown=markdown,
        )

    def _extract_metadata(self, document, pdf_path: Path) -> dict:
        """Extract document metadata."""
        title = None
        if hasattr(document, 'name') and document.name:
            title = document.name

        page_count = len(document.pages) if hasattr(document, 'pages') else 0

        return {
            'filename': pdf_path.name,
            'title': title or pdf_path.stem,
            'version': None,
            'extraction_date': datetime.now().isoformat(),
            'page_count': page_count,
            'extraction_method': 'vlm',
            'vlm_model': OPENAI_MODEL,
        }

    def _export_to_json(self, document) -> str:
        """Export Docling document to JSON format."""
        try:
            if hasattr(document, 'export_to_dict'):
                return json.dumps(document.export_to_dict(), indent=2)
            elif hasattr(document, 'model_dump'):
                return json.dumps(document.model_dump(), indent=2)
            else:
                return json.dumps({
                    'name': getattr(document, 'name', None),
                    'num_pages': len(document.pages) if hasattr(document, 'pages') else 0,
                }, indent=2)
        except Exception as e:
            return json.dumps({'error': str(e), 'type': 'serialization_failed'})


class GuidelineConverter:
    """Converts clinical guideline PDFs using Docling standard pipeline.

    Use this for faster processing or when VLM API is unavailable.
    For best results on complex documents, use GuidelineConverterVLM instead.
    """

    def __init__(
        self,
        enable_ocr: bool = True,
        enable_tables: bool = True,
        enable_images: bool = False
    ):
        """Initialize converter with Docling pipeline options.

        Args:
            enable_ocr: Enable OCR for scanned content
            enable_tables: Enable table structure extraction
            enable_images: Enable image extraction (not needed for Phase 1)
        """
        # Configure PDF pipeline options
        pdf_options = PdfPipelineOptions(
            do_ocr=enable_ocr,
            do_table_structure=enable_tables,
            generate_page_images=enable_images,
            generate_picture_images=enable_images,
        )

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)
            }
        )

    def convert(self, pdf_path: str, output_markdown: bool = True) -> ConversionResult:
        """Convert PDF to structured document.

        Args:
            pdf_path: Path to the PDF file
            output_markdown: Whether to save markdown file alongside PDF

        Returns:
            ConversionResult with document, metadata, JSON, and markdown

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            RuntimeError: If conversion fails
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Convert the document
        result = self.converter.convert(str(pdf_path))

        # Export to markdown
        markdown = result.document.export_to_markdown()

        # Save markdown file for validation
        if output_markdown:
            md_path = pdf_path.with_suffix(".extracted.md")
            md_path.write_text(markdown, encoding="utf-8")
            print(f"Markdown saved to: {md_path}")

        # Extract metadata
        metadata = self._extract_metadata(result.document, pdf_path)

        # Export to JSON for storage
        docling_json = self._export_to_json(result.document)

        return ConversionResult(
            document=result.document,
            metadata=metadata,
            docling_json=docling_json,
            markdown=markdown,
        )

    def _extract_metadata(self, document, pdf_path: Path) -> dict:
        """Extract document metadata.

        Args:
            document: Docling document object
            pdf_path: Original PDF path

        Returns:
            Dictionary of metadata
        """
        # Try to extract title from document
        title = self._extract_title(document) or pdf_path.stem

        # Count pages
        page_count = len(document.pages) if hasattr(document, 'pages') else 0

        return {
            'filename': pdf_path.name,
            'title': title,
            'version': None,  # Could be extracted from content if present
            'extraction_date': datetime.now().isoformat(),
            'page_count': page_count,
            'extraction_method': 'standard',
        }

    def _extract_title(self, document) -> Optional[str]:
        """Try to extract title from document structure.

        Args:
            document: Docling document object

        Returns:
            Title string or None
        """
        # Look for title in document metadata or first heading
        if hasattr(document, 'name') and document.name:
            return document.name

        # Try to get from first level-1 heading
        try:
            for item in document.iterate_items():
                if hasattr(item, 'label') and item.label == 'title':
                    return item.text
                if hasattr(item, 'level') and item.level == 1:
                    return item.text[:100]  # Truncate long titles
        except Exception:
            pass

        return None

    def _export_to_json(self, document) -> str:
        """Export Docling document to JSON format.

        Args:
            document: Docling document object

        Returns:
            JSON string representation
        """
        try:
            # Use Docling's built-in export if available
            if hasattr(document, 'export_to_dict'):
                return json.dumps(document.export_to_dict(), indent=2)
            elif hasattr(document, 'model_dump'):
                return json.dumps(document.model_dump(), indent=2)
            else:
                # Fallback: serialize what we can
                return json.dumps({
                    'name': getattr(document, 'name', None),
                    'num_pages': len(document.pages) if hasattr(document, 'pages') else 0,
                }, indent=2)
        except Exception as e:
            return json.dumps({'error': str(e), 'type': 'serialization_failed'})


def convert_guideline(pdf_path: str, enable_ocr: bool = True) -> ConversionResult:
    """Convenience function to convert a clinical guideline PDF using standard pipeline.

    Args:
        pdf_path: Path to PDF file
        enable_ocr: Whether to enable OCR

    Returns:
        ConversionResult with markdown export
    """
    converter = GuidelineConverter(enable_ocr=enable_ocr)
    return converter.convert(pdf_path)


def convert_guideline_vlm(
    pdf_path: str,
    api_key: Optional[str] = None,
    model: str = OPENAI_MODEL,
) -> ConversionResult:
    """Convert a clinical guideline PDF using VLM pipeline for best quality.

    This uses OpenAI GPT for superior extraction of:
    - Complex tables and multi-column layouts
    - Flowcharts and diagrams
    - Accurate preservation of medical terminology

    Args:
        pdf_path: Path to PDF file
        api_key: OpenAI API key (or set OPENAI_API_KEY env var)
        model: OpenAI model name

    Returns:
        ConversionResult with markdown export

    Example:
        >>> result = convert_guideline_vlm("guidelines.pdf", api_key="your-key")
        >>> print(result.markdown[:500])  # Preview extracted content
    """
    converter = GuidelineConverterVLM(api_key=api_key, model=model)
    return converter.convert(pdf_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert clinical guideline PDFs")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--vlm", action="store_true", help="Use VLM pipeline (requires API key)")
    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY)")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR (standard pipeline only)")

    args = parser.parse_args()

    if args.vlm:
        result = convert_guideline_vlm(args.pdf_path, api_key=args.api_key)
    else:
        result = convert_guideline(args.pdf_path, enable_ocr=not args.no_ocr)

    print(f"\nExtracted {result.metadata['page_count']} pages")
    print(f"Title: {result.metadata['title']}")
    print(f"Method: {result.metadata['extraction_method']}")
    print(f"\nMarkdown preview (first 500 chars):\n{result.markdown[:500]}...")
