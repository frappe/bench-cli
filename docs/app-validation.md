# App Validation

`App.validate` is the gate an app passes before pilot installs or builds it. Install, `update` and `switch-branch` all
call it, so an app that has moved revision is held to the same standard as a new one. Checks read the app's source and
never run it.

Each check lives in `pilot/core/app/validator/` as one class.

| Check | Catches |
| --- | --- |
| `RepoStructureCheck` | Missing files pilot expects: the module directory, `hooks.py`, `pyproject.toml` |
| `VersionSpecifiersCheck` | PEP 440 specifiers uv/pip would refuse, such as `>=20.19 <21` with the comma missing |
| `SymlinkCheck` | Symlinks resolving outside the app |
| `SyntaxCheck` | Any Python file that fails to parse |
| `HooksCheck` | Hook values of the wrong shape, and dotted paths naming code that does not exist |
| `FixturesCheck` | Fixture files that fail to parse, since frappe imports them during migrate |
| `DependencyDeclarationsCheck` | Dependency requirements in `hooks.py` and `pyproject.toml` that disagree or are malformed |
| `FrappeCompatibilityCheck` | A declared frappe version range the bench does not satisfy |
| `DependencyResolutionCheck` | Dependencies that cannot resolve against what every other app on the bench requires |
| `ImportCheck` | Module-scope imports that resolve nowhere on the bench |

## Blocking and advisory findings

Almost every finding is blocking: the check raises `AppValidationError`, and the install or update stops before anything
is installed or built.

A finding is advisory only where frappe itself catches the same failure and carries on. Blocking there would strand a
bench on a defect in an upstream app the operator cannot patch, while allowing it costs nothing frappe was not already
prepared to lose. Advisory findings are returned as warnings and reported by the calling task.

One case qualifies today:

- **A stale `scheduler_events` path.** frappe's `insert_single_event()` resolves each scheduler path with `get_attr()`,
  catches the failure, warns, and skips the job. The migrate completes and the job is simply never registered.

Every other hook is fatal, including the hooks that only fail long after an update finishes. `boot_session`, `on_login`,
`on_session_creation`, `auth_hooks` and `clear_cache` all reach a bare `get_attr()`, so allowing one through would trade
a blocked update for a Desk or login outage. The rule is fatal by default: a hook added later blocks unless someone
shows its consumer catches.

## What `ImportCheck` will not judge

Imports inside functions and `try` blocks are skipped, being lazy and often deliberately optional. What remains are
module-scope imports, which must resolve whenever the module loads.

Files only a developer runs are skipped by location: `test_*.py`, `conftest.py`, and anything under a `tests/` or
`benchmarks/` directory. Their imports come from dev extras a plain install never provides, and no request or migrate
loads them. Location is the only thing that excuses an import — declaring a package under
`[project.optional-dependencies]` does not, because the extra is never installed and the import would still fail on the
first request that loads the module.

## Limits

`HooksCheck` resolves a dotted path to a name that exists on disk, not to code that works. It cannot see a wrong
signature, and stops at the first attribute, so `module.Class.method` is checked only as far as `Class`.
