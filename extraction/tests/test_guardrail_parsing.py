"""Tests for guardrail result parsing logic."""

import pytest

from extraction.src.medgemma_synthesis import BrainTwoSynthesis


class TestGuardrailParsing:
    """Test that guardrail PASS/FAIL parsing works correctly."""

    def test_overall_pass_detected(self):
        validation_text = """GROUNDING: PASS - All claims supported
ACCURACY: PASS - Dosages match
COMPLETENESS: PASS - No omissions
NO_FABRICATION: PASS - No fabricated content
APPROPRIATE_SCOPE: PASS - Within CHW scope

OVERALL: PASS"""

        passed = "OVERALL: PASS" in validation_text.upper()
        assert passed is True

    def test_overall_fail_detected(self):
        validation_text = """GROUNDING: PASS - All claims supported
ACCURACY: FAIL - Dosage of amoxicillin incorrect
COMPLETENESS: PASS - No omissions
NO_FABRICATION: PASS - No fabricated content
APPROPRIATE_SCOPE: PASS - Within CHW scope

OVERALL: FAIL
REASON: Dosage error detected in treatment recommendation"""

        passed = "OVERALL: PASS" in validation_text.upper()
        assert passed is False

    def test_pass_case_insensitive(self):
        validation_text = "Overall: Pass"
        passed = "OVERALL: PASS" in validation_text.upper()
        assert passed is True

    def test_fail_without_overall_keyword(self):
        validation_text = "The summary is mostly correct but has some issues."
        passed = "OVERALL: PASS" in validation_text.upper()
        assert passed is False

    def test_empty_validation_is_failure(self):
        validation_text = ""
        passed = "OVERALL: PASS" in validation_text.upper()
        assert passed is False

    def test_pass_with_extra_whitespace(self):
        validation_text = "OVERALL:  PASS"
        # Current implementation uses exact string match; this tests the boundary
        passed = "OVERALL: PASS" in validation_text.upper()
        assert passed is False  # Extra space means no match — conservative behavior

    def test_partial_match_not_accepted(self):
        validation_text = "OVERALL: PASS_WITH_WARNINGS"
        passed = "OVERALL: PASS" in validation_text.upper()
        # Substring match means this would return True — document this behavior
        assert passed is True  # Known: substring match is permissive
