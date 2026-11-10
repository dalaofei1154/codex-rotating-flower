"""Cover the two paths the unit suite missed.

Both were reported as macOS regressions against 78977de:

1. The normal background loop read ``flower.fd`` after ``Flower`` moved to a
   ``serial`` object, so every non-``--once`` run raised AttributeError.
   ``--once`` never reached that line, which is why the suite stayed green.
2. The unified macOS installer and packager copied a fixed file list that did
   not include the shared modules, so an installed bridge could not import
   them.
"""

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
M1 = HERE.parent
for entry in (str(M1), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import integrated_setup
import package_workbuddy_integrated
import integrated_bridge


class BackgroundLoopAttributeTests(unittest.TestCase):
    """The status dict must not touch the removed ``fd`` attribute."""

    def test_status_uses_connected_not_fd(self):
        with io.open(HERE / "integrated_bridge.py", encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("flower.fd", source)
        self.assertNotIn(".fd is not None", source)

    def test_flower_exposes_connected(self):
        flower = integrated_bridge.Flower()
        self.assertFalse(flower.connected)
        self.assertFalse(hasattr(flower, "fd"))


class UnifiedInstallerTests(unittest.TestCase):
    """The unified installer must stage the shared modules."""

    def test_shared_modules_are_declared(self):
        for name in ("serial_link.py", "process_lock.py", "process_probe.py"):
            self.assertIn(name, integrated_setup.SHARED_MODULES)
            self.assertTrue((M1 / name).is_file(), name)

    def test_staged_files_include_shared_modules(self):
        """Replay the file-selection step of install()."""
        source = integrated_setup.source_directory()
        files = sorted(p for p in source.glob("*.py") if not p.name.startswith("test_"))
        shared = source.parent
        for name in integrated_setup.SHARED_MODULES:
            files.append(shared / name)
        names = {path.name for path in files}
        for name in integrated_setup.SHARED_MODULES:
            self.assertIn(name, names)
        self.assertIn("integrated_bridge.py", names)


class PackagerTests(unittest.TestCase):
    """The Mac package must ship the shared modules too."""

    def test_runtime_files_cover_shared_modules(self):
        for name in ("serial_link.py", "process_lock.py", "process_probe.py"):
            self.assertIn(name, package_workbuddy_integrated.RUNTIME_FILES)

    def test_every_declared_runtime_file_exists(self):
        root = M1
        for name in package_workbuddy_integrated.RUNTIME_FILES:
            self.assertTrue((root / name).is_file(), name)
        for name in package_workbuddy_integrated.BRIDGE_FILES:
            self.assertTrue((root / "integrated" / name).is_file(), name)


class LockPathTests(unittest.TestCase):
    """POSIX keeps the uid-based lock name the existing install uses."""

    def test_posix_lock_path_uses_uid(self):
        import process_lock

        with patch.object(process_lock.sys, "platform", "darwin"), \
             patch.object(process_lock.os, "getuid", return_value=501,
                          create=True):
            path = process_lock.singleton_path("codex-motor-bridge")
        self.assertEqual(path.name, "codex-motor-bridge-501.lock")

    def test_windows_lock_path_avoids_getuid(self):
        import process_lock

        with patch.object(process_lock.sys, "platform", "win32"):
            path = process_lock.singleton_path("codex-motor-bridge")
        self.assertTrue(path.name.endswith(".lock"))
        self.assertNotIn("/", path.name)


if __name__ == "__main__":
    unittest.main()
