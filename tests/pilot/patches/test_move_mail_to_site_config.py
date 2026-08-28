"""Tests for moving the alert mailbox into each bench's common_site_config.json."""

from __future__ import annotations

import json
from pathlib import Path

from cryptography.fernet import Fernet

from pilot.config.mail import MailConfig
from pilot.internal.toml import Toml
from pilot.patches.move_mail_to_site_config import run


def _benches_root(tmp_path: Path, limits: str, benches=("main",)) -> Path:
    root = tmp_path / "benches"
    root.mkdir()
    (root / "common_config.toml").write_text(f"[resource_limits]\n{limits}")
    for name in benches:
        bench = root / name
        (bench / "sites").mkdir(parents=True)
        (bench / "bench.toml").write_text(f'[bench]\nname = "{name}"\npython = "3.14"\n')
        (bench / "sites" / "common_site_config.json").write_text('{"db_host": "127.0.0.1"}')
    return root


def _encrypted(root: Path, password: str) -> str:
    key = Fernet.generate_key()
    (root / ".secret_key").write_bytes(key)
    return Fernet(key).encrypt(password.encode()).decode()


def test_the_mailbox_moves_into_every_bench(tmp_path: Path) -> None:
    root = _benches_root(tmp_path, "", benches=("one", "two"))
    ciphertext = _encrypted(root, "secret")
    (root / "common_config.toml").write_text(
        "[resource_limits]\n"
        'smtp_server = "smtp.example.com"\n'
        "smtp_port = 465\n"
        'smtp_email = "alerts@example.com"\n'
        f'smtp_password = "{ciphertext}"\n'
        "smtp_use_ssl = true\n"
        'email_recipients = ["ops@example.com"]\n'
    )

    run(root)

    for name in ("one", "two"):
        stored = json.loads((root / name / "sites" / "common_site_config.json").read_text())
        assert stored["mail_server"] == "smtp.example.com"
        assert stored["mail_password"] == "secret"
        assert stored["use_tls"] == 0
        assert stored["db_host"] == "127.0.0.1"


def test_the_moved_keys_leave_common_config(tmp_path: Path) -> None:
    root = _benches_root(tmp_path, "")
    ciphertext = _encrypted(root, "secret")
    (root / "common_config.toml").write_text(
        "[resource_limits]\n"
        "cpu_usage_limit = 85\n"
        'smtp_server = "smtp.example.com"\n'
        'smtp_email = "alerts@example.com"\n'
        f'smtp_password = "{ciphertext}"\n'
        'email_recipients = ["ops@example.com"]\n'
    )

    run(root)

    limits = Toml.loads((root / "common_config.toml").read_text())["resource_limits"]
    assert "smtp_server" not in limits
    assert "smtp_password" not in limits
    # Recipients have no framework key, so they stay where they were.
    assert limits["email_recipients"] == ["ops@example.com"]
    assert limits["cpu_usage_limit"] == 85


def test_a_bench_without_mail_is_left_alone(tmp_path: Path) -> None:
    root = _benches_root(tmp_path, "cpu_usage_limit = 85\n")

    run(root)

    stored = json.loads((root / "main" / "sites" / "common_site_config.json").read_text())
    assert stored == {"db_host": "127.0.0.1"}


def test_running_twice_does_not_undo_a_later_edit(tmp_path: Path) -> None:
    """The patch is marked per bench, so a second upgrade must not overwrite a
    mailbox the operator changed after the first one."""
    root = _benches_root(tmp_path, "")
    ciphertext = _encrypted(root, "secret")
    (root / "common_config.toml").write_text(
        "[resource_limits]\n"
        'smtp_server = "smtp.example.com"\n'
        'smtp_email = "alerts@example.com"\n'
        f'smtp_password = "{ciphertext}"\n'
    )
    run(root)

    sites = root / "main" / "sites"
    changed = MailConfig.read(sites)
    changed.server = "smtp2.example.com"
    changed.write(sites)

    run(root)

    assert MailConfig.read(sites).server == "smtp2.example.com"


