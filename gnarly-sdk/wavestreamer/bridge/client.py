"""WebSocket bridge client for connecting local models to wavestreamer."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shutil
import socket
import time
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger("wavestreamer.bridge")


class BridgeClient:
    """Connects to wavestreamer via WebSocket and routes inference requests to local models.

    Supports multiple local inference backends:
    - Ollama (default): localhost:11434, uses /api/chat
    - OpenAI-compatible (LM Studio, vLLM, LocalAI): uses /v1/chat/completions

    Args:
        api_key: waveStreamer API key for authentication.
        base_url: WebSocket base URL for the waveStreamer server.
        inference_url: Local inference endpoint base URL (default: http://localhost:11434).
        provider_type: "ollama" (default) or "openai-compatible".
        inference_api_key: API key for the local inference endpoint (optional, for OpenAI-compat).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "wss://wavestreamer.ai",
        inference_url: str = "http://localhost:11434",
        provider_type: str = "ollama",
        inference_api_key: str = "",
    ):
        self.api_key = api_key
        self.ws_url = f"{base_url}/api/ws/bridge"
        self.inference_url = inference_url.rstrip("/")
        self.provider_type = provider_type
        self.inference_api_key = inference_api_key
        self.models: list[str] = []
        self.connected = False
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 30.0
        self._ws: Optional[object] = None
        self._stop = False
        self._start_time = 0.0
        self.heartbeat_count = 0
        self._system_info: dict = {}

    async def connect(self, models: list[str]) -> None:
        """Connect and run the bridge loop with auto-reconnect."""
        self.models = models
        self._stop = False
        self._start_time = time.time()
        self._system_info = _collect_system_info_static()

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
            self.reconnect_delay = 1.0
            logger.info("Connected to wavestreamer bridge")

            await self._send_heartbeat()

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
        """Send heartbeat with model list, uptime, and system info."""
        if not self._ws:
            return

        uptime = int(time.time() - self._start_time) if self._start_time else 0

        # Merge static hardware info with dynamic metrics
        system_info = {**self._system_info}
        dynamic = _collect_system_info_dynamic()
        system_info.update(dynamic)

        # Add Ollama-specific info if running Ollama
        if self.provider_type == "ollama":
            ollama_info = _collect_ollama_status(self.inference_url)
            system_info.update(ollama_info)

        await self._ws.send(json.dumps({
            "type": "heartbeat",
            "payload": {
                "models": self.models,
                "uptime_seconds": uptime,
                "runner_source": "bridge",
                "system_info": system_info,
            },
        }))
        self.heartbeat_count += 1

    async def _handle_message(self, msg: dict) -> None:
        """Handle incoming messages from server."""
        msg_type = msg.get("type")
        if msg_type == "infer_request":
            await self._handle_inference(msg)

    async def _handle_inference(self, msg: dict) -> None:
        """Handle an inference request by calling the local inference endpoint.

        Supports both Ollama (/api/chat) and OpenAI-compatible (/v1/chat/completions)
        formats. The provider_type can be overridden per-request via the payload.
        """
        request_id = msg.get("request_id", "")
        payload = msg.get("payload", {})
        model = payload.get("model", "")
        system_prompt = payload.get("system_prompt", "")
        messages = payload.get("messages", [])

        # Allow per-request override of provider type and base URL
        req_provider = payload.get("provider_type", self.provider_type)
        req_base_url = payload.get("base_url", self.inference_url).rstrip("/")

        try:
            # Build messages list
            all_messages: list[dict] = []
            if system_prompt:
                all_messages.append({"role": "system", "content": system_prompt})
            all_messages.extend(messages)

            if req_provider == "openai-compatible":
                await self._infer_openai_compat(request_id, model, all_messages, req_base_url)
            else:
                await self._infer_ollama(request_id, model, all_messages, req_base_url)

        except Exception as e:
            logger.error(f"Inference error: {e}")
            if self._ws:
                await self._ws.send(json.dumps({
                    "type": "infer_error",
                    "request_id": request_id,
                    "payload": {"error": str(e)},
                }))

    async def _infer_ollama(self, request_id: str, model: str, messages: list[dict], base_url: str) -> None:
        """Route inference through Ollama's native /api/chat endpoint."""
        body = json.dumps({
            "model": model,
            "messages": messages,
            "stream": True,
        }).encode()

        req = urllib.request.Request(
            f"{base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
        )

        full_response = ""
        with urllib.request.urlopen(req, timeout=300) as resp:
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

    async def _infer_openai_compat(self, request_id: str, model: str, messages: list[dict], base_url: str) -> None:
        """Route inference through an OpenAI-compatible /v1/chat/completions endpoint.

        Works with LM Studio, vLLM, LocalAI, text-generation-webui, etc.
        """
        body = json.dumps({
            "model": model,
            "messages": messages,
            "stream": True,
        }).encode()

        headers = {"Content-Type": "application/json"}
        if self.inference_api_key:
            headers["Authorization"] = f"Bearer {self.inference_api_key}"

        # Ensure /v1 path
        url = base_url
        if not url.endswith("/v1"):
            url = f"{url}/v1"
        url = f"{url}/chat/completions"

        req = urllib.request.Request(url, data=body, headers=headers)

        full_response = ""
        with urllib.request.urlopen(req, timeout=300) as resp:
            for line in resp:
                line_str = line.decode("utf-8").strip()
                if not line_str or not line_str.startswith("data: "):
                    continue
                data_str = line_str[6:]  # strip "data: " prefix
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_response += content
                            if self._ws:
                                await self._ws.send(json.dumps({
                                    "type": "infer_chunk",
                                    "request_id": request_id,
                                    "payload": {"content": content},
                                }))
                except json.JSONDecodeError:
                    continue

        if self._ws:
            await self._ws.send(json.dumps({
                "type": "infer_done",
                "request_id": request_id,
                "payload": {"full_response": full_response},
            }))

    def stop(self) -> None:
        """Signal the bridge to stop."""
        self._stop = True


