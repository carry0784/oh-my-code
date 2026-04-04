"""
CR-048 RI-1 Purity Guard
================================
Verifies that all Pure Zone files contain no forbidden imports,
async patterns, side-effects, or runtime dependencies.

Pure Zone files:
  - app/services/sector_rotator.py
  - app/services/data_provider.py
  - app/services/symbol_screener.py
  - app/services/backtest_qualification.py
  - app/services/asset_validators.py
  - app/core/constitution.py
  - app/services/screening_transform.py
  - app/services/screening_qualification_pipeline.py
  - app/services/universe_manager.py
  - app/services/pipeline_shadow_runner.py
"""

import ast
import pathlib
import pytest

# ---------------------------------------------------------------------------
# Registry of files under purity guard
# ---------------------------------------------------------------------------

_PURE_ZONE_FILES = [
    pathlib.Path("app/services/sector_rotator.py"),
    pathlib.Path("app/services/data_provider.py"),
    pathlib.Path("app/services/symbol_screener.py"),
    pathlib.Path("app/services/backtest_qualification.py"),
    pathlib.Path("app/services/asset_validators.py"),
    pathlib.Path("app/core/constitution.py"),
    pathlib.Path("app/services/screening_transform.py"),
    pathlib.Path("app/services/screening_qualification_pipeline.py"),
    pathlib.Path("app/services/universe_manager.py"),
    pathlib.Path("app/services/pipeline_shadow_runner.py"),
]

# ---------------------------------------------------------------------------
# Forbidden module roots (top-level name or dotted prefix)
# ---------------------------------------------------------------------------

_FORBIDDEN_MODULES = [
    "asyncio",
    "sqlalchemy",
    "httpx",
    "requests",
    "aiohttp",
    "celery",
    "redis",
    "os",
    "dotenv",
    "socket",
    "urllib",
    "subprocess",
    "shutil",
    "tempfile",
]

_FORBIDDEN_SERVICE_IMPORTS = [
    "app.services.regime_detector",
    "app.services.asset_service",
    "app.services.registry_service",
    "app.services.injection_gateway",
    "app.services.runtime_strategy_loader",
]

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _read_source(path: pathlib.Path):
    """Return (source_text, ast_tree) for the given path.

    Raises FileNotFoundError if the file does not exist so individual
    tests get a clear failure rather than a confusing AttributeError.
    """
    if not path.exists():
        raise FileNotFoundError(f"Pure Zone file not found: {path}")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    return source, tree


def _collect_imports(tree: ast.AST) -> list:
    """Return a list of (module, names) tuples for every import statement.

    - import foo -> ("foo", [])
    - from foo import bar, baz -> ("foo", ["bar", "baz"])
    - from foo.bar import x -> ("foo.bar", ["x"])
    """
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                results.append((alias.name, []))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            results.append((module, names))
    return results


def _collect_async_defs(tree: ast.AST) -> list:
    """Return a list of AsyncFunctionDef node objects (not just names)."""
    return [node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)]


def _collect_decorators(tree: ast.AST) -> list:
    """Return a flat list of decorator name strings found anywhere in the tree.

    Handles simple names (@task), attributes (@app.task), and
    calls (@shared_task()).
    """
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                results.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                parts = []
                cur = dec
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr)
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    parts.append(cur.id)
                results.append(".".join(reversed(parts)))
            elif isinstance(dec, ast.Call):
                func = dec.func
                if isinstance(func, ast.Name):
                    results.append(func.id)
                elif isinstance(func, ast.Attribute):
                    parts = []
                    cur = func
                    while isinstance(cur, ast.Attribute):
                        parts.append(cur.attr)
                        cur = cur.value
                    if isinstance(cur, ast.Name):
                        parts.append(cur.id)
                    results.append(".".join(reversed(parts)))
    return results


