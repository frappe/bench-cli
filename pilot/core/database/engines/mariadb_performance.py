from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pilot.core.database.base import (
    FullTableScanQuery,
    PerformanceReport,
    RedundantIndex,
    TimeConsumingQuery,
    UnusedIndex,
)

SYSTEM_SCHEMAS = ("information_schema", "performance_schema", "mysql", "sys")

FRAMEWORK_INDEXES = ("parent", "creation")

TIME_CONSUMING_QUERIES = """
    SELECT SCHEMA_NAME AS db,
           DIGEST_TEXT AS query,
           SUM_TIMER_WAIT / SUM(SUM_TIMER_WAIT) OVER () * 100 AS percent,
           COUNT_STAR AS calls,
           ROUND(AVG_TIMER_WAIT / 1000000000, 1) AS average_time_ms,
           ROUND(SUM_TIMER_WAIT / 1000000000, 1) AS total_time_ms
    FROM performance_schema.events_statements_summary_by_digest
    WHERE (SCHEMA_NAME = %(database)s
           OR (%(database)s = '' AND SCHEMA_NAME NOT IN %(system_schemas)s))
    ORDER BY SUM_TIMER_WAIT DESC
    LIMIT 10
"""

FULL_TABLE_SCAN_QUERIES = """
    SELECT SCHEMA_NAME AS db,
           DIGEST_TEXT AS query,
           COUNT_STAR AS calls,
           SUM_ROWS_SENT AS rows_sent,
           SUM_ROWS_EXAMINED AS rows_examined
    FROM performance_schema.events_statements_summary_by_digest
    WHERE (SCHEMA_NAME = %(database)s
           OR (%(database)s = '' AND SCHEMA_NAME NOT IN %(system_schemas)s))
      AND (SUM_NO_INDEX_USED > 0 OR SUM_NO_GOOD_INDEX_USED > 0)
      AND DIGEST_TEXT NOT LIKE 'SHOW%%'
    ORDER BY ROUND(IFNULL(SUM_NO_INDEX_USED / NULLIF(COUNT_STAR, 0), 0) * 100, 0) DESC,
             SUM_TIMER_WAIT DESC
    LIMIT 10
"""

UNUSED_INDEXES = """
    SELECT OBJECT_SCHEMA AS db,
           OBJECT_NAME AS table_name,
           INDEX_NAME AS index_name
    FROM performance_schema.table_io_waits_summary_by_index_usage
    WHERE (OBJECT_SCHEMA = %(database)s
           OR (%(database)s = '' AND OBJECT_SCHEMA NOT IN %(system_schemas)s))
      AND INDEX_NAME IS NOT NULL
      AND INDEX_NAME <> 'PRIMARY'
      AND INDEX_NAME NOT IN %(framework_indexes)s
      AND COUNT_STAR = 0
    ORDER BY OBJECT_NAME, INDEX_NAME
"""

REDUNDANT_INDEXES = """
    WITH indexed_columns AS (
        SELECT TABLE_SCHEMA AS table_schema,
               TABLE_NAME AS table_name,
               INDEX_NAME AS index_name,
               MAX(NON_UNIQUE) AS non_unique,
               GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ',') AS index_columns
        FROM information_schema.STATISTICS
        WHERE INDEX_TYPE = 'BTREE'
          AND (TABLE_SCHEMA = %(database)s
               OR (%(database)s = '' AND TABLE_SCHEMA NOT IN %(system_schemas)s))
        GROUP BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME
    )
    SELECT redundant.table_schema AS db,
           redundant.table_name AS table_name,
           redundant.index_name AS redundant_index_name,
           redundant.index_columns AS redundant_index_columns,
           dominant.index_name AS dominant_index_name,
           dominant.index_columns AS dominant_index_columns
    FROM indexed_columns redundant
    JOIN indexed_columns dominant
      ON redundant.table_schema = dominant.table_schema
     AND redundant.table_name = dominant.table_name
     AND redundant.index_name <> dominant.index_name
    WHERE (
            redundant.index_columns = dominant.index_columns
            AND (
                redundant.non_unique > dominant.non_unique
                OR (
                    redundant.non_unique = dominant.non_unique
                    AND IF(redundant.index_name = 'PRIMARY', '', redundant.index_name)
                      > IF(dominant.index_name = 'PRIMARY', '', dominant.index_name)
                )
            )
        )
        OR (
            LOCATE(CONCAT(redundant.index_columns, ','), dominant.index_columns) = 1
            AND redundant.non_unique = 1
        )
        OR (
            LOCATE(CONCAT(dominant.index_columns, ','), redundant.index_columns) = 1
            AND dominant.non_unique = 0
        )
    ORDER BY redundant.table_name, redundant.index_name
"""


