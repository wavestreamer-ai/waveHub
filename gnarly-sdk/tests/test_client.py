"""Tests for the WaveStreamer SDK client."""

from unittest.mock import MagicMock, patch

import pytest

from wavestreamer import WaveStreamer, WaveStreamerError
from wavestreamer.client import Prediction, Question, _raise_for_response

# ---------------------------------------------------------------------------
# Helpers & sample data
# ---------------------------------------------------------------------------

def make_ok_response(json_data, status_code=200):
    resp = MagicMock()
    resp.ok = True
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def make_error_response(status_code, error_msg="request failed", code=""):
    resp = MagicMock()
    resp.ok = False
    resp.status_code = status_code
    resp.json.return_value = {"error": error_msg, "code": code}
    resp.reason = error_msg
    return resp


SAMPLE_QUESTION = {
    "id": "q-abc123",
    "question": "Will GPT-5 launch by end of 2026?",
    "category": "intelligence",
    "timeframe": "mid",
    "resolution_source": "Official OpenAI announcement",
    "resolution_date": "2026-12-31",
    "status": "open",
    "yes_count": 12,
    "no_count": 4,
    "question_type": "binary",
}

SAMPLE_PREDICTION = {
    "id": "pred-xyz789",
    "question_id": "q-abc123",
    "prediction": True,
    "confidence": 80,
    "reasoning": "Strong evidence points to a launch.",
}

# Reasoning that passes client-side validation: 200+ chars, 30+ unique words, 2+ URLs
VALID_REASONING = (
    "## Evidence\n"
    "According to recent industry analysis, multiple credible sources confirm significant "
    "progress toward this milestone. The technical infrastructure and organizational readiness "
    "indicators all point strongly in this direction based on observable deployment patterns.\n\n"
    "## Sources\n"
    "- https://example.com/report-2026 \n"
    "- https://techreview.example.org/analysis \n\n"
    "## Bottom Line\n"
    "The convergence of evidence suggests high probability of occurrence within the stated timeframe."
)

VALID_RESOLUTION_PROTOCOL = {
    "criterion": "Official announcement by 2026-12-31",
    "source_of_truth": "Company press release",
    "deadline": "2026-12-31T00:00:00Z",
    "resolver": "platform",
    "edge_cases": "Partial announcements don't count",
}


# ---------------------------------------------------------------------------
# Client initialization
# ---------------------------------------------------------------------------

class TestClientInit:
    def test_default_base_url(self):
        with patch("wavestreamer.client.requests.Session"):
            client = WaveStreamer()
        assert client.base_url == "https://wavestreamer.ai"

    def test_custom_base_url_strips_trailing_slash(self):
        with patch("wavestreamer.client.requests.Session"):
            client = WaveStreamer("http://localhost:8888/")
        assert client.base_url == "http://localhost:8888"

    def test_api_key_stored_and_set_in_session(self, mock_session):
        client = WaveStreamer("http://localhost:8888", api_key="sk_test_key")
        assert client.api_key == "sk_test_key"
        mock_session.headers.__setitem__.assert_any_call("X-API-Key", "sk_test_key")

    def test_admin_key_stored(self, mock_session):
        client = WaveStreamer("http://localhost:8888", admin_key="adm_key")
        assert client.admin_key == "adm_key"


# ---------------------------------------------------------------------------
# questions() — GET /api/questions
# ---------------------------------------------------------------------------

class TestGetQuestions:
    def test_returns_list_of_question_objects(self, mock_session):
        mock_session.request.return_value = make_ok_response(
            {"questions": [SAMPLE_QUESTION]}
        )
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        result = client.questions()
        assert len(result) == 1
        assert isinstance(result[0], Question)
        assert result[0].id == "q-abc123"
        assert result[0].yes_count == 12

    def test_passes_status_param(self, mock_session):
        mock_session.request.return_value = make_ok_response({"questions": []})
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        client.questions(status="closed")
        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["params"]["status"] == "closed"

    def test_empty_list_when_no_questions(self, mock_session):
        mock_session.request.return_value = make_ok_response({"questions": []})
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        result = client.questions()
        assert result == []


# ---------------------------------------------------------------------------
# predict() — POST /api/questions/:id/predict
# ---------------------------------------------------------------------------

