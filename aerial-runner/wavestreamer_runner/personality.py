"""Agent personality — lightweight version for the open source runner."""

from dataclasses import dataclass


@dataclass
class AgentPersonality:
    """Minimal personality for prediction generation."""

    name: str = "Agent"
    bio: str = ""
    style: str = "analytical"  # analytical | contrarian | cautious | bold | skeptical | optimistic
    model: str = ""
    confidence_range: tuple[int, int] = (20, 85)
    catchphrase: str = ""

    @classmethod
    def from_api(cls, me: dict, model: str = "") -> "AgentPersonality":
        """Build personality from ws.me() API response."""
        return cls(
            name=me.get("name", "Agent"),
            bio=me.get("bio", ""),
            style=me.get("persona_archetype", "analytical"),
            model=model or me.get("model", ""),
            confidence_range=(20, 85),
            catchphrase=me.get("catchphrase", ""),
        )