def _async_body_is_stub(func_node: ast.AsyncFunctionDef) -> bool:
    """Return True when the async function body is a pure stub.

    An acceptable stub body is one of:
      1. A single ... expression.
      2. A docstring (ast.Constant str) followed by a ... expression.
      3. A pass statement (treated equivalent to ...).
      4. A docstring followed by a pass statement.
    """
    body = func_node.body

    def _is_ellipsis(stmt) -> bool:
        return (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and stmt.value.value is ...
        )

    def _is_pass(stmt) -> bool:
        return isinstance(stmt, ast.Pass)

    def _is_docstring(stmt) -> bool:
        return (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        )

    if len(body) == 1:
        return _is_ellipsis(body[0]) or _is_pass(body[0])
    if len(body) == 2 and _is_docstring(body[0]):
        return _is_ellipsis(body[1]) or _is_pass(body[1])
    return False


def _module_is_forbidden(module: str, forbidden: str) -> bool:
    """Return True if module matches or is a sub-module of forbidden."""
    return module == forbidden or module.startswith(forbidden + ".")


# ── Parametrized checks applied to every Pure Zone file ──────────────

_SIDE_EFFECT_STRINGS = [
    "open(",
    "os.environ",
    "os.getenv",
    "beat_schedule",
]

_SESSION_STRINGS = [
    ".add(",
    ".flush(",
    ".commit(",
    ".execute(",
]

_FORBIDDEN_DECORATORS = [
    "app.task",
    "shared_task",
    "celery_app.task",
]


def _run_forbidden_import_check(path, forbidden_modules, forbidden_services):
    """Common forbidden-import check for a Pure Zone file."""
    _, tree = _read_source(path)
    imports = _collect_imports(tree)
    for mod, _ in imports:
        for fm in forbidden_modules:
            assert not _module_is_forbidden(mod, fm), (
                f"{path}: forbidden import '{fm}' found (via '{mod}')"
            )
        for fs in forbidden_services:
            assert not _module_is_forbidden(mod, fs), (
                f"{path}: forbidden service import '{fs}' found (via '{mod}')"
            )


def _run_side_effect_check(path):
    """Common side-effect string check for a Pure Zone file."""
    src, _ = _read_source(path)
    for pattern in _SIDE_EFFECT_STRINGS:
        assert pattern not in src, f"{path}: forbidden side-effect pattern '{pattern}' found"


def _run_decorator_check(path):
    """Common forbidden-decorator check for a Pure Zone file."""
    _, tree = _read_source(path)
    decorators = _collect_decorators(tree)
    for dec in decorators:
        for fd in _FORBIDDEN_DECORATORS:
            assert fd not in dec, f"{path}: forbidden decorator '{fd}' found in '{dec}'"


# ═══════════════════════════════════════════════════════════════════════
# Test Classes — one per Pure Zone file
# ═══════════════════════════════════════════════════════════════════════


class TestSectorRotatorPurity:
    _PATH = pathlib.Path("app/services/sector_rotator.py")

    def test_no_forbidden_imports(self):
        _run_forbidden_import_check(self._PATH, _FORBIDDEN_MODULES, _FORBIDDEN_SERVICE_IMPORTS)

    def test_no_async_functions(self):
        _, tree = _read_source(self._PATH)
        async_defs = _collect_async_defs(tree)
        assert len(async_defs) == 0, (
            f"sector_rotator.py has async functions: {[n.name for n in async_defs]}"
        )

    def test_no_await_keyword(self):
        src, _ = _read_source(self._PATH)
        assert "await " not in src

    def test_no_side_effects(self):
        _run_side_effect_check(self._PATH)

    def test_no_session_operations(self):
        src, _ = _read_source(self._PATH)
        for pat in _SESSION_STRINGS:
            assert pat not in src, f"sector_rotator.py: '{pat}' found"

    def test_no_forbidden_decorators(self):
        _run_decorator_check(self._PATH)

    def test_no_asyncio_import(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "asyncio")

    def test_no_network_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for net in ["httpx", "requests", "aiohttp", "socket", "urllib"]:
                assert not _module_is_forbidden(mod, net)

    def test_no_regime_detector_import(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "app.services.regime_detector")

    def test_no_file_operations(self):
        src, _ = _read_source(self._PATH)
        assert "open(" not in src
        # Path() is allowed for imports but not for read_text/write_text
        if "Path(" in src:
            assert ".read_text" not in src
            assert ".write_text" not in src

    def test_no_subprocess(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "subprocess")

    def test_all_functions_are_sync(self):
        """Every def in sector_rotator.py must be sync (not async)."""
        _, tree = _read_source(self._PATH)
        for node in ast.walk(tree):
            assert not isinstance(node, ast.AsyncFunctionDef), (
                f"sector_rotator.py: async function '{node.name}' found"
                if isinstance(node, ast.AsyncFunctionDef)
                else ""
            )


