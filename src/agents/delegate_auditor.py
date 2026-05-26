"""
ChainScout AI — Delegate-Code Auditor agent.

Stage 3: when the destination address has EIP-7702 delegated code (prefix 0xef0100…),
decode the delegate target and check whether it is a recognised aggregator
(Multicall3, common router) or an unverified contract that could be a drainer.

Token target: ~180K per call (reasoning model).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..mimo_client import MimoClient


KNOWN_DELEGATES: dict[str, str] = {
    # Multicall3 — canonical aggregator
    "0xca11bde05977b3631167028862be2a173976ca11": "Multicall3",
    # 1inch v6 router
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch v6 Aggregator",
    # CowSwap settlement
    "0x9008d19f58aabd9ed0d60971565aa8510560ab41": "CowSwap GPv2 Settlement",
}


@dataclass
class DelegateVerdict:
    has_delegate: bool
    delegate_target: str | None
    recognised_as: str | None
    risk_note: str


class DelegateAuditorAgent:
    """Resolve EIP-7702 delegated code and judge its risk profile."""

    SYSTEM = (
        "You audit EIP-7702 delegated authorities. Given a delegate target address "
        "and any available metadata (verified source, known label, recent usage), "
        "judge whether delegating to it is consistent with the user's stated intent. "
        "Drainer contracts often impersonate familiar names — be sceptical of any "
        "target that is unverified or has no code history before the last 24 hours."
    )

    def __init__(self, mimo: MimoClient):
        self.mimo = mimo

    async def audit(
        self,
        *,
        destination: str,
        delegate_target: str | None,
        target_metadata: dict | None = None,
    ) -> DelegateVerdict:
        if not delegate_target:
            return DelegateVerdict(
                has_delegate=False,
                delegate_target=None,
                recognised_as=None,
                risk_note="Destination has no EIP-7702 delegation.",
            )

        normalised = delegate_target.lower()
        recognised = KNOWN_DELEGATES.get(normalised)

        if recognised:
            return DelegateVerdict(
                has_delegate=True,
                delegate_target=delegate_target,
                recognised_as=recognised,
                risk_note=f"Delegate is the well-known {recognised} contract.",
            )

        prompt = (
            f"Destination wallet: {destination}\n"
            f"Delegate target: {delegate_target}\n"
            f"Metadata: {target_metadata or 'unverified, no public label'}\n\n"
            "Output a single line risk note in plain English. "
            "Lead with one of: SAFE / SUSPICIOUS / DRAINER-LIKELY."
        )
        risk_note = (await self.mimo.reason(prompt, system=self.SYSTEM)).strip()

        return DelegateVerdict(
            has_delegate=True,
            delegate_target=delegate_target,
            recognised_as=None,
            risk_note=risk_note or "Reasoner returned no risk note.",
        )