class TestMakePrediction:
    def test_predict_with_probability(self, mock_session):
        mock_session.request.return_value = make_ok_response(
            {"prediction": SAMPLE_PREDICTION}
        )
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        result = client.predict(
            "q-abc123",
            reasoning=VALID_REASONING,
            probability=80,
            resolution_protocol=VALID_RESOLUTION_PROTOCOL,
        )
        assert isinstance(result, Prediction)
        assert result.id == "pred-xyz789"
        # Verify the body sent
        body = mock_session.request.call_args[1]["json"]
        assert body["probability"] == 80
        assert "resolution_protocol" in body

    def test_predict_returns_prediction_object(self, mock_session):
        mock_session.request.return_value = make_ok_response(
            {"prediction": SAMPLE_PREDICTION}
        )
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        pred = client.predict(
            "q-abc123",
            reasoning=VALID_REASONING,
            probability=75,
            resolution_protocol=VALID_RESOLUTION_PROTOCOL,
        )
        assert pred.prediction is True
        assert pred.confidence == 80


# ---------------------------------------------------------------------------
# register() — POST /api/register
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_sets_api_key(self, mock_session):
        mock_session.request.return_value = make_ok_response(
            {"api_key": "sk_new_abc", "user": {"id": "u1", "name": "Bot", "points": 5000}},
            status_code=201,
        )
        client = WaveStreamer("http://localhost:8888")
        result = client.register(
            "TestBot",
            model="gpt-4o",
            persona_archetype="data_driven",
            risk_profile="moderate",
        )
        assert client.api_key == "sk_new_abc"
        assert result["user"]["points"] == 5000

    def test_register_missing_model_raises_valueerror(self, mock_session):
        client = WaveStreamer("http://localhost:8888")
        with pytest.raises(ValueError, match="model is required"):
            client.register("Bot", model="", persona_archetype="data_driven", risk_profile="moderate")


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_non_200_raises_wavestreamer_error(self, mock_session):
        mock_session.request.return_value = make_error_response(
            403, "agent not linked", "AGENT_NOT_LINKED"
        )
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        with pytest.raises(WaveStreamerError) as exc_info:
            client.questions()
        assert exc_info.value.status_code == 403
        assert exc_info.value.code == "AGENT_NOT_LINKED"

    def test_raise_for_response_ok_does_nothing(self):
        resp = MagicMock()
        resp.ok = True
        _raise_for_response(resp)  # should not raise

    def test_raise_for_response_non_json_error(self):
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 500
        resp.json.side_effect = ValueError("no json")
        resp.reason = "Internal Server Error"
        with pytest.raises(WaveStreamerError) as exc_info:
            _raise_for_response(resp)
        assert exc_info.value.status_code == 500
        assert "Internal Server Error" in str(exc_info.value)


# ---------------------------------------------------------------------------
# get_watchlist() — GET /api/me/watchlist
# ---------------------------------------------------------------------------

class TestGetWatchlist:
    def test_returns_list_of_questions(self, mock_session):
        mock_session.request.return_value = make_ok_response(
            {"questions": [{"id": "q1", "question": "Will X happen?"}]}
        )
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        result = client.get_watchlist()
        assert len(result) == 1
        assert result[0]["id"] == "q1"

    def test_passes_limit_param(self, mock_session):
        mock_session.request.return_value = make_ok_response({"questions": []})
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        client.get_watchlist(limit=10)
        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["params"]["limit"] == 10

    def test_empty_list_when_no_watchlist(self, mock_session):
        mock_session.request.return_value = make_ok_response({"questions": []})
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        result = client.get_watchlist()
        assert result == []

    def test_error_raises(self, mock_session):
        mock_session.request.return_value = make_error_response(401, "unauthorized")
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        with pytest.raises(WaveStreamerError) as exc_info:
            client.get_watchlist()
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# my_feed() — GET /api/me/feed
# ---------------------------------------------------------------------------

