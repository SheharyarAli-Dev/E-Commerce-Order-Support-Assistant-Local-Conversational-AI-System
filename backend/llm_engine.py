"""
llm_engine.py — Async streaming wrapper around the Ollama API.

Provides LLMEngine.stream() which yields text tokens as they arrive
from the locally running Ollama server.  The Conversation Manager
calls this; no LLM tool-calling or retrieval pipeline is used.
"""

import time
import asyncio
import logging
from typing import AsyncIterator

import ollama

from backend.config import (
    OLLAMA_HOST,
    MODEL_NAME,
    TEMPERATURE,
    TOP_P,
    MAX_TOKENS,
)

logger = logging.getLogger(__name__)


class LLMEngine:
    """
    Thin async wrapper over the Ollama client for streaming chat completions.

    The engine is stateless — all session state lives in the Session objects
    managed by the ConversationManager.
    """

    def __init__(self):
        self.client = ollama.AsyncClient(host=OLLAMA_HOST)
        self.model  = MODEL_NAME
        logger.info(f"LLMEngine initialized — model={self.model}, host={OLLAMA_HOST}")

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """
        Stream a chat completion.

        Args:
            messages: List of {role, content} dicts assembled by the PromptBuilder.

        Yields:
            Text tokens (strings) as they arrive from the model.

        Raises:
            LLMEngineError: On connection failure or model error.
        """
        t_start = time.perf_counter()
        first_token = True

        try:
            async for chunk in await self.client.chat(
                model   = self.model,
                messages= messages,
                stream  = True,
                options = {
                    "temperature": TEMPERATURE,
                    "top_p":       TOP_P,
                    "num_predict": MAX_TOKENS,
                },
            ):
                token = chunk.get("message", {}).get("content", "")
                if token:
                    if first_token:
                        ttft = time.perf_counter() - t_start
                        logger.info(f"Time to first token: {ttft:.3f}s")
                        first_token = False
                    yield token

            total_time = time.perf_counter() - t_start
            logger.info(f"LLM generation complete in {total_time:.2f}s")

        except ollama.ResponseError as e:
            logger.error(f"Ollama ResponseError: {e}")
            raise LLMEngineError(f"Model error: {e.error}") from e
        except Exception as e:
            logger.error(f"LLMEngine unexpected error: {e}")
            raise LLMEngineError(f"Inference failed: {str(e)}") from e

    async def health_check(self) -> dict:
        """
        Verify that Ollama is reachable and the model is available.

        Returns:
            {"status": "ok", "model": ..., "available": True/False}
        """
        try:
            models_response = await self.client.list()
            model_names = [m["model"] for m in models_response.get("models", [])]
            available = any(self.model in m for m in model_names)
            return {
                "status": "ok",
                "model": self.model,
                "available": available,
                "ollama_host": OLLAMA_HOST,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "model": self.model,
                "available": False,
            }


class LLMEngineError(Exception):
    """Raised when the LLM engine encounters a non-recoverable error."""
    pass