def test_an_undecryptable_password_stops_the_migration(tmp_path: Path) -> None:
    """The ciphertext is the only copy, so a password that cannot be read must
    be left alone for a later run rather than migrated away as blank."""
    root = _benches_root(tmp_path, "")
    _encrypted(root, "secret")
    (root / ".secret_key").write_bytes(Fernet.generate_key())
    original = (
        "[resource_limits]\n"
        'smtp_server = "smtp.example.com"\n'
        'smtp_email = "alerts@example.com"\n'
        'smtp_password = "gAAAAABmbogus"\n'
    )
    (root / "common_config.toml").write_text(original)

    run(root)

    assert (root / "common_config.toml").read_text() == original
    assert json.loads((root / "main" / "sites" / "common_site_config.json").read_text()) == {
        "db_host": "127.0.0.1"
    }


def test_a_missing_key_stops_the_migration(tmp_path: Path) -> None:
    root = _benches_root(tmp_path, "")
    (root / "common_config.toml").write_text(
        "[resource_limits]\n"
        'smtp_server = "smtp.example.com"\n'
        'smtp_email = "alerts@example.com"\n'
        'smtp_password = "gAAAAABmbogus"\n'
    )

    run(root)

    limits = Toml.loads((root / "common_config.toml").read_text())["resource_limits"]
    assert limits["smtp_password"] == "gAAAAABmbogus"


def test_a_retry_migrates_once_the_key_is_restored(tmp_path: Path) -> None:
    """Stopping must not be permanent: the bench is left unmarked, so a later
    run with the right key still moves the mailbox across."""
    root = _benches_root(tmp_path, "")
    ciphertext = _encrypted(root, "secret")
    key = (root / ".secret_key").read_bytes()
    (root / "common_config.toml").write_text(
        "[resource_limits]\n"
        'smtp_server = "smtp.example.com"\n'
        'smtp_email = "alerts@example.com"\n'
        f'smtp_password = "{ciphertext}"\n'
    )
    (root / ".secret_key").unlink()

    run(root)
    (root / ".secret_key").write_bytes(key)
    run(root)

    stored = json.loads((root / "main" / "sites" / "common_site_config.json").read_text())
    assert stored["mail_password"] == "secret"


def test_an_unusable_mailbox_stops_the_migration(tmp_path: Path) -> None:
    """write() declines a mailbox it cannot validate, so trimming the old fields
    would drop it with no copy left and no way to retry."""
    root = _benches_root(tmp_path, "")
    ciphertext = _encrypted(root, "secret")
    for bad in ('smtp_email = "not-an-address"', 'smtp_email = "a@b.test"\nsmtp_port = 70000'):
        (root / "common_config.toml").write_text(
            f'[resource_limits]\nsmtp_server = "smtp.example.com"\n{bad}\n'
            f'smtp_password = "{ciphertext}"\n'
        )

        run(root)

        limits = Toml.loads((root / "common_config.toml").read_text())["resource_limits"]
        assert limits["smtp_server"] == "smtp.example.com"
        assert json.loads((root / "main" / "sites" / "common_site_config.json").read_text()) == {
            "db_host": "127.0.0.1"
        }


def test_a_corrected_mailbox_migrates_on_the_next_run(tmp_path: Path) -> None:
    root = _benches_root(tmp_path, "")
    ciphertext = _encrypted(root, "secret")
    base = f'[resource_limits]\nsmtp_server = "smtp.example.com"\nsmtp_password = "{ciphertext}"\n'
    (root / "common_config.toml").write_text(base + 'smtp_email = "not-an-address"\n')
    run(root)

    (root / "common_config.toml").write_text(base + 'smtp_email = "alerts@example.com"\n')
    run(root)

    stored = json.loads((root / "main" / "sites" / "common_site_config.json").read_text())
    assert stored["mail_password"] == "secret"
    assert stored["auto_email_id"] == "alerts@example.com"


