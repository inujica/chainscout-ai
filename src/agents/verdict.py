"""
ChainScout AI — Verdict Synthesiser agent.

Stage 5: aggregate the findings from stages 1-4 into a single ALLOW / WARN / BLOCK
verdict plus a 3-sentence plain-English explanation the wallet can render
verbatim above the Sign button.

Token target: ~80K per call (fast model).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..mimo_client import MimoClient
from .calldata_decoder import DecodedCall
from .delegate_auditor import DelegateVerdict
from .mev_probe import MEVExposure
from .state_diff import StateDiffFindings


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass
class SentinelVerdict:
    verdict: Verdict
    headline: str
    reasons: list[str]


class VerdictAgent:
    """Synthesise a final user-facing verdict."""

    SYSTEM = (
        "You write the single sentence a Web3 user will read before signing a "
        "transaction. Be direct, no hedging. If anything is wrong, say what and why "
        "in language a non-technical user can understand. Output: VERDICT line, then "
        "HEADLINE line, then up to 3 REASON lines."
    )

    def __init__(self, mimo: MimoClient):
        self.mimo = mimo

    async def synthesise(
        self,
        *,
        decoded: DecodedCall,
        state_diff: StateDiffFindings,
        delegate: DelegateVerdict,
        mev: MEVExposure,
    ) -> SentinelVerdict:
        prompt = (
            "Inputs from previous stages:\n\n"
            f"Decoded function: {decoded.function_name}\n"
            f"Human summary: {decoded.human_summary}\n"
            f"State-diff flags: {state_diff.flagged or 'none'}\n"
            f"Storage writes: {state_diff.storage_writes}\n"
            f"Allowance grants: {len(state_diff.allowance_grants)}\n"
            f"Delegate has_delegate={delegate.has_delegate} target={delegate.delegate_target} note={delegate.risk_note}\n"
            f"MEV expected_loss_bps={mev.expected_loss_bps} worst_case_bps={mev.worst_case_loss_bps}\n\n"
            "Decision rules:\n"
            "- If state_diff.flagged contains an outflow the user did not request → BLOCK.\n"
            "- If delegate.risk_note starts with DRAINER-LIKELY → BLOCK.\n"
            "- If MEV worst_case_bps > 300 → WARN.\n"
            "- If allowance_grants > 0 and the spender is unverified → WARN.\n"
            "- Otherwise ALLOW.\n\n"
            "Output format:\n"
            "VERDICT: ALLOW|WARN|BLOCK\n"
            "HEADLINE: <one sentence>\n"
            "REASON: <bullet>\n"
            "REASON: <bullet>\n"
            "REASON: <bullet>"
        )

        raw = await self.mimo.fast(prompt, system=self.SYSTEM)
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> SentinelVerdict:
        verdict = Verdict.WARN
        headline = ""
        reasons: list[str] = []

        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("VERDICT:"):
                token = stripped.split(":", 1)[1].strip().upper()
                if token in Verdict.__members__:
                    verdict = Verdict[token]
            elif stripped.startswith("HEADLINE:"):
                headline = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("REASON:"):
                reasons.append(stripped.split(":", 1)[1].strip())

        return SentinelVerdict(
            verdict=verdict,
            headline=headline or "Sentinel produced no headline.",
            reasons=reasons,
        )
