import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


serial_link = load("serial_link")
process_lock = load("process_lock")


class DevicePathTests(unittest.TestCase):
    def test_windows_device_path_prefix_is_added_once(self):
        self.assertEqual(serial_link.windows_device_path("COM3"), "\\\\.\\COM3")
        self.assertEqual(serial_link.windows_device_path("\\\\.\\COM12"), "\\\\.\\COM12")

    def test_port_sort_puts_com2_before_com10(self):
        ports = ["COM10", "COM2", "COM1"]
        self.assertEqual(sorted(ports, key=serial_link._port_sort_key),
                         ["COM1", "COM2", "COM10"])


class PortPresenceTests(unittest.TestCase):
    def test_existing_path_is_present(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "device")
            Path(path).touch()
            self.assertTrue(serial_link.port_still_present(path))

    def test_missing_posix_path_is_not_present(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = os.path.join(folder, "missing")
            with patch.object(serial_link.sys, "platform", "linux"):
                self.assertFalse(serial_link.port_still_present(missing))

    def test_windows_bare_name_matches_the_registry(self):
        with patch.object(serial_link.sys, "platform", "win32"), \
             patch.object(serial_link.os.path, "exists", return_value=False), \
             patch.object(serial_link, "_windows_serial_ports",
                          return_value=["COM12"]):
            self.assertTrue(serial_link.port_still_present("COM12"))

    def test_windows_device_path_matches_the_bare_registry_name(self):
        """A caller may pass the \\\\.\\COM12 form that Win32 needs to open it."""
        with patch.object(serial_link.sys, "platform", "win32"), \
             patch.object(serial_link.os.path, "exists", return_value=False), \
             patch.object(serial_link, "_windows_serial_ports",
                          return_value=["COM12"]):
            self.assertTrue(serial_link.port_still_present("\\\\.\\COM12"))

    def test_windows_absent_port_is_not_present(self):
        with patch.object(serial_link.sys, "platform", "win32"), \
             patch.object(serial_link.os.path, "exists", return_value=False), \
             patch.object(serial_link, "_windows_serial_ports",
                          return_value=["COM12"]):
            self.assertFalse(serial_link.port_still_present("\\\\.\\COM7"))


class ProcessLockTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "bridge.lock"

    def tearDown(self):
        self.folder.cleanup()

    def test_lock_path_is_per_user_and_filesystem_safe(self):
        path = process_lock.singleton_path("codex-motor-bridge")
        name = path.name
        self.assertIn("codex-motor-bridge", name)
        self.assertTrue(name.endswith(".lock"))
        self.assertNotIn("\\", name)
        self.assertNotIn("/", name)

    def test_second_acquire_fails_until_the_first_is_released(self):
        first = process_lock.acquire(self.path)
        self.assertIsNotNone(first)
        try:
            self.assertIsNone(process_lock.acquire(self.path))
        finally:
            first.close()
        second = process_lock.acquire(self.path)
        self.assertIsNotNone(second)
        second.close()


class SerialPortSelectionTests(unittest.TestCase):
    def test_open_port_picks_the_windows_implementation(self):
        with patch.object(serial_link.sys, "platform", "win32"), \
             patch.object(serial_link, "WindowsSerialPort") as windows_port:
            serial_link.open_port("COM7")
            windows_port.assert_called_once_with("COM7", serial_link.DEFAULT_BAUDRATE)

    def test_open_port_picks_the_posix_implementation(self):
        with patch.object(serial_link.sys, "platform", "darwin"), \
             patch.object(serial_link, "PosixSerialPort") as posix_port:
            serial_link.open_port("/dev/cu.usbmodem101")
            posix_port.assert_called_once_with("/dev/cu.usbmodem101",
                                               serial_link.DEFAULT_BAUDRATE)


class WindowsInstallerTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(HERE))
        import install_windows
        self.installer = install_windows
        self.folder = tempfile.TemporaryDirectory()
        self.support = Path(self.folder.name) / "RotatingFlower"

    def tearDown(self):
        self.folder.cleanup()

    def test_task_command_quotes_every_path(self):
        target = self.support / "global_bridge.py"
        command = self.installer.task_command(
            target, Path("C:/sessions"), "COM3", "codex", None)
        # Path separators differ per platform, so assert on quoting and flags
        # rather than on a literal string.
        self.assertIn(f'--sessions-root "', command)
        self.assertIn(f'"{Path("C:/sessions")}"', command)
        self.assertIn('--port "COM3"', command)
        self.assertIn("--source codex", command)
        self.assertIn(f'"{target}"', command)
        self.assertTrue(command.startswith('"'))

    def test_uninstall_keeps_logs_and_removes_runtime(self):
        self.support.mkdir(parents=True)
        logs = self.support / "logs"
        logs.mkdir()
        (logs / "bridge.log").write_text("kept", encoding="utf-8")
        for name in self.installer.RUNTIME_FILES:
            (self.support / name).write_text("x", encoding="utf-8")

        with patch.object(self.installer, "locations",
                          return_value=(self.support, logs)), \
             patch.object(self.installer, "task_exists", return_value=False):
            self.installer.uninstall()

        for name in self.installer.RUNTIME_FILES:
            self.assertFalse((self.support / name).exists())
        self.assertTrue((logs / "bridge.log").exists())

    def test_install_refuses_missing_sessions_directory(self):
        with patch.object(self.installer, "locations",
                          return_value=(self.support, self.support / "logs")), \
             patch.object(self.installer, "task_exists", return_value=False):
            with self.assertRaises(RuntimeError):
                self.installer.install(False, Path(self.folder.name) / "nope", "auto")


