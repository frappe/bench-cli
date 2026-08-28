"""Tests for MariaDBPerformanceReport's scoping and Performance Schema gating."""

from __future__ import annotations

from unittest.mock import MagicMock

from pilot.core.database.engines.mariadb_performance import (
    FRAMEWORK_INDEXES,
    FULL_TABLE_SCAN_QUERIES,
    REDUNDANT_INDEXES,
    SYSTEM_SCHEMAS,
    TIME_CONSUMING_QUERIES,
    UNUSED_INDEXES,
    MariaDBPerformanceReport,
)


class FakeCursor:
    """Records executed statements and replays queued result sets in order."""

    def __init__(self, results: list[list[dict]]) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, dict]] = []
        self._current: list[dict] = []

    def execute(self, query, parameters=None):
        self.calls.append((query, parameters or {}))
        self._current = self.results.pop(0) if self.results else []

    def fetchone(self):
        return self._current[0] if self._current else None

    def fetchall(self):
        return self._current

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _connect(cursor: FakeCursor):
    connection = MagicMock()
    connection.cursor.return_value = cursor
    return lambda: connection


def _performance_schema_off() -> FakeCursor:
    return FakeCursor([[{"enabled": 0}], []])


def test_disabled_performance_schema_still_reports_redundant_indexes() -> None:
    cursor = FakeCursor(
        [
            [{"enabled": 0}],
            [
                {
                    "db": "site_db",
                    "table_name": "tabUser",
                    "redundant_index_name": "lft",
                    "redundant_index_columns": "lft",
                    "dominant_index_name": "lft_rgt",
                    "dominant_index_columns": "lft,rgt",
                }
            ],
        ]
    )
    report = MariaDBPerformanceReport(_connect(cursor), "site_db").build()

    assert report.performance_schema_enabled is False
    assert report.time_consuming_queries == []
    assert report.full_table_scan_queries == []
    assert report.unused_indexes == []
    assert len(report.redundant_indexes) == 1
    assert report.redundant_indexes[0].dominant_index == "lft_rgt"


def test_disabled_performance_schema_does_not_query_it() -> None:
    cursor = _performance_schema_off()
    MariaDBPerformanceReport(_connect(cursor), "site_db").build()

    queried = " ".join(query for query, _ in cursor.calls)
    assert "events_statements_summary_by_digest" not in queried
    assert "table_io_waits_summary_by_index_usage" not in queried


def test_site_scope_binds_the_database_name_instead_of_interpolating_it() -> None:
    cursor = _performance_schema_off()
    MariaDBPerformanceReport(_connect(cursor), "site_db").build()

    query, parameters = cursor.calls[-1]
    assert "site_db" not in query
    assert parameters["database"] == "site_db"


def test_server_scope_excludes_system_schemas() -> None:
    cursor = _performance_schema_off()
    MariaDBPerformanceReport(_connect(cursor), "").build()

    query, parameters = cursor.calls[-1]
    assert "%(system_schemas)s" in query
    assert parameters["system_schemas"] == SYSTEM_SCHEMAS
    assert parameters["database"] == ""


def test_statements_execute_verbatim_without_building_sql() -> None:
    cursor = FakeCursor([[{"enabled": 1}], [], [], [], []])
    MariaDBPerformanceReport(_connect(cursor), "site_db").build()

    statements = {
        TIME_CONSUMING_QUERIES,
        FULL_TABLE_SCAN_QUERIES,
        UNUSED_INDEXES,
        REDUNDANT_INDEXES,
    }
    assert {query for query, _ in cursor.calls} >= statements


def test_unused_indexes_exclude_framework_indexes() -> None:
    cursor = FakeCursor([[{"enabled": 1}], [], [], [], []])
    MariaDBPerformanceReport(_connect(cursor), "site_db").build()

    unused = next(query for query, _ in cursor.calls if "table_io_waits" in query)
    parameters = next(params for query, params in cursor.calls if "table_io_waits" in query)
    assert "framework_indexes" in unused
    assert parameters["framework_indexes"] == FRAMEWORK_INDEXES


def test_enabled_performance_schema_maps_every_section() -> None:
    cursor = FakeCursor(
        [
            [{"enabled": 1}],
            [
                {
                    "db": "site_db",
                    "query": "SELECT ?",
                    "percent": 42.5,
                    "calls": 3,
                    "average_time_ms": 1.5,
                    "total_time_ms": 4.5,
                }
            ],
            [
                {
                    "db": "site_db",
                    "query": "SELECT ? FROM tabUser",
                    "calls": 2,
                    "rows_sent": 1,
                    "rows_examined": 5000,
                }
            ],
            [{"db": "site_db", "table_name": "tabUser", "index_name": "modified"}],
            [],
        ]
    )
    report = MariaDBPerformanceReport(_connect(cursor), "site_db").build()

    assert report.performance_schema_enabled is True
    assert report.time_consuming_queries[0].percent == 42.5
    assert report.time_consuming_queries[0].calls == 3
    assert report.full_table_scan_queries[0].rows_examined == 5000
    assert report.unused_indexes[0].index == "modified"


def test_null_counters_become_zero_rather_than_failing() -> None:
    cursor = FakeCursor(
        [
            [{"enabled": 1}],
            [
                {
                    "db": None,
                    "query": None,
                    "percent": None,
                    "calls": None,
                    "average_time_ms": None,
                    "total_time_ms": None,
                }
            ],
            [],
            [],
            [],
        ]
    )
    report = MariaDBPerformanceReport(_connect(cursor), "").build()

    assert report.time_consuming_queries[0].percent == 0.0
    assert report.time_consuming_queries[0].calls == 0
