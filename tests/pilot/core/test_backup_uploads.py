"""Uploaded backup archives are staged privately until a restore consumes them."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pilot.core.site.backup_uploads import BackupUploads
from pilot.exceptions import BenchError


def _part(name: str, content: bytes = b"data"):
    return (name, io.BytesIO(content))


def test_save_stores_each_kind_under_a_fixed_name(tmp_path: Path) -> None:
    upload = BackupUploads(tmp_path).save(
        {
            "database": _part("20240101_000000-site-database.sql.gz", b"db"),
            "public_files": _part("20240101_000000-site-files.tar"),
            "private_files": _part("20240101_000000-site-private-files.tar"),
        }
    )

    assert upload.directory == tmp_path / "backups-uploads" / upload.upload_id
    assert Path(upload.db_file).name == "database.sql.gz"
    assert Path(upload.files["public_files"]).name == "files.tar"
    assert Path(upload.files["private_files"]).name == "private-files.tar"
    assert Path(upload.db_file).read_bytes() == b"db"


def test_save_requires_a_database_and_known_kinds(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)

    with pytest.raises(BenchError, match="database"):
        uploads.save({"public_files": _part("files.tar")})
    with pytest.raises(BenchError, match="Unknown"):
        uploads.save({"database": _part("db.sql.gz"), "logs": _part("x.log")})
    assert not (tmp_path / "backups-uploads").exists() or not any(
        (tmp_path / "backups-uploads").iterdir()
    )


def test_save_rejects_wrong_extensions_and_leaves_nothing_behind(tmp_path: Path) -> None:
    with pytest.raises(BenchError, match="must end with"):
        BackupUploads(tmp_path).save(
            {"database": _part("db.sql.gz"), "public_files": _part("files.zip")}
        )

    assert not any((tmp_path / "backups-uploads").iterdir())


def test_get_returns_the_saved_upload_and_rejects_bad_ids(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)
    saved = uploads.save({"database": _part("db.sql")})

    found = uploads.get(saved.upload_id)

    assert found.files == saved.files
    with pytest.raises(BenchError, match="Invalid"):
        uploads.get("../etc")
    with pytest.raises(BenchError, match="not found"):
        uploads.get("0123456789abcdef")


def test_remove_deletes_the_upload(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)
    saved = uploads.save({"database": _part("db.sql.gz")})

    uploads.remove(saved.upload_id)

    assert not saved.directory.exists()


def test_claim_reserves_the_upload_until_released(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)
    saved = uploads.save({"database": _part("db.sql.gz")})

    claimed = uploads.claim(saved.upload_id)
    with pytest.raises(BenchError, match="already being restored"):
        uploads.get(saved.upload_id)
    uploads.release(saved.upload_id, claimed.claim)

    assert claimed.files == saved.files
    assert uploads.get(saved.upload_id).files == saved.files


def test_remove_only_ever_touches_an_upload_directory(tmp_path: Path) -> None:
    outside = tmp_path / "precious"
    outside.mkdir()
    (outside / "keep").write_text("x")

    BackupUploads(tmp_path).remove("../precious")
    BackupUploads(tmp_path).remove(str(outside))

    assert (outside / "keep").exists()


def test_claim_is_exclusive_even_when_called_twice(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)
    saved = uploads.save({"database": _part("db.sql.gz")})

    uploads.claim(saved.upload_id)
    with pytest.raises(BenchError, match="already being restored"):
        uploads.claim(saved.upload_id)


def test_remove_with_an_archive_only_deletes_the_upload_that_holds_it(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)
    mine = uploads.save({"database": _part("db.sql.gz")})
    theirs = uploads.save({"database": _part("db.sql.gz")})

    # A task pointing at its own archives but naming someone else's upload id.
    uploads.remove(theirs.upload_id, archive=mine.db_file)
    assert theirs.directory.exists()

    uploads.remove(mine.upload_id, archive=mine.db_file)
    assert not mine.directory.exists()


def test_a_claimed_upload_is_removed_only_by_its_claim_holder(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)
    saved = uploads.save({"database": _part("db.sql.gz")})
    claimed = uploads.claim(saved.upload_id)

    uploads.remove(saved.upload_id, archive=claimed.db_file)
    assert claimed.directory.exists()
    uploads.remove(saved.upload_id, archive=claimed.db_file, claim="not-the-claim")
    assert claimed.directory.exists()

    uploads.remove(saved.upload_id, archive=claimed.db_file, claim=claimed.claim)
    assert not claimed.directory.exists()


def test_a_retry_with_the_same_key_gets_the_same_claim(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)
    saved = uploads.save({"database": _part("db.sql.gz")})

    first = uploads.claim(saved.upload_id, retry_key="req-1")
    retried = uploads.claim(saved.upload_id, retry_key="req-1")

    assert retried.claim == first.claim
    with pytest.raises(BenchError, match="already being restored"):
        uploads.claim(saved.upload_id, retry_key="req-2")
    with pytest.raises(BenchError, match="already being restored"):
        uploads.claim(saved.upload_id)


def test_release_only_by_the_claim_holder(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)
    saved = uploads.save({"database": _part("db.sql.gz")})
    claimed = uploads.claim(saved.upload_id)

    uploads.release(saved.upload_id, "someone-elses-claim")
    uploads.release(saved.upload_id, None)
    with pytest.raises(BenchError, match="already being restored"):
        uploads.get(saved.upload_id)

    uploads.release(saved.upload_id, claimed.claim)
    assert uploads.get(saved.upload_id).files == saved.files


def test_an_accepted_claim_can_no_longer_be_released(tmp_path: Path) -> None:
    """A same-key retry may share the claim; once either submission is accepted,
    the other's failure must not discard the reservation the task relies on."""
    uploads = BackupUploads(tmp_path)
    saved = uploads.save({"database": _part("db.sql.gz")})
    claimed = uploads.claim(saved.upload_id, retry_key="req-1")

    uploads.mark_queued(saved.upload_id, claimed.claim)
    uploads.release(saved.upload_id, claimed.claim)

    with pytest.raises(BenchError, match="already being restored"):
        uploads.get(saved.upload_id)
    uploads.remove(saved.upload_id, archive=claimed.db_file, claim=claimed.claim)
    assert not claimed.directory.exists()


def test_release_waits_for_the_marker_lock_and_honors_a_queued_claim(tmp_path: Path) -> None:
    """The loser of a shared-claim race releases while the winner marks queued.
    Marker operations serialize on the marker lock: a release that starts during
    the winner's critical section blocks, then sees the queued flag and refuses."""
    import json
    import threading

    from pilot.internal.atomic_file import exclusive_file_lock

    uploads = BackupUploads(tmp_path)
    saved = uploads.save({"database": _part("db.sql.gz")})
    claimed = uploads.claim(saved.upload_id, retry_key="req-1")
    marker = claimed.directory / ".claimed"

    released = threading.Event()

    def racing_release():
        uploads.release(saved.upload_id, claimed.claim)
        released.set()

    with exclusive_file_lock(marker):
        thread = threading.Thread(target=racing_release)
        thread.start()
        # The release must block on the lock, not proceed on its stale read.
        assert not released.wait(timeout=0.3)
        # The winner records acceptance inside its critical section.
        marker.write_text(json.dumps({"claim": claimed.claim, "retry_key": "req-1", "queued": True}))

    thread.join(timeout=10)
    assert released.is_set()
    assert marker.exists()
