# Status

| Phase | State |
|---|---|
| 0 — Scaffolding | Done (approved 2026-10-31, PR #1) |
| 1 — Data pipeline | In progress: code done, waiting for Yahoo network access to download data |
| 2 — Allocation backtesting + baselines | Not started |
| 3 — Allocation RL agent | Not started |
| 4 — Intraday data + execution simulator | Not started |
| 5 — Execution RL agent | Not started |
| 6 — Combined backtest | Not started |
| 7 — Shadow mode | Not started |
| 8 — Paper trading | Not started |

## Decisions (HANDOFF §10)

| Decision | Status |
|---|---|
| Asset universe and base currency | **Decided 2026-10-31:** EUR base. US ETFs (SPY, VGK, IEF, TLT, GLD) for research, UCITS equivalents for trading (`configs/universe.yaml`) |
| Rebalance frequency | Open (needed for Phase 2) |
| Execution window length and slice size | Open (needed for Phase 4) |
| Paid intraday data provider | Open (only if IBKR data is insufficient, Phase 4) |
| Risk limits (max weight, drawdown kill switch) | Open. `configs/runtime/*.yaml` hold placeholders |
| Where services run (host, ports, Traefik) | Open. Compose binds to 127.0.0.1 until decided |
| Daily data source (Phase 1) | **Decided 2026-10-31:** Yahoo Finance via yfinance, with quality checks; IBKR from Phase 7 |
