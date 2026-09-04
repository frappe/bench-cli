from __future__ import annotations

import json
import re
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from pilot.exceptions import BenchError
from pilot.internal.atomic_file import exclusive_file_lock
from pilot.utils import make_private_directory, open_private, write_private_text

UPLOADS_DIR = "backups-uploads"

_UPLOAD_ID_RE = re.compile(r"^[a-f0-9]{16}$")
_CLAIM_MARKER = ".claimed"

# kind -> (stored stem, accepted suffixes, longest first)
_KINDS = {
    "database": ("database", (".sql.gz", ".sql")),
    "public_files": ("files", (".tar.gz", ".tgz", ".tar")),
    "private_files": ("private-files", (".tar.gz", ".tgz", ".tar")),
}


@dataclass(frozen=True)
class BackupUpload:
    upload_id: str
    directory: Path
    files: dict[str, str]
    # Set by claim(): the capability a restore presents to delete this upload.
    claim: str | None = None

    @property
    def db_file(self) -> str:
        return self.files["database"]


class BackupUploads:
    """Backup archives uploaded through the admin, held under the bench until a
    restore consumes them. The database is required; file archives are optional."""

    def __init__(self, bench_root: Path) -> None:
        self.root = bench_root / UPLOADS_DIR

    def save(self, parts: dict[str, tuple[str, IO[bytes]]]) -> BackupUpload:
        """`parts` maps kind to (original filename, stream)."""
        if "database" not in parts:
            raise BenchError("A database backup file is required.")
        unknown = set(parts) - set(_KINDS)
        if unknown:
            raise BenchError(f"Unknown backup file kind: {', '.join(sorted(unknown))}.")

        upload_id = secrets.token_hex(8)
        directory = self.root / upload_id
        make_private_directory(directory, parents=True)
        files: dict[str, str] = {}
        try:
            for kind, (filename, stream) in parts.items():
                stem, allowed = _KINDS[kind]
                target = directory / f"{stem}{_extension(filename, allowed)}"
                with open_private(target, "wb") as out:
                    shutil.copyfileobj(stream, out)
                files[kind] = str(target)
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        return BackupUpload(upload_id, directory, files)

    def get(self, upload_id: str) -> BackupUpload:
        upload = self._read(upload_id)
        if (upload.directory / _CLAIM_MARKER).exists():
            raise BenchError("This backup upload is already being restored. Upload the files again.")
        return upload

    def _read(self, upload_id: str) -> BackupUpload:
        if not _UPLOAD_ID_RE.match(upload_id or ""):
            raise BenchError("Invalid backup upload id.")
        directory = self.root / upload_id
        if not directory.is_dir():
            raise BenchError("Backup upload not found. Upload the files again.")
        files = {}
        for kind, (stem, _allowed) in _KINDS.items():
            match = next((p for p in directory.iterdir() if p.name.startswith(stem + ".")), None)
            if match:
                files[kind] = str(match)
        if "database" not in files:
            raise BenchError("Backup upload is missing its database file. Upload the files again.")
        return BackupUpload(upload_id, directory, files)

    def _marker_lock(self, upload_id: str):
        """Marker reads and writes race across workers - a same-key retry can be
        queued while the original request is failing. Serialize them."""
        return exclusive_file_lock(self.root / upload_id / _CLAIM_MARKER)

    def claim(self, upload_id: str, retry_key: str | None = None) -> BackupUpload:
        """Reserve the upload for one restore: a task deletes it when done, so a
        second restore must not be pointed at the same archives. The marker is
        created exclusively, so concurrent claims cannot both succeed. A retry
        carrying the Idempotency-Key that made the claim gets the same claim
        back, so task submission can return the restore already accepted."""
        upload = self._read(upload_id)
        marker = upload.directory / _CLAIM_MARKER
        claim = secrets.token_hex(16)
        with self._marker_lock(upload_id):
            try:
                with open_private(marker, "w", exclusive=True) as handle:
                    handle.write(json.dumps({"claim": claim, "retry_key": retry_key}))
            except FileExistsError:
                existing = _read_marker(marker)
                if not retry_key or existing.get("retry_key") != retry_key:
                    raise BenchError(
                        "This backup upload is already being restored. Upload the files again."
                    ) from None
                claim = existing["claim"]
        return BackupUpload(upload.upload_id, upload.directory, upload.files, claim)

    def mark_queued(self, upload_id: str, claim: str | None) -> None:
        """Record that a restore holding this claim was accepted. From here the
        claim can no longer be released - only the task's cleanup ends it."""
        with self._marker_lock(upload_id):
            marker = self.root / upload_id / _CLAIM_MARKER
            data = _read_marker(marker)
            if claim and data.get("claim") == claim:
                data["queued"] = True
                write_private_text(marker, json.dumps(data))

    def release(self, upload_id: str, claim: str | None) -> None:
        """Undo a claim whose restore never got queued. Only the claim's holder
        may release it, and not once any submission carrying the claim has been
        accepted - a failed request cannot discard a reservation that a
        concurrent same-key retry has since turned into a task."""
        if not _UPLOAD_ID_RE.match(upload_id or "") or not claim:
            return
        with self._marker_lock(upload_id):
            marker = self.root / upload_id / _CLAIM_MARKER
            data = _read_marker(marker)
            if data.get("claim") == claim and not data.get("queued"):
                marker.unlink(missing_ok=True)

    def remove(self, upload_id: str, archive: str | None = None, claim: str | None = None) -> None:
        """Delete an upload. The id is validated, so only a directory under
        backups-uploads can ever be removed. A claimed upload is removed only by
        the restore holding its claim, and only if `archive` lives inside it -
        a restore cleans up the upload it consumed, never someone else's."""
        if not _UPLOAD_ID_RE.match(upload_id or ""):
            return
        directory = self.root / upload_id
        if archive is not None and not Path(archive).resolve().is_relative_to(directory.resolve()):
            return
        marker = directory / _CLAIM_MARKER
        if marker.exists() and (not claim or _read_marker(marker).get("claim") != claim):
            return
        shutil.rmtree(directory, ignore_errors=True)


def _read_marker(marker: Path) -> dict:
    try:
        data = json.loads(marker.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _extension(filename: str, allowed: tuple[str, ...]) -> str:
    lowered = (filename or "").lower()
    for suffix in allowed:
        if lowered.endswith(suffix):
            return suffix
    raise BenchError(f"'{filename}' must end with one of: {', '.join(allowed)}.")
