"""Exercise the Mac background loop and installed runtime without live services.

Task input, USB sends, signal registration and launchctl are mocked. Files and
the real singleton lock stay in temporary directories. Platform-specific
modules are imported only after unittest's macOS class guard is applied.
"""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


M1 = Path(__file__).resolve().parent


@unittest.skipUnless(sys.platform == "darwin", "macOS integrated runtime tests")
class IntegratedRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(sys, "path", [str(M1), str(M1 / "integrated"), *sys.path]):
            import integrated_bridge
            import integrated_setup
        cls.bridge = integrated_bridge
        cls.setup = integrated_setup

    def test_background_loop_writes_status_and_closes(self):
        import fcntl

        bridge = self.bridge
        with tempfile.TemporaryDirectory(prefix="flower runtime ") as folder:
            root = Path(folder)
            adapter = Mock()
            snapshot = {"healthy": True, "motor": "RUN LOW", "light": True,
                        "working_threads": ["synthetic"], "waiting_threads": [],
                        "pending_questions": 1}
            adapter.poll.return_value = snapshot
            handlers = {}

            def register_signal(number, handler):
                handlers[number] = handler

            def end_first_loop(_seconds):
                # Exercise the registered shutdown callback without an OS signal.
                handlers[bridge.signal.SIGTERM](bridge.signal.SIGTERM, None)

            argv = ["integrated_bridge.py", "--source", "workbuddy",
                    "--workbuddy-root", str(root / "tasks"),
                    "--sessions-root", str(root / "sessions"),
                    "--attention-cache", str(root / "attention.json"),
                    "--status-file", str(root / "status.json"),
                    "--launch-id", "runtime-test"]
            real_stop = bridge.Flower.stop
            with patch.object(sys, "argv", argv), \
                 patch.object(bridge, "WorkBuddyAdapter", return_value=adapter), \
                 patch.object(bridge.Flower, "send", autospec=True, return_value=False) as send, \
                 patch.object(bridge.Flower, "stop", autospec=True, side_effect=real_stop) as stop, \
                 patch.object(tempfile, "gettempdir", return_value=str(root)), \
                 patch.object(bridge.signal, "signal", side_effect=register_signal), \
                 patch.object(bridge.time, "sleep", side_effect=end_first_loop), \
                 redirect_stdout(io.StringIO()):
                bridge.main()

            status = json.loads((root / "status.json").read_text())
            self.assertEqual(status["launch_id"], "runtime-test")
            self.assertEqual(status["motor"], "RUN LOW")
            self.assertTrue(status["light"])
            self.assertFalse(status["device_connected"])
            self.assertEqual(status["sources"], {"workbuddy": snapshot})
            flower = send.call_args.args[0]
            send.assert_called_once_with(flower, "RUN LOW", True)
            stop.assert_called_once_with(flower)
            adapter.poll.assert_called_once()
            adapter.close.assert_called_once()
            # Both lock implementations must release the temporary lock on exit.
            locks = list(root.glob("*.lock"))
            self.assertEqual(len(locks), 1)
            with locks[0].open("a+b") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_installed_runtime_imports_without_source_checkout(self):
        setup = self.setup
        with tempfile.TemporaryDirectory(prefix="flower installed runtime ") as folder:
            root = Path(folder)
            support = root / "support"
            config = {"source": "workbuddy", "port": "auto",
                      "sessions_root": root / "sessions", "workbuddy_root": root / "tasks"}
            with patch.object(setup, "locations", return_value=(
                    support, root / "agents/service.plist", root / "logs")), \
                 patch.object(setup, "running", return_value=False), \
                 patch.object(setup, "launchctl", return_value=True), \
                 redirect_stdout(io.StringIO()):
                receipt = setup.install(config)

            installed = receipt["status_file"].parent
            # -I excludes PYTHONPATH, the user site and the checkout's cwd. Only
            # the installed runtime is added; no expected dependency list is copied.
            probe = """
import sys
from pathlib import Path
installed, source = (Path(value).resolve() for value in sys.argv[1:])
sys.path.insert(0, str(installed))
import integrated_bridge
assert Path(integrated_bridge.__file__).resolve() == installed / 'integrated_bridge.py'
for module in tuple(sys.modules.values()):
    location = getattr(module, '__file__', None)
    if location:
        assert not Path(location).resolve().is_relative_to(source), 'Imported checkout source'
print('installed-origin-ok')
sys.argv = ['integrated_bridge.py', '--help']
integrated_bridge.main()
"""
            result = subprocess.run(
                [sys.executable, "-I", "-B", "-c", probe, str(installed), str(M1)],
                cwd=root, capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("installed-origin-ok", result.stdout)
            self.assertIn("--status-file", result.stdout)


if __name__ == "__main__":
    unittest.main()
