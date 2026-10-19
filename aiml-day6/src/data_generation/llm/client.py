"""Thin wrapper around the OpenAI Responses API with retry and backoff."""

from __future__ import annotations

import random
import time

import openai
from openai import OpenAI

RETRYABLE = (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError)


class LLMClient:
    def __init__(self, api_key: str, model: str, reasoning_effort: str, max_retries: int = 5, timeout: float = 180):
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.max_retries = max_retries
        self._client = OpenAI(api_key=api_key, max_retries=0, timeout=timeout)

    def complete(self, instructions: str, prompt: str) -> str:
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.responses.create(
                    model=self.model,
                    reasoning={"effort": self.reasoning_effort},
                    instructions=instructions,
                    input=prompt,
                )
                return response.output_text.strip()
            except RETRYABLE:
                if attempt == self.max_retries:
                    raise
                time.sleep(min(60, 2 ** attempt) + random.uniform(0, 1))
        raise RuntimeError("unreachable")
