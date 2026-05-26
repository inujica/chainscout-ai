# 🔭 ChainScout AI

**Pre-Signing Transaction Sentinel — protect Web3 wallets BEFORE they sign, not after they get drained.**

ChainScout simulates every outbound transaction through a 5-stage AI reasoning pipeline powered by MiMo-V2.5-Pro before the user clicks "Sign". If something looks wrong — hidden allowances, spoofed permits, EIP-7702 delegate hijack, MEV sandwich exposure — the user sees a plain-English verdict in under 2 seconds.

> Most Web3 security tools are forensic. ChainScout is preventive.

---

## Why pre-signing?

Post-deployment scanners (audits, rugpull monitors, exploit DBs) all share one limitation: by the time they fire, the user is already on-chain. Drainer kits, EIP-7702 delegate phishing, infinite-approval traps and Uniswap V4 hook abuse all bypass static contract analysis because the malicious behaviour lives in the **calldata of the user's own transaction**, not the contract bytecode.

ChainScout intercepts at the wallet middleware layer:

```
   Wallet UI                ChainScout                MiMo-V2.5-Pro
       │                        │                          │
       │  unsigned tx ───────▶  │                          │
       │                        │  simulate (eth_call) ───▶│
       │                        │  decode (4byte + ABI) ──▶│
       │                        │  trace allowance delta ─▶│
       │                        │  check delegate code  ──▶│
       │                        │  MEV sandwich quote   ──▶│
       │                        │ ◀── verdict + reasons    │
       │ ◀── ALLOW / WARN / BLOCK                          │
```

The 5-stage pipeline is the cost driver. Each stage is one MiMo reasoning call.

---

## The 5 stages

| # | Stage | What it asks the model | Tokens / call |
|---|-------|------------------------|---------------|
| 1 | **Calldata Decoder** | "Given this 4-byte selector + raw calldata + verified ABI, what function is being called and with what arguments in human terms?" | ~120K |
| 2 | **State-Diff Reasoner** | "Here is the eth_call state diff. Which storage slots change? Which approvals/allowances grow? Is the user actually receiving anything?" | ~280K |
| 3 | **Delegate-Code Auditor** | "The destination has EIP-7702 delegated code 0xef0100…. Decode the delegate target. Is it Multicall3, a known router, or an unverified contract?" | ~180K |
| 4 | **MEV Exposure Probe** | "Given pool reserves + slippage tolerance, simulate the worst-case sandwich. What is the user's expected loss percentile?" | ~220K |
| 5 | **Verdict Synthesiser** | "Aggregate the four signals. Output: ALLOW / WARN / BLOCK + 3-sentence reason in plain English." | ~80K |

**Total per transaction: ~880K tokens.**

---

## Token consumption model

| User segment | Tx scanned/day | Tokens/day | Tokens/month |
|--------------|----------------|------------|--------------|
| Casual (1 wallet, 5 tx) | 5 | 4.4M | 132M |
| Active trader (10-30 tx) | 20 | 17.6M | 528M |
| Multi-wallet farmer (100 tx) | 100 | 88M | 2.6B |
| Power user (500 tx) | 500 | 440M | 13B |

Target onboarding: 50 active traders + 10 power users in first month → ~10B tokens/month.

---

## What's in this repo

```
chainscout-ai/
├── src/
│   ├── sentinel.py            # main entrypoint, hooks wallet RPC
│   ├── agents/
│   │   ├── calldata_decoder.py
│   │   ├── state_diff.py
│   │   ├── delegate_auditor.py
│   │   ├── mev_probe.py
│   │   └── verdict.py
│   └── mimo_client.py         # thin wrapper around MiMo OpenAI-compatible API
├── tests/
│   └── test_sentinel.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## Tech stack

- **Reasoning model:** MiMo-V2.5-Pro (long-chain reasoning, 1M ctx)
- **Light analysis:** MiMo-V2.5 (calldata decode, verdict synthesis)
- **EVM simulation:** `eth_call` + `debug_traceCall` against alchemy/drpc
- **ABI lookup:** 4byte.directory + sourcify
- **Wallet integration:** EIP-1193 middleware (works with rabby, frame, rainbow)
- **Orchestrator pattern:** Hermes Agent skill router

---

## Status

🚧 Pre-alpha. Core 5-agent pipeline is scaffolded with MiMo API plumbing. Working toward MVP integration with Rabby wallet's tx interception layer.

Seeking MiMo API credits to run the simulation pipeline at production scale — current bottleneck is reasoning calls per transaction (~880K tokens), not infrastructure.

---

## License

MIT
