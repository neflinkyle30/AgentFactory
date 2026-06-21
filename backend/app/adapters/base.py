"""Abstract base class for AI providers and shared data types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass
class TokenUsage:
    """Token usage and cost for a single AI query."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class ToolCall:
    """A tool call requested by the AI."""

    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResultMessage:
    """The result of an AI provider query.

    Contains the response text, any tool calls requested, and usage stats.
    """

    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str = "stop"
    model: str = ""


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class AIProvider(ABC):
    """Abstract interface for AI model providers.

    All providers must implement query().
    Streaming and token counting are optional (default no-op implementations).
    """

    @abstractmethod
    async def query(
        self,
        system_prompt: str,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        output_format: Optional[Dict[str, Any]] = None,
        thinking: bool = True,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> ResultMessage:
        """Send a query to the AI provider and return the result.

        Args:
            system_prompt: The system-level instruction for the AI.
            messages: Conversation history as a list of Message objects.
            tools: Optional tool definitions for function calling.
            output_format: Optional JSON schema for structured output.
            thinking: Whether to enable chain-of-thought reasoning (DeepSeek).
            model: Override the default model name.
            max_tokens: Maximum tokens in the response.

        Returns:
            ResultMessage with content, tool_calls, usage stats.
        """
        ...

    async def query_stream(
        self,
        system_prompt: str,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        thinking: bool = True,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream query results chunk by chunk.

        Default implementation delegates to query() and yields the full content.
        Providers should override for true streaming support.
        """
        result = await self.query(
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            thinking=thinking,
            model=model,
            max_tokens=max_tokens,
        )
        yield result.content

    def count_tokens(self, text: str) -> int:
        """Estimate token count for a text string.

        Default implementation uses a rough heuristic (4 chars ≈ 1 token).
        Providers with known tokenizers should override.
        """
        if not text:
            return 0
        # Rough approximation: ~4 characters per token
        return max(1, len(text) // 4)

    def calculate_cost(
        self, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Calculate cost in USD for the given token usage.

        Default implementation uses DeepSeek pricing:
        - Input:  $0.14 per 1M tokens
        - Output: $0.28 per 1M tokens
        """
        input_cost = (prompt_tokens / 1_000_000) * 0.14
        output_cost = (completion_tokens / 1_000_000) * 0.28
        return round(input_cost + output_cost, 8)