class MariaDBPerformanceReport:
    """Query and index findings read from Performance Schema and
    information_schema. `database` narrows every section to one database;
    empty covers every user schema on the server."""

    def __init__(self, connect: Callable[[], Any], database: str = "") -> None:
        self._connect = connect
        self._database = database

    def build(self) -> PerformanceReport:
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                enabled = self.is_performance_schema_enabled(cursor)
                return PerformanceReport(
                    performance_schema_enabled=enabled,
                    time_consuming_queries=self.get_time_consuming_queries(cursor) if enabled else [],
                    full_table_scan_queries=self.get_full_table_scan_queries(cursor) if enabled else [],
                    unused_indexes=self.get_unused_indexes(cursor) if enabled else [],
                    redundant_indexes=self.get_redundant_indexes(cursor),
                )
        finally:
            connection.close()

    def is_performance_schema_enabled(self, cursor) -> bool:
        cursor.execute("SELECT @@GLOBAL.performance_schema AS enabled")
        row = cursor.fetchone()
        return bool(row and row["enabled"])

    def get_time_consuming_queries(self, cursor) -> list[TimeConsumingQuery]:
        rows = self._fetch(cursor, TIME_CONSUMING_QUERIES)
        return [
            TimeConsumingQuery(
                database=row["db"],
                query=row["query"],
                percent=float(row["percent"] or 0),
                calls=int(row["calls"] or 0),
                average_time_ms=float(row["average_time_ms"] or 0),
                total_time_ms=float(row["total_time_ms"] or 0),
            )
            for row in rows
        ]

    def get_full_table_scan_queries(self, cursor) -> list[FullTableScanQuery]:
        rows = self._fetch(cursor, FULL_TABLE_SCAN_QUERIES)
        return [
            FullTableScanQuery(
                database=row["db"],
                query=row["query"],
                calls=int(row["calls"] or 0),
                rows_sent=int(row["rows_sent"] or 0),
                rows_examined=int(row["rows_examined"] or 0),
            )
            for row in rows
        ]

    def get_unused_indexes(self, cursor) -> list[UnusedIndex]:
        rows = self._fetch(cursor, UNUSED_INDEXES, framework_indexes=FRAMEWORK_INDEXES)
        return [
            UnusedIndex(database=row["db"], table=row["table_name"], index=row["index_name"]) for row in rows
        ]

    def get_redundant_indexes(self, cursor) -> list[RedundantIndex]:
        rows = self._fetch(cursor, REDUNDANT_INDEXES)
        return [
            RedundantIndex(
                database=row["db"],
                table=row["table_name"],
                redundant_index=row["redundant_index_name"],
                redundant_index_columns=row["redundant_index_columns"],
                dominant_index=row["dominant_index_name"],
                dominant_index_columns=row["dominant_index_columns"],
            )
            for row in rows
        ]

    def _fetch(self, cursor, query: str, **parameters) -> list[dict]:
        cursor.execute(
            query,
            {"database": self._database, "system_schemas": SYSTEM_SCHEMAS, **parameters},
        )
        return list(cursor.fetchall())