class TestDataProviderPurity:
    _PATH = pathlib.Path("app/services/data_provider.py")

    def test_no_forbidden_imports(self):
        _run_forbidden_import_check(self._PATH, _FORBIDDEN_MODULES, _FORBIDDEN_SERVICE_IMPORTS)

    def test_async_defs_are_stubs_only(self):
        """data_provider.py may have async def but ONLY as abstract stubs."""
        _, tree = _read_source(self._PATH)
        async_defs = _collect_async_defs(tree)
        for func_node in async_defs:
            assert _async_body_is_stub(func_node), (
                f"data_provider.py: async function '{func_node.name}' has "
                f"implementation code (not a stub)"
            )

    def test_no_await_keyword_outside_stubs(self):
        src, _ = _read_source(self._PATH)
        # 'await' should not appear in data_provider.py at all
        # (abstract stubs use ... not await)
        assert "await " not in src

    def test_no_side_effects(self):
        _run_side_effect_check(self._PATH)

    def test_no_session_operations(self):
        src, _ = _read_source(self._PATH)
        for pat in _SESSION_STRINGS:
            assert pat not in src, f"data_provider.py: '{pat}' found"

    def test_no_forbidden_decorators(self):
        _run_decorator_check(self._PATH)

    def test_no_network_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for net in ["httpx", "requests", "aiohttp", "socket", "urllib"]:
                assert not _module_is_forbidden(mod, net)

    def test_no_sqlalchemy(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "sqlalchemy")

    def test_no_celery(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "celery")

    def test_no_os_import(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "os")

    def test_no_file_operations(self):
        src, _ = _read_source(self._PATH)
        assert "open(" not in src

    def test_no_runtime_service_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for fs in _FORBIDDEN_SERVICE_IMPORTS:
                assert not _module_is_forbidden(mod, fs)


class TestSymbolScreenerPurity:
    _PATH = pathlib.Path("app/services/symbol_screener.py")

    def test_no_forbidden_imports(self):
        _run_forbidden_import_check(self._PATH, _FORBIDDEN_MODULES, _FORBIDDEN_SERVICE_IMPORTS)

    def test_no_async_functions(self):
        _, tree = _read_source(self._PATH)
        async_defs = _collect_async_defs(tree)
        assert len(async_defs) == 0, (
            f"symbol_screener.py has async functions: {[n.name for n in async_defs]}"
        )

    def test_no_await_keyword(self):
        src, _ = _read_source(self._PATH)
        assert "await " not in src

    def test_no_side_effects(self):
        _run_side_effect_check(self._PATH)

    def test_no_session_operations(self):
        src, _ = _read_source(self._PATH)
        for pat in _SESSION_STRINGS:
            assert pat not in src, f"symbol_screener.py: '{pat}' found"

    def test_no_forbidden_decorators(self):
        _run_decorator_check(self._PATH)

    def test_no_network_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for net in ["httpx", "requests", "aiohttp", "socket", "urllib"]:
                assert not _module_is_forbidden(mod, net)

    def test_no_sqlalchemy(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "sqlalchemy")

    def test_no_celery(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "celery")

    def test_no_regime_detector(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "app.services.regime_detector")

    def test_all_functions_are_sync(self):
        _, tree = _read_source(self._PATH)
        for node in ast.walk(tree):
            assert not isinstance(node, ast.AsyncFunctionDef), (
                f"symbol_screener.py: async function found"
            )

    def test_no_subprocess(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "subprocess")


