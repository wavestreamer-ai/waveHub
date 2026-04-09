"""Tests for bridge client and detect modules."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock
import io
import http.client

import pytest

from wavestreamer.bridge.detect import (
    detect_ollama,
    detect_openai_compatible,
    detect_all,
    LocalModel,
)
from wavestreamer.bridge.client import (
    _collect_system_info_static,
    _collect_system_info_dynamic,
    _collect_ollama_status,
)


# ── detect_ollama ───────────────────────────────────────────


class TestDetectOllama:
    def test_returns_models_on_success(self):
        response_data = json.dumps({
            "models": [
                {
                    "name": "qwen2.5:14b",
                    "details": {"parameter_size": "14.8B"},
                    "modified_at": "2026-01-01T00:00:00Z",
                },
                {
                    "name": "llama3:7b",
                    "details": {},
                    "modified_at": "",
                },
            ]
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            models = detect_ollama()

        assert len(models) == 2
        assert models[0].name == "qwen2.5:14b"
        assert models[0].provider == "ollama"
        assert models[0].size == "14.8B"
        assert models[1].name == "llama3:7b"
        assert models[1].size == "7B"  # parsed from name

    def test_returns_empty_on_connection_error(self):
        with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
            models = detect_ollama()
        assert models == []


# ── detect_openai_compatible ────────────────────────────────


class TestDetectOpenAICompatible:
    def test_returns_models_from_v1_models(self):
        response_data = json.dumps({
            "data": [
                {"id": "qwen2.5-14b-instruct", "object": "model", "owned_by": "local"},
                {"id": "llama-3.1-8b", "object": "model"},
            ]
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            models = detect_openai_compatible("http://localhost:1234", "lmstudio")

        assert len(models) == 2
        assert models[0].name == "qwen2.5-14b-instruct"
        assert models[0].provider == "lmstudio"

    def test_returns_empty_on_failure(self):
        with patch("urllib.request.urlopen", side_effect=OSError("fail")):
            models = detect_openai_compatible("http://localhost:9999", "custom")
        assert models == []

    def test_appends_v1_if_missing(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": []}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            detect_openai_compatible("http://localhost:1234", "test")
            # Should have called with /v1/models
            called_url = mock_open.call_args[0][0].full_url
            assert "/v1/models" in called_url


# ── detect_all ──────────────────────────────────────────────


class TestDetectAll:
    def test_combines_all_sources(self):
        ollama_models = [LocalModel("model1", "ollama", "7B", "")]
        mlx_models = [LocalModel("model2", "mlx", "14B", "")]

        with patch("wavestreamer.bridge.detect.detect_ollama", return_value=ollama_models), \
             patch("wavestreamer.bridge.detect.detect_mlx", return_value=mlx_models), \
             patch("wavestreamer.bridge.detect.detect_openai_compatible", return_value=[]):
            models = detect_all()

        assert len(models) >= 2
        names = [m.name for m in models]
        assert "model1" in names
        assert "model2" in names

    def test_extra_endpoints_probed(self):
        with patch("wavestreamer.bridge.detect.detect_ollama", return_value=[]), \
             patch("wavestreamer.bridge.detect.detect_mlx", return_value=[]), \
             patch("wavestreamer.bridge.detect.detect_openai_compatible") as mock_probe:
            mock_probe.return_value = [LocalModel("custom-model", "custom", "", "")]
            models = detect_all(extra_endpoints=[("http://localhost:9000", "custom")])

        # Should have been called for known endpoints + the extra one
        assert mock_probe.call_count >= 1
        # Check that custom endpoint was probed
        calls = [c[0] for c in mock_probe.call_args_list]
        urls = [c[0] for c in calls]
        assert "http://localhost:9000" in urls


# ── system info collection ──────────────────────────────────


class TestSystemInfoCollection:
    def test_static_info_has_required_fields(self):
        info = _collect_system_info_static()
        assert "platform" in info
        assert "arch" in info
        assert "hostname" in info
        assert "cpu_cores" in info
        assert info["cpu_cores"] > 0

    def test_dynamic_info_returns_dict(self):
        info = _collect_system_info_dynamic()
        assert isinstance(info, dict)
        # Should have at least disk_free_gb (cross-platform)
        if "disk_free_gb" in info:
            assert info["disk_free_gb"] >= 0

    def test_ollama_status_offline(self):
        with patch("urllib.request.urlopen", side_effect=OSError("fail")):
            info = _collect_ollama_status("http://localhost:11434")
        assert info["ollama_running"] is False
        assert info["ollama_loaded_count"] == 0
        assert info["ollama_loaded"] == []

    def test_ollama_status_with_loaded_models(self):
        response_data = json.dumps({
            "models": [
                {
                    "name": "qwen2.5:14b",
                    "size": 9663676416,
                    "size_vram": 9663676416,
                    "size_ram": 0,
                    "expires_at": "2026-04-10T15:30:00Z",
                },
            ]
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            info = _collect_ollama_status("http://localhost:11434")

        assert info["ollama_running"] is True
        assert info["ollama_loaded_count"] == 1
        assert len(info["ollama_loaded"]) == 1
        assert info["ollama_loaded"][0]["name"] == "qwen2.5:14b"
        assert info["ollama_loaded"][0]["vram_gb"] > 0
