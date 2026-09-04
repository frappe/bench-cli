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


def test_restore_backup_queues_a_new_site_task(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    db_file = _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    files = _make_backup_file(bench_root, "site.localhost", "20240101_000000", "files.tar")
    client = _client(bench_root)

    response = _request(
        client,
        "post",
        "/api/v1/sites/site.localhost/backups/20240101_000000/actions/restore",
        json={"new_site_name": "copy.localhost"},
    )

    body = response.get_json()
    assert response.status_code == 202
    assert body["command"] == "new-site-from-backup"
    assert body["args"]["name"] == "copy.localhost"
    # File paths ride in the task argv and the password in its private secrets;
    # neither lands in the public task resource.
    meta = json.loads((bench_root / "tasks" / body["task_id"] / "meta.json").read_text())
    assert meta["args"]["admin_password"] == "[redacted]"
    assert set(meta["resource_keys"]) == {"site:site.localhost", "site:copy.localhost"}
    # The archives are hardlinked into a staging dir, so a backup or retention
    # run deleting the originals cannot take the restore's inputs with it.
    staged = [
        Path(arg) for arg in meta["command_argv"] if "backups-staging" in arg
    ]
    assert {db_file.name, files.name} <= {p.name for p in staged}
    db_file.unlink()
    staged_db = next(p for p in staged if p.name == db_file.name)
    assert staged_db.read_text() == "data"


def test_restore_backup_falls_back_to_originals_when_linking_fails(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    db_file = _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    client = _client(bench_root)

    with patch("admin.backend.api.v1.sites.backups.os.link", side_effect=OSError):
        response = _request(
            client,
            "post",
            "/api/v1/sites/site.localhost/backups/20240101_000000/actions/restore",
            json={"new_site_name": "copy.localhost"},
        )

    body = response.get_json()
    assert response.status_code == 202
    meta = json.loads((bench_root / "tasks" / body["task_id"] / "meta.json").read_text())
    assert str(db_file) in meta["command_argv"]
    assert not (bench_root / "backups-staging").exists() or not any(
        (bench_root / "backups-staging").iterdir()
    )


def test_restore_backup_404s_for_an_unknown_timestamp(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    client = _client(bench_root)

    response = _request(
        client,
        "post",
        "/api/v1/sites/site.localhost/backups/20240101_000000/actions/restore",
        json={"new_site_name": "copy.localhost"},
    )

    assert response.status_code == 404


def test_restore_backup_rejects_an_occupied_new_name(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    _make_site(bench_root, "taken.localhost")
    _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    client = _client(bench_root)

    response = _request(
        client,
        "post",
        "/api/v1/sites/site.localhost/backups/20240101_000000/actions/restore",
        json={"new_site_name": "taken.localhost"},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "site_name_conflict"


def test_restore_backup_rejects_an_invalid_new_name(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    client = _client(bench_root)

    response = _request(
        client,
        "post",
        "/api/v1/sites/site.localhost/backups/20240101_000000/actions/restore",
        json={"new_site_name": "bad name!"},
    )

    assert response.status_code == 422


def test_restore_backup_retries_idempotently(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    client = _client(bench_root)

    def submit():
        return _request(
            client,
            "post",
            "/api/v1/sites/site.localhost/backups/20240101_000000/actions/restore",
            json={"new_site_name": "copy.localhost"},
            headers={"Idempotency-Key": "restore-once"},
        )

    first = submit()
    second = submit()

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.get_json()["task_id"] == second.get_json()["task_id"]


def test_conflicting_restore_keeps_the_accepted_restores_staging(tmp_path: Path) -> None:
    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    db_file = _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    client = _client(bench_root)
    url = "/api/v1/sites/site.localhost/backups/20240101_000000/actions/restore"
    body = {"new_site_name": "copy.localhost"}

    first = _request(client, "post", url, json=body)
    assert first.status_code == 202
    meta = json.loads((bench_root / "tasks" / first.get_json()["task_id"] / "meta.json").read_text())
    staged_db = next(Path(a) for a in meta["command_argv"] if a.endswith(db_file.name))
    assert staged_db.exists()

    # Same parameters, no idempotency key: the destination lock is held, so the
    # second submission conflicts - and must not take the first one's inputs.
    second = _request(client, "post", url, json=body)

    assert second.status_code == 409
    assert staged_db.exists()


def test_overlapping_restores_cannot_both_claim_staging_ownership(tmp_path: Path) -> None:
    """mkdir decides ownership atomically: a request that finds the directory
    already present never deletes it, even when the pre-check raced."""
    from admin.backend.api.v1.sites.backups import _stage_restore_files

    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    db_file = _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")

    class _File:
        kind = "database"
        filename = db_file.name
        path = str(db_file)

    first = _stage_restore_files(bench_root, "site.localhost", "20240101_000000", "copy.localhost", [_File()])
    second = _stage_restore_files(bench_root, "site.localhost", "20240101_000000", "copy.localhost", [_File()])

    assert first[2] is True
    assert second[2] is False
    assert first[1] == second[1]


def test_a_conflicting_creator_does_not_delete_the_winners_staging(tmp_path: Path) -> None:
    """The staging creator can lose the queue race to a same-parameter request
    that reused its directory; the resulting conflict must not delete it."""
    from admin.backend.api.v1.sites.backups import _queue_restore

    bench_root = tmp_path / "benches" / "current"
    _make_site(bench_root, "site.localhost")
    db_file = _make_backup_file(bench_root, "site.localhost", "20240101_000000", "database.sql.gz")
    client = _client(bench_root)
    url = "/api/v1/sites/site.localhost/backups/20240101_000000/actions/restore"

    accepted = _request(client, "post", url, json={"new_site_name": "copy.localhost"})
    assert accepted.status_code == 202
    meta = json.loads(
        (bench_root / "tasks" / accepted.get_json()["task_id"] / "meta.json").read_text()
    )
    staged_db = next(Path(a) for a in meta["command_argv"] if a.endswith(db_file.name))

    class _File:
        kind = "database"
        filename = db_file.name
        path = str(db_file)

    # Simulate the racing creator: it made the directory (created=True in its
    # view), then loses the queue to the accepted task's locks.
    import pytest

    from pilot.exceptions import TaskConflictError

    with (
        patch(
            "admin.backend.api.v1.sites.backups._stage_restore_files",
            return_value=({"database": str(staged_db)}, str(staged_db.parent), True),
        ),
        client.application.test_request_context(),
        pytest.raises(TaskConflictError),
    ):
        _queue_restore(
            bench_root, "site.localhost", "20240101_000000", "copy.localhost", [_File()]
        )

    assert staged_db.exists()
