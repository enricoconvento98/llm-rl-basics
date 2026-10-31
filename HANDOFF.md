# HANDOFF — RL Trading System (allocation + execution)

> Handoff for Claude Code. Read this whole file before writing code.
> Work **phase by phase**. Each phase ends at a **gate**: stop, summarize the results, and wait for Enrico's approval before starting the next phase.

---

## 1. Context

Personal project by Enrico (Data & ML Engineer, based in Italy). The goal is a reinforcement learning trading system, built in validated stages:

1. **Backtesting** on historical data.
2. **Shadow mode**: live data from the broker API; decisions are computed and logged, but no orders are sent.
3. **Paper trading**: real orders sent to a broker **paper account** (no real money).
4. **Small live stage**: only after an explicit go/no-go decision. Out of scope for now.

The system has two RL layers, plus extension points for more later:

| Layer | Question it answers | Time scale | Status |
|---|---|---|---|
| Allocation agent | *What* to hold (target weights) | Daily | In scope |
| Execution agent | *How* to fill the resulting orders | Minutes within a session | In scope |
| Hedging agent | How to offset risk of derivative positions | Continuous | Future (§9) |
| Market making | Quote bid/ask, earn spread | Seconds | Future, separate track (§9) |

### Non-goals (for now)
- No real-money trading. No code path may reach a live account without the explicit guard in §6.
- No high-frequency trading, no options, no leverage, no short selling.

---

## 2. Core design principles (non-negotiable)

1. **One code path.** Feature computation, state building and policy inference must be **the same modules** in backtest, shadow and paper modes. Only the data source and order sink change, through interfaces.
2. **No look-ahead.** Every feature at time *t* uses only data available strictly before the decision at *t*. Add tests for this (§7).
3. **Costs everywhere.** Every simulation includes commissions plus slippage/spread. No frictionless results get reported.
4. **Baselines first.** Every RL agent is compared against simple, non-learned baselines on the same splits and the same cost model.
5. **Risk controls live outside the model.** Position limits, turnover limits and kill switches are deterministic code that can override any policy output.
6. **Reproducibility.** Seeds, configs, data snapshots and model artifacts are tracked in MLflow. Every reported result must be reproducible from a run ID.
7. **Pluggable components.** Brokers, data providers, agents and environments implement interfaces, so future layers (§9) and future brokers plug in without rewrites.

---

## 3. Tech stack

