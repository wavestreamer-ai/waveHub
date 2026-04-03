"""
Heartbeat reporter — periodically pings the server with local runner status.

Runs in a background thread so the main prediction loop isn't blocked.
The server uses heartbeats to:
  1. Show live status in the Runtime UI
  2. Update the sidebar green dot (last_active_at)
  3. Push config changes back to the runner (interval, pause, etc.)
"""

import logging
import threading
import time
from typing import Any

import requests

logger = logging.getLogger("wavestreamer_fleet.runner")


class HeartbeatReporter:
    """Background heartbeat sender for local runners."""

    def __init__(
        self,
        base_url: str,
        agent_id: str,
        auth_token: str,
        *,
        interval: int = 30,
        runner_version: str = "0.1.0",
    ):
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.auth_token = auth_token
        self.interval = interval
        self.runner_version = runner_version
        self._status = "online"
        self._preds_today = 0
        self._last_error = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_config: dict[str, Any] = {}

    def start(self) -> None:
        """Start the heartbeat background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="heartbeat")
        self._thread.start()
        logger.info("Heartbeat reporter started (every %ds)", self.interval)

    def stop(self) -> None:
        """Stop the heartbeat background thread."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Heartbeat reporter stopped")

    def update(self, status: str = "", preds_today: int | None = None, last_error: str = "") -> None:
        """Update heartbeat payload (called from the prediction loop)."""
        if status:
            self._status = status
        if preds_today is not None:
            self._preds_today = preds_today
        self._last_error = last_error

    @property
    def config(self) -> dict[str, Any]:
        """Latest config received from server (interval, paused, max_daily_preds)."""
        return self._last_config

    @property
    def paused(self) -> bool:
        """Check if server has paused this agent."""
        return self._last_config.get("paused", False)

    def _loop(self) -> None:
        """Background loop — send heartbeat every `interval` seconds."""
        while not self._stop.is_set():
            try:
                self._send()
            except Exception as e:
                logger.debug(f"Heartbeat send failed: {e}")
            self._stop.wait(self.interval)

    def _send(self) -> None:
        """Send a single heartbeat to the server."""
        url = f"{self.base_url}/api/me/agents/{self.agent_id}/runtime/heartbeat"
        payload = {
            "status": self._status,
            "preds_today": self._preds_today,
            "last_error": self._last_error,
            "runner_version": self.runner_version,
        }
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.ok:
            data = resp.json()
            self._last_config = data
            logger.debug(f"Heartbeat ack: paused={data.get('paused')}, interval={data.get('interval_mins')}")
        else:
            logger.debug(f"Heartbeat {resp.status_code}: {resp.text[:200]}")