class TestBacktestQualifierPurity:
    _PATH = pathlib.Path("app/services/backtest_qualification.py")

    def test_no_forbidden_imports(self):
        _run_forbidden_import_check(self._PATH, _FORBIDDEN_MODULES, _FORBIDDEN_SERVICE_IMPORTS)

    def test_no_async_functions(self):
        _, tree = _read_source(self._PATH)
        async_defs = _collect_async_defs(tree)
        assert len(async_defs) == 0

    def test_no_await_keyword(self):
        src, _ = _read_source(self._PATH)
        assert "await " not in src

    def test_no_side_effects(self):
        _run_side_effect_check(self._PATH)

    def test_no_session_operations(self):
        src, _ = _read_source(self._PATH)
        for pat in _SESSION_STRINGS:
            assert pat not in src

    def test_no_forbidden_decorators(self):
        _run_decorator_check(self._PATH)

    def test_no_network_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for net in ["httpx", "requests", "aiohttp", "socket", "urllib"]:
                assert not _module_is_forbidden(mod, net)

    def test_no_sqlalchemy(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "sqlalchemy")

    def test_no_celery(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "celery")

    def test_all_functions_are_sync(self):
        _, tree = _read_source(self._PATH)
        for node in ast.walk(tree):
            assert not isinstance(node, ast.AsyncFunctionDef)

    def test_no_file_operations(self):
        src, _ = _read_source(self._PATH)
        assert "open(" not in src

    def test_no_subprocess(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "subprocess")


class TestAssetValidatorsPurity:
    _PATH = pathlib.Path("app/services/asset_validators.py")

    def test_no_forbidden_imports(self):
        _run_forbidden_import_check(self._PATH, _FORBIDDEN_MODULES, _FORBIDDEN_SERVICE_IMPORTS)

    def test_no_async_functions(self):
        _, tree = _read_source(self._PATH)
        async_defs = _collect_async_defs(tree)
        assert len(async_defs) == 0

    def test_no_await_keyword(self):
        src, _ = _read_source(self._PATH)
        assert "await " not in src

    def test_no_side_effects(self):
        _run_side_effect_check(self._PATH)

    def test_no_session_operations(self):
        src, _ = _read_source(self._PATH)
        for pat in _SESSION_STRINGS:
            assert pat not in src

    def test_no_forbidden_decorators(self):
        _run_decorator_check(self._PATH)

    def test_no_network_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for net in ["httpx", "requests", "aiohttp", "socket", "urllib"]:
                assert not _module_is_forbidden(mod, net)

    def test_no_sqlalchemy(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "sqlalchemy")

    def test_no_celery(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "celery")

    def test_all_functions_are_sync(self):
        _, tree = _read_source(self._PATH)
        for node in ast.walk(tree):
            assert not isinstance(node, ast.AsyncFunctionDef)

    def test_no_subprocess(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "subprocess")


