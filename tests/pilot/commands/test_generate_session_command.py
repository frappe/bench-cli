from __future__ import annotations

import urllib.parse
from pathlib import Path

import pytest

from admin.backend.internal.session import Session
from pilot.commands.admin.generate_session import GenerateSessionCommand
from pilot.config import BenchConfig
from pilot.core.bench import Bench
from pilot.exceptions import BenchError
from pilot.utils import admin_url


def _bench(tmp_path: Path, password: str = "secret", **admin_settings) -> Bench:
    toml_path = tmp_path / "bench.toml"
    toml_path.write_text(BenchConfig.from_flat(tmp_path.name, {"admin_password": password}).dumps())
    config = BenchConfig.from_file(toml_path)
    for key, value in admin_settings.items():
        setattr(config.admin, key, value)
    config.write(toml_path)
    return Bench(BenchConfig.from_file(toml_path), tmp_path)


def test_prints_a_bare_token_by_default(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    bench = _bench(tmp_path)

    GenerateSessionCommand(bench=bench).run()

    token = capsys.readouterr().out.strip()
    assert Session(bench).verify_token(token)["scope"] == "bench"


def test_bare_token_is_single_use_and_short_lived(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    bench = _bench(tmp_path)

    GenerateSessionCommand(bench=bench).run()

    claims = Session(bench).verify_token(capsys.readouterr().out.strip())
    assert claims["jti"]  # the ?sid= redemption path burns this jti
    assert claims["exp"] - claims["iat"] == Session.LOGIN_TTL


def test_full_path_prints_the_sign_in_url(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    bench = _bench(tmp_path)

    GenerateSessionCommand(bench=bench, full_path=True).run()

    url = capsys.readouterr().out.strip()
    prefix, _, token = url.partition("/?sid=")
    assert prefix == admin_url(bench.config)
    assert Session(bench).verify_token(urllib.parse.unquote(token))["scope"] == "bench"


def test_full_path_uses_the_admin_domain_in_production(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    bench = _bench(tmp_path, domain="admin.example.com", tls=True)
    bench.config.production.enabled = True

    GenerateSessionCommand(bench=bench, full_path=True).run()

    assert capsys.readouterr().out.startswith("https://admin.example.com/?sid=")


def test_requires_an_admin_password(tmp_path: Path) -> None:
    with pytest.raises(BenchError, match="no password set"):
        GenerateSessionCommand(bench=_bench(tmp_path, password="")).run()
