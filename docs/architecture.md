# LaunchForge Architecture

## Overview

LaunchForge is an **AI Game Publishing Operating System** for overseas casual mobile games. One person manages 10–50 games through autonomous AI agents.

## System Layers

```
┌─────────────────────────────────────┐
│         Agent Decision Layer        │  ← E16.x Business Brains
│   (ASO / Revenue / Economy / CFO)   │
├─────────────────────────────────────┤
│       Growth Operating System       │
│     (Orchestrator / Portfolio)      │
├─────────────────────────────────────┤
│         Execution Layer             │
│   (Publishing / Monetization Ops)   │
├─────────────────────────────────────┤
│         Reality / Data Layer        │
│   (MAX / Google Play / App Store)   │
├─────────────────────────────────────┤
│       Memory / Learning Layer       │
│   (Patterns / Experiments / Audit)  │
└─────────────────────────────────────┘
```

## Core Principles

1. **Lean**: Pure Python + JSONL. No FastAPI, Postgres, React.
2. **Three-Gate Execution**: Recommendation → Simulation → Approval → Execution
3. **SIM/SHADOW mode**: `real_api_called` locked to `false` by default
4. **Deterministic**: Rule-based engines, no LLM calls in decision pipeline
5. **Namespace packages**: `from src.xxx import yyy` (no `__init__.py`)

## Key Components

### E16.x Business Brain Agents
- **E16.1**: Revenue Intelligence (analyzer / forecasting / profit / portfolio)
- **E16.1.1**: Decision Loop (3-confidence gate: AUTO / HUMAN_QUEUE / RECORD_ONLY)
- **E16.2**: Economy Intelligence (price elasticity, simulator, offer optimizer)
- **E16.6**: ASO Intelligence (13 sub-agents — see [Agent Guide](agent-guide.md))

### Publishing
- E13.5 Google Play Runtime (PlayConnector + 5 Agents)
- E15.1 Autonomous Publishing Factory

### Monetization
- 123-file monetization pipeline: reality → intelligence → strategy → executor → learning
- MAX / LevelPlay / AdMob / RemoteConfig providers
- Sandbox shadow mode for safe experimentation

## Data Flow

```
Real-World APIs → Reality Layer → Feature Store → Decision Engine
                                                      ↓
Memory Feedback ← Learning Layer ← Execution ← Approval Gate
```

## Directory Structure

```
launchforge/
├── src/            # E16.x agent brains (ASO, Revenue, Economy)
├── operation/      # Production ops engine (291 files)
├── monetization/   # Monetization pipeline (123 files)
├── security/       # Secret management, scanner, permissions
├── observability/  # Agent logging and metrics
├── audit/          # Decision and execution audit trail
├── release_gate/   # Merge gate (pytest + security scan)
├── backup/         # Snapshot / restore project data
├── tests/          # 1181 tests
├── docs/           # Documentation
├── data/           # Runtime data (JSONL)
├── credentials/    # API keys (gitignored)
└── deploy/         # Docker deployment
```
