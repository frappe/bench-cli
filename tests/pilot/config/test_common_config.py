from __future__ import annotations

from pathlib import Path

from pilot.config import BenchConfig
from pilot.config.common import CommonConfig
from pilot.config.letsencrypt import LetsEncryptConfig
from pilot.config.mariadb import MariaDBConfig
from pilot.config.postgres import PostgresConfig

_BENCH_TOML = """
[bench]
name = "test-bench"
python = "3.14"

[[apps]]
name = "frappe"
repo = "https://github.com/frappe/frappe"
branch = "version-16"

[redis]
cache_port = 13000
queue_port = 11000
"""


def _write_bench(benches_root: Path, shared_tables: str = "") -> Path:
    bench_dir = benches_root / "test-bench"
    bench_dir.mkdir(parents=True, exist_ok=True)
    (bench_dir / "bench.toml").write_text(_BENCH_TOML + shared_tables)
    return bench_dir


def test_path_resolves_next_to_benches_root(tmp_path: Path) -> None:
    assert CommonConfig.path(tmp_path) == tmp_path / "common_config.toml"


def test_read_missing_file_returns_defaults(tmp_path: Path) -> None:
    assert CommonConfig.read(tmp_path) == CommonConfig()


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    config = CommonConfig(
        mariadb=MariaDBConfig(host="db.internal", port=3307, root_password="s3cret", admin_user="root"),
        postgres=PostgresConfig(host="pg.internal", port=5433, root_password="pgsecret"),
        letsencrypt=LetsEncryptConfig(email="ops@example.com"),
        jwks_url="https://issuer.example.com/jwks.json",
        jwks_audience="bench-fleet",
    )
    config.write(tmp_path)
    assert CommonConfig.read(tmp_path) == config


def test_read_ignores_stale_mariadb_instance_keys(tmp_path: Path) -> None:
    """Legacy MariaDB instance keys (from an older Pilot schema) are
    ignored, not rejected, when read back."""
    (tmp_path / "common_config.toml").write_text(
        '[mariadb]\nroot_password = "root"\ninstance = "old-bench"\n'
        'version = "10.6"\ndata_dir = "/var/lib/mysql-old-bench"\n'
    )
    config = CommonConfig.read(tmp_path)
    assert not hasattr(config.mariadb, "instance")
    assert config.mariadb.root_password == "root"


def test_read_ignores_stale_postgres_instance_keys(tmp_path: Path) -> None:
    (tmp_path / "common_config.toml").write_text(
        '[postgres]\nroot_password = "secret"\ninstance = "old-bench"\nversion = "15"\n'
    )
    config = CommonConfig.read(tmp_path)
    assert not hasattr(config.postgres, "instance")
    assert config.postgres.root_password == "secret"


def test_jwks_omitted_from_output_when_unset(tmp_path: Path) -> None:
    CommonConfig().write(tmp_path)
    assert "[admin]" not in CommonConfig.path(tmp_path).read_text()


def test_bench_toml_tables_used_while_common_config_is_missing(tmp_path: Path) -> None:
    """A bench that predates common_config.toml keeps the servers its own
    bench.toml points at, instead of silently falling back to the defaults."""
    bench_dir = _write_bench(
        tmp_path,
        '\n[mariadb]\nport = 3306\nroot_password = "mariadbpw"\n'
        '\n[postgres]\nport = 5432\nroot_password = "postgrespw"\n',
    )

    config = BenchConfig.read(bench_dir)

    assert (config.mariadb.port, config.mariadb.root_password) == (3306, "mariadbpw")
    assert (config.postgres.port, config.postgres.root_password) == (5432, "postgrespw")


def test_common_config_wins_over_bench_toml_tables(tmp_path: Path) -> None:
    bench_dir = _write_bench(tmp_path, '\n[postgres]\nport = 5432\nroot_password = "stale"\n')
    CommonConfig(postgres=PostgresConfig(port=5433, root_password="shared")).write(tmp_path)

    config = BenchConfig.read(bench_dir)

    assert (config.postgres.port, config.postgres.root_password) == (5433, "shared")


def test_defaults_apply_when_no_file_carries_shared_tables(tmp_path: Path) -> None:
    config = BenchConfig.read(_write_bench(tmp_path))

    assert config.postgres.port == PostgresConfig().port
    assert config.mariadb.port == MariaDBConfig().port
