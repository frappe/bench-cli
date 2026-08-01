import re
from dataclasses import dataclass, field

from pilot import is_dev_build
from pilot.exceptions import ConfigError

_HOSTNAME_PATTERN = re.compile(
    r"^(?=.{1,253}$)[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)


@dataclass
class AdminConfig:
    port: int = 7000  # New series not conflicting with sites
    timeout: int = 180  # seconds
    enabled: bool = False
    password: str = ""
    jwt_secret: str = ""
    jwks_url: str = ""  # trust session tokens minted by a remote issuer publishing keys here
    # Required with jwks_url; binds remote tokens to this bench.
    jwks_audience: str = ""
    domain: str = ""
    tls: bool = False
    # Off by default outside a --dev install: bench management exposes powerful,
    # cross-bench operations and should be an explicit opt-in in production.
    allow_bench_management: bool = field(default_factory=lambda: is_dev_build)
    # Break-glass codes for when no enrolled device is available. Stored in the clear so
    # an operator with server access can still read them; the API returns them only when
    # they are issued, never on demand.
    recovery_codes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "AdminConfig":
        return cls(
            port=data.get("port", 7000),
            timeout=data.get("timeout", 180),
            enabled=data.get("enabled", False),
            password=data.get("password", ""),
            jwt_secret=data.get("jwt_secret", ""),
            jwks_url=data.get("jwks_url", ""),
            jwks_audience=data.get("jwks_audience", ""),
            domain=data.get("domain", ""),
            tls=data.get("tls", False),
            allow_bench_management=data.get("allow_bench_management", is_dev_build),
            recovery_codes=list(data.get("recovery_codes", [])),
        )

    @property
    def internal_port(self) -> int:
        """Localhost-only Gunicorn port behind nginx."""
        return self.port + 1

    def validate(self, production_enabled: bool, bench_name: str) -> None:
        if not self.domain:
            if production_enabled:
                raise ConfigError(
                    f"admin.domain is required in production but is missing for bench '{bench_name}'. "
                    f"Set it in bench.toml (e.g. admin.example.com) or pass "
                    f"'pilot setup production --admin-domain <domain>'."
                )
            return
        if not _HOSTNAME_PATTERN.match(self.domain):
            raise ConfigError(f"admin.domain '{self.domain}' is not a valid hostname (bench '{bench_name}').")
