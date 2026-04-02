"""Detect locally available AI models (Ollama, MLX)."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LocalModel:
    name: str
    provider: str  # "ollama" or "mlx"
    size: str  # e.g. "7B", "13B"
    modified: str


def detect_ollama() -> list[LocalModel]:
    """Check localhost:11434/api/tags for running Ollama models."""
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []

    models: list[LocalModel] = []
    for m in data.get("models", []):
        name = m.get("name", "")
        # Extract size from details or name
        details = m.get("details", {})
        size = details.get("parameter_size", "")
        if not size:
            # Try to guess from the name (e.g. "llama3:7b")
            for part in name.split(":"):
                part_lower = part.lower()
                if part_lower.endswith("b") and part_lower[:-1].replace(".", "").isdigit():
                    size = part.upper()
                    break
        modified = m.get("modified_at", "")
        models.append(LocalModel(
            name=name,
            provider="ollama",
            size=size,
            modified=modified,
        ))
    return models


def detect_mlx() -> list[LocalModel]:
    """Check if mlx_lm is installed and list cached models with MLX weights."""
    try:
        import importlib
        importlib.import_module("mlx_lm")
    except (ImportError, ModuleNotFoundError):
        return []

    models: list[LocalModel] = []
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    if not cache_dir.exists():
        return []

    for model_dir in cache_dir.iterdir():
        if not model_dir.is_dir() or not model_dir.name.startswith("models--"):
            continue
        # Check for MLX weight files in snapshots
        snapshots = model_dir / "snapshots"
        if not snapshots.exists():
            continue
        has_mlx = False
        for snapshot in snapshots.iterdir():
            if not snapshot.is_dir():
                continue
            # Look for mlx weight files (*.safetensors with mlx config or weights.npz)
            for f in snapshot.iterdir():
                if f.name in ("weights.npz", "config.json") or (
                    "mlx" in f.name.lower() and f.suffix == ".safetensors"
                ):
                    has_mlx = True
                    break
            if has_mlx:
                break
        if not has_mlx:
            continue

        # Parse model name from directory: models--org--name -> org/name
        parts = model_dir.name.replace("models--", "").split("--")
        name = "/".join(parts)

        # Try to guess size from name
        size = ""
        name_lower = name.lower()
        for token in name_lower.replace("-", " ").replace("_", " ").split():
            if token.endswith("b") and token[:-1].replace(".", "").isdigit():
                size = token.upper()
                break

        models.append(LocalModel(
            name=name,
            provider="mlx",
            size=size,
            modified="",
        ))

    return models


def detect_all() -> list[LocalModel]:
    """Detect all locally available models."""
    return detect_ollama() + detect_mlx()