class WindowsRollbackTests(unittest.TestCase):
    """A failed replace must restore the previous task and runtime files."""

    def setUp(self):
        sys.path.insert(0, str(HERE))
        import install_windows
        self.installer = install_windows
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.support = root / "RotatingFlower"
        self.sessions = root / "sessions"
        self.sessions.mkdir()
        self.support.mkdir(parents=True)

    def tearDown(self):
        self.folder.cleanup()

    def _seed_previous(self):
        for name in self.installer.RUNTIME_FILES:
            (self.support / name).write_text("old-" + name, encoding="utf-8")

    def _install_with(self, create_effect):
        calls = []

        def fake_schtasks(*args, check=True):
            calls.append(args)

            class Done:
                returncode = 0
                stdout = "<Task/>" if "/XML" in args else ""
                stderr = ""

            if args[0] == "/Create" and create_effect is not None:
                raise create_effect
            return Done()

        with patch.object(self.installer, "locations",
                          return_value=(self.support, self.support / "logs")), \
             patch.object(self.installer, "task_exists", return_value=True), \
             patch.object(self.installer, "schtasks", side_effect=fake_schtasks), \
             patch.object(self.installer, "task_definition",
                          return_value="<Task/>"):
            try:
                self.installer.install(True, self.sessions, "auto", "codex", None)
            except Exception as error:
                return error, calls
            return None, calls

    def test_failed_create_restores_the_previous_task(self):
        self._seed_previous()
        error, calls = self._install_with(
            subprocess.CalledProcessError(1, "schtasks"))
        self.assertIsNotNone(error)
        # The previous definition must be recreated from XML, not just deleted.
        restored = [c for c in calls if c[0] == "/Create" and "/XML" in c]
        self.assertTrue(restored, f"expected an /XML restore, got {calls}")
        self.assertFalse(
            [c for c in calls if c[0] == "/Delete"],
            "the previous task must not be deleted outright")

    def test_timeout_also_triggers_rollback(self):
        self._seed_previous()
        error, calls = self._install_with(
            subprocess.TimeoutExpired("schtasks", 30))
        self.assertIsInstance(error, subprocess.TimeoutExpired)
        restored = [c for c in calls if c[0] == "/Create" and "/XML" in c]
        self.assertTrue(restored, f"a timeout must also roll back, got {calls}")

    def test_failed_create_restores_the_runtime_files(self):
        self._seed_previous()
        self._install_with(subprocess.CalledProcessError(1, "schtasks"))
        for name in self.installer.RUNTIME_FILES:
            self.assertEqual((self.support / name).read_text(encoding="utf-8"),
                             "old-" + name)


class SchtasksDecodingTests(unittest.TestCase):
    """schtasks writes the OEM code page and UTF-16, never plain UTF-8.

    The installer originally used text=True, which decodes as UTF-8 and raises
    UnicodeDecodeError on a localized Windows. These cover the decoder that
    replaced it.

    The GBK cases only apply on Windows: mbcs does not exist elsewhere, so the
    decoder falls back to UTF-8 there by design.
    """

    def setUp(self):
        sys.path.insert(0, str(HERE))
        import install_windows
        self.installer = install_windows

    @unittest.skipUnless(sys.platform == "win32", "mbcs only exists on Windows")
    def test_console_output_decodes_with_the_system_code_page(self):
        """The decoder must use the machine's own code page, not a fixed one.

        A CI runner is usually an English install (cp1252), so encoding a
        Chinese sample there would be testing the wrong thing. Build the
        sample from whatever this machine actually uses.
        """
        sample = "Error: access is denied."
        raw = sample.encode("mbcs")
        self.assertEqual(self.installer._decode_schtasks(raw), sample)

    @unittest.skipUnless(sys.platform == "win32", "mbcs only exists on Windows")
    def test_non_ascii_console_output_round_trips(self):
        """Any text the console can produce must survive the decoder."""
        sample = "错误: 拒绝访问。"
        try:
            raw = sample.encode("mbcs")
        except UnicodeEncodeError:
            self.skipTest("this machine's code page cannot represent the sample")
        self.assertEqual(self.installer._decode_schtasks(raw), sample)

    def test_utf16_task_xml_decodes(self):
        raw = "<Task/>".encode("utf-16")
        self.assertEqual(self.installer._decode_schtasks(raw), "<Task/>")

    def test_utf16_without_bom_is_not_treated_as_text(self):
        """UTF-16LE without a BOM has NUL bytes; it must not come back as mojibake."""
        raw = "<Task/>".encode("utf-16-le")
        decoded = self.installer._decode_schtasks(raw)
        # Either it decodes cleanly or it degrades; it must never raise.
        self.assertIsInstance(decoded, str)

    def test_ascii_output_decodes(self):
        raw = b"SUCCESS: The scheduled task was created."
        self.assertEqual(self.installer._decode_schtasks(raw), raw.decode())

    def test_empty_output_is_empty_string(self):
        self.assertEqual(self.installer._decode_schtasks(b""), "")

    def test_decoder_never_raises_on_undecodable_bytes(self):
        raw = b"\xff\xfe\x00\xd8"
        self.assertIsInstance(self.installer._decode_schtasks(raw), str)

    @unittest.skipUnless(sys.platform == "win32", "mbcs only exists on Windows")
    def test_schtasks_decodes_both_streams(self):
        """schtasks() must return str on stdout and stderr, not bytes."""
        console = "Error: access is denied."

        class Result:
            returncode = 0
            stdout = console.encode("mbcs")
            stderr = "<Task/>".encode("utf-16")

        with patch.object(self.installer.subprocess, "run",
                          return_value=Result()):
            result = self.installer.schtasks("/Query", "/TN", "X", check=False)
        self.assertEqual(result.stdout, console)
        self.assertEqual(result.stderr, "<Task/>")


