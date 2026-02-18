"""Tests for clinical prompt formatting."""

import pytest

from extraction.src.clinical_prompts import (
    ChunkContext,
    HighRiskAlertContext,
    format_alerts_for_prompt,
    format_chunks_for_prompt,
    guardrail_prompt,
    synthesis_prompt,
)


# --- Chunk Formatting Tests ---

class TestFormatChunks:

    def test_includes_chunk_content(self):
        chunks = [ChunkContext(
            content="Malaria treatment: AL twice daily for 3 days",
            headings=["Chapter 3", "Malaria"],
            page_number=5,
            score=0.95,
        )]
        result = format_chunks_for_prompt(chunks)
        assert "Malaria treatment: AL twice daily for 3 days" in result

    def test_includes_heading_path(self):
        chunks = [ChunkContext(
            content="Some content",
            headings=["Chapter 3", "Malaria", "Treatment"],
            page_number=5,
        )]
        result = format_chunks_for_prompt(chunks)
        assert "Chapter 3 > Malaria > Treatment" in result

    def test_includes_page_number(self):
        chunks = [ChunkContext(content="Content", headings=[], page_number=42)]
        result = format_chunks_for_prompt(chunks)
        assert "p.42" in result

    def test_respects_max_chars_limit(self):
        chunks = [
            ChunkContext(content="A" * 500, headings=["H1"], page_number=1),
            ChunkContext(content="B" * 500, headings=["H2"], page_number=2),
            ChunkContext(content="C" * 500, headings=["H3"], page_number=3),
        ]
        result = format_chunks_for_prompt(chunks, max_chars=600)
        assert "A" * 500 in result
        assert "C" * 500 not in result

    def test_numbers_chunks_sequentially(self):
        chunks = [
            ChunkContext(content="First", headings=[], page_number=1),
            ChunkContext(content="Second", headings=[], page_number=2),
        ]
        result = format_chunks_for_prompt(chunks)
        assert "[1]" in result
        assert "[2]" in result


# --- Alert Formatting Tests ---

class TestFormatAlerts:

    def test_empty_alerts_returns_empty(self):
        result = format_alerts_for_prompt([])
        assert result == ""

    def test_high_severity_formatted_as_danger(self):
        alerts = [HighRiskAlertContext(term="convulsions", category="Neurological", severity="High")]
        result = format_alerts_for_prompt(alerts)
        assert "DANGER SIGNS DETECTED" in result
        assert "convulsions" in result

    def test_medium_severity_formatted_as_caution(self):
        alerts = [HighRiskAlertContext(term="headache", category="Neurological", severity="Medium")]
        result = format_alerts_for_prompt(alerts)
        assert "Caution" in result
        assert "headache" in result

    def test_mixed_severities(self):
        alerts = [
            HighRiskAlertContext(term="convulsions", category="Neurological", severity="High"),
            HighRiskAlertContext(term="headache", category="Neurological", severity="Medium"),
        ]
        result = format_alerts_for_prompt(alerts)
        assert "DANGER SIGNS DETECTED" in result
        assert "Caution" in result


# --- Synthesis Prompt Tests ---

class TestSynthesisPrompt:

    def test_includes_all_chunk_content(self):
        chunks = [
            ChunkContext(content="Chunk one content", headings=["H1"], page_number=1),
            ChunkContext(content="Chunk two content", headings=["H2"], page_number=2),
        ]
        result = synthesis_prompt("test query", chunks)
        assert "Chunk one content" in result
        assert "Chunk two content" in result

    def test_includes_query(self):
        chunks = [ChunkContext(content="Content", headings=[], page_number=1)]
        result = synthesis_prompt("malaria danger signs", chunks)
        assert "malaria danger signs" in result

    def test_includes_safety_alerts_when_provided(self):
        chunks = [ChunkContext(content="Content", headings=[], page_number=1)]
        alerts = [HighRiskAlertContext(term="convulsions", category="Neurological", severity="High")]
        result = synthesis_prompt("test", chunks, alerts)
        assert "SAFETY ALERTS" in result
        assert "convulsions" in result

    def test_no_safety_section_without_alerts(self):
        chunks = [ChunkContext(content="Content", headings=[], page_number=1)]
        result = synthesis_prompt("test", chunks, alerts=None)
        assert "SAFETY ALERTS" not in result

    def test_includes_instructions(self):
        chunks = [ChunkContext(content="Content", headings=[], page_number=1)]
        result = synthesis_prompt("test", chunks)
        assert "NEVER fabricate" in result
        assert "CHW" in result


# --- Guardrail Prompt Tests ---

class TestGuardrailPrompt:

    def test_includes_source_and_summary(self):
        chunks = [ChunkContext(content="Source content", headings=["H1"], page_number=1)]
        result = guardrail_prompt("query", "Generated summary text", chunks)
        assert "Source content" in result
        assert "Generated summary text" in result

    def test_includes_validation_criteria(self):
        chunks = [ChunkContext(content="Content", headings=[], page_number=1)]
        result = guardrail_prompt("query", "summary", chunks)
        assert "GROUNDING" in result
        assert "ACCURACY" in result
        assert "COMPLETENESS" in result
        assert "NO FABRICATION" in result or "NO_FABRICATION" in result
        assert "APPROPRIATE SCOPE" in result or "APPROPRIATE_SCOPE" in result

    def test_includes_pass_fail_format(self):
        chunks = [ChunkContext(content="Content", headings=[], page_number=1)]
        result = guardrail_prompt("query", "summary", chunks)
        assert "OVERALL: [PASS/FAIL]" in result
