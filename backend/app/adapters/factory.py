"""Provider factory — selects the appropriate AI provider based on settings."""

from app.adapters.base import AIProvider
from app.adapters.deepseek import DeepSeekProvider
from app.adapters.mock import MockProvider
from app.config import settings


def get_provider() -> AIProvider:
    """Return the configured AI provider.

    When AGENT_FACTORY_MOCK=1, returns MockProvider (no API calls).
    Otherwise returns DeepSeekProvider (requires DEEPSEEK_API_KEY).
    """
    if settings.mock_mode:
        return MockProvider()

    return DeepSeekProvider()