# ── System Info Collection (platform-aware) ─────────────────────

def _collect_system_info_static() -> dict:
    """Collect static hardware info (doesn't change during session).

    Platform-aware:
    - macOS: sysctl for CPU/RAM, system_profiler for GPU
    - Linux: /proc/cpuinfo, /proc/meminfo, lspci for GPU
    - Windows: wmic for CPU/RAM/GPU
    """
    info: dict = {
        "platform": platform.system().lower(),  # "darwin", "linux", "windows"
        "arch": platform.machine(),             # "arm64", "x86_64"
        "hostname": socket.gethostname(),
    }

    system = info["platform"]

    # CPU cores (cross-platform)
    try:
        info["cpu_cores"] = os.cpu_count() or 0
    except Exception:
        info["cpu_cores"] = 0

    # RAM + GPU (platform-specific)
    if system == "darwin":
        _collect_macos_static(info)
    elif system == "linux":
        _collect_linux_static(info)
    elif system == "windows":
        _collect_windows_static(info)

    return info


def _collect_macos_static(info: dict) -> None:
    """macOS: sysctl for RAM, system_profiler for GPU."""
    import subprocess

    # Total RAM via sysctl
    try:
        out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=5, text=True)
        info["total_ram_gb"] = round(int(out.strip()) / (1024 ** 3), 1)
    except Exception:
        info["total_ram_gb"] = 0

    # GPU via system_profiler (Apple Silicon reports unified memory)
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType", "-detailLevel", "basic"],
            timeout=10, text=True,
        )
        for line in out.splitlines():
            stripped = line.strip()
            if stripped.startswith("Chipset Model:") or stripped.startswith("Chip:"):
                info["gpu_name"] = stripped.split(":", 1)[1].strip()
            elif "VRAM" in stripped or "Total Number of Cores" in stripped:
                # Apple Silicon doesn't report VRAM separately — unified memory = total RAM
                pass

        # For Apple Silicon, VRAM = total system RAM (unified memory architecture)
        if info.get("gpu_name", "").startswith("Apple"):
            info["gpu_memory_gb"] = info.get("total_ram_gb", 0)
    except Exception:
        pass


def _collect_linux_static(info: dict) -> None:
    """Linux: /proc/meminfo for RAM, lspci/nvidia-smi for GPU."""
    # Total RAM from /proc/meminfo
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    info["total_ram_gb"] = round(kb / (1024 ** 2), 1)
                    break
    except Exception:
        info["total_ram_gb"] = 0

    # GPU via nvidia-smi (NVIDIA) or lspci fallback
    import subprocess
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            timeout=5, text=True,
        )
        parts = out.strip().split(", ")
        if len(parts) >= 1:
            info["gpu_name"] = parts[0]
        if len(parts) >= 2:
            info["gpu_memory_gb"] = round(int(parts[1]) / 1024, 1)
    except Exception:
        # Fallback: lspci for GPU name
        try:
            out = subprocess.check_output(["lspci"], timeout=5, text=True)
            for line in out.splitlines():
                if "VGA" in line or "3D" in line or "Display" in line:
                    info["gpu_name"] = line.split(":", 2)[-1].strip()
                    break
        except Exception:
            pass


