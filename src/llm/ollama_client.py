"""
Asynchronous Ollama HTTP client optimized for Apple Silicon local inference.
Connects directly to the Ollama REST engine (http://localhost:11434) with health checks,
structured JSON schema extraction, and latency benchmarking.
"""

from __future__ import annotations

import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class OllamaClient:
    """
    High-performance asynchronous client communicating with local Ollama daemon.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b-instruct-q4_K_M",
        timeout_seconds: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout_seconds

    async def is_server_online(self) -> bool:
        """Checks if local Ollama daemon is reachable."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def list_available_models(self) -> list[str]:
        """Returns list of local model names present in Ollama."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    return [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            pass
        return []

    async def is_model_available(self, model_name: str | None = None) -> bool:
        """Checks if specified model is pulled locally."""
        target = model_name or self.model
        available = await self.list_available_models()
        # Check exact or prefix match (e.g. 'qwen2.5:7b' in 'qwen2.5:7b-instruct-q4_K_M')
        return any(target in m or m.startswith(target.split(":")[0]) for m in available)

    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
        format_json: bool = False,
    ) -> dict[str, Any]:
        """
        Sends generation request to /api/generate with token timing metrics.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if system_instruction:
            payload["system"] = system_instruction

        if format_json:
            payload["format"] = "json"

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()

        elapsed = time.perf_counter() - start_time
        total_eval_tokens = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 0)
        tokens_per_sec = (total_eval_tokens / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0.0

        return {
            "response": data.get("response", ""),
            "total_tokens": total_eval_tokens,
            "elapsed_seconds": elapsed,
            "tokens_per_second": round(tokens_per_sec, 2),
        }

    async def chat_structured(
        self,
        messages: list[dict[str, str]],
        schema: type[T],
        temperature: float = 0.0,
    ) -> T:
        """
        Executes chat completion and parses response into specified Pydantic schema.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": schema.model_json_schema(),
            "options": {
                "temperature": temperature,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "{}")

        return schema.model_validate_json(content)
