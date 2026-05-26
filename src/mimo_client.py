"""
ChainScout AI — MiMo API client.

Thin async wrapper around MiMo's OpenAI-compatible chat completions endpoint.
Handles model routing (reasoning vs fast), token accounting, and retry on transient 5xx.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class MimoUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "MimoUsage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens


@dataclass
class MimoClient:
    api_key: str = field(default_factory=lambda: os.environ.get("MIMO_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1"))
    reasoning_model: str = field(default_factory=lambda: os.environ.get("MIMO_REASONING_MODEL", "mimo-v2.5-pro"))
    fast_model: str = field(default_factory=lambda: os.environ.get("MIMO_FAST_MODEL", "mimo-v2.5"))
    timeout: float = 120.0
    usage: MimoUsage = field(default_factory=MimoUsage)

    async def reason(self, prompt: str, *, system: Optional[str] = None, temperature: float = 0.2) -> str:
        """Long-chain reasoning call. Use for state-diff analysis, delegate decode, MEV probe."""
        return await self._chat(self.reasoning_model, prompt, system=system, temperature=temperature)

    async def fast(self, prompt: str, *, system: Optional[str] = None, temperature: float = 0.1) -> str:
        """Fast call. Use for calldata decode and verdict synthesis."""
        return await self._chat(self.fast_model, prompt, system=system, temperature=temperature)

    async def _chat(self, model: str, prompt: str, *, system: Optional[str], temperature: float) -> str:
        if not self.api_key:
            raise RuntimeError("MIMO_API_KEY not set")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }

        last_err: Optional[Exception] = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code >= 500:
                        raise httpx.HTTPStatusError(f"upstream {resp.status_code}", request=resp.request, response=resp)
                    resp.raise_for_status()
                    data = resp.json()
                    self._record_usage(data)
                    return data["choices"][0]["message"]["content"]
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_err = exc
                await asyncio.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"MiMo call failed after retries: {last_err}")

    def _record_usage(self, data: dict) -> None:
        u = data.get("usage", {}) or {}
        self.usage.add(
            MimoUsage(
                prompt_tokens=u.get("prompt_tokens", 0),
                completion_tokens=u.get("completion_tokens", 0),
                total_tokens=u.get("total_tokens", 0),
            )
        )
