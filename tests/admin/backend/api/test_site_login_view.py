from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tests.admin.backend.test_admin_app import _client


def _write_site(bench_root: Path, name: str = "s.localhost", **config) -> None:
    site_path = bench_root / "sites" / name
    site_path.mkdir(parents=True)
    (site_path / "site_config.json").write_text(json.dumps(config))


def _site_assertion(bench_root: Path, site: str = "s.localhost") -> str:
    from admin.backend.internal.session import Session
    from pilot.core.bench import Bench

    return Session(Bench(bench_root)).issue_session_token(scope="site", site=site)[0]


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
    create_session.assert_called_once_with("Administrator")


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


def test_open_site_login_redirects_with_fresh_sid(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    _write_site(bench_root)
    token = _site_assertion(bench_root)

    with patch("pilot.core.site.login.SiteLogin.create_session", return_value="frappe-session-id"):
        response = client.get(f"/api/v1/sites/s.localhost/login?sid={token}")

    assert response.status_code == 302
    assert response.headers["Location"] == "http://s.localhost:8000/desk?sid=frappe-session-id"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_open_site_login_is_single_use(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    _write_site(bench_root)
    token = _site_assertion(bench_root)

    with patch("pilot.core.site.login.SiteLogin.create_session", return_value="sid1"):
        first = client.get(f"/api/v1/sites/s.localhost/login?sid={token}")
        replay = client.get(f"/api/v1/sites/s.localhost/login?sid={token}")

    assert first.status_code == 302
    assert replay.status_code == 401


def test_open_site_login_rejects_wrong_site_and_missing_token(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    _write_site(bench_root)
    _write_site(bench_root, "other.localhost")
    other_scope = _site_assertion(bench_root, "other.localhost")

    with patch("pilot.core.site.login.SiteLogin.create_session", return_value="sid1") as create_session:
        wrong_site = client.get(f"/api/v1/sites/s.localhost/login?sid={other_scope}")
        no_token = client.get("/api/v1/sites/s.localhost/login")

    assert wrong_site.status_code == no_token.status_code == 401
    create_session.assert_not_called()


def test_open_site_login_fails_closed_on_unknown_scope(tmp_path: Path) -> None:
    # A future constrained scope this bench doesn't understand must be rejected, never
    # silently downgraded to an Administrator session.
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)
    _write_site(bench_root)
    from admin.backend.internal.session import Session
    from pilot.core.bench import Bench

    token = Session(Bench(bench_root)).issue_session_token(scope="site_user", site="s.localhost")[0]
    with patch("pilot.core.site.login.SiteLogin.create_session") as create_session:
        response = client.get(f"/api/v1/sites/s.localhost/login?sid={token}")

    assert response.status_code == 401
    create_session.assert_not_called()
