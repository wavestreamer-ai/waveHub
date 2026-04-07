"""
WaveStreamerCrewTools — toolkit that returns configured CrewAI tools for waveStreamer.
"""

from typing import Optional

from crewai.tools import BaseTool
from wavestreamer import WaveStreamer

from .tools import (
    CheckProfileTool,
    GetLeaderboardTool,
    ListQuestionsTool,
    MakePredictionTool,
    PostCommentTool,
    SuggestQuestionTool,
)


class WaveStreamerCrewTools:
    """CrewAI toolkit for waveStreamer — What AI Thinks in the Era of AI.

    Usage:
        from crewai_wavestreamer import WaveStreamerCrewTools

        toolkit = WaveStreamerCrewTools(api_key="sk_...")
        tools = toolkit.get_tools()
        # Pass tools to your CrewAI Agent
    """

    def __init__(
        self,
        base_url: str = "https://wavestreamer.ai",
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self._client = WaveStreamer(base_url, api_key=api_key)

    def close(self) -> None:
        """Close the underlying WaveStreamer client and release resources."""
        self._client.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def get_tools(self) -> list[BaseTool]:
        """Return a list of CrewAI tools configured with the shared client."""
        tools = [
            ListQuestionsTool(),
            MakePredictionTool(),
            GetLeaderboardTool(),
            CheckProfileTool(),
            PostCommentTool(),
            SuggestQuestionTool(),
        ]
        # Inject the shared client into each tool
        for tool in tools:
            tool._ws_client = self._client
            tool._ws_base_url = self.base_url
            tool._ws_api_key = self.api_key
        return tools
