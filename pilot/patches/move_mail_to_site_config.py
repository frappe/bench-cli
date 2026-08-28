from __future__ import annotations

from pathlib import Path

PATCH_NAME = Path(__file__).stem

KEY_FILENAME = ".secret_key"


def run(benches_root: Path) -> None:
    """Move the alert mailbox out of [resource_limits] in common_config.toml and
    into each bench's sites/common_site_config.json, under the keys the
    framework's Email Account reads."""
    from pilot.internal.patch_state import is_applied, mark_applied
    from pilot.internal.toml import Toml

    common_path = benches_root / "common_config.toml"
    if not common_path.exists():
        return

    raw = Toml.loads(common_path.read_text(encoding="utf-8"))
    limits = raw.get("resource_limits") or {}
    stored = {key: limits[key] for key in _MAIL_KEYS if key in limits}

    bench_dirs = [
        entry
        for entry in sorted(benches_root.glob("*"))
        if entry.is_dir() and (entry / "bench.toml").exists() and not is_applied(entry, PATCH_NAME)
    ]
    if not bench_dirs:
        return

    try:
        mail = _mail_config(benches_root, stored)
    except UnreadablePassword as error:
        # Leave the ciphertext in place: it is the only copy, and a later run
        # with the right key can still migrate it.
        print(f"Skipping {PATCH_NAME}: {error}")
        return

    for bench_dir in bench_dirs:
        if mail is not None:
            mail.write(bench_dir / "sites")
        mark_applied(bench_dir, PATCH_NAME)

    if stored:
        _trim_common_config(common_path, raw, limits)


class UnreadablePassword(Exception):
    """The stored password cannot be decrypted, so migrating would destroy it."""


_MAIL_KEYS = (
    "smtp_server",
    "smtp_port",
    "smtp_email",
    "smtp_login",
    "smtp_password",
    "smtp_use_ssl",
)


def _mail_config(benches_root: Path, stored: dict):
    """None when there was no mailbox to move, so an unconfigured bench is left
    alone rather than having an empty mail block written into it."""
    from pilot.config.mail import MailConfig

    if not stored.get("smtp_server"):
        return None
    return MailConfig(
        server=str(stored.get("smtp_server", "")),
        port=int(stored.get("smtp_port", 0) or 0),
        email=str(stored.get("smtp_email", "")),
        login=str(stored.get("smtp_login", "")),
        password=_decrypt(benches_root, str(stored.get("smtp_password", ""))),
        use_ssl=bool(stored.get("smtp_use_ssl", False)),
    )


def _decrypt(benches_root: Path, ciphertext: str) -> str:
    """The password was stored Fernet-encrypted under benches_root/.secret_key.
    Raise on one that cannot be read: the migration trims the ciphertext once it
    is done, so treating an unreadable password as blank would destroy the only
    copy of it."""
    if not ciphertext:
        return ""
    key_path = benches_root / KEY_FILENAME
    if not key_path.exists():
        raise UnreadablePassword(f"{key_path} is missing, so smtp_password cannot be decrypted.")
    from cryptography.fernet import Fernet, InvalidToken

    try:
        return Fernet(key_path.read_bytes()).decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError) as error:
        raise UnreadablePassword(
            f"the key at {key_path} does not match the stored smtp_password."
        ) from error


def _trim_common_config(path: Path, raw: dict, limits: dict) -> None:
    from pilot.internal.atomic_file import atomic_write_private_text
    from pilot.internal.toml import Toml

    for key in _MAIL_KEYS:
        limits.pop(key, None)
    raw["resource_limits"] = limits
    atomic_write_private_text(path, Toml.dumps(raw))


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from pilot.utils import benches_dir

    run(benches_dir())
