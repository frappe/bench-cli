from __future__ import annotations

import contextlib
import hashlib
import os
import secrets
import shutil
from pathlib import Path

from flask import current_app, jsonify, request, send_file

from admin.backend.api.responses import accepted_task_response, error_response, no_content_response
from admin.backend.api.v1.sites import sites_bp
from admin.backend.api.v1.sites.shared import (
    internal_error,
    invalid_fields,
    malformed_body,
    new_site_name_error,
    site_name,
    site_name_failure,
    site_not_found,
    task_failure,
    text_fields,
)
from admin.backend.middleware import require_scope
from pilot.core.bench import Bench
from pilot.exceptions import BenchError, TaskConflictError
from pilot.internal.site_paths import site_exists
from pilot.internal.validators import validate_cron_expression, validate_site_name
from pilot.tasks.backup_site import BackupSiteTask
from pilot.tasks.new_site_from_backup import NewSiteFromBackupTask

_DEFAULT_BACKUPS_PAGE_SIZE = 20


@sites_bp.post("/<name>/backups")
@require_scope(site_name)
def backup_site(name: str):
    bench_root = Path(current_app.config["BENCH_ROOT"])
    if not site_exists(bench_root, name):
        return site_not_found()
    try:
        task_id = BackupSiteTask.queue(Bench(bench_root), site=name, with_files=True)
    except Exception as error:
        return task_failure(error)
    return accepted_task_response(bench_root, task_id)


@sites_bp.get("/<name>/backups")
@require_scope(site_name)
def list_backups(name: str):
    from admin.backend.providers.backups import BackupProvider

    bench_root = Path(current_app.config["BENCH_ROOT"])
    limit = request.args.get("limit", _DEFAULT_BACKUPS_PAGE_SIZE, type=int)
    try:
        sets = BackupProvider(bench_root, name).get_all(limit=limit)
    except Exception:
        return internal_error("Could not read site backups.")
    return jsonify([_backup_set_resource(s) for s in sets])


@sites_bp.get("/<name>/backups/<timestamp>")
@require_scope(site_name)
def get_backup(name: str, timestamp: str):
    bench_root = Path(current_app.config["BENCH_ROOT"])
    match, failure = _find_backup_set(bench_root, name, timestamp)
    if failure:
        return failure
    return jsonify(_backup_set_resource(match))


def _find_backup_set(bench_root: Path, name: str, timestamp: str):
    """The site's backup set for `timestamp` as (set, error_response) - one is None."""
    from admin.backend.providers.backups import BackupProvider

    try:
        sets = BackupProvider(bench_root, name).get_all()
    except Exception:
        return None, internal_error("Could not read site backups.")
    match = next((s for s in sets if s.timestamp == timestamp), None)
    if match is None:
        return None, error_response("backup_not_found", "Backup not found.", 404)
    return match, None


def _backup_set_resource(s) -> dict:
    return {
        "timestamp": s.timestamp,
        "created_at": s.created_at.isoformat(),
        "is_offsite": s.is_offsite,
        "files": [
            {
                "filename": f.filename,
                "path": f.path,
                "size_bytes": f.size_bytes,
                "kind": f.kind,
            }
            for f in s.files
        ],
    }


@sites_bp.post("/<name>/backups/<timestamp>/actions/restore")
@require_scope(site_name)
def restore_backup(name: str, timestamp: str):
    """Create a new site from this backup set. Restoring to a fresh name keeps
    the source site untouched, which also covers copying a site."""
    bench_root = Path(current_app.config["BENCH_ROOT"])
    if not site_exists(bench_root, name):
        return site_not_found()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return malformed_body()
    fields = text_fields(data, "new_site_name")
    if fields is None:
        return invalid_fields()

    new_site_name = fields["new_site_name"]
    err = validate_site_name(new_site_name) or new_site_name_error(bench_root, new_site_name)
    if err:
        return site_name_failure(err)

    match, failure = _find_backup_set(bench_root, name, timestamp)
    if failure:
        return failure

    files = {f.kind: f for f in match.files if f.path}
    if "database" not in files:
        return error_response(
            "backup_file_missing",
            "This backup's database file is not on this server. Download it from offsite storage first.",
            422,
        )

    try:
        task_id = _queue_restore(bench_root, name, timestamp, new_site_name, files.values())
    except Exception as error:
        return task_failure(error)
    return accepted_task_response(bench_root, task_id)


