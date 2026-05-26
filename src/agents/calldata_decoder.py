"""
ChainScout AI — Calldata Decoder agent.

Stage 1 of the 5-stage sentinel pipeline. Translates raw 4-byte selector + calldata
into a plain-English description of what the transaction is asking the user to do.

Token target: ~120K per call (fast model).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..mimo_client import MimoClient


@dataclass
class DecodedCall:
    function_name: str
    human_summary: str
    arguments: dict
    abi_source: str  # "4byte" | "sourcify" | "unknown"


class CalldataDecoderAgent:
    """Decode raw transaction calldata into intent."""

    SYSTEM = (
        "You are a Web3 calldata decoder. Given a 4-byte function selector and the "
        "raw calldata bytes, your job is to identify the function and explain in one "
        "or two sentences what the user is being asked to authorise. Be precise about "
        "values, recipients and approval scope. Never speculate beyond what the "
        "calldata directly encodes."
    )

    def __init__(self, mimo: MimoClient):
        self.mimo = mimo

    async def decode(self, *, to: str, selector: str, calldata: str, abi_hint: Optional[str] = None) -> DecodedCall:
        prompt = self._build_prompt(to=to, selector=selector, calldata=calldata, abi_hint=abi_hint)
        raw = await self.mimo.fast(prompt, system=self.SYSTEM)
        return self._parse(raw, abi_hint=abi_hint)

    def _build_prompt(self, *, to: str, selector: str, calldata: str, abi_hint: Optional[str]) -> str:
        sections = [
            f"Destination contract: {to}",
            f"Selector: {selector}",
            f"Calldata: {calldata}",
        ]
        if abi_hint:
            sections.append(f"Known ABI hint: {abi_hint}")
        sections.append(
            "\nRespond in this exact format:\n"
            "FUNCTION: <name>\n"
            "SUMMARY: <one-sentence human description>\n"
            "ARGS: <key=value pairs, one per line>"
        )
        return "\n".join(sections)

    def _parse(self, raw: str, *, abi_hint: Optional[str]) -> DecodedCall:
        function_name = "unknown"
        summary = ""
        args: dict = {}

        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("FUNCTION:"):
                function_name = line.split(":", 1)[1].strip()
            elif line.startswith("SUMMARY:"):
                summary = line.split(":", 1)[1].strip()
            elif "=" in line and not line.startswith("ARGS:"):
                key, _, value = line.partition("=")
                args[key.strip()] = value.strip()

        return DecodedCall(
            function_name=function_name,
            human_summary=summary or "Decoder produced no summary.",
            arguments=args,
            abi_source="sourcify" if abi_hint else "4byte",
        )
