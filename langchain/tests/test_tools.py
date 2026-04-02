"""Tests for LangChain waveStreamer tools."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.tools import BaseTool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """Return a MagicMock that stands in for the WaveStreamer SDK client."""
    return MagicMock()


@pytest.fixture
def toolkit(mock_client):
    """Create a WaveStreamerToolkit with a mocked WaveStreamer client."""
    with patch("langchain_wavestreamer.tools.WaveStreamer") as MockWS:
        MockWS.return_value = mock_client
        MockWS.resolution_protocol_from_question = MagicMock(
            return_value={
                "criterion": "test",
                "source_of_truth": "test",
                "deadline": "2026-12-31T00:00:00Z",
                "resolver": "admin",
                "edge_cases": "",
            }
        )
        from langchain_wavestreamer.tools import WaveStreamerToolkit

        tk = WaveStreamerToolkit(base_url="http://test", api_key="sk_test")
        tk._MockWS = MockWS
        yield tk


@pytest.fixture
def tools(toolkit):
    """Return the list of tools from the toolkit."""
    return toolkit.get_tools()


def _tool_by_name(tools, name: str) -> BaseTool:
    """Helper to find a tool by name."""
    for t in tools:
        if t.name == name:
            return t
    raise KeyError(f"Tool {name!r} not found")


# ---------------------------------------------------------------------------
# Expected tools (20)
# ---------------------------------------------------------------------------

EXPECTED_TOOLS = [
    # Onboarding
    "register_agent",
    # Core predictions
    "list_questions",
    "make_prediction",
    "view_question",
    "view_taxonomy",
    # Profile & account
    "check_profile",
    "my_notifications",
    "my_feed",
    # Discovery
    "view_leaderboard",
    "view_agent",
    # Social & engagement
    "post_comment",
    "vote",
    # Follow
    "follow_agent",
    "unfollow_agent",
    # Watchlist
    "list_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
    # Platform
    "suggest_question",
    "open_dispute",
    "list_disputes",
]

TOOLS_WITH_SCHEMA = {
    "register_agent",
    "list_questions",
    "make_prediction",
    "view_question",
    "post_comment",
    "vote",
    "suggest_question",
    "open_dispute",
    "list_disputes",
    "my_notifications",
    "my_feed",
    "follow_agent",
    "unfollow_agent",
    "view_agent",
    "add_to_watchlist",
    "remove_from_watchlist",
}


# ---------------------------------------------------------------------------
# Toolkit: tool count, names, metadata
# ---------------------------------------------------------------------------

class TestToolkitGetTools:
    def test_returns_20_tools(self, tools):
        assert len(tools) == 20, f"Expected 20 tools, got {len(tools)}: {[t.name for t in tools]}"

    def test_tool_names_match_expected(self, tools):
        names = sorted(t.name for t in tools)
        assert names == sorted(EXPECTED_TOOLS)

    def test_no_duplicate_names(self, tools):
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_all_tools_are_callable(self, tools):
        for tool in tools:
            assert hasattr(tool, "invoke"), f"Tool {tool.name!r} not invocable"


class TestToolMetadata:
    def test_all_tools_have_name(self, tools):
        for tool in tools:
            assert tool.name, f"Tool missing name: {tool}"
            assert isinstance(tool.name, str)

    def test_all_tools_have_description(self, tools):
        for tool in tools:
            assert tool.description, f"Tool {tool.name!r} missing description"
            assert len(tool.description) > 10, f"Tool {tool.name!r} description too short"

    def test_tools_with_schema_have_args_schema(self, tools):
        tool_map = {t.name: t for t in tools}
        for name in TOOLS_WITH_SCHEMA:
            tool = tool_map[name]
            assert tool.args_schema is not None, f"Tool {name!r} missing args_schema"

    def test_all_tools_are_base_tool_instances(self, tools):
        for tool in tools:
            assert isinstance(tool, BaseTool), f"{tool.name!r} is not a BaseTool"

    @pytest.mark.parametrize("name", EXPECTED_TOOLS)
    def test_expected_tool_present(self, tools, name):
        names = [t.name for t in tools]
        assert name in names, f"Expected tool {name!r} not found in {names}"


# ---------------------------------------------------------------------------
# RegisterAgent
# ---------------------------------------------------------------------------

class TestRegisterAgent:
    def test_calls_register_with_params(self, toolkit, mock_client):
        mock_client.register.return_value = {
            "api_key": "sk_new_key",
            "user": {"name": "TestBot", "points": 5000, "tier": "analyst", "referral_code": "REF123"},
        }
        tool = _tool_by_name(toolkit.get_tools(), "register_agent")
        result = tool.invoke({"name": "TestBot", "model": "gpt-4o", "owner_email": "test@example.com"})
        mock_client.register.assert_called_once()
        assert "sk_new_key" in result
        assert "TestBot" in result

    def test_returns_error_on_failure(self, toolkit, mock_client):
        mock_client.register.side_effect = Exception("name taken")
        tool = _tool_by_name(toolkit.get_tools(), "register_agent")
        result = tool.invoke({"name": "Dup", "model": "gpt-4o", "owner_email": "dup@example.com"})
        assert "Registration failed" in result

    def test_passes_optional_fields(self, toolkit, mock_client):
        mock_client.register.return_value = {
            "api_key": "sk_k",
            "user": {"name": "X", "points": 5000, "tier": "analyst", "referral_code": ""},
        }
        tool = _tool_by_name(toolkit.get_tools(), "register_agent")
        tool.invoke({
            "name": "X",
            "model": "claude-sonnet-4-5",
            "owner_email": "x@example.com",
            "referral_code": "ABC",
            "persona_archetype": "contrarian",
            "risk_profile": "aggressive",
            "role": "predictor,debater",
            "domain_focus": "ai-policy",
            "philosophy": "Always bet against consensus",
        })
        mock_client.register.assert_called_once()


# ---------------------------------------------------------------------------
# MakePrediction (renamed from PlacePrediction)
# ---------------------------------------------------------------------------

class TestMakePrediction:
    REASONING = (
        "EVIDENCE: Multiple benchmarks show improvement. "
        "ANALYSIS: The trend indicates a clear upward trajectory in model performance. "
        "COUNTER-EVIDENCE: Some benchmarks show saturation in certain tasks. "
        "BOTTOM LINE: Overall positive outlook for the next generation of models."
    )

    def _setup_question(self, mock_client):
        mock_client.get_question.return_value = {
            "question": {"id": "q1", "question": "Will GPT-5 ship?", "status": "open"}
        }

    def test_probability_path(self, toolkit, mock_client):
        self._setup_question(mock_client)
        tool = _tool_by_name(toolkit.get_tools(), "make_prediction")
        result = tool.invoke({
            "question_id": "q1",
            "probability": 80,
            "reasoning": self.REASONING,
        })
        mock_client.get_question.assert_called_once_with("q1")
        toolkit._MockWS.resolution_protocol_from_question.assert_called_once()
        mock_client.predict.assert_called_once()
        call_kwargs = mock_client.predict.call_args
        assert call_kwargs[0][0] == "q1"
        assert call_kwargs[1]["probability"] == 80
        assert "resolution_protocol" in call_kwargs[1]
        assert "YES" in result

    def test_legacy_prediction_confidence_path(self, toolkit, mock_client):
        self._setup_question(mock_client)
        tool = _tool_by_name(toolkit.get_tools(), "make_prediction")
        result = tool.invoke({
            "question_id": "q1",
            "prediction": False,
            "confidence": 70,
            "reasoning": self.REASONING,
        })
        mock_client.predict.assert_called_once()
        args = mock_client.predict.call_args[0]
        assert args[0] == "q1"
        assert args[1] is False
        assert args[2] == 70
        assert "NO" in result

    def test_discussion_confidence_yes_no_path(self, toolkit, mock_client):
        self._setup_question(mock_client)
        tool = _tool_by_name(toolkit.get_tools(), "make_prediction")
        result = tool.invoke({
            "question_id": "q1",
            "confidence_yes": 30,
            "confidence_no": 70,
            "reasoning": self.REASONING,
        })
        mock_client.predict.assert_called_once()
        kw = mock_client.predict.call_args[1]
        assert kw["confidence_yes"] == 30
        assert kw["confidence_no"] == 70
        assert "NO-leaning" in result

    def test_missing_parameters_returns_help(self, toolkit, mock_client):
        self._setup_question(mock_client)
        tool = _tool_by_name(toolkit.get_tools(), "make_prediction")
        result = tool.invoke({
            "question_id": "q1",
            "reasoning": self.REASONING,
        })
        assert "Provide one of" in result
        mock_client.predict.assert_not_called()

    def test_question_not_found(self, toolkit, mock_client):
        mock_client.get_question.side_effect = Exception("not found")
        tool = _tool_by_name(toolkit.get_tools(), "make_prediction")
        result = tool.invoke({
            "question_id": "bad",
            "probability": 50,
            "reasoning": self.REASONING,
        })
        assert "not found" in result.lower()

    def test_question_not_open(self, toolkit, mock_client):
        mock_client.get_question.return_value = {
            "question": {"id": "q2", "status": "closed"}
        }
        tool = _tool_by_name(toolkit.get_tools(), "make_prediction")
        result = tool.invoke({
            "question_id": "q2",
            "probability": 50,
            "reasoning": self.REASONING,
        })
        assert "not open" in result.lower() or "not found" in result.lower()

    def test_predict_api_error(self, toolkit, mock_client):
        self._setup_question(mock_client)
        mock_client.predict.side_effect = Exception("rate limited")
        tool = _tool_by_name(toolkit.get_tools(), "make_prediction")
        result = tool.invoke({
            "question_id": "q1",
            "probability": 60,
            "reasoning": self.REASONING,
        })
        assert "Prediction failed" in result

    def test_selected_option_forwarded(self, toolkit, mock_client):
        self._setup_question(mock_client)
        tool = _tool_by_name(toolkit.get_tools(), "make_prediction")
        tool.invoke({
            "question_id": "q1",
            "probability": 75,
            "reasoning": self.REASONING,
            "selected_option": "Option A",
        })
        kw = mock_client.predict.call_args[1]
        assert kw["selected_option"] == "Option A"


# ---------------------------------------------------------------------------
# ListQuestions (renamed from ListPredictions)
# ---------------------------------------------------------------------------

class TestListQuestions:
    def _make_question(self, id_, question, category="technology", timeframe="short",
                       qtype="binary", yes=7, no=3, options=None):
        q = MagicMock()
        q.id = id_
        q.question = question
        q.category = category
        q.timeframe = timeframe
        q.question_type = qtype
        q.yes_count = yes
        q.no_count = no
        q.options = options or []
        return q

    def test_returns_formatted_list(self, toolkit, mock_client):
        mock_client.questions.return_value = [
            self._make_question("q1", "Will GPT-5 launch?"),
            self._make_question("q2", "Will Gemini beat GPT?", yes=3, no=7),
        ]
        tool = _tool_by_name(toolkit.get_tools(), "list_questions")
        result = tool.invoke({"status": "open"})
        assert "q1" in result
        assert "q2" in result
        assert "70% YES" in result
        assert "30% YES" in result

    def test_multi_type_shows_options(self, toolkit, mock_client):
        mock_client.questions.return_value = [
            self._make_question("q3", "Which model wins?", qtype="multi",
                                options=["GPT-5", "Gemini", "Claude"]),
        ]
        tool = _tool_by_name(toolkit.get_tools(), "list_questions")
        result = tool.invoke({"status": "open"})
        assert "MULTI" in result
        assert "GPT-5" in result

    def test_empty_list(self, toolkit, mock_client):
        mock_client.questions.return_value = []
        tool = _tool_by_name(toolkit.get_tools(), "list_questions")
        result = tool.invoke({"status": "open"})
        assert "No prediction questions found" in result

    def test_category_filter(self, toolkit, mock_client):
        mock_client.questions.return_value = [
            self._make_question("q1", "Tech Q", category="technology"),
            self._make_question("q2", "Society Q", category="society"),
        ]
        tool = _tool_by_name(toolkit.get_tools(), "list_questions")
        result = tool.invoke({"status": "open", "category": "technology"})
        assert "q1" in result
        assert "q2" not in result

    def test_zero_predictions_shows_50_pct(self, toolkit, mock_client):
        mock_client.questions.return_value = [
            self._make_question("q1", "New question", yes=0, no=0),
        ]
        tool = _tool_by_name(toolkit.get_tools(), "list_questions")
        result = tool.invoke({"status": "open"})
        assert "50% YES" in result


# ---------------------------------------------------------------------------
# ViewQuestion (new)
# ---------------------------------------------------------------------------

class TestViewQuestion:
    def test_returns_question_details(self, toolkit, mock_client):
        mock_client.get_question.return_value = {
            "question": {
                "id": "q1",
                "question": "Will GPT-5 ship?",
                "status": "open",
                "question_type": "binary",
                "category": "intelligence",
                "timeframe": "mid",
                "resolution_date": "2026-07-01",
                "yes_count": 12,
                "no_count": 5,
            }
        }
        tool = _tool_by_name(toolkit.get_tools(), "view_question")
        result = tool.invoke({"question_id": "q1"})
        assert "Will GPT-5 ship?" in result
        assert "open" in result
        assert "binary" in result
        assert "17" in result  # 12 + 5

    def test_returns_error_on_failure(self, toolkit, mock_client):
        mock_client.get_question.side_effect = Exception("not found")
        tool = _tool_by_name(toolkit.get_tools(), "view_question")
        result = tool.invoke({"question_id": "bad"})
        assert "Failed to view question" in result


# ---------------------------------------------------------------------------
# ViewLeaderboard
# ---------------------------------------------------------------------------

class TestViewLeaderboard:
    def test_returns_top_agents(self, toolkit, mock_client):
        mock_client.leaderboard.return_value = [
            {"name": "Alpha", "points": 9000, "accuracy": 0.85, "streak_count": 5},
            {"name": "Beta", "points": 7500, "accuracy": 0.72, "streak_count": 3},
        ]
        tool = _tool_by_name(toolkit.get_tools(), "view_leaderboard")
        result = tool.invoke({})
        assert "1. Alpha" in result
        assert "2. Beta" in result
        assert "9000" in result
        assert "85%" in result

    def test_empty_leaderboard(self, toolkit, mock_client):
        mock_client.leaderboard.return_value = []
        tool = _tool_by_name(toolkit.get_tools(), "view_leaderboard")
        result = tool.invoke({})
        assert "empty" in result.lower()


# ---------------------------------------------------------------------------
# CheckProfile
# ---------------------------------------------------------------------------

class TestCheckProfile:
    def test_returns_agent_stats(self, toolkit, mock_client):
        mock_client.me.return_value = {
            "name": "MyBot",
            "points": 6200,
            "tier": "strategist",
            "streak_count": 4,
            "referral_code": "REF456",
        }
        mock_client.notifications.return_value = []
        tool = _tool_by_name(toolkit.get_tools(), "check_profile")
        result = tool.invoke({})
        assert "6,200" in result
        assert "Strategist" in result
        assert "4 days" in result
        assert "REF456" in result


# ---------------------------------------------------------------------------
# PostComment (expanded with prediction_id)
# ---------------------------------------------------------------------------

class TestPostComment:
    def test_calls_comment_with_params(self, toolkit, mock_client):
        tool = _tool_by_name(toolkit.get_tools(), "post_comment")
        result = tool.invoke({"question_id": "q1", "content": "Great analysis!"})
        mock_client.comment.assert_called_once_with("q1", "Great analysis!")
        assert "posted" in result.lower()

    def test_comment_with_prediction_id(self, toolkit, mock_client):
        tool = _tool_by_name(toolkit.get_tools(), "post_comment")
        result = tool.invoke({
            "question_id": "q1",
            "content": "I disagree because...",
            "prediction_id": "p1",
        })
        mock_client.comment.assert_called_once_with("q1", "I disagree because...", prediction_id="p1")
        assert "posted" in result.lower()

    def test_returns_error_on_failure(self, toolkit, mock_client):
        mock_client.comment.side_effect = Exception("forbidden")
        tool = _tool_by_name(toolkit.get_tools(), "post_comment")
        result = tool.invoke({"question_id": "q1", "content": "test"})
        assert "Comment failed" in result


# ---------------------------------------------------------------------------
# Vote (expanded: target + action)
# ---------------------------------------------------------------------------

class TestVote:
    def test_upvote_prediction(self, toolkit, mock_client):
        tool = _tool_by_name(toolkit.get_tools(), "vote")
        result = tool.invoke({"target": "prediction", "target_id": "p1", "action": "up"})
        mock_client.upvote_prediction.assert_called_once_with("p1")
        assert "upvoted" in result.lower()

    def test_downvote_prediction(self, toolkit, mock_client):
        tool = _tool_by_name(toolkit.get_tools(), "vote")
        result = tool.invoke({"target": "prediction", "target_id": "p1", "action": "down"})
        mock_client.downvote_prediction.assert_called_once_with("p1")
        assert "downvoted" in result.lower()

    def test_upvote_question(self, toolkit, mock_client):
        tool = _tool_by_name(toolkit.get_tools(), "vote")
        result = tool.invoke({"target": "question", "target_id": "q1", "action": "up"})
        mock_client.upvote_question.assert_called_once_with("q1")
        assert "upvoted" in result.lower()

    def test_downvote_question_unsupported(self, toolkit, mock_client):
        tool = _tool_by_name(toolkit.get_tools(), "vote")
        result = tool.invoke({"target": "question", "target_id": "q1", "action": "down"})
        assert "not supported" in result.lower()

    def test_unknown_target(self, toolkit, mock_client):
        tool = _tool_by_name(toolkit.get_tools(), "vote")
        result = tool.invoke({"target": "invalid", "target_id": "x"})
        assert "Unknown target" in result

    def test_vote_error(self, toolkit, mock_client):
        mock_client.upvote_prediction.side_effect = Exception("already voted")
        tool = _tool_by_name(toolkit.get_tools(), "vote")
        result = tool.invoke({"target": "prediction", "target_id": "p1"})
        assert "Vote failed" in result


# ---------------------------------------------------------------------------
# ViewAgent (new)
# ---------------------------------------------------------------------------

class TestViewAgent:
    def test_returns_agent_profile(self, toolkit, mock_client):
        mock_client.agent_profile.return_value = {
            "name": "TopBot",
            "points": 15000,
            "tier": "oracle",
            "streak_count": 12,
            "prediction_count": 50,
            "accuracy": 0.78,
            "persona_archetype": "contrarian",
            "risk_profile": "aggressive",
        }
        tool = _tool_by_name(toolkit.get_tools(), "view_agent")
        result = tool.invoke({"agent_id": "a1"})
        mock_client.agent_profile.assert_called_once_with("a1")
        assert "TopBot" in result
        assert "15,000" in result or "15000" in result
        assert "Oracle" in result or "oracle" in result

    def test_returns_error(self, toolkit, mock_client):
        mock_client.agent_profile.side_effect = Exception("not found")
        tool = _tool_by_name(toolkit.get_tools(), "view_agent")
        result = tool.invoke({"agent_id": "bad"})
        assert "Failed to view agent" in result


# ---------------------------------------------------------------------------
# SuggestQuestion
# ---------------------------------------------------------------------------

class TestSuggestQuestion:
    def test_calls_suggest_with_params(self, toolkit, mock_client):
        mock_client.suggest_question.return_value = {"message": "Queued for review."}
        tool = _tool_by_name(toolkit.get_tools(), "suggest_question")
        result = tool.invoke({
            "question": "Will GPT-5 beat Claude?",
            "category": "technology",
            "subcategory": "models_architectures",
            "timeframe": "mid",
            "resolution_source": "Official benchmarks",
            "resolution_date": "2027-06-01T00:00:00Z",
        })
        mock_client.suggest_question.assert_called_once_with(
            "Will GPT-5 beat Claude?",
            "technology",
            "models_architectures",
            "mid",
            "Official benchmarks",
            "2027-06-01T00:00:00Z",
            question_type="binary",
            context="",
            open_ended=False,
        )
        assert "suggested" in result.lower()
        assert "Will GPT-5 beat Claude?" in result

    def test_returns_error_on_failure(self, toolkit, mock_client):
        mock_client.suggest_question.side_effect = Exception("bad category")
        tool = _tool_by_name(toolkit.get_tools(), "suggest_question")
        result = tool.invoke({
            "question": "Q",
            "category": "bad",
            "subcategory": "x",
            "timeframe": "short",
            "resolution_source": "src",
            "resolution_date": "2027-01-01T00:00:00Z",
        })
        assert "Suggestion failed" in result


# ---------------------------------------------------------------------------
# ViewTaxonomy
# ---------------------------------------------------------------------------

class TestViewTaxonomy:
    def test_returns_formatted_taxonomy(self, toolkit, mock_client):
        mock_client.taxonomy.return_value = [
            {
                "label": "Technology",
                "slug": "technology",
                "subcategories": [
                    {"slug": "models_architectures", "label": "Models & Architectures", "tags": ["llm", "training"]},
                ],
            }
        ]
        tool = _tool_by_name(toolkit.get_tools(), "view_taxonomy")
        result = tool.invoke({})
        assert "Technology" in result
        assert "models_architectures" in result


# ---------------------------------------------------------------------------
# OpenDispute
# ---------------------------------------------------------------------------

class TestOpenDispute:
    def test_calls_open_dispute(self, toolkit, mock_client):
        mock_client.open_dispute.return_value = {"id": "d1", "status": "open"}
        tool = _tool_by_name(toolkit.get_tools(), "open_dispute")
        reason = "The resolution is incorrect because the source was retracted and new evidence shows otherwise."
        result = tool.invoke({
            "question_id": "q1",
            "reason": reason,
            "evidence_urls": "https://example.com/a, https://example.com/b",
        })
        mock_client.open_dispute.assert_called_once_with(
            "q1",
            reason,
            evidence_urls=["https://example.com/a", "https://example.com/b"],
        )
        assert "d1" in result

    def test_empty_evidence_urls(self, toolkit, mock_client):
        mock_client.open_dispute.return_value = {"id": "d2", "status": "open"}
        tool = _tool_by_name(toolkit.get_tools(), "open_dispute")
        reason = "The resolution is incorrect because the source was retracted and new evidence shows otherwise."
        tool.invoke({"question_id": "q1", "reason": reason})
        mock_client.open_dispute.assert_called_once_with("q1", reason, evidence_urls=None)


# ---------------------------------------------------------------------------
# ListDisputes
# ---------------------------------------------------------------------------

class TestListDisputes:
    def test_returns_disputes(self, toolkit, mock_client):
        mock_client.list_disputes.return_value = [
            {"id": "d1", "status": "open", "disputer_name": "Bot1", "reason": "Wrong resolution"},
        ]
        tool = _tool_by_name(toolkit.get_tools(), "list_disputes")
        result = tool.invoke({"question_id": "q1"})
        assert "d1" in result
        assert "Bot1" in result

    def test_no_disputes(self, toolkit, mock_client):
        mock_client.list_disputes.return_value = []
        tool = _tool_by_name(toolkit.get_tools(), "list_disputes")
        result = tool.invoke({"question_id": "q1"})
        assert "No disputes" in result


# ---------------------------------------------------------------------------
# Follow / Unfollow
# ---------------------------------------------------------------------------

class TestFollowAgent:
    def test_follow(self, toolkit, mock_client):
        tool = _tool_by_name(toolkit.get_tools(), "follow_agent")
        result = tool.invoke({"agent_id": "a1"})
        mock_client.follow_agent.assert_called_once_with("a1")
        assert "following" in result.lower()

    def test_follow_error(self, toolkit, mock_client):
        mock_client.follow_agent.side_effect = Exception("already following")
        tool = _tool_by_name(toolkit.get_tools(), "follow_agent")
        result = tool.invoke({"agent_id": "a1"})
        assert "Follow failed" in result


class TestUnfollowAgent:
    def test_unfollow(self, toolkit, mock_client):
        tool = _tool_by_name(toolkit.get_tools(), "unfollow_agent")
        result = tool.invoke({"agent_id": "a1"})
        mock_client.unfollow_agent.assert_called_once_with("a1")
        assert "unfollowed" in result.lower()

    def test_unfollow_error(self, toolkit, mock_client):
        mock_client.unfollow_agent.side_effect = Exception("not following")
        tool = _tool_by_name(toolkit.get_tools(), "unfollow_agent")
        result = tool.invoke({"agent_id": "a1"})
        assert "Unfollow failed" in result


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

class TestListWatchlist:
    def test_returns_watchlist(self, toolkit, mock_client):
        mock_client.get_watchlist.return_value = [
            {"id": "q1", "question": "Will GPT-5 ship?"},
            {"id": "q2", "question": "Will Gemini 3 beat Claude?"},
        ]
        tool = _tool_by_name(toolkit.get_tools(), "list_watchlist")
        result = tool.invoke({})
        assert "q1" in result
        assert "q2" in result
        assert "2 question(s)" in result

    def test_empty_watchlist(self, toolkit, mock_client):
        mock_client.get_watchlist.return_value = []
        tool = _tool_by_name(toolkit.get_tools(), "list_watchlist")
        result = tool.invoke({})
        assert "empty" in result.lower()


class TestAddToWatchlist:
    def test_add(self, toolkit, mock_client):
        tool = _tool_by_name(toolkit.get_tools(), "add_to_watchlist")
        result = tool.invoke({"question_id": "q1"})
        mock_client.add_to_watchlist.assert_called_once_with("q1")
        assert "added" in result.lower()

    def test_add_error(self, toolkit, mock_client):
        mock_client.add_to_watchlist.side_effect = Exception("already watching")
        tool = _tool_by_name(toolkit.get_tools(), "add_to_watchlist")
        result = tool.invoke({"question_id": "q1"})
        assert "Failed" in result


class TestRemoveFromWatchlist:
    def test_remove(self, toolkit, mock_client):
        tool = _tool_by_name(toolkit.get_tools(), "remove_from_watchlist")
        result = tool.invoke({"question_id": "q1"})
        mock_client.remove_from_watchlist.assert_called_once_with("q1")
        assert "removed" in result.lower()

    def test_remove_error(self, toolkit, mock_client):
        mock_client.remove_from_watchlist.side_effect = Exception("not watching")
        tool = _tool_by_name(toolkit.get_tools(), "remove_from_watchlist")
        result = tool.invoke({"question_id": "q1"})
        assert "Failed" in result


# ---------------------------------------------------------------------------
# MyNotifications
# ---------------------------------------------------------------------------

class TestMyNotifications:
    def test_returns_notifications(self, toolkit, mock_client):
        mock_client.notifications.return_value = [
            {"type": "new_follower", "read": False, "message": "BotX started following you"},
            {"type": "question_resolved", "read": True, "message": "Question resolved: GPT-5"},
        ]
        tool = _tool_by_name(toolkit.get_tools(), "my_notifications")
        result = tool.invoke({})
        assert "new_follower" in result
        assert "UNREAD" in result
        assert "question_resolved" in result

    def test_empty_notifications(self, toolkit, mock_client):
        mock_client.notifications.return_value = []
        tool = _tool_by_name(toolkit.get_tools(), "my_notifications")
        result = tool.invoke({})
        assert "caught up" in result.lower()


# ---------------------------------------------------------------------------
# MyFeed
# ---------------------------------------------------------------------------

class TestMyFeed:
    def test_returns_feed(self, toolkit, mock_client):
        mock_client.feed.return_value = [
            {"type": "prediction", "agent_name": "AlphaBot", "description": "Predicted YES on GPT-5"},
        ]
        tool = _tool_by_name(toolkit.get_tools(), "my_feed")
        result = tool.invoke({})
        assert "AlphaBot" in result
        assert "prediction" in result.lower()

    def test_empty_feed(self, toolkit, mock_client):
        mock_client.feed.return_value = []
        tool = _tool_by_name(toolkit.get_tools(), "my_feed")
        result = tool.invoke({})
        assert "empty" in result.lower()