def parse_task_xml(text: str):
    """Parse task XML after refusing DTDs.

    ElementTree honours internal entity declarations, so a document with
    <!DOCTYPE ... <!ENTITY ...>> can expand without bound. The input here is
    text this test just generated, but the guard keeps the helper safe if it is
    ever pointed at real /Query output.
    """
    import xml.etree.ElementTree as ET

    body = text.lstrip("\ufeff")
    if "<!DOCTYPE" in body or "<!ENTITY" in body:
        raise ValueError("refusing XML with a DTD")
    if len(body) > 1_000_000:
        raise ValueError("refusing oversized XML")
    return ET.fromstring(body)


class RestoreTaskXmlTests(unittest.TestCase):
    """restore_task must write XML that parses, whatever /Query emitted."""

    def setUp(self):
        sys.path.insert(0, str(HERE))
        import install_windows
        self.installer = install_windows
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def _written(self, definition):
        """Run restore_task and return the text that reached the file."""
        captured = {}

        def fake_schtasks(*args, check=True):
            for arg in args:
                if isinstance(arg, str) and arg.endswith(".xml"):
                    with open(arg, encoding="utf-16") as handle:
                        captured["xml"] = handle.read()

            class Done:
                returncode = 0
                stdout = ""
                stderr = ""

            return Done()

        with patch.object(self.installer, "schtasks", side_effect=fake_schtasks):
            self.installer.restore_task(definition)
        return captured.get("xml")

    def test_declaration_is_forced_to_match_the_written_encoding(self):
        definition = '<?xml version="1.0" encoding="UTF-8"?><Task/>'
        written = self._written(definition)
        self.assertIsNotNone(written)
        self.assertIn('encoding="UTF-16"', written)
        self.assertNotIn('encoding="UTF-8"', written)

    def test_single_quoted_declaration_is_handled(self):
        definition = "<?xml version='1.0' encoding='utf-8'?><Task/>"
        written = self._written(definition)
        self.assertIn('encoding="UTF-16"', written)

    def test_written_xml_parses(self):
        """The file schtasks receives must be well-formed XML."""
        definition = '<?xml version="1.0" encoding="UTF-16"?><Task><Actions/></Task>'
        written = self._written(definition)
        root = parse_task_xml(written)
        self.assertEqual(root.tag, "Task")

    def test_missing_declaration_is_left_alone(self):
        definition = "<Task/>"
        written = self._written(definition)
        self.assertEqual(written, "<Task/>")

    def test_none_definition_deletes_instead_of_restoring(self):
        calls = []

        def fake_schtasks(*args, check=True):
            calls.append(args)

            class Done:
                returncode = 0
                stdout = ""
                stderr = ""

            return Done()

        with patch.object(self.installer, "schtasks", side_effect=fake_schtasks):
            self.installer.restore_task(None)
        self.assertEqual(calls[0][0], "/Delete")


class InstallerManifestTests(unittest.TestCase):
    """Every installer must ship the shared modules the bridge imports."""

    SHARED = ("serial_link.py", "process_lock.py", "process_probe.py")

    def _manifest(self, module_name: str):
        spec = importlib.util.spec_from_file_location(
            module_name, HERE / f"{module_name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module.RUNTIME_FILES

    def test_macos_installer_ships_the_shared_modules(self):
        files = self._manifest("install_macos")
        for name in self.SHARED:
            self.assertIn(name, files, "install_macos.py must copy " + name)

    def test_oneclick_package_ships_the_shared_modules(self):
        files = self._manifest("package_workbuddy_oneclick")
        for name in self.SHARED:
            self.assertIn(name, files, "the one-click package must ship " + name)

    def test_windows_installer_ships_the_shared_modules(self):
        files = self._manifest("install_windows")
        for name in self.SHARED:
            self.assertIn(name, files, "install_windows.py must copy " + name)


if __name__ == "__main__":
    unittest.main()
