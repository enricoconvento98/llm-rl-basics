# CLAUDE.md

**Read [`HANDOFF.md`](HANDOFF.md) first.** It is the spec: phases, gates, interfaces and safety rules.
Work one phase at a time and stop at each gate for Enrico's approval.

## Current phase

See [`docs/STATUS.md`](docs/STATUS.md).

## Commands

| Command | What it does |
|---|---|
| `make install` | Create the venv and install everything (`uv sync`) |
| `make check` | Lint + format check + type check + tests. Run before every commit |
| `make test` | Tests only |
| `make up` / `make down` | Start / stop Postgres and MLflow (`docker/docker-compose.yml`) |
| `make services-check` | Check that Postgres and MLflow are healthy |

## Conventions

- **Python 3.12+**, managed with `uv`. Add dependencies with `uv add`, never by editing the lock file.
- **src layout**: all logic lives in `src/rltrading/`. Notebooks are for exploration only.
- **Configs over constants.** Anything that could change (limits, costs, windows, symbols) goes in
  `configs/*.yaml` and is loaded through the Pydantic models in `rltrading.config`. No magic numbers.
- **Interfaces in `base.py`** (`typing.Protocol`). New brokers, data providers and agents implement
  a protocol; the orchestrator never imports a concrete implementation directly.
- **Domain objects** (`rltrading.domain`) are frozen dataclasses that validate themselves on creation.
- **Features are pure functions**: no I/O, no global state, and only data strictly before *t*.
  Every feature gets a no-look-ahead test.
- **Timestamps are timezone-aware UTC** everywhere inside the system.
- **Safety (HANDOFF §6) is never optional.** Anything touching live trading, the live port or
  `RLTRADING_ALLOW_LIVE`: stop and ask.
- **Never commit credentials.** Secrets come from environment variables / `.env` (git-ignored).
- **No result without costs, multiple seeds and out-of-sample splits.**
- Strict typing: `mypy --strict` must pass on `src/`.