class TestConstitutionPurity:
    _PATH = pathlib.Path("app/core/constitution.py")

    def test_no_forbidden_imports(self):
        _run_forbidden_import_check(self._PATH, _FORBIDDEN_MODULES, _FORBIDDEN_SERVICE_IMPORTS)

    def test_no_async_functions(self):
        _, tree = _read_source(self._PATH)
        async_defs = _collect_async_defs(tree)
        assert len(async_defs) == 0

    def test_no_await_keyword(self):
        src, _ = _read_source(self._PATH)
        assert "await " not in src

    def test_no_side_effects(self):
        _run_side_effect_check(self._PATH)

    def test_no_session_operations(self):
        src, _ = _read_source(self._PATH)
        for pat in _SESSION_STRINGS:
            assert pat not in src

    def test_no_forbidden_decorators(self):
        _run_decorator_check(self._PATH)

    def test_no_network_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for net in ["httpx", "requests", "aiohttp", "socket", "urllib"]:
                assert not _module_is_forbidden(mod, net)

    def test_no_sqlalchemy(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "sqlalchemy")

    def test_no_runtime_service_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for fs in _FORBIDDEN_SERVICE_IMPORTS:
                assert not _module_is_forbidden(mod, fs)

    def test_no_subprocess(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "subprocess")


class TestScreeningTransformPurity:
    _PATH = pathlib.Path("app/services/screening_transform.py")

    def test_no_forbidden_imports(self):
        _run_forbidden_import_check(self._PATH, _FORBIDDEN_MODULES, _FORBIDDEN_SERVICE_IMPORTS)

    def test_no_async_functions(self):
        _, tree = _read_source(self._PATH)
        async_defs = _collect_async_defs(tree)
        assert len(async_defs) == 0, (
            f"screening_transform.py has async functions: {[n.name for n in async_defs]}"
        )

    def test_no_await_keyword(self):
        src, _ = _read_source(self._PATH)
        assert "await " not in src

    def test_no_side_effects(self):
        _run_side_effect_check(self._PATH)

    def test_no_session_operations(self):
        src, _ = _read_source(self._PATH)
        for pat in _SESSION_STRINGS:
            assert pat not in src, f"screening_transform.py: '{pat}' found"

    def test_no_forbidden_decorators(self):
        _run_decorator_check(self._PATH)

    def test_no_network_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for net in ["httpx", "requests", "aiohttp", "socket", "urllib"]:
                assert not _module_is_forbidden(mod, net)

    def test_no_sqlalchemy(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "sqlalchemy")

    def test_no_celery(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "celery")

    def test_all_functions_are_sync(self):
        _, tree = _read_source(self._PATH)
        for node in ast.walk(tree):
            assert not isinstance(node, ast.AsyncFunctionDef), (
                f"screening_transform.py: async function found"
            )

    def test_no_file_operations(self):
        src, _ = _read_source(self._PATH)
        assert "open(" not in src

    def test_no_subprocess(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "subprocess")


class TestScreeningQualificationPipelinePurity:
    _PATH = pathlib.Path("app/services/screening_qualification_pipeline.py")

    def test_no_forbidden_imports(self):
        _run_forbidden_import_check(self._PATH, _FORBIDDEN_MODULES, _FORBIDDEN_SERVICE_IMPORTS)

    def test_no_async_functions(self):
        _, tree = _read_source(self._PATH)
        async_defs = _collect_async_defs(tree)
        assert len(async_defs) == 0, (
            f"screening_qualification_pipeline.py has async functions: "
            f"{[n.name for n in async_defs]}"
        )

    def test_no_await_keyword(self):
        src, _ = _read_source(self._PATH)
        assert "await " not in src

    def test_no_side_effects(self):
        _run_side_effect_check(self._PATH)

    def test_no_session_operations(self):
        src, _ = _read_source(self._PATH)
        for pat in _SESSION_STRINGS:
            assert pat not in src, f"screening_qualification_pipeline.py: '{pat}' found"

    def test_no_forbidden_decorators(self):
        _run_decorator_check(self._PATH)

    def test_no_network_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for net in ["httpx", "requests", "aiohttp", "socket", "urllib"]:
                assert not _module_is_forbidden(mod, net)

    def test_no_sqlalchemy(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "sqlalchemy")

    def test_no_celery(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "celery")

    def test_all_functions_are_sync(self):
        _, tree = _read_source(self._PATH)
        for node in ast.walk(tree):
            assert not isinstance(node, ast.AsyncFunctionDef), (
                f"screening_qualification_pipeline.py: async function found"
            )

    def test_no_file_operations(self):
        src, _ = _read_source(self._PATH)
        assert "open(" not in src

    def test_no_subprocess(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "subprocess")


