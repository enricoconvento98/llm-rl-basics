# rl-trading

A reinforcement learning trading system with two layers: an **allocation agent** (what to hold,
daily) and an **execution agent** (how to fill the orders, intraday). It is built and validated in
stages: backtest → shadow mode → paper trading. **No real-money trading.**

- Spec, phases and safety rules: [`HANDOFF.md`](HANDOFF.md)
- Progress and open decisions: [`docs/STATUS.md`](docs/STATUS.md)
- Conventions for contributors (human or Claude): [`CLAUDE.md`](CLAUDE.md)

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Docker. This project lives in the `rl-trading/` folder of
the `llm-rl-basics` repository; run every command from that folder.

```bash
cd rl-trading
make install                 # venv + dependencies + pre-commit hooks
make check                   # lint, format check, type check, tests

cp .env.example .env         # then set a real POSTGRES_PASSWORD
make up                      # Postgres + MLflow
make services-check          # verify both are healthy
```

MLflow UI: http://127.0.0.1:5000 (services bind to localhost only until the hosting decision in
HANDOFF §10 is made).

## Layout

| Path | What lives there |
|---|---|
| `configs/` | YAML configs: universe, costs, risk limits, one runtime file per mode |
| `src/rltrading/domain.py` | Domain objects: `TargetWeights`, `ParentOrder`, `ChildOrder`, `Fill` |
| `src/rltrading/*/base.py` | Interfaces: `DataProvider`, `Broker`, `Agent` |
| `src/rltrading/config.py` | Typed config loading and environment settings |
| `docker/` | Docker Compose for Postgres and MLflow |
| `tests/` | pytest suite and in-memory fakes of the interfaces |
