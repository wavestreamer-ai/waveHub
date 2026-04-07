"""WebSocket bridge client for connecting local models to wavestreamer."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger("wavestreamer.bridge")


class BridgeClient:
    """Connects to wavestreamer via WebSocket and routes inference requests to local models."""

    def __init__(self, api_key: str, base_url: str = "wss://wavestreamer.ai"):
        self.api_key = api_key
        self.ws_url = f"{base_url}/api/ws/bridge"
        self.models: list[str] = []
        self.connected = False
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 30.0
        self._ws: Optional[object] = None
        self._stop = False
        self._start_time = 0.0
        self.heartbeat_count = 0

    async def connect(self, models: list[str]) -> None:
        """Connect and run the bridge loop with auto-reconnect."""
        self.models = models
        self._stop = False
        self._start_time = time.time()

        while not self._stop:
            try:
                await self._connect_once()
            except Exception as e:
                if self._stop:
                    break
                logger.warning(f"Connection lost: {e}. Reconnecting in {self.reconnect_delay:.0f}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    async def _connect_once(self) -> None:
        """Single connection attempt."""
        import websockets

        headers = {"X-API-Key": self.api_key}
        async with websockets.connect(self.ws_url, additional_headers=headers) as ws:
            self._ws = ws
            self.connected = True
            self.reconnect_delay = 1.0  # Reset backoff on successful connect
            logger.info("Connected to wavestreamer bridge")

            # Send initial heartbeat with models
            await self._send_heartbeat()

            # Run heartbeat + message handler concurrently
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    await self._handle_message(msg)
            finally:
                heartbeat_task.cancel()
                self.connected = False

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat every 30 seconds."""
        while True:
            await asyncio.sleep(30)
            await self._send_heartbeat()

    async def _send_heartbeat(self) -> None:
        """Send heartbeat with model list and uptime."""
        if self._ws:
            uptime = int(time.time() - self._start_time) if self._start_time else 0
            await self._ws.send(json.dumps({
                "type": "heartbeat",
                "payload": {"models": self.models, "uptime_seconds": uptime, "runner_source": "bridge"},
            }))
            self.heartbeat_count += 1

    async def _handle_message(self, msg: dict) -> None:
        """Handle incoming messages from server."""
        msg_type = msg.get("type")
        if msg_type == "infer_request":
            await self._handle_inference(msg)

    async def _handle_inference(self, msg: dict) -> None:
        """Handle an inference request by calling local Ollama."""
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        model = payload.get("model", "")
        system_prompt = payload.get("system_prompt", "")
        messages = payload.get("messages", [])

        try:
            # Build Ollama chat request
            ollama_messages: list[dict] = []
            if system_prompt:
                ollama_messages.append({"role": "system", "content": system_prompt})
            ollama_messages.extend(messages)

            body = json.dumps({
                "model": model,
                "messages": ollama_messages,
                "stream": True,
            }).encode()

            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=body,
                headers={"Content-Type": "application/json"},
            )

            full_response = ""
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        full_response += content
                        if self._ws:
                            await self._ws.send(json.dumps({
                                "type": "infer_chunk",
                                "request_id": request_id,
                                "payload": {"content": content},
                            }))

            if self._ws:
                await self._ws.send(json.dumps({
                    "type": "infer_done",
                    "request_id": request_id,
                    "payload": {"full_response": full_response},
                }))

        except Exception as e:
            logger.error(f"Inference error: {e}")
            if self._ws:
                await self._ws.send(json.dumps({
                    "type": "infer_error",
                    "request_id": request_id,
                    "payload": {"error": str(e)},
                }))

    def stop(self) -> None:
        """Signal the bridge to stop."""
        self._stop = True
