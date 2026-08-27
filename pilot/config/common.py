from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

from pilot.config.alert_limit import ResourceLimitConfig
from pilot.config.central import CentralConfig
from pilot.config.datum import DatumConfig
from pilot.config.letsencrypt import LetsEncryptConfig
from pilot.config.logs import LogsConfig
from pilot.config.mariadb import MariaDBConfig
from pilot.config.postgres import PostgresConfig
from pilot.internal.atomic_file import atomic_write_private_text
from pilot.internal.toml import ConfigDict, Toml

FILENAME = "common_config.toml"


@dataclass
class CommonConfig:
    """Settings shared by every bench under one benches directory: one MariaDB
    server, one Postgres server, one ACME account, one trusted admin JWKS
    issuer, one Central enrolment, one metrics destination, one logs
    destination. Stored once at ``common_config.toml`` next to the bench
    folders. BenchConfig is the only reader/writer; other code reaches these
    values through a bench's own config instead."""

    mariadb: MariaDBConfig = field(default_factory=MariaDBConfig)
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    letsencrypt: LetsEncryptConfig = field(default_factory=LetsEncryptConfig)
    central: CentralConfig = field(default_factory=CentralConfig)
    datum: DatumConfig = field(default_factory=DatumConfig)
    logs: LogsConfig = field(default_factory=LogsConfig)
    resource_limits: ResourceLimitConfig = field(default_factory=ResourceLimitConfig)
    jwks_url: str = ""
    jwks_audience: str = ""

    @classmethod
    def path(cls, benches_root: Path) -> Path:
        return Path(benches_root) / FILENAME

    @classmethod
    def read(cls, benches_root: Path) -> "CommonConfig":
        path = cls.path(benches_root)
        if not path.exists():
            return cls()
        return cls.from_raw_dict(Toml.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def from_raw_dict(cls, data: dict) -> "CommonConfig":
        """Build from a parsed TOML dict shaped like common_config.toml (or a
        bench.toml that still carries these tables pre-migration)."""
        admin = data.get("admin", {})
        return cls(
            mariadb=MariaDBConfig(**_known_fields(MariaDBConfig, data.get("mariadb", {}))),
            postgres=PostgresConfig(**_known_fields(PostgresConfig, data.get("postgres", {}))),
            letsencrypt=LetsEncryptConfig.from_dict(data.get("letsencrypt", {})),
            central=CentralConfig.from_dict(data.get("central", {})),
            datum=DatumConfig.from_dict(data.get("datum", {})),
            logs=LogsConfig.from_dict(data.get("logs", {})),
            resource_limits=ResourceLimitConfig(
                **_known_fields(ResourceLimitConfig, data.get("resource_limits", {}))
            ),
            jwks_url=admin.get("jwks_url", ""),
            jwks_audience=admin.get("jwks_audience", ""),
        )

    def write(self, benches_root: Path) -> None:
        atomic_write_private_text(self.path(benches_root), Toml.dumps(self._to_toml_dict()))

    def _to_toml_dict(self) -> ConfigDict:
        data: ConfigDict = {
            "mariadb": {
                "host": self.mariadb.host,
                "port": self.mariadb.port,
                "root_password": self.mariadb.root_password,
                "admin_user": self.mariadb.admin_user,
                "socket_path": self.mariadb.socket_path,
                "existing": self.mariadb.existing,
            },
            "postgres": {
                "host": self.postgres.host,
                "port": self.postgres.port,
                "root_password": self.postgres.root_password,
                "admin_user": self.postgres.admin_user,
                "existing": self.postgres.existing,
            },
            "letsencrypt": {
                "email": self.letsencrypt.email,
                "webroot_path": str(self.letsencrypt.webroot_path),
            },
        }
        if self.central != CentralConfig():
            data["central"] = self._central_section()
        if self.datum != DatumConfig():
            data["datum"] = {"endpoint": self.datum.endpoint, "token": self.datum.token}
        if self.logs != LogsConfig():
            data["logs"] = {
                "endpoint": self.logs.endpoint,
                "token": self.logs.token,
                "enabled": self.logs.enabled,
            }
        if self.resource_limits != ResourceLimitConfig():
            data["resource_limits"] = self._resource_limits_section()
        if self.jwks_url:
            data["admin"] = {"jwks_url": self.jwks_url, "jwks_audience": self.jwks_audience}
        return data

    def _resource_limits_section(self) -> ConfigDict:
        return {
            "cpu_usage_limit": self.resource_limits.cpu_usage_limit,
            "memory_usage_limit": self.resource_limits.memory_usage_limit,
            "disk_space_limit": self.resource_limits.disk_space_limit,
            "site_uptime": self.resource_limits.site_uptime,
            "webhook_endpoints": self.resource_limits.webhook_endpoints,
        }

    def _central_section(self) -> ConfigDict:
        data: ConfigDict = {"endpoint": self.central.endpoint, "auth_token": self.central.auth_token}
        if self.central.bootstrap_token:
            data["bootstrap_token"] = self.central.bootstrap_token
        return data


def _known_fields(dataclass_type: type, data: dict) -> dict:
    known = {f.name for f in fields(dataclass_type)}
    return {key: value for key, value in data.items() if key in known}
