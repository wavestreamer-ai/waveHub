"""Tests for AgentPersonality."""

from wavestreamer_runner.personality import AgentPersonality


class TestAgentPersonality:
    def test_defaults(self):
        p = AgentPersonality()
        assert p.name == "Agent"
        assert p.style == "analytical"
        assert p.confidence_range == (20, 85)
        assert p.bio == ""

    def test_custom_values(self):
        p = AgentPersonality(
            name="TestBot",
            bio="A test agent",
            style="contrarian",
            model="llama3.1",
            confidence_range=(30, 90),
            catchphrase="Always bet against the crowd",
        )
        assert p.name == "TestBot"
        assert p.style == "contrarian"
        assert p.model == "llama3.1"
        assert p.confidence_range == (30, 90)

    def test_from_api_full(self):
        api_response = {
            "name": "OracleBot",
            "bio": "Expert forecaster",
            "persona_archetype": "skeptical",
            "model": "gpt-4o",
            "catchphrase": "Doubt everything",
        }
        p = AgentPersonality.from_api(api_response, model="claude-sonnet-4")
        assert p.name == "OracleBot"
        assert p.bio == "Expert forecaster"
        assert p.style == "skeptical"
        assert p.model == "claude-sonnet-4"  # explicit model overrides API

    def test_from_api_minimal(self):
        p = AgentPersonality.from_api({})
        assert p.name == "Agent"
        assert p.style == "analytical"
        assert p.model == ""

    def test_from_api_uses_api_model_as_fallback(self):
        api_response = {"model": "llama3.1"}
        p = AgentPersonality.from_api(api_response)
        assert p.model == "llama3.1"
