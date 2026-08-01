from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from pilot.core.database.base import QueryResult
from pilot.core.database.engines import MariaDB, PostgreSQL
from pilot.core.site import config as site_config
from pilot.exceptions import DatabaseError

_BENCH_ROOT = Path("/bench")


def _mariadb() -> MariaDB:
    return MariaDB(host="localhost", port=3306, user="u", password="p", database="site_db")


def _postgres() -> PostgreSQL:
    return PostgreSQL(host="localhost", port=5432, user="u", password="p", database="site_db")


def _make_sqlite_site(bench_root: Path, site_name: str, setup_complete: str, apps: list[str]) -> None:
    """A real SQLite site, so the probe runs against an actual Frappe-shaped schema."""
    site_path = bench_root / "sites" / site_name
    (site_path / "db").mkdir(parents=True)
    (site_path / "site_config.json").write_text(json.dumps({"db_type": "sqlite", "db_name": "site_db"}))

    connection = sqlite3.connect(site_path / "db" / "site_db.db")
    with connection:
        connection.execute("CREATE TABLE `tabSingles` (doctype TEXT, field TEXT, value TEXT)")
        connection.execute(
            "INSERT INTO `tabSingles` VALUES ('System Settings', 'setup_complete', ?)",
            (setup_complete,),
        )
        connection.execute("CREATE TABLE `tabInstalled Application` (app_name TEXT, idx INTEGER)")
        connection.executemany(
            "INSERT INTO `tabInstalled Application` VALUES (?, ?)",
            [(app, index) for index, app in enumerate(apps)],
        )
    connection.close()


def _stub_database(monkeypatch: pytest.MonkeyPatch, engine, rows: list[list]) -> list[str]:
    """Keep the real engine so identifier quoting is exercised, stub the wire."""
    executed: list[str] = []

    def execute(self, query: str, read_only: bool = True) -> QueryResult:
        executed.append(query)
        return QueryResult(columns=["value"], rows=rows, duration_ms=0.0)

    monkeypatch.setattr(type(engine), "execute", execute)
    monkeypatch.setattr(site_config, "make_site_database", lambda *args, **kwargs: engine)
    return executed


def test_is_setup_complete_true_on_mariadb(monkeypatch: pytest.MonkeyPatch) -> None:
    executed = _stub_database(monkeypatch, _mariadb(), [["1"]])

    assert site_config.is_setup_complete(_BENCH_ROOT, "site.localhost") is True
    assert "`tabSingles`" in executed[0]


def test_is_setup_complete_false_on_mariadb(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_database(monkeypatch, _mariadb(), [["0"]])

    assert site_config.is_setup_complete(_BENCH_ROOT, "site.localhost") is False


def test_is_setup_complete_true_on_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    executed = _stub_database(monkeypatch, _postgres(), [["1"]])

    assert site_config.is_setup_complete(_BENCH_ROOT, "postgres.localhost") is True
    assert '"tabSingles"' in executed[0]
    assert "`" not in executed[0]


@pytest.mark.parametrize("stored", ["true", "TRUE", " true "])
def test_is_setup_complete_accepts_postgres_boolean_spelling(
    monkeypatch: pytest.MonkeyPatch, stored: str
) -> None:
    """set_single_value writes a Python bool: psycopg2 renders it 'true', mysqlclient '1'."""
    _stub_database(monkeypatch, _postgres(), [[stored]])

    assert site_config.is_setup_complete(_BENCH_ROOT, "postgres.localhost") is True


@pytest.mark.parametrize("stored", ["0", "false", "", "t", "yes"])
def test_is_setup_complete_rejects_other_values(monkeypatch: pytest.MonkeyPatch, stored: str) -> None:
    _stub_database(monkeypatch, _postgres(), [[stored]])

    assert site_config.is_setup_complete(_BENCH_ROOT, "postgres.localhost") is False


def test_is_setup_complete_false_when_setting_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_database(monkeypatch, _postgres(), [])

    assert site_config.is_setup_complete(_BENCH_ROOT, "postgres.localhost") is False


def test_is_setup_complete_none_when_database_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def unreachable(*args, **kwargs):
        raise DatabaseError("connection refused")

    monkeypatch.setattr(site_config, "make_site_database", unreachable)

    assert site_config.is_setup_complete(_BENCH_ROOT, "site.localhost") is None


def test_is_setup_complete_none_when_site_config_missing(tmp_path: Path) -> None:
    assert site_config.is_setup_complete(tmp_path, "missing.localhost") is None


def test_query_installed_apps_via_db_on_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    executed = _stub_database(monkeypatch, _postgres(), [["frappe"], ["erpnext"]])

    apps = site_config.query_installed_apps_via_db(_BENCH_ROOT, "postgres.localhost")

    assert apps == ["frappe", "erpnext"]
    assert '"tabInstalled Application"' in executed[0]


def test_is_setup_complete_true_on_sqlite(tmp_path: Path) -> None:
    """SQLite sites have no db_password, which used to short-circuit the probe."""
    _make_sqlite_site(tmp_path, "sqlite.localhost", "1", ["frappe"])

    assert site_config.is_setup_complete(tmp_path, "sqlite.localhost") is True


def test_is_setup_complete_false_on_sqlite(tmp_path: Path) -> None:
    _make_sqlite_site(tmp_path, "sqlite.localhost", "0", ["frappe"])

    assert site_config.is_setup_complete(tmp_path, "sqlite.localhost") is False


def test_query_installed_apps_via_db_on_sqlite(tmp_path: Path) -> None:
    _make_sqlite_site(tmp_path, "sqlite.localhost", "1", ["frappe", "erpnext"])

    apps = site_config.query_installed_apps_via_db(tmp_path, "sqlite.localhost")

    assert apps == ["frappe", "erpnext"]


def test_query_installed_apps_via_db_none_when_database_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unreachable(*args, **kwargs):
        raise DatabaseError("connection refused")

    monkeypatch.setattr(site_config, "make_site_database", unreachable)

    assert site_config.query_installed_apps_via_db(_BENCH_ROOT, "site.localhost") is None
