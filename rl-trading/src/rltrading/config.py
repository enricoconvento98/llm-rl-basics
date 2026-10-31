"""Typed configuration.

YAML files in `configs/` hold everything that can change between experiments or environments
(HANDOFF §11: configs over constants). Each file maps to a frozen Pydantic model that rejects
unknown keys, so a typo fails loudly instead of being silently ignored. Secrets never live in
YAML: they come from environment variables through `Settings`.
"""

from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from rltrading.domain import RunMode

# The exact value RLTRADING_ALLOW_LIVE must have before anything may touch a live account (HANDOFF §6).
LIVE_OPT_IN_VALUE = "I_UNDERSTAND"

BrokerKind = Literal["simulated", "dryrun", "ibkr"]
ListingKind = Literal["research", "trading"]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]

# Which order sink each run mode is allowed to use. Live mode is out of scope (HANDOFF §1, §7 phase 8).
ALLOWED_BROKERS: dict[RunMode, frozenset[str]] = {
    RunMode.BACKTEST: frozenset({"simulated"}),
    RunMode.SHADOW: frozenset({"dryrun"}),
    RunMode.PAPER: frozenset({"ibkr"}),
    RunMode.LIVE: frozenset(),
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------- universe.yaml


class Listing(_Strict):
    """One tradable line of an asset on one exchange."""

    symbol: str = Field(min_length=1)  # exchange ticker
    exchange: str = Field(min_length=1)
    currency: Currency
    calendar: str = Field(min_length=1)  # exchange_calendars name, e.g. "XNYS", "XETR"
    isin: str | None = Field(default=None, pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
    data_symbols: dict[str, str] = Field(min_length=1)  # provider name -> that provider's symbol


class Asset(_Strict):
    """An exposure the allocation agent can hold, with the listing used for research (long US history)
    and the listing actually traded (UCITS, buyable from an EU retail account)."""

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    asset_class: Literal["equity", "bond", "commodity"]
    research: Listing
    trading: Listing


class FxRate(_Strict):
    """Quote convention: `data_symbol` gives units of `currency` per 1 unit of the base currency
    (Yahoo's "EURUSD=X" is USD per EUR), so price_in_base = price / rate."""

    currency: Currency
    data_symbols: dict[str, str] = Field(min_length=1)


class UniverseConfig(_Strict):
    base_currency: Currency
    start_date: date
    end_date: date | None = None  # None = up to the latest available data
    assets: list[Asset] = Field(min_length=1)
    fx: list[FxRate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> Self:
        ids = [a.id for a in self.assets]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate asset ids in universe: {ids}")
        if self.end_date is not None and self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        quoted = {f.currency for f in self.fx}
        needed = {lst.currency for a in self.assets for lst in (a.research, a.trading)} - {self.base_currency}
        if missing := needed - quoted:
            raise ValueError(
                f"no fx rate configured for {sorted(missing)} (base currency {self.base_currency})"
            )
        return self

    @property
    def asset_ids(self) -> list[str]:
        return [a.id for a in self.assets]

    def listing(self, asset_id: str, kind: ListingKind) -> Listing:
        asset = next((a for a in self.assets if a.id == asset_id), None)
        if asset is None:
            raise KeyError(asset_id)
        return asset.research if kind == "research" else asset.trading


# ---------------------------------------------------------------- costs.yaml


class CommissionConfig(_Strict):
    """Commission per order = clip(per_share * qty + pct_of_notional * notional, min, max)."""

    per_share: float = Field(ge=0)
    pct_of_notional: float = Field(ge=0, lt=1)
    min_per_order: float = Field(ge=0)
    max_pct_of_notional: float = Field(gt=0, le=1)


class CostsConfig(_Strict):
    commission: CommissionConfig
    half_spread_bps: float = Field(ge=0)  # used when no quotes are available
    slippage_bps: float = Field(ge=0)  # extra cost on top of the spread for every fill

    @model_validator(mode="after")
    def _costs_everywhere(self) -> Self:
        # HANDOFF §2.3: no frictionless simulations. Zero costs are only allowed in tests,
        # which build CostsConfig directly instead of loading a file.
        c = self.commission
        if c.per_share == 0 and c.pct_of_notional == 0 and c.min_per_order == 0:
            raise ValueError("commission model is zero: every simulation must include commissions")
        if self.half_spread_bps == 0 and self.slippage_bps == 0:
            raise ValueError("spread and slippage are both zero: every simulation must include them")
        return self


# ---------------------------------------------------------------- runtime/*.yaml


class KillSwitchConfig(_Strict):
    max_drawdown: float = Field(gt=0, lt=1)  # fraction of peak equity
    flag_file: Path  # if this file exists, trading stops
    env_var: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")  # if this env var is set, trading stops


class RiskLimits(_Strict):
    """Deterministic pre-trade limits, applied in every mode (HANDOFF §6). Allowed symbols = the universe."""

    max_weight_per_asset: float = Field(gt=0, le=1)
    max_order_notional: float = Field(gt=0)
    max_daily_turnover: float = Field(gt=0)  # sum of |trade notional| / portfolio value
    max_orders_per_day: int = Field(gt=0)
    market_hours_only: bool
    kill_switch: KillSwitchConfig


class RuntimeConfig(_Strict):
    run_mode: RunMode
    broker: BrokerKind
    data_provider: str = Field(min_length=1)
    universe_file: Path
    costs_file: Path
    risk_file: Path

    @field_validator("run_mode")
    @classmethod
    def _no_live(cls, mode: RunMode) -> RunMode:
        if mode is RunMode.LIVE:
            raise ValueError("live mode is out of scope (HANDOFF §1 and §6): no live config may be loaded")
        return mode

    @model_validator(mode="after")
    def _broker_matches_mode(self) -> Self:
        if self.broker not in ALLOWED_BROKERS[self.run_mode]:
            raise ValueError(
                f"run_mode {self.run_mode} may not use broker {self.broker!r}; "
                f"allowed: {sorted(ALLOWED_BROKERS[self.run_mode])}"
            )
        return self


class AppConfig(_Strict):
    """Everything one run needs, loaded from a runtime file and the files it points to."""

    runtime: RuntimeConfig
    universe: UniverseConfig
    costs: CostsConfig
    risk: RiskLimits


# ---------------------------------------------------------------- data_quality.yaml


class QualityConfig(_Strict):
    stale_run_sessions: int = Field(gt=1)
    jump_abs_log_return: float = Field(gt=0)
    jump_abs_log_return_by_calendar: dict[str, float] = {}  # overrides, e.g. tighter for fx
    jump_reversal_ratio: float = Field(gt=0, le=1)
    max_missing_share: float = Field(ge=0, lt=1)


# ---------------------------------------------------------------- features.yaml


class MomentumConfig(_Strict):
    lookback: int = Field(gt=1)  # sessions
    skip: int = Field(ge=0)  # most recent sessions left out (short-term reversal)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.skip >= self.lookback:
            raise ValueError("momentum skip must be shorter than lookback")
        return self


class FeaturesConfig(_Strict):
    return_windows: list[int] = Field(min_length=1)
    volatility_windows: list[int] = Field(min_length=1)
    correlation_window: int = Field(gt=2)
    momentum: MomentumConfig
    sessions_per_year: int = Field(gt=0)  # for annualizing volatility

    @field_validator("return_windows", "volatility_windows")
    @classmethod
    def _positive_unique(cls, windows: list[int]) -> list[int]:
        if any(w < 1 for w in windows) or len(set(windows)) != len(windows):
            raise ValueError(f"windows must be unique and >= 1, got {windows}")
        return sorted(windows)


# ---------------------------------------------------------------- environment settings


class Settings(BaseSettings):
    """Values from environment variables (prefix RLTRADING_) or a local .env file."""

    model_config = SettingsConfigDict(env_prefix="RLTRADING_", env_file=".env", extra="ignore", frozen=True)

    config_dir: Path = Path("configs")
    data_dir: Path = Path("data")  # git-ignored: downloaded bars and their snapshot metadata
    postgres_dsn: SecretStr | None = None
    mlflow_tracking_uri: str = "http://127.0.0.1:5000"
    allow_live: str | None = None

    @property
    def live_opt_in(self) -> bool:
        """True only if RLTRADING_ALLOW_LIVE is exactly the opt-in value. One of several §6 checks."""
        return self.allow_live == LIVE_OPT_IN_VALUE


# ---------------------------------------------------------------- loading


def load_yaml[M: BaseModel](path: Path, model: type[M]) -> M:
    with path.open() as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return model.model_validate(data)


def load_app_config(runtime_file: Path, config_dir: Path | None = None) -> AppConfig:
    """Load a runtime config and the universe/costs/risk files it references (relative to config_dir)."""
    config_dir = config_dir or runtime_file.parent.parent
    runtime = load_yaml(runtime_file, RuntimeConfig)
    return AppConfig(
        runtime=runtime,
        universe=load_yaml(config_dir / runtime.universe_file, UniverseConfig),
        costs=load_yaml(config_dir / runtime.costs_file, CostsConfig),
        risk=load_yaml(config_dir / runtime.risk_file, RiskLimits),
    )
