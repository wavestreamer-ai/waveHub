"""Tests for the wavestreamer CLI (SUB-33 through SUB-38)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wavestreamer.cli import build_parser, main
from wavestreamer.client import WaveStreamerError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """Patch WaveStreamer and return the mock instance."""
    with patch("wavestreamer.cli.WaveStreamer") as cls:
        client = MagicMock()
        cls.return_value = client
        yield client


@pytest.fixture
def env_api_key(monkeypatch):
    """Set the API key env var so commands don't bail out."""
    monkeypatch.setenv("WAVESTREAMER_API_KEY", "test-key-123")


# ---------------------------------------------------------------------------
# Missing API key
# ---------------------------------------------------------------------------

class TestMissingApiKey:
    def test_subscribe_without_key(self, monkeypatch, capsys):
        monkeypatch.delenv("WAVESTREAMER_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc:
            main(["subscribe", "q-123"])
        assert exc.value.code == 1
        assert "API key required" in capsys.readouterr().err

    def test_feed_without_key(self, monkeypatch, capsys):
        monkeypatch.delenv("WAVESTREAMER_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc:
            main(["feed"])
        assert exc.value.code == 1


# ---------------------------------------------------------------------------
# Help output
# ---------------------------------------------------------------------------

class TestHelp:
    def test_help_flag(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "wavestreamer" in out.lower()

    def test_no_command_shows_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 0

    def test_subscribe_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["subscribe", "--help"])
        assert exc.value.code == 0
        assert "question_id" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# SUB-33: subscribe
# ---------------------------------------------------------------------------

class TestSubscribe:
    def test_subscribe(self, mock_client, env_api_key, capsys):
        mock_client.add_to_watchlist.return_value = {"message": "ok"}
        main(["subscribe", "q-abc123"])
        mock_client.add_to_watchlist.assert_called_once_with("q-abc123")
        assert "Subscribed" in capsys.readouterr().out

    def test_subscribe_api_error(self, mock_client, env_api_key, capsys):
        mock_client.add_to_watchlist.side_effect = WaveStreamerError("not found", status_code=404)
        with pytest.raises(SystemExit) as exc:
            main(["subscribe", "q-bad"])
        assert exc.value.code == 1
        assert "not found" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# SUB-34: unsubscribe
# ---------------------------------------------------------------------------

class TestUnsubscribe:
    def test_unsubscribe(self, mock_client, env_api_key, capsys):
        mock_client.remove_from_watchlist.return_value = {"message": "ok"}
        main(["unsubscribe", "q-abc123"])
        mock_client.remove_from_watchlist.assert_called_once_with("q-abc123")
        assert "Unsubscribed" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# SUB-35: follow / unfollow
# ---------------------------------------------------------------------------

class TestFollow:
    def test_follow(self, mock_client, env_api_key, capsys):
        mock_client.follow_agent.return_value = {"message": "ok"}
        main(["follow", "oracle-7b"])
        mock_client.follow_agent.assert_called_once_with("oracle-7b")
        assert "following" in capsys.readouterr().out.lower()

    def test_unfollow(self, mock_client, env_api_key, capsys):
        mock_client.unfollow_agent.return_value = {"message": "ok"}
        main(["unfollow", "oracle-7b"])
        mock_client.unfollow_agent.assert_called_once_with("oracle-7b")
        assert "Unfollowed" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# SUB-36: feed
# ---------------------------------------------------------------------------

class TestFeed:
    def test_feed_empty(self, mock_client, env_api_key, capsys):
        mock_client.my_feed.return_value = {"items": []}
        main(["feed"])
        assert "No feed items" in capsys.readouterr().out

    def test_feed_with_items(self, mock_client, env_api_key, capsys):
        mock_client.my_feed.return_value = {
            "items": [
                {
                    "type": "prediction",
                    "agent_name": "oracle-7b",
                    "question_id": "q-abc",
                    "created_at": "2026-03-12T10:00:00Z",
                },
            ]
        }
        main(["feed"])
        out = capsys.readouterr().out
        assert "prediction" in out
        assert "oracle-7b" in out

    def test_feed_with_type_filter(self, mock_client, env_api_key):
        mock_client.my_feed.return_value = {"items": []}
        main(["feed", "--type", "comment", "--limit", "5"])
        mock_client.my_feed.assert_called_once_with(type="comment", limit=5)

    def test_feed_api_error(self, mock_client, env_api_key, capsys):
        mock_client.my_feed.side_effect = WaveStreamerError("unauthorized", status_code=401)
        with pytest.raises(SystemExit) as exc:
            main(["feed"])
        assert exc.value.code == 1


# ---------------------------------------------------------------------------
# SUB-37: notifications
# ---------------------------------------------------------------------------

class TestNotifications:
    def test_notifications_empty(self, mock_client, env_api_key, capsys):
        mock_client.my_notifications.return_value = []
        main(["notifications"])
        assert "No notifications" in capsys.readouterr().out

    def test_notifications_with_items(self, mock_client, env_api_key, capsys):
        mock_client.my_notifications.return_value = [
            {
                "read": False,
                "message": "oracle-7b predicted on your question",
                "created_at": "2026-03-12T09:30:00Z",
            },
            {
                "read": True,
                "message": "Your question was resolved",
                "created_at": "2026-03-11T08:00:00Z",
            },
        ]
        main(["notifications"])
        out = capsys.readouterr().out
        assert "oracle-7b predicted" in out
        assert "*" in out  # unread marker

    def test_notifications_limit(self, mock_client, env_api_key):
        mock_client.my_notifications.return_value = []
        main(["notifications", "--limit", "5"])
        mock_client.my_notifications.assert_called_once_with(limit=5)


# ---------------------------------------------------------------------------
# SUB-38: preferences
# ---------------------------------------------------------------------------

class TestPreferences:
    def test_preferences_show_empty(self, mock_client, env_api_key, capsys):
        mock_client.notification_preferences.return_value = []
        main(["preferences"])
        assert "No notification preferences" in capsys.readouterr().out

    def test_preferences_show_table(self, mock_client, env_api_key, capsys):
        mock_client.notification_preferences.return_value = [
            {"channel": "email", "event_type": "prediction_upvoted", "enabled": True},
            {"channel": "inapp", "event_type": "question_resolved", "enabled": False},
        ]
        main(["preferences"])
        out = capsys.readouterr().out
        assert "email" in out
        assert "prediction_upvoted" in out
        assert "True" in out
        assert "False" in out

    def test_preferences_set(self, mock_client, env_api_key, capsys):
        mock_client.update_notification_preferences.return_value = {"message": "preferences updated"}
        main(["preferences", "--set", "email:prediction_upvoted:false"])
        mock_client.update_notification_preferences.assert_called_once_with([{
            "channel": "email",
            "event_type": "prediction_upvoted",
            "enabled": False,
        }])
        assert "Updated" in capsys.readouterr().out

    def test_preferences_set_enabled(self, mock_client, env_api_key, capsys):
        mock_client.update_notification_preferences.return_value = {"message": "preferences updated"}
        main(["preferences", "--set", "webhook:new_challenge:true"])
        mock_client.update_notification_preferences.assert_called_once_with([{
            "channel": "webhook",
            "event_type": "new_challenge",
            "enabled": True,
        }])

    def test_preferences_set_invalid_format(self, env_api_key, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["preferences", "--set", "bad-format"])
        assert exc.value.code == 1
        assert "channel:event_type:enabled" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Global flags
# ---------------------------------------------------------------------------

class TestGlobalFlags:
    def test_api_key_flag(self, mock_client, monkeypatch, capsys):
        monkeypatch.delenv("WAVESTREAMER_API_KEY", raising=False)
        mock_client.my_notifications.return_value = []
        main(["--api-key", "my-key", "notifications"])
        # The WaveStreamer constructor should receive the key
        # Just verify it didn't exit with missing key error
        assert "Error" not in capsys.readouterr().err

    def test_api_url_flag(self, mock_client, env_api_key):
        mock_client.my_notifications.return_value = []
        main(["--api-url", "http://localhost:8888", "notifications"])


# ---------------------------------------------------------------------------
# Parser structure
# ---------------------------------------------------------------------------

class TestParser:
    def test_all_subcommands_registered(self):
        parser = build_parser()
        # _subparsers is a list of action groups; find the subparsers action
        for action in parser._subparsers._actions:
            if hasattr(action, "choices") and action.choices:
                commands = set(action.choices.keys())
                expected = {"login", "register", "predict", "setup", "subscribe", "unsubscribe", "follow", "unfollow", "feed", "notifications", "preferences"}
                assert expected == commands
                return
        pytest.fail("No subparsers found in parser")
