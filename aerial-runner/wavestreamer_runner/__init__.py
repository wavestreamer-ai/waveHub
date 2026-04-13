"""wavestreamer-runner — autonomous prediction agent for waveStreamer."""

__version__ = "0.1.1"

from .personality import AgentPersonality
from .runner import AgentRunner

__all__ = ["AgentRunner", "AgentPersonality"]

# Private training is optional — import only when chromadb is available
try:
    from .private_rag import PrivateRAG  # noqa: F401
    __all__.append("PrivateRAG")
except ImportError:
    pass
