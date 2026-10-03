"""
Verification script for Sprint 1: Local Ollama Client & Inference Engine.
Tests asynchronous Ollama client connectivity, model availability checks,
and fallback resilience.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pydantic import BaseModel, Field

from src.llm.ollama_client import OllamaClient


class MockStructuredOutput(BaseModel):
    summary: str = Field(description="Summary test string")
    skills: list[str] = Field(default_factory=list)


async def test_ollama_client():
    print("==================================================")
    print("  Testing Local Ollama Async Client")
    print("==================================================")

    client = OllamaClient(
        base_url="http://localhost:11434",
        model="qwen2.5:7b-instruct-q4_K_M",
    )

    # 1. Test Server Connectivity Check
    is_online = await client.is_server_online()
    print(f"📡 Local Ollama Daemon Online: {is_online}")

    if not is_online:
        print("ℹ️ Note: Ollama daemon is currently offline on http://localhost:11434.")
        print("   Verifying that client methods handle offline states gracefully...")

        models = await client.list_available_models()
        assert models == [], "Expected empty model list when daemon is offline"
        has_model = await client.is_model_available("qwen2.5:7b")
        assert has_model is False, "Expected False for model check when offline"
        print("✅ Graceful offline exception handling verified.")
        return

    # 2. If daemon is online, inspect models and run benchmark
    models = await client.list_available_models()
    print(f"📦 Discovered local models: {models}")

    target_model = "qwen2.5:7b"
    model_ready = await client.is_model_available(target_model)
    print(f"🔍 Target model '{target_model}' ready: {model_ready}")

    if model_ready:
        print(f"\n⚡ Running inference benchmark on {target_model}...")
        prompt = "Explain in one sentence why automated tests prevent regressions in CI/CD."
        result = await client.generate(prompt=prompt, temperature=0.0)
        print(f"   Response: {result['response'].strip()}")
        print(f"   Tokens generated: {result['total_tokens']}")
        print(f"   Tokens/sec: {result['tokens_per_second']} t/s")
        print(f"   Latency: {result['elapsed_seconds']:.2f}s")
        assert result["total_tokens"] > 0, "No tokens returned from generation"
        print("✅ Local Ollama generation benchmark verified.")


def main():
    asyncio.run(test_ollama_client())
    print("\n" + "=" * 50)
    print("✅ VERIFICATION SCRIPT 28 (OLLAMA CLIENT) PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    main()
