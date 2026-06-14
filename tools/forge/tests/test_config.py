import tomllib

from forge import config
from forge.config import DEFAULT_CONFIG, ForgeConfig, _parse


def test_review_defaults():
    cfg = ForgeConfig()
    assert cfg.review.model == "sonnet"
    assert cfg.review.max_rounds == 2


def test_review_parsed_from_toml():
    cfg = _parse({"review": {"model": "opus", "max_rounds": 3}})
    assert cfg.review.model == "opus"
    assert cfg.review.max_rounds == 3


def test_review_partial_override_keeps_defaults():
    cfg = _parse({"review": {"model": "opus"}})
    assert cfg.review.model == "opus"
    assert cfg.review.max_rounds == 2


def test_default_config_has_review_block():
    data = tomllib.loads(DEFAULT_CONFIG)
    assert data["review"]["model"] == "sonnet"
    assert data["review"]["max_rounds"] == 2


def test_load_falls_back_to_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "missing.toml")
    assert config.load().review.model == "sonnet"
