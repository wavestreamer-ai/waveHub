"""wavestreamer-runner — autonomous prediction agent for waveStreamer."""

__version__ = "0.1.0"

from .runner import AgentRunner
from .personality import AgentPersonality

__all__ = ["AgentRunner", "AgentPersonality"]