def _collect_windows_static(info: dict) -> None:
    """Windows: wmic for RAM and GPU."""
    import subprocess

    # Total RAM via wmic
    try:
        out = subprocess.check_output(
            ["wmic", "computersystem", "get", "TotalPhysicalMemory", "/value"],
            timeout=5, text=True,
        )
        for line in out.splitlines():
            if "TotalPhysicalMemory" in line:
                val = line.split("=")[1].strip()
                info["total_ram_gb"] = round(int(val) / (1024 ** 3), 1)
                break
    except Exception:
        info["total_ram_gb"] = 0

    # GPU via wmic
    try:
        out = subprocess.check_output(
            ["wmic", "path", "win32_VideoController", "get", "Name,AdapterRAM", "/value"],
            timeout=5, text=True,
        )
        for line in out.splitlines():
            if line.startswith("Name="):
                info["gpu_name"] = line.split("=", 1)[1].strip()
            elif line.startswith("AdapterRAM="):
                val = line.split("=", 1)[1].strip()
                if val.isdigit():
                    info["gpu_memory_gb"] = round(int(val) / (1024 ** 3), 1)
    except Exception:
        pass


def _collect_system_info_dynamic() -> dict:
    """Collect dynamic system metrics (changes each heartbeat).

    Uses psutil if available, falls back to platform-specific commands.
    """
    info: dict = {}

    # Try psutil first (most accurate, cross-platform)
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["used_ram_gb"] = round(mem.used / (1024 ** 3), 1)
        info["free_ram_gb"] = round(mem.available / (1024 ** 3), 1)
        info["cpu_percent"] = psutil.cpu_percent(interval=0.1)

        # Load average (Unix only)
        if hasattr(os, "getloadavg"):
            load = os.getloadavg()
            info["load_avg_1m"] = round(load[0], 2)

        # Disk free on model storage volume
        disk = shutil.disk_usage(os.path.expanduser("~"))
        info["disk_free_gb"] = round(disk.free / (1024 ** 3), 1)

        return info
    except ImportError:
        pass

    # Fallback: platform-specific
    system = platform.system().lower()

    if system == "darwin":
        try:
            import subprocess
            out = subprocess.check_output(["vm_stat"], timeout=5, text=True)
            page_size = 16384  # Apple Silicon default
            active = wired = compressed = 0
            for line in out.splitlines():
                if "page size" in line.lower():
                    parts = line.split()
                    for p in parts:
                        if p.isdigit():
                            page_size = int(p)
                            break
                elif "Pages active:" in line:
                    active = int(line.split(":")[1].strip().rstrip("."))
                elif "Pages wired" in line:
                    wired = int(line.split(":")[1].strip().rstrip("."))
                elif "Pages occupied by compressor:" in line:
                    compressed = int(line.split(":")[1].strip().rstrip("."))

            used_bytes = (active + wired + compressed) * page_size
            info["used_ram_gb"] = round(used_bytes / (1024 ** 3), 1)
        except Exception:
            pass

    elif system == "linux":
        try:
            with open("/proc/meminfo") as f:
                mem_total = mem_avail = 0
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_avail = int(line.split()[1])
                if mem_total and mem_avail:
                    info["used_ram_gb"] = round((mem_total - mem_avail) / (1024 ** 2), 1)
                    info["free_ram_gb"] = round(mem_avail / (1024 ** 2), 1)
        except Exception:
            pass

    # Load average (Unix)
    if hasattr(os, "getloadavg"):
        try:
            load = os.getloadavg()
            info["load_avg_1m"] = round(load[0], 2)
        except Exception:
            pass

    # Disk free
    try:
        disk = shutil.disk_usage(os.path.expanduser("~"))
        info["disk_free_gb"] = round(disk.free / (1024 ** 3), 1)
    except Exception:
        pass

    return info


def _collect_ollama_status(inference_url: str) -> dict:
    """Query Ollama /api/ps for currently loaded models."""
    info: dict = {
        "ollama_running": False,
        "ollama_loaded_count": 0,
        "ollama_loaded": [],
    }

    try:
        req = urllib.request.Request(
            f"{inference_url}/api/ps",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            models = data.get("models", [])
            info["ollama_running"] = True
            info["ollama_loaded_count"] = len(models)
            info["ollama_loaded"] = [
                {
                    "name": m.get("name", ""),
                    "size_gb": round(m.get("size", 0) / (1024 ** 3), 2),
                    "vram_gb": round(m.get("size_vram", 0) / (1024 ** 3), 2),
                    "ram_gb": round(m.get("size_ram", m.get("size", 0)) / (1024 ** 3), 2),
                    "expires_at": m.get("expires_at", ""),
                }
                for m in models
            ]
    except Exception:
        # Ollama not running or /api/ps not available
        pass

    return info
