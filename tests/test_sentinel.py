"""Smoke tests for ChainScout sentinel parsing logic.

These do not hit the MiMo API — they exercise the deterministic parsers so the
pipeline shape is testable without API credits.
"""
from __future__ import annotations

from src.agents.calldata_decoder import CalldataDecoderAgent
from src.agents.delegate_auditor import KNOWN_DELEGATES
from src.agents.mev_probe import MEVProbeAgent
from src.agents.state_diff import StateDiffAgent
from src.agents.verdict import Verdict, VerdictAgent


def test_calldata_parser_extracts_function_summary_args():
    raw = (
        "FUNCTION: transferFrom\n"
        "SUMMARY: Move 1000 USDC from sender to a new recipient.\n"
        "ARGS:\n"
        "from=0xabc\n"
        "to=0xdef\n"
        "amount=1000000000\n"
    )
    decoder = CalldataDecoderAgent.__new__(CalldataDecoderAgent)
    parsed = decoder._parse(raw, abi_hint=None)
    assert parsed.function_name == "transferFrom"
    assert "Move 1000 USDC" in parsed.human_summary
    assert parsed.arguments["from"] == "0xabc"
    assert parsed.arguments["amount"] == "1000000000"


def test_state_diff_parser_handles_storage_writes_and_flags():
    raw = (
        "ALLOWANCE_GRANTS: token=0xUSDC spender=0xRouter before=0 after=2**256-1\n"
        "BALANCE_CHANGES: token=0xUSDC before=1000 after=0\n"
        "STORAGE_WRITES: 4\n"
        "FLAGS: Infinite approval to unverified spender\n"
        "REASONING: The diff shows a max-uint approval combined with a balance drop to zero.\n"
    )
    state = StateDiffAgent.__new__(StateDiffAgent)
    out = state._parse(raw)
    assert out.storage_writes == 4
    assert any("Infinite approval" in entry for entry in out.flagged)
    assert "max-uint approval" in out.raw_reasoning


def test_known_delegates_lookup_is_lowercase():
    for key in KNOWN_DELEGATES:
        assert key == key.lower()


def test_mev_probe_parser_extracts_loss_bps():
    raw = (
        "EXPECTED_LOSS_BPS: 42\n"
        "WORST_CASE_LOSS_BPS: 380\n"
        "RATIONALE: A 0.42% expected loss at the requested slippage floor.\n"
    )
    probe = MEVProbeAgent.__new__(MEVProbeAgent)
    out = probe._parse(raw, pool="0xpool")
    assert out.expected_loss_bps == 42
    assert out.worst_case_loss_bps == 380
    assert out.pool == "0xpool"


def test_verdict_parser_assigns_block_when_specified():
    raw = (
        "VERDICT: BLOCK\n"
        "HEADLINE: This transaction would drain all of your USDC.\n"
        "REASON: The destination is an unverified contract.\n"
        "REASON: It requests an infinite approval.\n"
        "REASON: Your balance would drop to zero on success.\n"
    )
    out = VerdictAgent._parse(raw)
    assert out.verdict == Verdict.BLOCK
    assert "drain all of your USDC" in out.headline
    assert len(out.reasons) == 3


def test_verdict_parser_falls_back_to_warn_on_unknown():
    raw = "VERDICT: MAYBE\nHEADLINE: unclear\n"
    out = VerdictAgent._parse(raw)
    assert out.verdict == Verdict.WARN
