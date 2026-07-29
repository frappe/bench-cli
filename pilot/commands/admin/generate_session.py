from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Annotated, ClassVar

from pilot.commands import Arg, Command
from pilot.exceptions import BenchError


@dataclass(kw_only=True)
class GenerateSessionCommand(Command):
    name: ClassVar[str] = "generate-session"
    group: ClassVar[str] = "admin"
    help: ClassVar[str] = "Issue a 5-minute one-time sign-in token (use --full-path for a sign-in URL)."

    full_path: Annotated[bool, Arg(help="Print the full admin URL with ?sid= instead of the bare token.")] = (
        False
    )

    def run(self) -> None:
        from admin.backend.internal.session import Session
        from pilot.utils import admin_url

        if not self.bench.config.admin.password:
            raise BenchError("Admin has no password set; configure [admin].password in bench.toml first.")
        token = Session(self.bench).issue_login_token()
        if self.full_path:
            self.report(f"{admin_url(self.bench.config)}/?sid={urllib.parse.quote(token, safe='')}")
        else:
            self.report(token)
