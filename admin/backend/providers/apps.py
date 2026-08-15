from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from pilot.internal.git import GitRepo
from pilot.utils import installed_app_version


@dataclass
class AppInfo:
    name: str
    title: str
    description: str
    repo: str
    branch: str
    is_cloned: bool
    current_commit: str
    commit_message: str
    has_local_changes: bool
    installed_version: str
    has_update: bool
    logo_url: str = ""


class AppProvider:
    def __init__(self, bench_root: Path) -> None:
        self._bench_root = bench_root

    def get_all(self) -> list[AppInfo]:
        apps_path = self._bench_root / "apps"
        if not apps_path.is_dir():
            return []

        return [
            self.get_app(d.name) for d in sorted(apps_path.iterdir()) if d.is_dir() and (d / ".git").exists()
        ]

    def get_app(self, name: str) -> AppInfo:
        app_path = self._bench_root / "apps" / name
        repo = GitRepo(app_path)
        title, description = self.get_pyproject_meta(app_path, name)
        logo_path = self.find_logo_path(app_path, name)

        app_info = AppInfo(
            name=name,
            title=title,
            description=description,
            repo="",
            branch="",
            is_cloned=False,
            current_commit="",
            commit_message="",
            has_local_changes=False,
            installed_version=installed_app_version(self._bench_root / "env", name),
            has_update=False,
            logo_url=f"/api/v1/apps/{name}/logo" if logo_path else "",
        )
        if not repo.is_cloned:
            return app_info

        sha = repo.head_sha
        remote_sha = repo.tracking_sha(repo.branch)
        app_info.is_cloned = True
        app_info.repo = repo.remote_url
        app_info.branch = repo.branch
        app_info.current_commit = sha[:7]
        app_info.commit_message = repo.commit_subject(sha)
        app_info.has_local_changes = repo.has_local_changes
        app_info.has_update = bool(remote_sha and sha and remote_sha != sha)
        return app_info

    def get_pyproject_meta(self, app_path: Path, name: str) -> tuple[str, str]:
        """Title and description from pyproject.toml.

        Prefer `[tool.bench].app_title` (human label). Fall back to the folder /
        package name so the UI can sentence-case it.
        """
        pyproject = app_path / "pyproject.toml"
        if not pyproject.exists():
            return name, ""

        try:
            data = tomllib.loads(pyproject.read_text())
        except (tomllib.TOMLDecodeError, OSError):
            return name, ""

        project = data.get("project") or {}
        bench = ((data.get("tool") or {}).get("bench") or {})
        title = (bench.get("app_title") or "").strip() or name
        description = (
            (project.get("description") or "").strip()
            or (bench.get("app_description") or "").strip()
        )
        return title, description

    def find_logo_path(self, app_path: Path, name: str) -> Path | None:
        """Resolve a local app logo for Pilot marketplace / apps list."""
        pyproject = app_path / "pyproject.toml"
        declared = ""
        if pyproject.exists():
            try:
                data = tomllib.loads(pyproject.read_text())
                declared = str((((data.get("tool") or {}).get("bench") or {}).get("app_logo") or "")).strip()
            except (tomllib.TOMLDecodeError, OSError):
                declared = ""

        candidates: list[Path] = []
        if declared:
            # Paths in pyproject are usually relative to the repo root.
            candidates.append(app_path / declared)
            # Also accept module-relative paths written as rozh_fieldops/public/...
            if declared.startswith(f"{name}/"):
                candidates.append(app_path / declared)
        candidates.extend(
            [
                app_path / "logo.svg",
                app_path / "logo.png",
                app_path / name / "public" / "logo.svg",
                app_path / name / "public" / "logo.png",
                app_path / name / "public" / "images" / f"{name.replace('_', '-')}-logo.svg",
                app_path / name / "public" / "images" / f"{name}-logo.svg",
            ]
        )
        for path in candidates:
            if path.is_file():
                return path
        return None
