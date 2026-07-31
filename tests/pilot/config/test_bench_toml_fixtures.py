from __future__ import annotations

from pathlib import Path

import pytest

from pilot.config import BenchConfig

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "bench_toml"


@pytest.mark.parametrize(
    ("filename", "name", "db_type", "process_manager"),
    [
        ("development_postgres.toml", "postgres-dev", "postgres", ""),
        ("production_systemd.toml", "systemd-prod", "mariadb", "systemd"),
        ("legacy_supervisor.toml", "legacy-supervisor", "mariadb", "supervisor"),
    ],
)
def test_representative_bench_toml_loads_and_round_trips(
    tmp_path: Path,
    filename: str,
    name: str,
    db_type: str,
    process_manager: str,
) -> None:
    config = BenchConfig.from_file(FIXTURES / filename)
    # Nest under tmp_path/benches/ so common_config.toml (one level above the
    # bench dir) never escapes this test's own tmp_path into the shared
    # pytest basetemp - see BenchConfig._benches_root().
    round_trip_path = tmp_path / "benches" / name / "bench.toml"
    round_trip_path.parent.mkdir(parents=True)
    config.write(round_trip_path)

    assert config.name == name
    assert config.db_type == db_type
    assert config.production.process_manager == process_manager
    assert BenchConfig.from_file(round_trip_path) == config


def test_from_file_on_a_standalone_fixture_reads_its_own_common_fields() -> None:
    """development_postgres.toml carries real postgres/jwks values and has no
    common_config.toml two levels up, so from_file() keeps what it declares."""
    config = BenchConfig.from_file(FIXTURES / "development_postgres.toml")
    assert config.postgres.host == "db.internal"
    assert config.postgres.root_password == "fixture-postgres-password"
    assert config.admin.jwks_url == "https://identity.example.test/.well-known/jwks.json"


def test_from_file_at_the_real_benches_root_depth_merges_common_config(tmp_path: Path) -> None:
    """The same fixture's postgres/jwks fields DO merge correctly once the
    bench.toml sits at the real <benches_root>/<bench>/bench.toml depth with
    a real common_config.toml (holding those same values) beside it."""
    from pilot.config.common import CommonConfig
    from pilot.config.postgres import PostgresConfig

    benches_root = tmp_path / "benches"
    bench_dir = benches_root / "postgres-dev"
    bench_dir.mkdir(parents=True)
    bench_toml = bench_dir / "bench.toml"
    bench_toml.write_text((FIXTURES / "development_postgres.toml").read_text())

    common = CommonConfig(
        postgres=PostgresConfig(
            host="db.internal", port=5433, root_password="fixture-postgres-password", existing=True
        ),
        jwks_url="https://identity.example.test/.well-known/jwks.json",
        jwks_audience="postgres-dev",
    )
    common.write(benches_root)

    reloaded = BenchConfig.from_file(bench_toml)
    assert reloaded.postgres.host == "db.internal"
    assert reloaded.postgres.root_password == "fixture-postgres-password"
    assert reloaded.admin.jwks_url == "https://identity.example.test/.well-known/jwks.json"
