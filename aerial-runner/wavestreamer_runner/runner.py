"""
AgentRunner — continuous autonomous prediction loop.

Usage:
    from wavestreamer_runner import AgentRunner
    runner = AgentRunner(api_key="sk_...", agent_id="...")
    runner.run()       # continuous loop
    runner.run_once()  # single prediction cycle
"""

import logging
import os
import signal
import time
from typing import Any

from openai import OpenAI
from wavestreamer import WaveStreamer

from .cycle import run_one_cycle
from .heartbeat import HeartbeatReporter
from .personality import AgentPersonality

logger = logging.getLogger("wavestreamer_runner")

RUNNER_VERSION = "0.1.0"


class AgentRunner:
    """Runs a single agent locally, predicting on a schedule."""

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        *,
        base_url: str = "",
        auth_token: str = "",
        interval_mins: int = 240,
        max_daily: int = 20,
        provider: str = "",
        model: str = "",
        llm_api_key: str = "",
        llm_base_url: str = "",
    ):
        self.agent_id = agent_id
        self.base_url = base_url or os.environ.get("WAVESTREAMER_URL", "https://wavestreamer.ai")
        self.auth_token = auth_token
        self.interval_mins = interval_mins
        self.max_daily = max_daily
        self.preds_today = 0
        self._running = False

        # SDK client (uses agent's API key)
        self.ws = WaveStreamer(self.base_url, api_key=api_key)

        # LLM client
        self.llm = self._build_llm(provider, model, llm_api_key, llm_base_url)
        self.llm_model = model or os.environ.get("OLLAMA_MODEL", "llama3.1")

        # Agent personality from API
        self.personality = self._load_personality()

        # Heartbeat reporter (needs owner's JWT)
        self.heartbeat: HeartbeatReporter | None = None
        if auth_token:
            self.heartbeat = HeartbeatReporter(
                self.base_url, agent_id, auth_token,
                runner_version=RUNNER_VERSION,
            )

    def _build_llm(self, provider: str, model: str, api_key: str, base_url: str) -> OpenAI:
        """Build OpenAI-compatible LLM client."""
        ollama_url = base_url or os.environ.get("OLLAMA_URL", "http://localhost:11434/v1")

        if provider == "ollama" or not provider:
            return OpenAI(base_url=ollama_url, api_key="ollama", timeout=300.0)
        if provider == "openrouter":
            key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
            return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
        if provider == "anthropic":
            return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        if provider == "google":
            return OpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=api_key,
            )
        # Default: ollama
        return OpenAI(base_url=ollama_url, api_key=api_key or "ollama", timeout=300.0)

    def _load_personality(self) -> AgentPersonality:
        """Load agent personality from the API."""
        try:
            me = self.ws.me()
            return AgentPersonality.from_api(me, model=self.llm_model)
        except Exception as e:
            logger.warning("Failed to load personality from API: %s", e)
            return AgentPersonality(name="Agent", model=self.llm_model)

    def run_once(self) -> dict[str, Any]:
        """Run a single prediction cycle and return the result."""
        logger.info("Starting prediction cycle for agent %s", self.agent_id)

        if self.heartbeat:
            self.heartbeat.update(status="predicting", preds_today=self.preds_today)

        result = run_one_cycle(
            self.ws, self.llm, self.personality,
            max_daily=self.max_daily, preds_today=self.preds_today,
        )

        if result["status"] == "ok":
            self.preds_today += 1
            logger.info(
                "Prediction placed: %s (confidence=%s) on Q: %s",
                result.get("prediction_id"), result.get("confidence"),
                result.get("question", "")[:60],
            )
        elif result["status"] == "error":
            logger.error("Cycle failed at step '%s': %s", result.get("step"), result.get("error"))
        else:
            logger.info("Cycle skipped: %s", result.get("reason"))

        if self.heartbeat:
            self.heartbeat.update(
                status="idle", preds_today=self.preds_today,
                last_error=result.get("error", ""),
            )

        return result

    def run(self) -> None:
        """Run continuous prediction loop until stopped."""
        self._running = True
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        logger.info(
            "Starting agent runner: id=%s interval=%dm max_daily=%d",
            self.agent_id, self.interval_mins, self.max_daily,
        )

        # Activate local runtime mode on server
        if self.auth_token:
            self._activate_local_mode()

        if self.heartbeat:
            self.heartbeat.start()

        try:
            while self._running:
                # Check if server has paused us
                if self.heartbeat and self.heartbeat.paused:
                    logger.info("Agent paused by server, waiting...")
                    time.sleep(30)
                    continue

                # Sync config from server
                if self.heartbeat and self.heartbeat.config:
                    cfg = self.heartbeat.config
                    if cfg.get("interval_mins"):
                        self.interval_mins = cfg["interval_mins"]
                    if cfg.get("max_daily_preds"):
                        self.max_daily = cfg["max_daily_preds"]

                self.run_once()

                # Wait with jitter
                wait_secs = self.interval_mins * 60
                jitter = int(wait_secs * 0.2 * (2 * (0.5 - __import__("random").random())))
                total_wait = max(60, wait_secs + jitter)
                logger.info("Next cycle in %d minutes", total_wait // 60)

                # Sleep in 1s increments (responsive to stop signals)
                for _ in range(total_wait):
                    if not self._running:
                        break
                    time.sleep(1)
        finally:
            if self.heartbeat:
                self.heartbeat.update(status="offline")
                self.heartbeat._send()
                self.heartbeat.stop()
            logger.info("Agent runner stopped")

    def _activate_local_mode(self) -> None:
        """Tell the server we're starting in local mode."""
        try:
            import requests
            url = f"{self.base_url}/api/me/agents/{self.agent_id}/runtime/start-local"
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            resp = requests.post(url, headers=headers, timeout=10)
            if resp.ok:
                logger.info("Local runtime mode activated on server")
            else:
                logger.warning("Failed to activate local mode: %s", resp.text[:200])
        except Exception as e:
            logger.warning("Failed to activate local mode: %s", e)

    def _handle_signal(self, signum: int, frame: Any) -> None:
        logger.info("Received signal %d, stopping...", signum)
        self._running = False
