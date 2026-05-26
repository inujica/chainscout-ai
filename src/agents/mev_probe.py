"""
ChainScout AI — MEV Exposure Probe agent.

Stage 4: when the tx swaps through an AMM, simulate the worst-case sandwich and
estimate the user's expected loss percentile given current pool reserves and
their slippage tolerance.

Token target: ~220K per call (reasoning model).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..mimo_client import MimoClient


@dataclass
class MEVExposure:
    is_swap: bool
    pool: str | None
    expected_loss_bps: int    # basis points (1% = 100 bps)
    worst_case_loss_bps: int
    rationale: str


class MEVProbeAgent:
    """Estimate MEV exposure for AMM swap calldata."""

    SYSTEM = (
        "You are an MEV simulation expert. Given pool reserves, the user's input "
        "amount, and their min-out slippage tolerance, compute the worst-case loss "
        "if a searcher front-runs and back-runs the swap. Return loss in basis "
        "points (10000 = 100%). Be conservative — if data is missing, bias toward "
        "warning the user."
    )

    def __init__(self, mimo: MimoClient):
        self.mimo = mimo

    async def probe(
        self,
        *,
        is_swap: bool,
        pool_address: str | None,
        reserves: dict | None,
        amount_in: int | None,
        min_amount_out: int | None,
    ) -> MEVExposure:
        if not is_swap or pool_address is None:
            return MEVExposure(
                is_swap=False,
                pool=None,
                expected_loss_bps=0,
                worst_case_loss_bps=0,
                rationale="Transaction is not an AMM swap.",
            )

        prompt = (
            f"Pool: {pool_address}\n"
            f"Reserves: {reserves}\n"
            f"User input amount: {amount_in}\n"
            f"User min-out (slippage floor): {min_amount_out}\n\n"
            "Output exactly three lines:\n"
            "EXPECTED_LOSS_BPS: <integer>\n"
            "WORST_CASE_LOSS_BPS: <integer>\n"
            "RATIONALE: <one paragraph explanation>"
        )

        raw = await self.mimo.reason(prompt, system=self.SYSTEM)
        return self._parse(raw, pool_address)

    def _parse(self, raw: str, pool: str) -> MEVExposure:
        expected = 0
        worst = 0
        rationale = ""

        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("EXPECTED_LOSS_BPS:"):
                expected = self._safe_int(stripped.split(":", 1)[1])
            elif stripped.startswith("WORST_CASE_LOSS_BPS:"):
                worst = self._safe_int(stripped.split(":", 1)[1])
            elif stripped.startswith("RATIONALE:"):
                rationale = stripped.split(":", 1)[1].strip()

        return MEVExposure(
            is_swap=True,
            pool=pool,
            expected_loss_bps=expected,
            worst_case_loss_bps=worst,
            rationale=rationale or "Reasoner returned no rationale.",
        )

    @staticmethod
    def _safe_int(value: str) -> int:
        try:
            return int(value.strip())
        except ValueError:
            return 0
