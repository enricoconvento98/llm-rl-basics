# Status

| Phase | State |
|---|---|
| 0 — Scaffolding | In progress |
| 1 — Data pipeline | Not started |
| 2 — Allocation backtesting + baselines | Not started |
| 3 — Allocation RL agent | Not started |
| 4 — Intraday data + execution simulator | Not started |
| 5 — Execution RL agent | Not started |
| 6 — Combined backtest | Not started |
| 7 — Shadow mode | Not started |
| 8 — Paper trading | Not started |

## Open decisions (HANDOFF §10)

| Decision | Status |
|---|---|
| Asset universe and base currency | Open (needed for Phase 1) |
| Rebalance frequency | Open (needed for Phase 2) |
| Execution window length and slice size | Open (needed for Phase 4) |
| Paid intraday data provider | Open (only if IBKR data is insufficient, Phase 4) |
| Risk limits (max weight, drawdown kill switch) | Open. `configs/runtime/*.yaml` hold placeholders |
| Where services run (host, ports, Traefik) | Open. Compose binds to 127.0.0.1 until decided |
