"""Tests for /api/v1/sites/<name>/backups and /backup-schedule routes."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from pilot.config import BenchConfig


def _client(bench_root: Path, password: str = "secret"):
    from admin.backend.app import create_app
    from admin.backend.internal.session import Session
    from pilot.core.bench import Bench

    bench_root.mkdir(parents=True, exist_ok=True)
    (bench_root / "bench.toml").write_text(
        BenchConfig.from_flat(bench_root.name, {"admin_enabled": True, "admin_password": password}).dumps()
    )
    app = create_app(bench_root)
    app.config["TESTING"] = True
    client = app.test_client()
    client.set_cookie("sid", Session(Bench(bench_root)).issue_session_token()[0])
    return client


def _make_site(bench_root: Path, name: str, **config) -> None:
    site_dir = bench_root / "sites" / name
    site_dir.mkdir(parents=True)
    (site_dir / "site_config.json").write_text(json.dumps(config))


def _make_backup_file(bench_root: Path, site: str, timestamp: str, suffix: str) -> Path:
    backups_dir = bench_root / "sites" / site / "private" / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    path = backups_dir / f"{timestamp}-{site}-{suffix}"
    path.write_text("data")
    return path


def _request(client, method, path, **kwargs):
    with patch(
        "pilot.internal.tasks.runner.task_workers.wake",
        return_value=False,
    ):
        return getattr(client, method)(path, **kwargs)


def test_backup_site_queues_task(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)

    response = _request(client, "post", "/api/v1/sites/site.localhost/backups")

    body = response.get_json()
    assert response.status_code == 202
    assert body["command"] == "backup-site"
    assert body["args"] == {"site": "site.localhost", "with_files": True}


def test_backup_site_rejects_missing_site(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)

    response = _request(client, "post", "/api/v1/sites/missing.localhost/backups")

    assert response.status_code == 404


def test_list_backups_includes_local_files(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    client = _client(bench_root)

    response = client.get("/api/v1/sites/site.localhost/backups")

    body = response.get_json()
    assert response.status_code == 200
    assert body[0]["timestamp"] == "20240101_000000"
    assert body[0]["files"][0]["kind"] == "database"


def test_get_backup_returns_the_matching_set(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    client = _client(bench_root)

    response = client.get("/api/v1/sites/site.localhost/backups/20240101_000000")

    assert response.status_code == 200
    assert response.get_json()["timestamp"] == "20240101_000000"


def test_get_backup_404s_for_an_unknown_timestamp(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)

    response = client.get("/api/v1/sites/site.localhost/backups/20240101_000000")

    assert response.status_code == 404


def test_download_backup_file_serves_the_file(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    client = _client(bench_root)

    response = client.get(
        "/api/v1/sites/site.localhost/backups/20240101_000000/files/"
        "20240101_000000-site.localhost-database.sql.gz/content"
    )

    assert response.status_code == 200
    assert response.data == b"data"


def test_download_backup_file_is_audited(tmp_path: Path) -> None:
    from pilot.core.bench import Bench
    from pilot.core.bench.audit_log import AuditLog

    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    client = _client(bench_root)

    client.get(
        "/api/v1/sites/site.localhost/backups/20240101_000000/files/"
        "20240101_000000-site.localhost-database.sql.gz/content"
    )

    entries = AuditLog(Bench(bench_root)).entries(entry_type="backup")
    assert entries[0]["event"] == "download"
    assert entries[0]["site"] == "site.localhost"
    assert entries[0]["timestamp"] == "20240101_000000"
    assert entries[0]["file"] == "20240101_000000-site.localhost-database.sql.gz"


def test_download_backup_file_rejects_a_timestamp_mismatch(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    client = _client(bench_root)

    response = client.get(
        "/api/v1/sites/site.localhost/backups/20240102_000000/files/"
        "20240101_000000-site.localhost-database.sql.gz/content"
    )

    assert response.status_code == 422


def test_download_backup_file_rejects_a_dotfile(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)

    response = client.get("/api/v1/sites/site.localhost/backups/20240101_000000/files/.hidden/content")

    assert response.status_code == 422


def test_backup_download_links_returns_urls_directly(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)
    offsite = Mock()
    offsite.get_backup.return_value = {"database": "20240101_000000-database.sql.gz"}
    offsite.presigned_url.return_value = "https://bucket.example/signed"

    with patch(
        "pilot.integrations.s3.backups.OffsiteBackup.from_config",
        return_value=offsite,
    ):
        response = client.get("/api/v1/sites/site.localhost/backups/20240101_000000/download-links")

    assert response.status_code == 200
    assert response.get_json() == {"database": "https://bucket.example/signed"}


def test_backup_download_links_is_audited(tmp_path: Path) -> None:
    from pilot.core.bench import Bench
    from pilot.core.bench.audit_log import AuditLog

    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)
    offsite = Mock()
    offsite.get_backup.return_value = {"database": "20240101_000000-database.sql.gz"}
    offsite.presigned_url.return_value = "https://bucket.example/signed"

    with patch(
        "pilot.integrations.s3.backups.OffsiteBackup.from_config",
        return_value=offsite,
    ):
        client.get("/api/v1/sites/site.localhost/backups/20240101_000000/download-links")

    entries = AuditLog(Bench(bench_root)).entries(entry_type="backup")
    assert entries[0]["event"] == "download"
    assert entries[0]["site"] == "site.localhost"
    assert entries[0]["via"] == "s3"


def test_backup_schedule_put_returns_the_saved_resource(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)

    with (
        patch("pilot.managers.cron.CronManager.get_schedule", return_value="0 2 * * *"),
        patch("pilot.managers.cron.CronManager.set_schedule") as set_schedule,
    ):
        response = client.put(
            "/api/v1/sites/site.localhost/backup-schedule",
            json={"schedule": "0 2 * * *", "retention": {"scheme": "fifo", "keep_last": 5}},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["schedule"] == "0 2 * * *"
    assert body["retention"]["keep_last"] == 5
    set_schedule.assert_called_once()


def test_backup_schedule_put_rejects_invalid_cron(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)

    response = client.put(
        "/api/v1/sites/site.localhost/backup-schedule",
        json={"schedule": "not-a-cron"},
    )

    assert response.status_code == 422


def test_backup_schedule_delete_returns_no_content(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)

    with patch("pilot.managers.cron.CronManager.remove_schedule") as remove_schedule:
        response = client.delete("/api/v1/sites/site.localhost/backup-schedule")

    assert response.status_code == 204
    assert response.data == b""
    remove_schedule.assert_called_once_with("site.localhost")


def _upload(client, **extra_parts):
    import io

    data = {"database": (io.BytesIO(b"dump"), "site-database.sql.gz"), **extra_parts}
    response = client.post("/api/v1/sites/backup-uploads", data=data, content_type="multipart/form-data")
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def test_backup_upload_stages_the_archives(tmp_path: Path) -> None:
    import io

    bench_root = tmp_path / "benches" / "current"
    client = _client(bench_root)

    body = _upload(client, public_files=(io.BytesIO(b"tar"), "site-files.tar"))

    assert sorted(body["files"]) == ["database", "public_files"]
    staged = bench_root / "backups-uploads" / body["upload_id"]
    assert (staged / "database.sql.gz").read_bytes() == b"dump"
    assert (staged / "files.tar").read_bytes() == b"tar"


def test_backup_upload_rejects_a_missing_database_or_bad_extension(tmp_path: Path) -> None:
    import io

    client = _client(tmp_path / "benches" / "current")

    missing = client.post(
        "/api/v1/sites/backup-uploads",
        data={"public_files": (io.BytesIO(b"tar"), "files.tar")},
        content_type="multipart/form-data",
    )
    wrong = client.post(
        "/api/v1/sites/backup-uploads",
        data={"database": (io.BytesIO(b"x"), "dump.zip")},
        content_type="multipart/form-data",
    )

    assert missing.status_code == 422
    assert missing.get_json()["error"]["code"] == "backup_file_missing"
    assert wrong.status_code == 422
    assert wrong.get_json()["error"]["code"] == "invalid_backup_file"


def test_restore_in_place_queues_a_restore_task_over_the_upload(tmp_path: Path) -> None:
    import io

    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)
    upload = _upload(client, private_files=(io.BytesIO(b"tar"), "private-files.tar"))

    response = _request(
        client,
        "post",
        "/api/v1/sites/site.localhost/actions/restore",
        json={"upload_id": upload["upload_id"]},
    )

    body = response.get_json()
    assert response.status_code == 202
    assert body["command"] == "restore-site"
    assert body["args"]["site"] == "site.localhost"
    meta = json.loads((bench_root / "tasks" / body["task_id"] / "meta.json").read_text())
    staged = bench_root / "backups-uploads" / upload["upload_id"]
    assert str(staged / "database.sql.gz") in meta["command_argv"]
    assert str(staged / "private-files.tar") in meta["command_argv"]
    assert upload["upload_id"] in meta["command_argv"]
    assert json.loads((staged / ".claimed").read_text())["claim"] in meta["command_argv"]
    assert meta["resource_keys"] == ["site:site.localhost"]


def test_an_upload_feeds_exactly_one_restore(tmp_path: Path) -> None:
    """The restoring task deletes the upload when done, so a second restore
    pointed at the same archives would lose its inputs - refuse it up front."""
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    _make_site(bench_root, "other.localhost")
    client = _client(bench_root)
    upload = _upload(client)

    first = _request(
        client, "post", "/api/v1/sites/site.localhost/actions/restore", json={"upload_id": upload["upload_id"]}
    )
    second = _request(
        client, "post", "/api/v1/sites/other.localhost/actions/restore", json={"upload_id": upload["upload_id"]}
    )

    assert first.status_code == 202
    assert second.status_code == 404
    assert "already being restored" in second.get_json()["error"]["message"]


def test_a_failed_queue_releases_the_upload_claim(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)
    upload = _upload(client)

    with patch(
        "admin.backend.api.v1.sites.backups.RestoreSiteTask.queue", side_effect=RuntimeError("boom")
    ):
        failed = client.post(
            "/api/v1/sites/site.localhost/actions/restore", json={"upload_id": upload["upload_id"]}
        )
    retried = _request(
        client, "post", "/api/v1/sites/site.localhost/actions/restore", json={"upload_id": upload["upload_id"]}
    )

    assert failed.status_code == 500
    assert retried.status_code == 202


def test_restore_in_place_rejects_unknown_uploads_and_sites(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)

    unknown_upload = client.post(
        "/api/v1/sites/site.localhost/actions/restore", json={"upload_id": "0123456789abcdef"}
    )
    unknown_site = client.post(
        "/api/v1/sites/missing.localhost/actions/restore", json={"upload_id": "0123456789abcdef"}
    )

    assert unknown_upload.status_code == 404
    assert unknown_upload.get_json()["error"]["code"] == "backup_upload_not_found"
    assert unknown_site.status_code == 404


def test_restore_retries_with_the_same_idempotency_key_return_the_accepted_task(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)
    upload = _upload(client)

    def submit():
        return _request(
            client,
            "post",
            "/api/v1/sites/site.localhost/actions/restore",
            json={"upload_id": upload["upload_id"]},
            headers={"Idempotency-Key": "restore-once"},
        )

    first = submit()
    second = submit()

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.get_json()["task_id"] == second.get_json()["task_id"]