class TestUniverseManagerPurity:
    _PATH = pathlib.Path("app/services/universe_manager.py")

    def test_no_forbidden_imports(self):
        _run_forbidden_import_check(self._PATH, _FORBIDDEN_MODULES, _FORBIDDEN_SERVICE_IMPORTS)

    def test_no_async_functions(self):
        _, tree = _read_source(self._PATH)
        async_defs = _collect_async_defs(tree)
        assert len(async_defs) == 0, (
            f"universe_manager.py has async functions: {[n.name for n in async_defs]}"
        )

    def test_no_await_keyword(self):
        src, _ = _read_source(self._PATH)
        assert "await " not in src

    def test_no_side_effects(self):
        _run_side_effect_check(self._PATH)

    def test_no_session_operations(self):
        src, _ = _read_source(self._PATH)
        for pat in _SESSION_STRINGS:
            assert pat not in src, f"universe_manager.py: '{pat}' found"

    def test_no_forbidden_decorators(self):
        _run_decorator_check(self._PATH)

    def test_no_network_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for net in ["httpx", "requests", "aiohttp", "socket", "urllib"]:
                assert not _module_is_forbidden(mod, net)

    def test_no_sqlalchemy(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "sqlalchemy")

    def test_no_celery(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "celery")

    def test_all_functions_are_sync(self):
        _, tree = _read_source(self._PATH)
        for node in ast.walk(tree):
            assert not isinstance(node, ast.AsyncFunctionDef), (
                f"universe_manager.py: async function found"
            )

    def test_no_file_operations(self):
        src, _ = _read_source(self._PATH)
        assert "open(" not in src

    def test_no_subprocess(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "subprocess")


class TestPipelineShadowRunnerPurity:
    _PATH = pathlib.Path("app/services/pipeline_shadow_runner.py")

    def test_no_forbidden_imports(self):
        _run_forbidden_import_check(self._PATH, _FORBIDDEN_MODULES, _FORBIDDEN_SERVICE_IMPORTS)

    def test_no_async_functions(self):
        _, tree = _read_source(self._PATH)
        async_defs = _collect_async_defs(tree)
        assert len(async_defs) == 0, (
            f"pipeline_shadow_runner.py has async functions: {[n.name for n in async_defs]}"
        )

    def test_no_await_keyword(self):
        src, _ = _read_source(self._PATH)
        assert "await " not in src

    def test_no_side_effects(self):
        _run_side_effect_check(self._PATH)

    def test_no_session_operations(self):
        src, _ = _read_source(self._PATH)
        for pat in _SESSION_STRINGS:
            assert pat not in src, f"pipeline_shadow_runner.py: '{pat}' found"

    def test_no_forbidden_decorators(self):
        _run_decorator_check(self._PATH)

    def test_no_network_imports(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            for net in ["httpx", "requests", "aiohttp", "socket", "urllib"]:
                assert not _module_is_forbidden(mod, net)

    def test_no_sqlalchemy(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "sqlalchemy")

    def test_no_celery(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "celery")

    def test_all_functions_are_sync(self):
        _, tree = _read_source(self._PATH)
        for node in ast.walk(tree):
            assert not isinstance(node, ast.AsyncFunctionDef), (
                f"pipeline_shadow_runner.py: async function found"
            )

    def test_no_file_operations(self):
        src, _ = _read_source(self._PATH)
        assert "open(" not in src

    def test_no_subprocess(self):
        _, tree = _read_source(self._PATH)
        imports = _collect_imports(tree)
        for mod, _ in imports:
            assert not _module_is_forbidden(mod, "subprocess")
