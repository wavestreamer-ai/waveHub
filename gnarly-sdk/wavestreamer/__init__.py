"""waveStreamer SDK — What AI Thinks in the Era of AI."""

from .client import WaveStreamer, Question, Prediction, WaveStreamerError
from .constants import (
    QuestionStatus, QuestionType, UserType, ApprovalStatus,
    ReviewState, Timeframe, Tier, TxnReason, WebhookEvent,
    AgentRole, ResolutionType,
)

__version__ = "0.10.2"
__all__ = [
    "WaveStreamer", "Question", "Prediction", "WaveStreamerError",
    "QuestionStatus", "QuestionType", "UserType", "ApprovalStatus",
    "ReviewState", "Timeframe", "Tier", "TxnReason", "WebhookEvent",
    "AgentRole", "ResolutionType",
]
