"""Tests for prediction JSON parsing and normalization."""

import json

from wavestreamer_runner.personality import AgentPersonality
from wavestreamer_runner.predict import _get_perspective, _normalize, _parse_prediction_json


class TestParsePredictionJson:
    """Test _parse_prediction_json handles various LLM output formats."""

    def test_clean_json(self):
        text = json.dumps({
            "prediction": True,
            "confidence": 72,
            "reasoning": "EVIDENCE: Test evidence. ANALYSIS: Test analysis. COUNTER-EVIDENCE: Test counter. BOTTOM LINE: Test conclusion.",
        })
        result = _parse_prediction_json(text, "binary")
        assert result["prediction"] is True
        assert result["confidence"] == 72
        assert "EVIDENCE" in result["reasoning"]

    def test_json_in_code_block(self):
        text = """Here's my prediction:
```json
{"prediction": false, "confidence": 65, "reasoning": "EVIDENCE: Data shows decline. ANALYSIS: Trend continues. COUNTER-EVIDENCE: Some uptick. BOTTOM LINE: Unlikely."}
```"""
        result = _parse_prediction_json(text, "binary")
        assert result["prediction"] is False
        assert result["confidence"] == 65

    def test_json_in_code_block_no_lang(self):
        text = """```
{"prediction": true, "confidence": 80, "reasoning": "Test reasoning content here."}
```"""
        result = _parse_prediction_json(text, "binary")
        assert result["prediction"] is True
        assert result["confidence"] == 80

    def test_json_with_thinking_tags(self):
        text = """<think>Let me think about this carefully...</think>
{"prediction": true, "confidence": 70, "reasoning": "After careful analysis, the evidence suggests yes."}"""
        result = _parse_prediction_json(text, "binary")
        assert result["prediction"] is True
        assert result["confidence"] == 70

    def test_multi_option(self):
        text = json.dumps({
            "prediction": True,
            "confidence": 75,
            "selected_option": "Option B",
            "reasoning": "Option B fits the data best.",
        })
        result = _parse_prediction_json(text, "multi")
        assert result["selected_option"] == "Option B"
        assert result["confidence"] == 75

    def test_malformed_json_regex_fallback(self):
        text = """I think this is likely.
prediction: true
confidence: 68
reasoning: "EVIDENCE: Strong signals. ANALYSIS: Positive trend. COUNTER-EVIDENCE: Minor risk. BOTTOM LINE: Yes."
"""
        result = _parse_prediction_json(text, "binary")
        assert result["confidence"] == 68

    def test_confidence_clamped_to_range(self):
        text = json.dumps({"prediction": True, "confidence": 5, "reasoning": "Test"})
        result = _parse_prediction_json(text, "binary")
        assert result["confidence"] >= 50  # clamped by _normalize

    def test_confidence_capped_at_99(self):
        text = json.dumps({"prediction": True, "confidence": 100, "reasoning": "Test"})
        result = _parse_prediction_json(text, "binary")
        assert result["confidence"] <= 99


class TestNormalize:
    """Test _normalize handles edge cases in LLM output."""

    def test_answer_alias(self):
        result = _normalize({"answer": True, "confidence": 70, "reasoning": "test"}, "binary")
        assert result["prediction"] is True

    def test_verdict_alias(self):
        result = _normalize({"verdict": "yes", "confidence": 60, "reasoning": "test"}, "binary")
        assert result["prediction"] is True

    def test_string_confidence_converted(self):
        result = _normalize({"prediction": True, "confidence": "75", "reasoning": "test"}, "binary")
        assert result["confidence"] == 75
        assert isinstance(result["confidence"], int)

    def test_missing_confidence_gets_default(self):
        result = _normalize({"prediction": True, "reasoning": "test"}, "binary")
        assert 55 <= result["confidence"] <= 80

    def test_missing_reasoning_gets_empty(self):
        result = _normalize({"prediction": True, "confidence": 70}, "binary")
        assert result["reasoning"] == ""

    def test_analysis_alias_for_reasoning(self):
        result = _normalize({"prediction": True, "confidence": 70, "analysis": "detailed analysis"}, "binary")
        assert result["reasoning"] == "detailed analysis"

    def test_explanation_alias_for_reasoning(self):
        result = _normalize({"prediction": True, "confidence": 70, "explanation": "my explanation"}, "binary")
        assert result["reasoning"] == "my explanation"


class TestGetPerspective:
    def test_known_style(self):
        p = AgentPersonality(style="contrarian")
        perspective = _get_perspective(p)
        assert "CONTRARIAN" in perspective

    def test_unknown_style_falls_back_to_analytical(self):
        p = AgentPersonality(style="nonexistent_style")
        perspective = _get_perspective(p)
        assert "DATA-DRIVEN" in perspective

    def test_bio_appended(self):
        p = AgentPersonality(style="analytical", bio="Expert in quantum computing")
        perspective = _get_perspective(p)
        assert "quantum computing" in perspective
