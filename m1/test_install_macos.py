import importlib.util
import plistlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).parent))
import install_macos as installer
import workbuddy_setup as setup


@unittest.skipUnless(sys.platform == "darwin", "macOS LaunchAgent installer tests")
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.support = self.root / "support"
        self.plist = self.root / "agents" / "flower.plist"
        self.logs = self.root / "logs"
        self.workbuddy = self.root / "workbuddy"
        self.workbuddy.mkdir()
        (self.workbuddy / "workbuddy.db").touch()
        self.locations = patch.object(installer, "locations", return_value=(self.support, self.plist, self.logs))
        self.locations.start()
        self.addCleanup(self.locations.stop)

    def test_workbuddy_only_installs_without_codex_and_uses_runtime_fallback(self):
        with patch.object(installer, "launchctl"):
            installer.install(False, self.root / "missing-codex", "auto", "workbuddy", self.workbuddy)
        arguments = plistlib.loads(self.plist.read_bytes())["ProgramArguments"]
        self.assertEqual(arguments[0], "/bin/bash")
        self.assertEqual(arguments[arguments.index("--source") + 1], "workbuddy")
        for name in installer.RUNTIME_FILES:
            self.assertTrue((self.support / name).is_file())

    def test_new_user_setup_and_uninstall_use_only_workbuddy_without_codex(self):
        # Exercise the real setup entrypoint and metadata reader against a
        # temporary first-install location, without changing HOME or launchd.
        with sqlite3.connect(self.workbuddy / "workbuddy.db") as connection:
            connection.execute("""CREATE TABLE sessions (
                id TEXT, status TEXT, updated_at INTEGER,
                transport TEXT, deleted_at INTEGER, model TEXT)""")
            connection.execute("""INSERT INTO sessions VALUES
                ('example', 'completed', 0, 'local', NULL, 'fast-model')""")
        with patch.object(setup, "app_version", return_value="5.9.3"), \
             patch.object(setup.bridge, "serial_candidates", return_value=[]), \
             patch.object(installer, "launchctl") as launchctl, \
             patch.object(setup, "verify_installation", return_value=True) as verify:
            self.assertEqual(setup.main(["install", "--workbuddy-root", str(self.workbuddy),
                                         "--verify-seconds", "12"]), 0)
            arguments = plistlib.loads(self.plist.read_bytes())["ProgramArguments"]
            self.assertEqual(arguments[arguments.index("--source") + 1], "workbuddy")
            self.assertEqual(arguments[arguments.index("--workbuddy-root") + 1], str(self.workbuddy))
            self.assertEqual(arguments[arguments.index("--port") + 1], "auto")
            verify.assert_called_once_with(0, 12)
            self.assertEqual(launchctl.call_args.args[0], "bootstrap")
            log = self.logs / "bridge.log"
            log.write_text("test install log\n")
            self.assertEqual(setup.main(["uninstall"]), 0)
            self.assertFalse(self.plist.exists())
            self.assertTrue(log.exists(), "uninstall should keep diagnostic logs")
            for name in installer.RUNTIME_FILES:
                self.assertFalse((self.support / name).exists())

    def test_failed_replacement_restores_previous_files_and_service(self):
        self.support.mkdir()
        self.plist.parent.mkdir()
        original_plist = plistlib.dumps({"Label": installer.LABEL, "ProgramArguments": ["old"]})
        self.plist.write_bytes(original_plist)
        (self.support / "global_bridge.py").write_bytes(b"old bridge")
        bootstrap_count = 0

        def launchctl(*args, **kwargs):
            nonlocal bootstrap_count
            if args[0] == "bootstrap":
                bootstrap_count += 1
                if bootstrap_count == 1:
                    raise subprocess.CalledProcessError(1, ["launchctl"])

        with patch.object(installer, "launchctl", side_effect=launchctl):
            with self.assertRaises(subprocess.CalledProcessError):
                installer.install(True, self.root / "unused", "auto", "workbuddy", self.workbuddy)
        self.assertEqual(self.plist.read_bytes(), original_plist)
        self.assertEqual((self.support / "global_bridge.py").read_bytes(), b"old bridge")
        self.assertFalse((self.support / "launch_bridge.sh").exists())
        self.assertEqual(bootstrap_count, 2)
        self.assertEqual(len(list((self.support / "backups").iterdir())), 1)

    def test_setup_keeps_existing_codex_root_and_selected_port(self):
        options = {"--source": "codex", "--sessions-root": "/custom/codex/sessions", "--port": "/dev/cu.test"}
        with patch.object(setup, "existing_options", return_value=options), \
             patch.object(setup, "app_version", return_value="5.8.3"), \
             patch.object(setup, "status", return_value=Mock(last_error=None, status_counts={"completed": 1})), \
             patch.object(installer, "install") as install:
            self.assertEqual(setup.main(["install", "--workbuddy-root", str(self.workbuddy)]), 0)
        install.assert_called_once_with(True, Path("/custom/codex/sessions"), "/dev/cu.test", "both", self.workbuddy)

    def test_removing_workbuddy_from_combined_service_keeps_codex(self):
        with patch.object(setup, "existing_options", return_value={"--source": "both", "--sessions-root": "/custom"}), \
             patch.object(installer, "install") as install, \
             patch.object(installer, "uninstall") as uninstall:
            self.assertEqual(setup.main(["uninstall"]), 0)
        install.assert_called_once_with(True, Path("/custom"), "auto", source="codex")
        uninstall.assert_not_called()

    def test_verification_rejects_old_handshake_and_disconnected_ports(self):
        self.logs.mkdir()
        log = self.logs / "bridge.log"
        log.write_text("Motor connected: /dev/cu.old\n")
        offset = log.stat().st_size
        with patch.object(setup, "service_running", return_value=True), \
             patch.object(setup.bridge, "serial_candidates", return_value=["/dev/cu.old"]):
            self.assertFalse(setup.verify_installation(offset, 0))
        with log.open("a") as file:
            file.write("Motor connected: /dev/cu.new\n")
        with patch.object(setup, "service_running", return_value=True), \
             patch.object(setup.bridge, "serial_candidates", return_value=["/dev/cu.old"]):
            self.assertFalse(setup.verify_installation(offset, 0))
        with patch.object(setup, "service_running", return_value=True), \
             patch.object(setup.bridge, "serial_candidates", return_value=["/dev/cu.new"]):
            self.assertTrue(setup.verify_installation(offset, 0))

    def test_fresh_handshake_without_running_service_does_not_pass(self):
        self.logs.mkdir()
        (self.logs / "bridge.log").write_text("Motor connected: /dev/cu.new\n")
        with patch.object(setup, "service_running", return_value=False), \
             patch.object(setup.bridge, "serial_candidates", return_value=["/dev/cu.new"]):
            self.assertFalse(setup.verify_installation(0, 0))

    def test_failed_usb_verification_reports_partial_install_exit_code(self):
        with patch.object(setup, "existing_options", return_value={}), \
             patch.object(setup, "app_version", return_value="5.8.3"), \
             patch.object(setup, "status", return_value=Mock(last_error=None, status_counts={"working": 1})), \
             patch.object(installer, "install", return_value=42), \
             patch.object(setup, "verify_installation", return_value=False) as verify:
            self.assertEqual(setup.main(["install", "--verify-seconds", "12"]), 3)
        verify.assert_called_once_with(42, 12)


if __name__ == "__main__":
    unittest.main()