class TestMyFeed:
    def test_returns_feed_dict(self, mock_session):
        mock_session.request.return_value = make_ok_response(
            {"items": [{"type": "prediction", "id": "f1"}], "next_cursor": "abc"}
        )
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        result = client.my_feed()
        assert "items" in result
        assert result["next_cursor"] == "abc"

    def test_passes_filter_params(self, mock_session):
        mock_session.request.return_value = make_ok_response({"items": []})
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        client.my_feed(type="prediction", source="following", cursor="cur123", limit=5)
        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["params"]["type"] == "prediction"
        assert call_kwargs["params"]["source"] == "following"
        assert call_kwargs["params"]["cursor"] == "cur123"
        assert call_kwargs["params"]["limit"] == 5

    def test_omits_empty_optional_params(self, mock_session):
        mock_session.request.return_value = make_ok_response({"items": []})
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        client.my_feed()
        call_kwargs = mock_session.request.call_args[1]
        assert "type" not in call_kwargs["params"]
        assert "source" not in call_kwargs["params"]
        assert "cursor" not in call_kwargs["params"]


# ---------------------------------------------------------------------------
# my_notifications() — GET /api/me/notifications
# ---------------------------------------------------------------------------

class TestMyNotifications:
    def test_returns_list(self, mock_session):
        mock_session.request.return_value = make_ok_response(
            {"notifications": [{"id": "n1", "type": "prediction_resolved"}]}
        )
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        result = client.my_notifications()
        assert len(result) == 1
        assert result[0]["type"] == "prediction_resolved"

    def test_passes_limit(self, mock_session):
        mock_session.request.return_value = make_ok_response({"notifications": []})
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        client.my_notifications(limit=5)
        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["params"]["limit"] == 5

    def test_empty_when_no_notifications(self, mock_session):
        mock_session.request.return_value = make_ok_response({"notifications": []})
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        assert client.my_notifications() == []


# ---------------------------------------------------------------------------
# link_agent() — POST /api/me/agents
# ---------------------------------------------------------------------------

class TestLinkAgent:
    def test_sends_jwt_and_agent_key(self, mock_session):
        mock_session.request.return_value = make_ok_response(
            {"message": "agent linked", "agent": {"id": "a1"}}
        )
        client = WaveStreamer("http://localhost:8888")
        result = client.link_agent("jwt_human_token", "sk_agent_key")
        assert result["message"] == "agent linked"
        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["json"]["agent_api_key"] == "sk_agent_key"
        assert call_kwargs["headers"]["Authorization"] == "Bearer jwt_human_token"

    def test_error_raises(self, mock_session):
        mock_session.request.return_value = make_error_response(403, "forbidden")
        client = WaveStreamer("http://localhost:8888")
        with pytest.raises(WaveStreamerError) as exc_info:
            client.link_agent("bad_jwt", "sk_key")
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# apply_for_guardian() — POST /api/me/apply-guardian
# ---------------------------------------------------------------------------

class TestApplyForGuardian:
    def test_apply_with_motivation(self, mock_session):
        mock_session.request.return_value = make_ok_response(
            {"message": "application submitted", "application": {"id": "app1"}}
        )
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        result = client.apply_for_guardian(motivation="I want to help moderate")
        assert result["message"] == "application submitted"
        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["json"]["motivation"] == "I want to help moderate"

    def test_apply_without_motivation(self, mock_session):
        mock_session.request.return_value = make_ok_response({"message": "ok"})
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        client.apply_for_guardian()
        call_kwargs = mock_session.request.call_args[1]
        assert "motivation" not in call_kwargs["json"]

    def test_error_raises(self, mock_session):
        mock_session.request.return_value = make_error_response(400, "already applied")
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        with pytest.raises(WaveStreamerError):
            client.apply_for_guardian()


# ---------------------------------------------------------------------------
# community_stats() — GET /api/community/stats
# ---------------------------------------------------------------------------

class TestCommunityStats:
    def test_returns_stats_dict(self, mock_session):
        mock_session.request.return_value = make_ok_response(
            {"total_agents": 288, "total_predictions": 5000, "total_questions": 120}
        )
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        result = client.community_stats()
        assert result["total_agents"] == 288
        assert result["total_predictions"] == 5000

    def test_no_json_body_sent(self, mock_session):
        mock_session.request.return_value = make_ok_response({"total_agents": 0})
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        client.community_stats()
        call_kwargs = mock_session.request.call_args[1]
        assert "json" not in call_kwargs

    def test_error_raises(self, mock_session):
        mock_session.request.return_value = make_error_response(403, "forbidden")
        client = WaveStreamer("http://localhost:8888", api_key="sk_test")
        with pytest.raises(WaveStreamerError) as exc_info:
            client.community_stats()
        assert exc_info.value.status_code == 403
