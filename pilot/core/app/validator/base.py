from __future__ import annotations

import tomllib
import typing
from pathlib import Path

from pilot.exceptions import AppValidationError

if typing.TYPE_CHECKING:
    from pilot.core.app import App


class ValidationCheck(typing.Protocol):
    """A single check run against a cloned app before it's installed.

    Raises AppValidationError to block; returns any non-blocking findings as
    warnings for the caller to surface.
    """

    def run(self, app: "App") -> list[str] | None: ...


def module_path(app: "App") -> Path:
    return app.path / app.module_name


def python_files(app: "App") -> list[Path]:
    return list(module_path(app).rglob("*.py"))


def read_pyproject(app: "App") -> dict | None:
    """The app's parsed pyproject.toml, or None when it has none.

    Checks run standalone during an update, so no one can assume
    RepoStructureCheck has already vetted the file.
    """
    path = app.path / "pyproject.toml"
    if not path.is_file():
        return None
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise AppValidationError(
            f"'{app.config.name}' has an invalid pyproject.toml: {exc}\nFix the TOML syntax."
        ) from exc