def _queue_restore(bench_root: Path, name: str, timestamp: str, new_site_name: str, files) -> str:
    """Stage the archives and queue the restore. Staging this call created is
    discarded when queueing fails; a directory that already existed belongs to
    an accepted restore for the same parameters - the usual cause of a
    conflict here - and must survive for that task to read."""
    paths, staging_dir, created = _stage_restore_files(bench_root, name, timestamp, new_site_name, files)
    try:
        return NewSiteFromBackupTask.queue(
            Bench(bench_root),
            name=new_site_name,
            db_file=paths["database"],
            admin_password=secrets.token_urlsafe(16),
            public_files=paths.get("public-file"),
            private_files=paths.get("private-file"),
            staging_dir=staging_dir,
            idempotency_key=request.headers.get("Idempotency-Key"),
            # Both locks: the destination is being created, and holding the source
            # keeps site-level tasks (drop, reinstall, backup) from mutating the
            # backup files this restore is about to read.
            resource_key=[f"site:{name.lower()}", f"site:{new_site_name.lower()}"],
        )
    except TaskConflictError:
        # A conflict means an active task holds these locks - a same-parameter
        # restore that may be reading this staging. Never delete it here; the
        # winning task removes it on success.
        raise
    except Exception:
        if created and staging_dir:
            shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def _stage_restore_files(
    bench_root: Path, name: str, timestamp: str, new_site_name: str, files
) -> tuple[dict[str, str], str | None, bool]:
    """Hardlink the selected archives so a backup or retention run cannot delete
    them out from under the queued restore. The directory is derived from the
    restore's parameters, keeping Idempotency-Key retries on the same task
    fingerprint. Falls back to the originals when the filesystem refuses the
    links (e.g. backups on another device). Returns (paths, staging_dir,
    created) - `created` says whether this call made the directory."""
    digest = hashlib.sha256(f"{name}:{timestamp}:{new_site_name}".encode()).hexdigest()[:16]
    staging = bench_root / "backups-staging" / digest
    staged = {}
    created = False
    try:
        # mkdir itself decides ownership: overlapping same-parameter requests
        # cannot both observe "absent" and later delete each other's staging.
        try:
            staging.mkdir(parents=True)
            created = True
        except FileExistsError:
            pass
        for file in files:
            target = staging / file.filename
            # Already staged by an equivalent request - same source, same
            # inode. Concurrent stagers must not fall back to the unprotected
            # originals over this.
            with contextlib.suppress(FileExistsError):
                os.link(file.path, target)
            staged[file.kind] = str(target)
    except OSError:
        if created:
            shutil.rmtree(staging, ignore_errors=True)
        return {file.kind: file.path for file in files}, None, False
    return staged, str(staging), created


@sites_bp.get("/<name>/backups/<timestamp>/files/<file_id>/content")
@require_scope(site_name)
def download_backup_file(name: str, timestamp: str, file_id: str):
    bench_root = Path(current_app.config["BENCH_ROOT"])
    bench = Bench(bench_root)
    try:
        target = bench.site(name).backups.download_file_path(timestamp, file_id)
    except BenchError:
        return error_response("invalid_filename", "Backup filename is invalid.", 422)
    except Exception:
        return error_response("backup_not_found", "Backup file not found.", 404)

    bench.audit_action(
        "backup", {"site": name, "event": "download", "timestamp": timestamp, "file": file_id}
    )
    return send_file(target, as_attachment=True, download_name=file_id)


def _site_backups_dir(bench_root: Path, name: str) -> Path:
    return Bench(bench_root).site(name).backups.directory


@sites_bp.get("/<name>/backups/<timestamp>/download-links")
@require_scope(site_name)
def backup_download_links(name: str, timestamp: str):
    """Pre-signed S3 URLs for a backup run's files - the user downloads
    straight from the bucket, so this server never proxies the transfer."""
    bench_root = Path(current_app.config["BENCH_ROOT"])
    bench = Bench(bench_root)
    try:
        links = bench.site(name).backups.download_links(timestamp)
    except FileNotFoundError:
        return error_response("backup_not_found", "Offsite backup not found.", 404)
    except Exception:
        return internal_error("Could not create offsite backup URLs.")

    bench.audit_action("backup", {"site": name, "event": "download", "timestamp": timestamp, "via": "s3"})
    return jsonify(links)


def _backup_cron_command(bench_root: Path, site: str) -> str:
    return Bench(bench_root).site(site).backups._cron_command()


def _retention_from_payload(block: dict | None):
    from pilot.core.site.backups import retention_from_payload

    return retention_from_payload(block)


@sites_bp.get("/<name>/backup-schedule")
@require_scope(site_name)
def get_backup_schedule(name: str):
    bench_root = Path(current_app.config["BENCH_ROOT"])
    try:
        schedule = Bench(bench_root).site(name).backups.schedule()
    except Exception:
        return internal_error("Could not read the backup schedule.")
    return jsonify(schedule)


@sites_bp.put("/<name>/backup-schedule")
@require_scope(site_name)
def set_backup_schedule(name: str):
    bench_root = Path(current_app.config["BENCH_ROOT"])
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return malformed_body()
    fields = text_fields(data, "schedule")
    retention_value = data.get("retention")
    if fields is None or (retention_value is not None and not isinstance(retention_value, dict)):
        return invalid_fields()
    schedule = fields["schedule"]
    if err := validate_cron_expression(schedule):
        return error_response("invalid_schedule", err, 422)
    backups = Bench(bench_root).site(name).backups
    retention = backups.retention_from_payload(retention_value)
    if isinstance(retention, str):
        return error_response("invalid_retention", retention, 422)
    try:
        saved = backups.set_schedule(schedule, retention)
    except Exception:
        return internal_error("Could not update the backup schedule.")
    return jsonify(saved)


@sites_bp.delete("/<name>/backup-schedule")
@require_scope(site_name)
def delete_backup_schedule(name: str):
    bench_root = Path(current_app.config["BENCH_ROOT"])
    try:
        Bench(bench_root).site(name).backups.clear_schedule()
    except Exception:
        return internal_error("Could not remove the backup schedule.")
    return no_content_response()
