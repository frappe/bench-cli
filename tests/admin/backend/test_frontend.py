from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import pilot
from admin.backend import frontend
from pilot.exceptions import BenchError

REPO_ROOT = Path(__file__).resolve().parents[3]


def _layout(root: Path, *, source: bool, dist: bool) -> None:
    if source:
        pkg = root / "admin" / "frontend" / "dashboard" / "package.json"
        pkg.parent.mkdir(parents=True, exist_ok=True)
        pkg.write_text("{}")
    if dist:
        assets = root / "admin" / "backend" / "static" / "dashboard" / "assets"
        assets.mkdir(parents=True, exist_ok=True)


def _ensure(root: Path, *, is_dev: bool) -> object:
    with (
        patch.object(pilot, "is_dev_build", is_dev),
        patch("pilot.utils.cli_root", return_value=root),
        patch.object(frontend, "build_admin_frontend") as build,
    ):
        frontend.ensure_admin_frontend()
    return build


def test_released_install_serves_dist_without_building(tmp_path: Path) -> None:
    _layout(tmp_path, source=True, dist=True)
    build = _ensure(tmp_path, is_dev=False)
    build.assert_not_called()


def test_dev_build_compiles_from_source(tmp_path: Path) -> None:
    _layout(tmp_path, source=True, dist=True)
    build = _ensure(tmp_path, is_dev=True)
    build.assert_called_once()


def test_released_install_without_dist_raises(tmp_path: Path) -> None:
    _layout(tmp_path, source=True, dist=False)
    with (
        patch.object(pilot, "is_dev_build", False),
        patch("pilot.utils.cli_root", return_value=tmp_path),
        pytest.raises(BenchError, match="missing from this release"),
    ):
        frontend.ensure_admin_frontend()


def _install_command(tmp_path: Path, *, lockfile: bool) -> list[str]:
    """Run a stale build and return the install command it chose."""
    source = tmp_path / "dashboard"
    source.mkdir()
    (source / "package.json").write_text("{}")
    if lockfile:
        (source / "package-lock.json").write_text("{}")
    with patch("pilot.utils.run_command") as run_command:
        frontend._build_frontend(source, "dashboard", lambda message: None)
    return run_command.call_args_list[0].args[0]


def test_locked_frontend_installs_without_rewriting_lockfile(tmp_path: Path) -> None:
    assert _install_command(tmp_path, lockfile=True) == ["npm", "ci"]


def test_frontend_without_lockfile_falls_back_to_npm_install(tmp_path: Path) -> None:
    assert _install_command(tmp_path, lockfile=False) == ["npm", "install"]


@pytest.mark.skipif(not (REPO_ROOT / ".git").exists(), reason="not a git checkout")
def test_build_artifacts_ignored_at_every_frontend_depth() -> None:
    artifacts = [
        "admin/frontend/node_modules/vue",
        "admin/frontend/components.d.ts",
        "admin/frontend/dashboard/node_modules/vue",
        "admin/frontend/dashboard/components.d.ts",
        "admin/frontend/editor/node_modules/vue",
        "admin/frontend/editor/components.d.ts",
    ]
    ignored = subprocess.run(
        ["git", "check-ignore", *artifacts],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert sorted(ignored) == sorted(artifacts)
