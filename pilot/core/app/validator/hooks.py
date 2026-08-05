from __future__ import annotations

import ast
import typing
from pathlib import Path

from pilot.core.app.validator.base import module_path
from pilot.exceptions import AppValidationError

if typing.TYPE_CHECKING:
    from pilot.core.app import App

# frappe's append_hook branches on dict, so a non-dict here reaches consumers
# that call .items() and breaks install or migrate.
_DICT_HOOKS = frozenset(
    [
        "additional_timeline_content",
        "base_template_map",
        "doc_events",
        "doctype_js",
        "extend_doctype_class",
        "extend_website_page_controller_context",
        "has_permission",
        "jinja",
        "override_doctype_class",
        "override_whitelisted_methods",
        "page_js",
        "permission_query_conditions",
        "role_home_page",
        "scheduler_events",
        "standard_queries",
        "webform_include_css",
        "webform_include_js",
        "website_context",
    ]
)

# Hooks whose leaf strings are dotted paths frappe resolves with get_attr().
_PATH_HOOKS = frozenset(
    [
        "additional_timeline_content",
        "after_build",
        "after_install",
        "after_migrate",
        "after_sync",
        "after_uninstall",
        "auth_hooks",
        "before_install",
        "before_migrate",
        "before_tests",
        "before_uninstall",
        "before_write_file",
        "boot_session",
        "clear_cache",
        "delete_file_data_content",
        "doc_events",
        "extend_bootinfo",
        "extend_doctype_class",
        "extend_website_page_controller_context",
        "get_sender_details",
        "get_web_pages_with_dynamic_routes",
        "get_website_user_home_page",
        "has_permission",
        "jinja",
        "notification_config",
        "on_login",
        "on_logout",
        "on_session_creation",
        "override_doctype_class",
        "override_email_send",
        "override_whitelisted_methods",
        "permission_query_conditions",
        "scheduler_events",
        "send_sms",
        "send_token_via_sms",
        "standard_queries",
        "update_website_context",
        "website_clear_cache",
        "website_path_resolver",
        "write_file",
    ]
)

# The subset frappe resolves eagerly during install, migrate, build, or uninstall,
# with a bare get_attr() and no guard - a stale path there aborts the operation
# pilot is running. Every other path hook resolves lazily on a runtime action, and
# frappe skips a scheduler_events path it cannot import instead of failing migrate.
_BLOCKING_PATH_HOOKS = frozenset(
    [
        "after_build",
        "after_install",
        "after_migrate",
        "after_sync",
        "after_uninstall",
        "before_install",
        "before_migrate",
        "before_uninstall",
    ]
)


# Shapes a dict hook definitely isn't. A name or a call may still evaluate to a
# dict at import time, so those are left alone rather than guessed at.
_NOT_A_DICT = (ast.List, ast.Tuple, ast.Set, ast.Constant)


class HooksCheck:
    """Verify hooks.py shapes and that its dotted paths point at real code.

    Only documented hooks are inspected; app-specific hook names are left alone.
    SyntaxCheck guarantees hooks.py parses first.

    A stale path only blocks when frappe would abort on it. The rest are returned
    as warnings: refusing to update over them would strand a bench on a defect in
    an upstream app the operator cannot patch.
    """

    def run(self, app: "App") -> list[str]:
        hooks_path = module_path(app) / "hooks.py"
        if not hooks_path.is_file():
            return []  # RepoStructureCheck owns this when it runs; updates skip it
        tree = ast.parse(hooks_path.read_text())

        blocking: list[str] = []
        advisory: list[str] = []
        for name, value in _hook_assignments(tree):
            if name in _DICT_HOOKS and isinstance(value, _NOT_A_DICT):
                blocking.append(f"line {value.lineno}: {name} must be a dict")
                continue
            if name not in _PATH_HOOKS:
                continue
            for path, lineno in _string_values(value):
                error = _path_error(app, path)
                if error:
                    problem = f"line {lineno}: {name} -> {path}: {error}"
                    (blocking if name in _BLOCKING_PATH_HOOKS else advisory).append(problem)

        if blocking:
            raise AppValidationError(_blocking_message(app, blocking))
        location = f"{app.module_name}/hooks.py"
        return [f"'{app.config.name}' has a stale hook in {location}: {problem}" for problem in advisory]


