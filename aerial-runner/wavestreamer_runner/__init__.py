"""wavestreamer-runner — autonomous prediction agent for waveStreamer."""

__version__ = "0.1.1"

from .runner import AgentRunner
from .personality import AgentPersonality

__all__ = ["AgentRunner", "AgentPersonality"]

# Private training is optional — import only when chromadb is available
try:
    from .private_rag import PrivateRAG
    __all__.append("PrivateRAG")
except ImportError:
    pass
