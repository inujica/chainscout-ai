"""
ChainScout AI — sentinel orchestrator.

Glues the 5 agents together. Given an unsigned transaction, returns a
SentinelReport that the wallet middleware can render before the Sign button.
"""
from __future__ import annotations

from dataclasses import dataclass

from .agents import (
    CalldataDecoderAgent,
    DelegateAuditorAgent,
    MEVProbeAgent,
    SentinelVerdict,
    StateDiffAgent,
    VerdictAgent,
)
from .mimo_client import MimoClient, MimoUsage


@dataclass
class UnsignedTx:
    from_address: str
    to: str
    value: int
    data: str          # hex calldata, "0x..."
    chain_id: int
    abi_hint: str | None = None
    delegate_target: str | None = None
    delegate_metadata: dict | None = None
    is_swap: bool = False
    pool_address: str | None = None
    pool_reserves: dict | None = None
    swap_amount_in: int | None = None
    swap_min_out: int | None = None
    simulation_result: dict | None = None


@dataclass
class SentinelReport:
    verdict: SentinelVerdict
    usage: MimoUsage


class ChainScoutSentinel:
    """5-stage pre-signing sentinel."""

    def __init__(self, mimo: MimoClient | None = None):
        self.mimo = mimo or MimoClient()
        self.calldata = CalldataDecoderAgent(self.mimo)
        self.state = StateDiffAgent(self.mimo)
        self.delegate = DelegateAuditorAgent(self.mimo)
        self.mev = MEVProbeAgent(self.mimo)
        self.verdict_agent = VerdictAgent(self.mimo)

    async def evaluate(self, tx: UnsignedTx) -> SentinelReport:
        # Stage 1 — decode calldata
        selector = tx.data[:10] if tx.data and tx.data.startswith("0x") and len(tx.data) >= 10 else "0x"
        decoded = await self.calldata.decode(
            to=tx.to,
            selector=selector,
            calldata=tx.data,
            abi_hint=tx.abi_hint,
        )

        # Stage 2 — state diff
        state_diff = await self.state.analyze(
            user_intent_summary=decoded.human_summary,
            simulation_result=tx.simulation_result or {},
            from_address=tx.from_address,
        )

        # Stage 3 — delegate audit
        delegate_verdict = await self.delegate.audit(
            destination=tx.to,
            delegate_target=tx.delegate_target,
            target_metadata=tx.delegate_metadata,
        )

        # Stage 4 — MEV probe
        mev = await self.mev.probe(
            is_swap=tx.is_swap,
            pool_address=tx.pool_address,
            reserves=tx.pool_reserves,
            amount_in=tx.swap_amount_in,
            min_amount_out=tx.swap_min_out,
        )

        # Stage 5 — verdict synthesis
        verdict = await self.verdict_agent.synthesise(
            decoded=decoded,
            state_diff=state_diff,
            delegate=delegate_verdict,
            mev=mev,
        )

        return SentinelReport(verdict=verdict, usage=self.mimo.usage)
