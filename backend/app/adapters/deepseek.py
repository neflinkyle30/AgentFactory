"""DeepSeek AI provider — uses the OpenAI-compatible DeepSeek API."""

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI

from app.adapters.base import (
    AIProvider,
    Message,
    ResultMessage,
    TokenUsage,
    ToolCall,
)
from app.config import settings

logger = logging.getLogger(__name__)

# ── DeepSeek pricing (per 1M tokens) ──────────────────────────────
# These may be overridden via config in the future.
DEEPSEEK_INPUT_PRICE = 0.14  # USD per 1M input tokens
DEEPSEEK_OUTPUT_PRICE = 0.28  # USD per 1M output tokens


class DeepSeekProvider(AIProvider):
    """AI provider backed by the DeepSeek API (OpenAI-compatible).

    Uses the openai.AsyncOpenAI client pointed at DeepSeek's base URL.
    Supports system prompts, multi-turn messages, tool calling,
    JSON structured output, and chain-of-thought thinking mode.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
    ) -> None:
        """Initialize the DeepSeek provider.

        Args:
            api_key: DeepSeek API key. Defaults to settings.deepseek_api_key.
            base_url: DeepSeek API base URL. Defaults to settings.deepseek_base_url.
            default_model: Default model name. Defaults to settings.deepseek_model.
        """
        self._api_key = api_key or settings.deepseek_api_key
        self._base_url = base_url or settings.deepseek_base_url
        self._default_model = default_model or settings.deepseek_model

        if not self._api_key:
            logger.warning(
                "DEEPSEEK_API_KEY is not set — DeepSeekProvider will fail "
                "on query(). Use AGENT_FACTORY_MOCK=1 for development."
            )

        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
        )

    # ── Public API ─────────────────────────────────────────────────

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
        """Send a query to DeepSeek and return the structured result.

        See AIProvider.query() for parameter documentation.
        """
        model_name = model or self._default_model
        api_messages = self._build_messages(system_prompt, messages)

        # Build the request kwargs
        request_kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": api_messages,
            "temperature": 0.3,
        }

        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens

        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        if output_format:
            request_kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "schema": output_format,
                    "strict": True,
                },
            }

        # Send the request
        response = await self._client.chat.completions.create(**request_kwargs)

        # Parse the response
        choice = response.choices[0]
        content = choice.message.content or ""
        finish_reason = choice.finish_reason or "stop"

        # Parse tool calls if present
        tool_calls: List[ToolCall] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {"raw": tc.function.arguments}
                tool_calls.append(
                    ToolCall(
                        id=tc.id or "",
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        # Build usage stats
        usage = TokenUsage()
        if response.usage:
            usage.prompt_tokens = response.usage.prompt_tokens or 0
            usage.completion_tokens = response.usage.completion_tokens or 0
            usage.total_tokens = response.usage.total_tokens or 0
            usage.cost_usd = self.calculate_cost(
                usage.prompt_tokens, usage.completion_tokens
            )

        return ResultMessage(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            model=response.model,
        )

    async def query_stream(
        self,
        system_prompt: str,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        thinking: bool = True,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Stream query results from DeepSeek chunk by chunk.

        Uses OpenAI's streaming API. Yields content deltas as they arrive.
        """
        model_name = model or self._default_model
        api_messages = self._build_messages(system_prompt, messages)

        request_kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": api_messages,
            "temperature": 0.3,
            "stream": True,
        }

        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens
        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        stream = await self._client.chat.completions.create(**request_kwargs)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken with DeepSeek-compatible encoding.

        DeepSeek uses a tokenizer similar to OpenAI's o200k_base.
        Falls back to character-based estimation if tiktoken fails.
        """
        if not text:
            return 0
        try:
            import tiktoken

            # o200k_base is the encoding used by DeepSeek / GPT-4o
            encoding = tiktoken.get_encoding("o200k_base")
            return len(encoding.encode(text))
        except Exception:
            return super().count_tokens(text)

    def calculate_cost(
        self, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Calculate DeepSeek API cost.

        DeepSeek pricing:
        - Input:  $0.14 per 1M tokens
        - Output: $0.28 per 1M tokens
        - Cache hit input: $0.014 per 1M tokens (not yet tracked)
        """
        input_cost = (prompt_tokens / 1_000_000) * DEEPSEEK_INPUT_PRICE
        output_cost = (completion_tokens / 1_000_000) * DEEPSEEK_OUTPUT_PRICE
        return round(input_cost + output_cost, 8)

    # ── Helpers ────────────────────────────────────────────────────

    def _build_messages(
        self, system_prompt: str, messages: List[Message]
    ) -> List[Dict[str, Any]]:
        """Build the OpenAI-compatible message list from system prompt + history."""
        api_messages: List[Dict[str, Any]] = []

        # System prompt goes first
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        # Add conversation messages
        for msg in messages:
            entry: Dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            api_messages.append(entry)

        return api_messages
