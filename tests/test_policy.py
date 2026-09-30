from __future__ import annotations

from pathlib import Path

import pytest
from statguard.config import ConfigError

from statguard_desktop.adapter import (
    config_for_target,
    make_policy,
    scan_desktop,
    threshold_reached,
)
from statguard_desktop.policy import CONFIG_CUSTOM, CONFIG_NONE, CONFIG_PROJECT, project_config_path
from tests.helpers import RISKY_ML001


def test_project_config_is_target_root_or_file_parent_only(tmp_path) -> None:
    root = tmp_path / "project"
    nested = root / "src"
    nested.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[tool.statguard]\ndisable-rules=['ML001']\n")
    source = nested / "analysis.py"
    source.write_text("pass\n")
    assert project_config_path(root) == root / "pyproject.toml"
    assert project_config_path(source) == nested / "pyproject.toml"
    config, path = config_for_target(CONFIG_PROJECT, source)
    assert config.disable_rules == ()
    assert path == str(nested / "pyproject.toml")


def test_directory_project_config_loads_core_policy(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.statguard]\ndisable-rules=['ML001']\nexclude=['ignored']\nfail-on='warning'\n"
    )
    config, path = config_for_target(CONFIG_PROJECT, tmp_path)
    assert config.disable_rules == ("ML001",)
    assert config.exclude == ("ignored",)
    assert config.fail_on == "warning"
    assert path == str(tmp_path / "pyproject.toml")


def test_none_config_ignores_existing_invalid_project_config(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.statguard]\nunknown=true\n")
    config, path = config_for_target(CONFIG_NONE, tmp_path)
    assert config.disable_rules == config.exclude == ()
    assert config.fail_on is None
    assert path is None


def test_custom_toml_loads_core_settings(tmp_path) -> None:
    custom = tmp_path / "settings.toml"
    custom.write_text(
        "[tool.statguard]\ndisable-rules=['ST002']\nexclude=['cache']\nfail-on='error'\n"
    )
    config, path = config_for_target(CONFIG_CUSTOM, tmp_path, custom)
    assert config.disable_rules == ("ST002",)
    assert config.exclude == ("cache",)
    assert config.fail_on == "error"
    assert path == str(custom)


@pytest.mark.parametrize(
    "text",
    [
        "[tool.statguard]\nunknown=true\n",
        "[tool.statguard]\ndisable-rules=['ML999']\n",
        "[tool.statguard]\nfail-on='critical'\n",
        "[tool.statguard]\nexclude='not-array'\n",
        "this is not toml [",
    ],
)
def test_custom_config_errors_are_core_validation_errors(tmp_path, text) -> None:
    config = tmp_path / "custom.toml"
    config.write_text(text)
    with pytest.raises(ConfigError):
        config_for_target(CONFIG_CUSTOM, tmp_path, config)


@pytest.mark.parametrize("exclude", ["", ".", "../outside", "a/../../x", "C:\\outside", "/abs"])
def test_invalid_exclusions_are_rejected(exclude) -> None:
    with pytest.raises(ValueError):
        make_policy(exclude=(exclude,))


def test_threshold_policy_uses_core_semantics(tmp_path) -> None:
    source = tmp_path / "risk.py"
    source.write_text(RISKY_ML001, encoding="utf-8")
    none = scan_desktop(source, make_policy(fail_on=None))
    warning = scan_desktop(source, make_policy(fail_on="warning"))
    error = scan_desktop(source, make_policy(fail_on="error"))
    assert threshold_reached(none) is False
    assert threshold_reached(warning) is True
    assert threshold_reached(error) is False


def test_exclusion_is_applied_to_directory_scan(tmp_path) -> None:
    (tmp_path / "visible.py").write_text(RISKY_ML001, encoding="utf-8")
    ignored = tmp_path / "ignored"
    ignored.mkdir()
    (ignored / "hidden.py").write_text(RISKY_ML001, encoding="utf-8")
    result = scan_desktop(tmp_path, make_policy(exclude=("ignored",)))
    assert [Path(item.path).name for item in result.report.results] == ["visible.py"]
