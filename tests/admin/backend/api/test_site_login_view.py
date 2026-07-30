from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tests.admin.backend.test_admin_app import _client


def _write_site(bench_root: Path, name: str = "s.localhost", **config) -> None:
    site_path = bench_root / "sites" / name
    site_path.mkdir(parents=True)
    (site_path / "site_config.json").write_text(json.dumps(config))


def _bearer(bench_root: Path, scope: str = "site", site: str = "s.localhost") -> dict:
    from admin.backend.internal.session import Session
    from pilot.core.bench import Bench

    token = Session(Bench(bench_root)).issue_session_token(scope=scope, site=site)[0]
    return {"Authorization": f"Bearer {token}"}


def test_create_login_link_returns_url_with_sid(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    _write_site(bench_root)

    with patch(
        "pilot.core.site.login.SiteLogin.create_session",
        return_value="frappe-session-id",
    ) as create_session:
        response = client.post("/api/v1/sites/s.localhost/login")

    assert response.status_code == 201
    body = response.get_json()
    assert response.headers["Location"] == body["url"]
    assert response.headers["Cache-Control"] == "no-store"
    assert body["url"] == "http://s.localhost:8000/desk?sid=frappe-session-id"
    create_session.assert_called_once_with()


def test_create_login_link_fails_when_session_creation_fails(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    _write_site(bench_root)

    with patch(
        "pilot.core.site.login.SiteLogin.create_session",
        return_value=None,
    ):
        response = client.post("/api/v1/sites/s.localhost/login")

    assert response.status_code == 503


def test_login_link_rejects_missing_and_symlinked_sites(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    outside = tmp_path / "outside"
    _write_site(outside, "linked.localhost")
    sites = bench_root / "sites"
    sites.mkdir()
    (sites / "linked.localhost").symlink_to(
        outside / "sites" / "linked.localhost",
        target_is_directory=True,
    )

    missing = client.post("/api/v1/sites/missing.localhost/login")
    linked = client.post("/api/v1/sites/linked.localhost/login")

    assert missing.status_code == linked.status_code == 404


def test_login_link_accepts_site_scoped_bearer(tmp_path: Path) -> None:
    # The Central relay POSTs a scope=site assertion as a Bearer; the bench mints the session.
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    _write_site(bench_root)

    with patch("pilot.core.site.login.SiteLogin.create_session", return_value="frappe-session-id"):
        response = client.post("/api/v1/sites/s.localhost/login", headers=_bearer(bench_root))

    assert response.status_code == 201
    assert response.get_json()["url"] == "http://s.localhost:8000/desk?sid=frappe-session-id"


def test_login_link_fails_closed_on_wrong_site_and_unknown_scope(tmp_path: Path) -> None:
    # A token for another site, or a future scope this bench doesn't understand, must be
    # rejected — never silently downgraded to an Administrator session.
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    _write_site(bench_root)

    with patch("pilot.core.site.login.SiteLogin.create_session") as create_session:
        wrong_site = client.post(
            "/api/v1/sites/s.localhost/login", headers=_bearer(bench_root, site="other.localhost")
        )
        unknown_scope = client.post(
            "/api/v1/sites/s.localhost/login", headers=_bearer(bench_root, scope="site_user")
        )

    assert wrong_site.status_code == unknown_scope.status_code == 403
    create_session.assert_not_called()
