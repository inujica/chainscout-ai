"""
ChainScout AI — State-Diff Reasoner agent.

Stage 2: simulates the unsigned tx via eth_call / debug_traceCall, captures the
storage diff, and asks the reasoning model whether the resulting state changes
match the user's stated intent.

Token target: ~280K per call (reasoning model).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..mimo_client import MimoClient


@dataclass
class StateDiffFindings:
    allowance_grants: list[dict]    # token, spender, before, after
    balance_changes: list[dict]     # token, before, after
    storage_writes: int
    flagged: list[str]              # human-readable concerns
    raw_reasoning: str


class StateDiffAgent:
    """Reason about post-tx state changes."""

    SYSTEM = (
        "You are an EVM state-diff auditor. Given an eth_call simulation result "
        "(pre-state, post-state, logs), identify every approval that grows, every "
        "balance that drops, and any storage slot write that looks suspicious. "
        "Flag infinite approvals, unexpected delegate writes, and outflows that "
        "the user did not explicitly request."
    )

    def __init__(self, mimo: MimoClient):
        self.mimo = mimo

    async def analyze(
        self,
        *,
        user_intent_summary: str,
        simulation_result: dict,
        from_address: str,
    ) -> StateDiffFindings:
        prompt = self._build_prompt(
            user_intent_summary=user_intent_summary,
            simulation_result=simulation_result,
            from_address=from_address,
        )
        raw = await self.mimo.reason(prompt, system=self.SYSTEM)
        return self._parse(raw)

    def _build_prompt(self, *, user_intent_summary: str, simulation_result: dict, from_address: str) -> str:
        return (
            f"User-facing description of the transaction:\n{user_intent_summary}\n\n"
            f"Sender: {from_address}\n\n"
            f"Simulation result (eth_call + state diff):\n{simulation_result}\n\n"
            "Walk through the diff slot by slot. Output the following sections:\n"
            "ALLOWANCE_GRANTS: <list, one per line: token=<addr> spender=<addr> before=<n> after=<n>>\n"
            "BALANCE_CHANGES: <list, one per line>\n"
            "STORAGE_WRITES: <integer>\n"
            "FLAGS: <list, one per line — concerns in plain English>\n"
            "REASONING: <your full chain-of-thought>"
        )

    def _parse(self, raw: str) -> StateDiffFindings:
        sections: dict[str, list[str]] = {
            "ALLOWANCE_GRANTS": [],
            "BALANCE_CHANGES": [],
            "FLAGS": [],
        }
        storage_writes = 0
        current: Optional[str] = None
        reasoning_lines: list[str] = []

        for line in raw.splitlines():
            stripped = line.strip()
            for header in sections:
                if stripped.startswith(f"{header}:"):
                    current = header
                    rest = stripped.split(":", 1)[1].strip()
                    if rest:
                        sections[header].append(rest)
                    break
            else:
                if stripped.startswith("STORAGE_WRITES:"):
                    try:
                        storage_writes = int(stripped.split(":", 1)[1].strip())
                    except ValueError:
                        storage_writes = 0
                    current = None
                elif stripped.startswith("REASONING:"):
                    current = "REASONING"
                    rest = stripped.split(":", 1)[1].strip()
                    if rest:
                        reasoning_lines.append(rest)
                elif current == "REASONING":
                    reasoning_lines.append(line)
                elif current and stripped:
                    sections[current].append(stripped)

        return StateDiffFindings(
            allowance_grants=[{"raw": entry} for entry in sections["ALLOWANCE_GRANTS"]],
            balance_changes=[{"raw": entry} for entry in sections["BALANCE_CHANGES"]],
            storage_writes=storage_writes,
            flagged=sections["FLAGS"],
            raw_reasoning="\n".join(reasoning_lines).strip(),
        )
