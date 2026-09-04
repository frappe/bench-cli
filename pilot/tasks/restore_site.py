from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from pilot.core.site.backup_uploads import BackupUploads
from pilot.tasks import Task, step


@dataclass(kw_only=True)
class RestoreSiteTask(Task):
    """Restore a backup into an existing site in place via Site.restore."""

    command: ClassVar[str] = "restore-site"
    # The database is dropped and recreated mid-run; a kill leaves it half-loaded.
    is_cancellable_while_running: ClassVar[bool] = False

    site: str
    db_file: str
    public_files: str | None = None
    private_files: str | None = None
    # The staged upload these archives came from; removed once the restore
    # succeeds, kept on failure so a retry still has its inputs.
    upload_id: str | None = None
    upload_claim: str | None = None

    def run(self) -> None:
        self.require_production_privileges()
        self.restore()
        if self.upload_id:
            BackupUploads(self.bench_root).remove(
                self.upload_id, archive=self.db_file, claim=self.upload_claim
            )

    @step("restore", lambda self: f"Restore backup into {self.site}")
    def restore(self) -> None:
        self.bench.site(self.site).restore(self.db_file, self.public_files, self.private_files)


if __name__ == "__main__":
    RestoreSiteTask.main()