- Python 3.11+, `uv` or `poetry` for dependencies
- pandas / polars, numpy
- Gymnasium (environments), Stable-Baselines3 (PPO, SAC, DQN)
- PostgreSQL for metadata and decision/order logs; Parquet for bar data
- MLflow for experiment tracking and model registry
- `ib_async` for Interactive Brokers (IB Gateway in Docker)
- Docker Compose for all services (runs on Enrico's self-hosted Docker host)
- pytest, ruff, mypy
- Pydantic settings + YAML configs

Verify current library versions and APIs before pinning; don't rely on memory for them.

---

## 4. Repository layout

```
rl-trading/
├── CLAUDE.md                  # short pointer to this file + coding conventions
├── HANDOFF.md                 # this file
├── configs/
│   ├── universe.yaml          # tickers, dates
│   ├── costs.yaml             # commission, slippage, spread models
│   ├── allocation/*.yaml      # env + agent hyperparams
│   ├── execution/*.yaml
│   └── runtime/{backtest,shadow,paper}.yaml
├── docker/
│   ├── docker-compose.yml     # postgres, mlflow, ib-gateway, agent-service
│   └── ...
├── src/rltrading/
│   ├── data/
│   │   ├── providers/         # base.py (DataProvider), ibkr.py, yfinance_dev.py, ...
│   │   ├── store.py           # Parquet/Postgres I/O
│   │   └── quality.py         # gap, split, outlier checks
│   ├── features/              # pure functions, no I/O; shared by all modes
│   ├── costs/                 # commission + slippage + fill models
│   ├── envs/
│   │   ├── base.py            # common TradingEnv helpers
│   │   ├── allocation_env.py
│   │   └── execution_env.py
│   ├── agents/
│   │   ├── base.py            # Agent interface: act(state) -> action
│   │   ├── baselines/         # equal_weight, buy_hold, momentum, min_var, twap, vwap
│   │   └── rl/                # SB3 wrappers, training loops
│   ├── backtest/
│   │   ├── engine.py          # daily allocation backtester
│   │   ├── intraday.py        # execution simulator (child orders, fill model)
│   │   ├── walkforward.py
│   │   └── metrics.py
│   ├── broker/
│   │   ├── base.py            # Broker interface (see §5)
│   │   ├── simulated.py       # used by backtests
│   │   ├── ibkr.py            # paper (and later live) via ib_async
│   │   └── dryrun.py          # shadow mode: logs orders, sends nothing
│   ├── risk/                  # limits, kill switch, pre-trade checks
│   ├── runtime/
│   │   ├── scheduler.py       # daily cycle orchestration
│   │   └── orchestrator.py    # allocation -> risk -> execution -> broker
│   └── monitoring/            # logging, alerts, report generation
├── tests/
└── notebooks/                 # exploration only; no logic lives here
```

---

## 5. Key interfaces

Define these early (Phase 0). Everything else depends on them.

```python
class DataProvider(Protocol):
    def daily_bars(self, symbols, start, end) -> pd.DataFrame: ...
    def intraday_bars(self, symbols, start, end, freq) -> pd.DataFrame: ...
    def quotes(self, symbols, start, end) -> pd.DataFrame: ...   # optional per provider

class Broker(Protocol):
    def positions(self) -> dict[str, float]: ...
    def cash(self) -> float: ...
    def place_order(self, order: ChildOrder) -> OrderId: ...
    def cancel(self, order_id: OrderId) -> None: ...
    def fills(self, since) -> list[Fill]: ...

class Agent(Protocol):
    def act(self, state: np.ndarray) -> np.ndarray: ...

# Domain objects (dataclasses / pydantic)
TargetWeights   # output of allocation layer
ParentOrder     # symbol, side, qty, deadline  (allocation -> execution)
ChildOrder      # symbol, side, qty, type (MKT/LMT), limit_price, tif
Fill            # order_id, qty, price, ts, fees
```

Data flow per trading day:

```
DataProvider -> features -> AllocationAgent -> TargetWeights
   -> diff vs positions -> ParentOrders -> RiskChecks
   -> ExecutionAgent (per slice) -> ChildOrders -> Broker -> Fills -> logs/metrics
```

Every step writes to Postgres (decision log, order log, fill log) with a `run_mode` column (`backtest` / `shadow` / `paper` / `live`).

---

## 6. Safety rules for the broker layer

- IBKR ports: IB Gateway **paper = 4002**, **live = 4001** (TWS: 7497 / 7496). Verify these against current IBKR docs.
- `IBKRBroker` must **refuse to start** unless:
  - `run_mode == "paper"` **and** the connected account ID starts with the paper prefix (`DU…`), **or**
  - `run_mode == "live"` **and** the environment variable `RLTRADING_ALLOW_LIVE=I_UNDERSTAND` is set **and** a `live.yaml` config exists. Not to be created in this handoff's scope.
- Pre-trade risk checks (always on, in all modes): max weight per asset, max order notional, max daily turnover, max number of orders per day, allowed symbols only, market hours only.
- Kill switch: a drawdown threshold or a manual flag file/env var cancels all open orders and blocks new ones.
- Credentials only via env vars / Docker secrets. Never commit them.

---

## 7. Phases

### Phase 0 — Scaffolding
- Repo layout, tooling (ruff, mypy, pytest, pre-commit), config loading.
- Interfaces and domain objects from §5.
- Docker Compose with Postgres + MLflow running.
- **Gate:** `make test` passes; services come up with `docker compose up`.

### Phase 1 — Data pipeline (daily)
- Universe: 5–10 liquid ETFs plus cash (initial proposal: broad US and EU equity, bonds, gold; **ask Enrico to confirm the list**).
- Daily OHLCV, adjusted for splits/dividends, 10+ years where available.
- Data quality checks: gaps, duplicates, stale prices, split anomalies.
- Feature module: multi-window returns, rolling volatility, rolling correlations, momentum. Pure functions.
- **Tests:** a no-look-ahead test (perturb future data and assert features at *t* don't change).
- **Gate:** data report (coverage, gaps) + feature sanity plots.

### Phase 2 — Allocation backtesting + baselines
- Daily backtest engine using `SimulatedBroker` and the cost model from `costs.yaml`.
- Baselines: buy-and-hold, equal weight with monthly rebalance, momentum, minimum variance.
- Walk-forward framework (expanding or rolling train window, 1-year test windows).
- Metrics: CAGR, annualized vol, Sharpe, Sortino, max drawdown, turnover, cost drag.
- **Gate:** baseline results table across all walk-forward folds.

### Phase 3 — Allocation RL agent
- `AllocationEnv` (Gymnasium):
  - State: features + current weights (+ cash).
  - Action: continuous vector → softmax → target weights.
  - Reward: daily net return after costs, with a risk penalty (configurable: variance penalty or differential Sharpe).
- Train PPO and SAC per walk-forward fold, with **≥5 seeds** each.
- Log everything to MLflow; register the best model per fold.
- **Gate:** out-of-sample comparison vs baselines, per fold and per seed (show the spread, not just the mean). Explicitly report whether the RL agent beats the best baseline after costs.

### Phase 4 — Intraday data + execution simulator
- Intraday bars (1–5 min) and, if available, bid/ask quotes for the same universe. IBKR historical data first; note the gaps and ask Enrico before adding a paid provider (Databento, Polygon).
- `backtest/intraday.py`: simulate child orders within a session.
  - Market orders: fill at the ask/bid (or close of bar + half spread if no quotes) + slippage model.
  - Limit orders: probabilistic or conservative fill model (e.g. fill only if price trades *through* the limit). Make it configurable and **conservative by default**.
- Execution baselines: all-at-open market order, TWAP, VWAP.
- **Gate:** baseline implementation-shortfall stats; fill model assumptions documented.

### Phase 5 — Execution RL agent
- `ExecutionEnv`:
  - Episode = one parent order with a deadline (default: first 2 hours of the session).
  - State: remaining qty (normalized), remaining time, spread, short-term volatility, short-term momentum, relative volume.
  - Action: fraction of the remaining qty to trade this slice + order type (market / limit at touch). Start with a discrete action space (DQN/PPO), keep it extensible.
  - Reward: negative implementation shortfall vs arrival price; penalty for unfilled qty at the deadline (forced market order at the end).
- Training data: parent orders sampled from the allocation agent's historical decisions, plus synthetic sizes.
- **Gate:** shortfall vs TWAP/VWAP out of sample, in basis points, with confidence intervals. Expect small gains at retail size; report honestly.

### Phase 6 — Combined backtest
- Orchestrator runs allocation → risk → execution → simulated broker end to end.
- Compare: allocation agent + naive execution vs allocation agent + RL execution vs best baseline stack.
- **Gate:** net performance attribution (how much comes from allocation and how much from execution).

### Phase 7 — Shadow mode (API, no orders)
- IB Gateway container + `IBKRBroker` (read-only calls) + `DryRunBroker` as the order sink.
- Daily scheduler: pull live data, compute decisions, log intended parent and child orders.
- Reconciliation job: recompute the same day offline from stored data and assert identical decisions. Any mismatch is a bug.
- **Gate:** ≥2 weeks of shadow logs with zero unexplained mismatches.

### Phase 8 — Paper trading
- Switch the order sink to `IBKRBroker` on the **paper** account.
- Log every child order, fill, rejection, cancellation and latency.
- Monitoring: daily report (PnL, positions, realized slippage vs simulator assumptions), alerts on errors, kill switch tested.
- Run for **≥2–3 months**.
- Known limitation: paper fills are simulated by IBKR and don't reflect real queue position or impact. Paper validates **plumbing and allocation**; execution quality needs a small live stage later.
- **Gate:** report comparing paper vs backtest expectations, plus a go/no-go recommendation. **Do not implement the live stage.**

---

## 8. Testing requirements
- Unit tests for features (including no-look-ahead), cost models, fill models, risk checks.
- Property test: backtest with zero costs and a buy-and-hold agent equals the asset's adjusted return.
- Integration test: one simulated trading day through the full orchestrator.
- Broker tests run against a fake broker; never hit IBKR in CI.
- Guard test: `IBKRBroker` refuses live ports/accounts without the explicit flag.

---

## 9. Future developments — design for them now, don't build them yet

Keep the interfaces general enough that these slot in later:

1. **Small live stage.** Same orchestrator, `run_mode=live`, tiny capital, guarded per §6. Main purpose: validate execution quality with real fills. Note for Enrico: Italian taxation of gains depends on the broker regime (IBKR is *regime dichiarativo*); plan for reporting.
2. **Crypto sandbox for execution research.** Add a `CcxtBroker` / `CcxtDataProvider` (exchange testnets, order book data). Execution effects are much more visible there, which makes it a better lab for the execution agent.
3. **Order-book-level execution.** Extend `ExecutionEnv` state with L2 features (depth, imbalance) once quote/book data is available; switch to finer slices.
4. **Hedging layer.** If options are added (for example protective puts on the portfolio), add a `HedgingAgent` between allocation and execution. Deep hedging is trained on simulated paths (GBM/Heston calibrated to market), with reward = negative CVaR of hedged PnL. Requires an `OptionPosition` domain object and pricing utilities.
5. **Market making.** A separate track, not a layer of this pipeline: needs tick/L2 data, an event-driven simulator, and low-latency infra. Reuse only `costs/`, `risk/`, `broker/` interfaces and MLflow conventions.
6. **Larger universe / multi-market.** EU equities (Xetra, Borsa Italiana), FX for currency exposure. Universe and calendars must be config-driven, never hard-coded.
7. **Regime awareness.** Optional regime classifier (volatility/trend states) as an extra state feature for both agents.
8. **Forecasting features.** Supervised models (volatility forecast, return direction) whose outputs are fed into the RL state. Keep them in `features/` with the same no-look-ahead guarantees.
9. **Additional brokers.** Any new broker only implements the `Broker` protocol; the orchestrator must not change.
10. **Dashboard.** A web dashboard over the Postgres logs (equity curve, positions, slippage, decision traces).

---

## 10. Open decisions for Enrico (ask, don't assume)
- Final asset universe and base currency (EUR vs USD) — affects FX exposure.
- Rebalance frequency (daily vs weekly) for the allocation agent.
- Execution window length and slice size.
- Intraday data source if IBKR historical data is insufficient (paid providers cost money).
- Risk limits: max weight per asset, drawdown kill-switch threshold.
- Where services run (which host, ports, Traefik routing for MLflow and the dashboard).

---

## 11. How to work
- One phase per branch/PR; small commits; the PR description includes the gate report.
- Configs over constants. No magic numbers in code.
- Never report a result without costs, multiple seeds and out-of-sample splits.
- If something is ambiguous or touches §6 safety or §10 decisions: **stop and ask**.
