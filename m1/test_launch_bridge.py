import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


class RuntimeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="小花 launcher with spaces ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.trace = self.root / "runtime-probes.txt"
        self.bundled = self.root / "workbuddy/binaries/python/versions/3.13/bin/python3"
        self.system = self.root / "system/python3"
        self.xcode = self.root / "system/xcode-select"
        # Redirect only filesystem/executable locations in an isolated copy.
        # Never change HOME, invoke the real Python stub or touch a LaunchAgent.
        source = Path(__file__).with_name("launch_bridge.sh").read_text()
        replacements = {
            '"$HOME"/.workbuddy/': shlex.quote(str(self.root / "workbuddy")) + "/",
            '"$HOME"/.workbuddy-ai/': shlex.quote(str(self.root / "workbuddy-ai")) + "/",
            "/opt/homebrew/bin/python3": shlex.quote(str(self.root / "missing-homebrew/python3")),
            "/usr/local/bin/python3": shlex.quote(str(self.root / "missing-local/python3")),
            "/usr/bin/python3": shlex.quote(str(self.system)),
            "/usr/bin/xcode-select": shlex.quote(str(self.xcode)),
        }
        for original, replacement in replacements.items():
            source = source.replace(original, replacement)
        self.launcher = self.root / "launch_bridge.sh"
        self.launcher.write_text(source)

    def executable(self, path, contents):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/bash\n" + contents)
        path.chmod(0o755)

    def python(self, path, name):
        self.executable(path, (
            f"printf '%s\\n' '{name}' >> {shlex.quote(str(self.trace))}\n"
            'if [[ "$1" == "-c" ]]; then exit 0; fi\n'
            f"printf '%s\\n' '{name}'\n"
            'printf \'%s\\n\' "$@"\n'
        ))

    def tools_available(self, available):
        self.executable(self.xcode, (
            f"printf '%s\\n' 'xcode-check' >> {shlex.quote(str(self.trace))}\n"
            f"exit {0 if available else 1}\n"
        ))

    def run_launcher(self, preferred=""):
        return subprocess.run(["/bin/bash", str(self.launcher), preferred,
                               "脚本 with spaces.py", "--example", "value with spaces"],
                              capture_output=True, text=True, timeout=5)

    def probes(self):
        return self.trace.read_text().splitlines() if self.trace.exists() else []

    def test_bundled_python_needs_no_developer_tools_and_preserves_arguments(self):
        self.python(self.bundled, "bundled")
        self.python(self.system, "system")
        self.tools_available(False)
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(),
                         ["bundled", "脚本 with spaces.py", "--example", "value with spaces"])
        self.assertNotIn("xcode-check", self.probes())
        self.assertNotIn("system", self.probes())

    def test_clean_mac_does_not_execute_system_python_stub(self):
        self.python(self.system, "system")
        self.tools_available(False)
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Open WorkBuddy, run a Python task", result.stderr)
        self.assertEqual(self.probes(), ["xcode-check"])

    def test_system_python_is_available_when_developer_tools_exist(self):
        self.python(self.system, "system")
        self.tools_available(True)
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "system")
        self.assertEqual(self.probes(), ["xcode-check", "system", "system"])

    def test_old_preferred_system_python_does_not_bypass_clean_mac_check(self):
        self.python(self.bundled, "bundled")
        self.python(self.system, "system")
        self.tools_available(False)
        result = self.run_launcher(str(self.system))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "bundled")
        self.assertNotIn("system", self.probes())
        self.assertEqual(self.probes()[0], "xcode-check")


if __name__ == "__main__":
    unittest.main()
