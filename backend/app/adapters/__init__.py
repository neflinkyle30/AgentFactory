"""AI provider adapters for Agent Factory.

Provides a pluggable AI backend: DeepSeek (production) or Mock (development).
"""

from app.adapters.base import AIProvider, ResultMessage, TokenUsage
from app.adapters.factory import get_provider

__all__ = [
    "AIProvider",
    "ResultMessage",
    "TokenUsage",
    "get_provider",
]