def _blocking_message(app: "App", problems: list[str]) -> str:
    return (
        f"'{app.config.name}' has invalid hooks in {app.module_name}/hooks.py:\n"
        + "\n".join(f"  {problem}" for problem in problems)
        + "\nPoint each path at code that exists (or drop the hook). Hook shapes: "
        "https://docs.frappe.io/framework/user/en/python-api/hooks"
    )


def _hook_assignments(tree: ast.Module) -> list[tuple[str, ast.expr]]:
    """Every module-level `hook_name = value` in hooks.py, as (name, value) pairs."""
    hooks = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            hooks += [(target.id, node.value) for target in node.targets if isinstance(target, ast.Name)]
    return hooks


def _string_values(node: ast.expr) -> list[tuple[str, int]]:
    """Every string inside a hook's value, with its line number, however deeply nested.

    `{"ToDo": {"on_update": ["myapp.overrides.on_update"]}}` yields that one path.
    Dict keys are skipped - those are doctype names and cron expressions, not paths.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [(node.value, node.lineno)]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [found for element in node.elts for found in _string_values(element)]
    if isinstance(node, ast.Dict):
        return [found for value in node.values if value for found in _string_values(value)]
    return []


def _path_error(app: "App", dotted: str) -> str | None:
    """Why a hook's dotted path doesn't point at real code, or None if it does.

    `"myapp.setup.after_migrate"` looks for `after_migrate` in `myapp/setup.py`.
    """
    app_module, *rest = dotted.rsplit(":", 1)[-1].split(".")  # jenv-style "alias:path"
    # The app under validation may be staged outside apps/; anything else is a
    # pip package, which ImportCheck already covers.
    package = (
        module_path(app) if app_module == app.module_name else app.bench.apps_path / app_module / app_module
    )
    if not package.is_dir():
        return None

    module_file, attributes = _find_module(package, rest)
    if module_file is None:
        return f"no module '{dotted}'"
    if not attributes:
        return None  # the path names a module, not something inside one

    symbols = _top_level_symbols(module_file)
    if symbols is None or attributes[0] in symbols:
        return None
    # Only the first attribute is checked, so `some.module.Class.method` stops at `Class`.
    module_name = module_file.parent.name if module_file.stem == "__init__" else module_file.stem
    return f"'{module_name}' has no '{attributes[0]}'"


def _find_module(package: Path, parts: list[str]) -> tuple[Path | None, list[str]]:
    """Split a path's parts into the module file they name and the attributes after it.

    `["setup", "after_migrate"]` -> `(myapp/setup.py, ["after_migrate"])`.
    """
    current = package
    for index, part in enumerate(parts):
        if (current / part).is_dir():
            current = current / part  # a package - keep walking
        elif (current / f"{part}.py").is_file():
            return current / f"{part}.py", parts[index + 1 :]
        else:
            # Neither: `part` and everything after it must be attributes of the
            # package we're standing in, defined in its __init__.py.
            return _package_init(current), parts[index:]
    return _package_init(current), []


def _package_init(package: Path) -> Path | None:
    init = package / "__init__.py"
    return init if init.is_file() else None


def _reachable_statements(body: list[ast.stmt]) -> list[ast.stmt]:
    """Module-level statements, plus those inside any if/try guarding them.

    A name defined in an `except ImportError:` fallback or behind a version
    check is as importable as one defined at the top level.
    """
    statements = []
    for node in body:
        statements.append(node)
        if isinstance(node, ast.If):
            statements += _reachable_statements(node.body + node.orelse)
        elif isinstance(node, ast.Try):
            handled = [statement for handler in node.handlers for statement in handler.body]
            statements += _reachable_statements(node.body + node.orelse + node.finalbody + handled)
    return statements


def _top_level_symbols(module_file: Path) -> set[str] | None:
    """Names a module defines or imports - everything frappe's get_attr() could find.

    None means a `from x import *` hides them, so nothing can be concluded.
    """
    symbols = set()
    for node in _reachable_statements(ast.parse(module_file.read_text()).body):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    return None
                symbols.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.Assign):
            symbols.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            symbols.add(node.target.id)
    return symbols
