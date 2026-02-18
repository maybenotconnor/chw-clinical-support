"""
Clinical prompt templates for MedGemma synthesis.

These prompts are designed for MedGemma 1.5 4B-it to:
1. Synthesize clinical summaries from retrieved guideline chunks
2. Validate summaries against source material (guardrail)
3. Analyze clinical images and match to guidelines

All prompts follow the Gemma chat template format.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ChunkContext:
    """A retrieved chunk for prompt context."""
    content: str
    headings: List[str]
    page_number: Optional[int] = None
    score: float = 0.0


@dataclass
class HighRiskAlertContext:
    """A high-risk alert for prompt context."""
    term: str
    category: str
    severity: str  # "High" or "Medium"


def format_chunks_for_prompt(chunks: List[ChunkContext], max_chars: int = 4000) -> str:
    """Format retrieved chunks as numbered context for the prompt.

    Args:
        chunks: Retrieved chunks with metadata
        max_chars: Maximum characters to include (to fit context window)

    Returns:
        Formatted string of numbered chunks
    """
    formatted = []
    total_chars = 0

    for i, chunk in enumerate(chunks, 1):
        heading_path = " > ".join(chunk.headings) if chunk.headings else "General"
        page_info = f" (p.{chunk.page_number})" if chunk.page_number else ""

        entry = f"[{i}] {heading_path}{page_info}\n{chunk.content}"

        if total_chars + len(entry) > max_chars:
            break

        formatted.append(entry)
        total_chars += len(entry)

    return "\n\n".join(formatted)


def format_alerts_for_prompt(alerts: List[HighRiskAlertContext]) -> str:
    """Format high-risk alerts as warnings in the prompt."""
    if not alerts:
        return ""

    high = [a for a in alerts if a.severity == "High"]
    medium = [a for a in alerts if a.severity == "Medium"]

    lines = []
    if high:
        terms = ", ".join(a.term for a in high)
        lines.append(f"DANGER SIGNS DETECTED: {terms}")
    if medium:
        terms = ", ".join(a.term for a in medium)
        lines.append(f"Caution terms found: {terms}")

    return "\n".join(lines)


def synthesis_prompt(
    query: str,
    chunks: List[ChunkContext],
    alerts: Optional[List[HighRiskAlertContext]] = None,
    max_context_chars: int = 4000,
) -> str:
    """Build the clinical synthesis prompt.

    Takes a user query and retrieved guideline chunks, produces a prompt
    that asks MedGemma to synthesize a clinical summary grounded in the
    provided evidence.

    Args:
        query: The CHW's clinical question
        chunks: Retrieved guideline chunks (from Brain 1)
        alerts: Optional high-risk alerts detected
        max_context_chars: Max chars for chunk context

    Returns:
        Complete prompt string for MedGemma
    """
    context = format_chunks_for_prompt(chunks, max_context_chars)
    alert_text = format_alerts_for_prompt(alerts or [])

    alert_section = ""
    if alert_text:
        alert_section = f"""
⚠️ SAFETY ALERTS:
{alert_text}
You MUST prominently address these safety concerns in your response.
"""

    return f"""You are a clinical decision support assistant for Community Health Workers (CHWs) in Uganda. Your role is to synthesize clinical guidelines into clear, actionable guidance.

CLINICAL GUIDELINE EXCERPTS:
{context}
{alert_section}
CHW QUESTION: {query}

INSTRUCTIONS:
1. Answer ONLY using information from the guideline excerpts above
2. Use simple, clear language appropriate for CHWs with basic medical training
3. Structure your response with clear sections when appropriate
4. Include specific dosages, age ranges, and treatment steps when available
5. If danger signs are mentioned, list them prominently at the top
6. If the guidelines do not contain enough information to answer, say so clearly
7. NEVER fabricate clinical information not present in the excerpts
8. Include relevant page references using [p.X] format

Provide a concise clinical summary (150-300 words):"""


def guardrail_prompt(
    query: str,
    summary: str,
    chunks: List[ChunkContext],
    max_context_chars: int = 3000,
) -> str:
    """Build the guardrail validation prompt.

    This is a second inference pass that checks whether the generated
    summary is grounded in the source chunks and is clinically safe.

    Args:
        query: Original clinical question
        summary: Generated summary to validate
        chunks: Source chunks the summary should be grounded in
        max_context_chars: Max chars for chunk context

    Returns:
        Complete guardrail prompt string
    """
    context = format_chunks_for_prompt(chunks, max_context_chars)

    return f"""You are a clinical safety validator. Your job is to verify that a generated clinical summary is grounded in source guidelines and is safe for Community Health Workers.

SOURCE GUIDELINES:
{context}

QUESTION: {query}

GENERATED SUMMARY:
{summary}

VALIDATION CRITERIA:
1. GROUNDING: Every clinical claim in the summary must be supported by the source guidelines
2. ACCURACY: Dosages, age ranges, and treatment steps must exactly match the sources
3. COMPLETENESS: Critical safety information (danger signs, referral criteria) must not be omitted
4. NO FABRICATION: The summary must not contain clinical information absent from the sources
5. APPROPRIATE SCOPE: The summary should not recommend actions beyond CHW scope of practice

For each criterion, evaluate PASS or FAIL with a brief explanation.

Respond in this exact format:
GROUNDING: [PASS/FAIL] - [explanation]
ACCURACY: [PASS/FAIL] - [explanation]
COMPLETENESS: [PASS/FAIL] - [explanation]
NO_FABRICATION: [PASS/FAIL] - [explanation]
APPROPRIATE_SCOPE: [PASS/FAIL] - [explanation]

OVERALL: [PASS/FAIL]
REASON: [one sentence summary if FAIL]"""


def image_analysis_prompt(
    image_description: Optional[str] = None,
) -> str:
    """Build the multimodal image analysis prompt.

    For MedGemma's vision capability - analyzes a clinical photo and
    generates a description that can be used as a search query.

    Args:
        image_description: Optional text context about the image

    Returns:
        Complete image analysis prompt string
    """
    context = ""
    if image_description:
        context = f"\nAdditional context from the health worker: {image_description}"

    return f"""You are a clinical image analysis assistant for Community Health Workers (CHWs). A CHW has taken a photo of a patient's condition for guidance.
{context}
Analyze this clinical image and provide:

1. OBSERVATION: Describe what you observe in clinical terms (appearance, location, characteristics)
2. POSSIBLE CONDITIONS: List 2-3 possible conditions that could match these observations
3. KEY FEATURES: Note specific features that would help narrow the differential
4. SEARCH TERMS: Suggest 2-3 search terms to look up in clinical guidelines

IMPORTANT:
- Do NOT provide a definitive diagnosis
- This is for guideline lookup assistance only
- Always recommend the CHW consult guidelines and refer if uncertain
- Be specific enough to enable useful guideline searches

Provide your analysis:"""


def search_query_from_image_prompt() -> str:
    """Build a prompt to extract a search query from image analysis.

    Used after image_analysis_prompt to get a concise search query
    for Brain 1.

    Returns:
        Prompt string
    """
    return """Based on your image analysis above, provide a single concise search query (5-15 words) that would best match clinical guidelines relevant to this condition. Output ONLY the search query, nothing else."""


# Convenience: full pipeline prompts as a dict for easy iteration
PROMPT_TEMPLATES = {
    "synthesis": synthesis_prompt,
    "guardrail": guardrail_prompt,
    "image_analysis": image_analysis_prompt,
}
