from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from rltrading.config import (
    CommissionConfig,
    CostsConfig,
    RuntimeConfig,
    Settings,
    UniverseConfig,
    load_app_config,
    load_yaml,
)
from rltrading.domain import RunMode

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"
RUNTIME_FILES = sorted((CONFIG_DIR / "runtime").glob("*.yaml"))


@pytest.mark.parametrize("runtime_file", RUNTIME_FILES, ids=lambda p: p.stem)
def test_every_shipped_runtime_config_loads(runtime_file: Path) -> None:
    cfg = load_app_config(runtime_file)
    assert cfg.runtime.run_mode == RunMode(runtime_file.stem)
    assert cfg.universe.symbols
    assert 0 < cfg.risk.max_weight_per_asset <= 1


def test_runtime_files_exist_for_all_non_live_modes() -> None:
    assert {p.stem for p in RUNTIME_FILES} == {"backtest", "shadow", "paper"}
    assert not (CONFIG_DIR / "runtime" / "live.yaml").exists(), "live.yaml is out of scope (HANDOFF §6)"


def _runtime(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "run_mode": "backtest",
        "broker": "simulated",
        "data_provider": "parquet_store",
        "universe_file": "universe.yaml",
        "costs_file": "costs.yaml",
        "risk_file": "risk.yaml",
    }
    return base | overrides


@pytest.mark.parametrize(
    ("mode", "broker"),
    [("backtest", "ibkr"), ("shadow", "ibkr"), ("shadow", "simulated"), ("paper", "dryrun")],
)
def test_broker_must_match_run_mode(mode: str, broker: str) -> None:
    with pytest.raises(ValidationError, match="may not use broker"):
        RuntimeConfig.model_validate(_runtime(run_mode=mode, broker=broker))


def test_live_mode_is_rejected() -> None:
    with pytest.raises(ValidationError, match="live mode is out of scope"):
        RuntimeConfig.model_validate(_runtime(run_mode="live", broker="ibkr"))


def test_unknown_keys_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        RuntimeConfig.model_validate(_runtime(max_wieght=0.5))


def test_costs_cannot_be_zero(tmp_path: Path) -> None:
    def costs(per_share: float, half_spread_bps: float, slippage_bps: float) -> dict[str, object]:
        commission = {
            "per_share": per_share,
            "pct_of_notional": 0,
            "min_per_order": 0,
            "max_pct_of_notional": 0.01,
        }
        return {"commission": commission, "half_spread_bps": half_spread_bps, "slippage_bps": slippage_bps}

    path = tmp_path / "costs.yaml"
    path.write_text(yaml.safe_dump(costs(per_share=0, half_spread_bps=1, slippage_bps=1)))
    with pytest.raises(ValidationError, match="commission model is zero"):
        load_yaml(path, CostsConfig)
    path.write_text(yaml.safe_dump(costs(per_share=0.005, half_spread_bps=0, slippage_bps=0)))
    with pytest.raises(ValidationError, match="spread and slippage"):
        load_yaml(path, CostsConfig)


def test_commission_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        CommissionConfig(per_share=-0.01, pct_of_notional=0, min_per_order=1, max_pct_of_notional=0.01)


def test_universe_rejects_duplicates_and_bad_dates() -> None:
    asset = {"symbol": "SPY", "name": "x", "asset_class": "equity", "exchange": "ARCA", "currency": "USD"}
    base = {"base_currency": "USD", "start_date": "2010-01-01", "calendar": "XNYS"}
    with pytest.raises(ValidationError, match="duplicate"):
        UniverseConfig.model_validate(base | {"assets": [asset, asset]})
    with pytest.raises(ValidationError, match="end_date"):
        UniverseConfig.model_validate(base | {"end_date": "2009-01-01", "assets": [asset]})


def test_load_yaml_requires_mapping(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("- just\n- a list\n")
    with pytest.raises(ValueError, match="mapping"):
        load_yaml(path, UniverseConfig)


class TestSettings:
    def test_defaults_without_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)  # no .env file here
        for var in ("RLTRADING_ALLOW_LIVE", "RLTRADING_POSTGRES_DSN"):
            monkeypatch.delenv(var, raising=False)
        s = Settings()
        assert s.postgres_dsn is None
        assert not s.live_opt_in

    @pytest.mark.parametrize(
        ("value", "expected"), [("I_UNDERSTAND", True), ("yes", False), ("i_understand", False)]
    )
    def test_live_opt_in_needs_exact_value(
        self, monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
    ) -> None:
        monkeypatch.setenv("RLTRADING_ALLOW_LIVE", value)
        assert Settings().live_opt_in is expected

    def test_secrets_are_not_printed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RLTRADING_POSTGRES_DSN", "postgresql://u:hunter2@db/x")
        assert "hunter2" not in repr(Settings())