def test_a_bench_without_a_site_config_is_left_for_a_later_run(tmp_path: Path) -> None:
    """write() has nothing to merge into before the bench is set up, so trimming
    the legacy fields would lose the mailbox with no way to retry."""
    root = _benches_root(tmp_path, "")
    ciphertext = _encrypted(root, "secret")
    (root / "common_config.toml").write_text(
        "[resource_limits]\n"
        'smtp_server = "smtp.example.com"\n'
        'smtp_email = "alerts@example.com"\n'
        f'smtp_password = "{ciphertext}"\n'
    )
    (root / "main" / "sites" / "common_site_config.json").unlink()

    run(root)

    limits = Toml.loads((root / "common_config.toml").read_text())["resource_limits"]
    assert limits["smtp_server"] == "smtp.example.com"
    assert not (root / "main" / ".patches.json").exists()


def test_the_mailbox_moves_once_the_bench_has_a_site_config(tmp_path: Path) -> None:
    root = _benches_root(tmp_path, "")
    ciphertext = _encrypted(root, "secret")
    (root / "common_config.toml").write_text(
        "[resource_limits]\n"
        'smtp_server = "smtp.example.com"\n'
        'smtp_email = "alerts@example.com"\n'
        f'smtp_password = "{ciphertext}"\n'
    )
    site_config = root / "main" / "sites" / "common_site_config.json"
    site_config.unlink()
    run(root)

    site_config.write_text('{"db_host": "127.0.0.1"}')
    run(root)

    assert json.loads(site_config.read_text())["mail_password"] == "secret"


def test_one_unmigrated_bench_holds_the_legacy_fields_for_all(tmp_path: Path) -> None:
    """The legacy settings are shared, so they may only be trimmed once every
    bench that needs them is holding its own copy."""
    root = _benches_root(tmp_path, "", benches=("one", "two"))
    ciphertext = _encrypted(root, "secret")
    (root / "common_config.toml").write_text(
        "[resource_limits]\n"
        'smtp_server = "smtp.example.com"\n'
        'smtp_email = "alerts@example.com"\n'
        f'smtp_password = "{ciphertext}"\n'
    )
    (root / "two" / "sites" / "common_site_config.json").unlink()

    run(root)

    limits = Toml.loads((root / "common_config.toml").read_text())["resource_limits"]
    assert limits["smtp_server"] == "smtp.example.com"
    assert json.loads((root / "one" / "sites" / "common_site_config.json").read_text())[
        "mail_password"
    ] == "secret"


def test_legacy_fields_without_a_server_are_not_trimmed(tmp_path: Path) -> None:
    """There is nowhere to migrate them to, so removing them would delete the
    only stored credential."""
    root = _benches_root(tmp_path, "")
    ciphertext = _encrypted(root, "secret")
    (root / "common_config.toml").write_text(
        f'[resource_limits]\nsmtp_email = "alerts@example.com"\nsmtp_password = "{ciphertext}"\n'
    )

    run(root)

    limits = Toml.loads((root / "common_config.toml").read_text())["resource_limits"]
    assert limits["smtp_password"] == ciphertext
    assert not (root / "main" / ".patches.json").exists()


def test_a_bench_with_a_damaged_site_config_is_skipped(tmp_path: Path) -> None:
    root = _benches_root(tmp_path, "")
    ciphertext = _encrypted(root, "secret")
    (root / "common_config.toml").write_text(
        "[resource_limits]\n"
        'smtp_server = "smtp.example.com"\n'
        'smtp_email = "alerts@example.com"\n'
        f'smtp_password = "{ciphertext}"\n'
    )
    damaged = '{"db_host": "127.0.0.1", "redis_cache": trunc'
    (root / "main" / "sites" / "common_site_config.json").write_text(damaged)

    run(root)

    assert (root / "main" / "sites" / "common_site_config.json").read_text() == damaged
    limits = Toml.loads((root / "common_config.toml").read_text())["resource_limits"]
    assert limits["smtp_server"] == "smtp.example.com"
