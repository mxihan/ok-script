import logging
import os
import sys
import types
import unittest

# Stub ok package
_ok_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "ok"))
_stub_ok = types.ModuleType("ok")
_stub_ok.__path__ = [_ok_dir]
_stub_ok.__package__ = "ok"
sys.modules["ok"] = _stub_ok
_ok_util = types.ModuleType("ok.util")
_ok_util.__path__ = [os.path.join(_ok_dir, "util")]
_ok_util.__package__ = "ok.util"
sys.modules["ok.util"] = _ok_util
_ml = types.ModuleType("ok.util.logger")


class _ML:
    @staticmethod
    def get_logger(name):
        return logging.getLogger(name)


_ml.Logger = _ML
sys.modules["ok.util.logger"] = _ml

from ok.sandbox.sandbox_runner import (
    SAFE_BUILTINS, BLOCKED_IMPORTS, create_restricted_builtins,
    _clear_dangerous_modules, _restricted_import, _original_import,
)


class TestBuiltinRestriction(unittest.TestCase):

    def test_safe_builtins_included(self):
        builtins = create_restricted_builtins()
        self.assertIn("print", builtins)
        self.assertIn("len", builtins)
        self.assertIn("range", builtins)
        self.assertIn("int", builtins)
        self.assertIn("Exception", builtins)

    def test_dangerous_builtins_excluded(self):
        builtins = create_restricted_builtins()
        self.assertNotIn("open", builtins)
        self.assertNotIn("exec", builtins)
        self.assertNotIn("eval", builtins)
        self.assertNotIn("compile", builtins)
        # __import__ is present but replaced with the restricted version
        self.assertIs(builtins["__import__"], _restricted_import)

    def test_blocked_imports(self):
        self.assertIn("os", BLOCKED_IMPORTS)
        self.assertIn("subprocess", BLOCKED_IMPORTS)
        self.assertIn("socket", BLOCKED_IMPORTS)
        self.assertIn("ctypes", BLOCKED_IMPORTS)
        self.assertIn("http", BLOCKED_IMPORTS)
        self.assertIn("sys", BLOCKED_IMPORTS)
        self.assertIn("importlib", BLOCKED_IMPORTS)

    def test_restricted_import_blocks_os(self):
        builtins = create_restricted_builtins()
        restricted_import = builtins["__import__"]
        with self.assertRaises(ImportError):
            restricted_import("os")

    def test_restricted_import_allows_allowed(self):
        builtins = create_restricted_builtins()
        restricted_import = builtins["__import__"]
        # math is not blocked
        import math
        result = restricted_import("math")
        self.assertEqual(result, math)

    def test_restricted_import_blocks_submodules(self):
        """Blocked top-level module should block submodule imports too."""
        builtins = create_restricted_builtins()
        restricted_import = builtins["__import__"]
        with self.assertRaises(ImportError):
            restricted_import("os.path")

    def test_restricted_import_is_not_original(self):
        """The __import__ in restricted builtins is our custom one, not the original."""
        builtins = create_restricted_builtins()
        self.assertEqual(builtins["__import__"], _restricted_import)
        self.assertIsNot(builtins["__import__"], _original_import)


class TestSysModulesCleanup(unittest.TestCase):

    def test_clear_dangerous_modules_removes_os(self):
        """Ensure _clear_dangerous_modules removes dangerous entries."""
        self.assertIn("os", sys.modules)
        import os as os_mod
        try:
            _clear_dangerous_modules()
            self.assertNotIn("os", sys.modules)
            self.assertNotIn("subprocess", sys.modules)
        finally:
            sys.modules["os"] = os_mod

    def test_clear_preserves_sandbox_modules(self):
        """Ensure sandbox infrastructure modules are NOT cleared."""
        try:
            _clear_dangerous_modules()
            # ok.sandbox modules should survive
            self.assertIn("ok.sandbox.sandbox_runner", sys.modules)
            # numpy should survive (needed for frame data)
            if "numpy" in sys.modules:
                self.assertIn("numpy", sys.modules)
        finally:
            import os
            sys.modules["os"] = os

    def test_cannot_access_os_via_sys_modules_after_clear(self):
        """After clearing, accessing sys.modules['os'] should fail."""
        import os as os_mod
        try:
            _clear_dangerous_modules()
            with self.assertRaises(KeyError):
                sys.modules["os"]
        finally:
            sys.modules["os"] = os_mod


class TestBuiltinBypass(unittest.TestCase):

    def test_cannot_get_open_via_getattr(self):
        """open should not be reachable through restricted builtins."""
        builtins = create_restricted_builtins()
        self.assertNotIn("open", builtins)

    def test_cannot_get_exec_or_eval(self):
        builtins = create_restricted_builtins()
        self.assertNotIn("exec", builtins)
        self.assertNotIn("eval", builtins)

    def test_restricted_import_is_used(self):
        """Verify the __import__ in restricted builtins is our custom one."""
        builtins = create_restricted_builtins()
        self.assertEqual(builtins["__import__"], _restricted_import)


if __name__ == "__main__":
    unittest.main()
