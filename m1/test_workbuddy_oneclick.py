import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).parent))
import package_workbuddy_oneclick as package


@unittest.skipUnless(sys.platform == "darwin", "macOS one-click package tests")
class SelfContainedInstallerTests(unittest.TestCase):
    def run_fixture(self, result=0, arguments=()):
        # Exercise extraction, quoting, default flags, error propagation and
        # cleanup without touching a real LaunchAgent or USB device.
        with tempfile.TemporaryDirectory(prefix="flower package with spaces ") as directory:
            script = Path(directory) / "小花一键安装.sh"
            runtime = {
                "launch_bridge.sh": ('#!/bin/bash\nshift\nexec ' +
                                     "'" + sys.executable.replace("'", "'\\''") + "'" + ' "$@"\n').encode(),
                "workbuddy_setup.py": (
                    'import json,sys\nfrom pathlib import Path\n'
                    'print(json.dumps({"args":sys.argv[1:],"stage":str(Path(__file__).parent)}))\n'
                    f'sys.exit({result})\n').encode(),
                "global_bridge.py": b"# fixture\n",
                "install_macos.py": b"# fixture\n",
                "INSTALL.md": b"fixture instructions\n",
            }
            script.write_bytes(package.make_script(runtime))
            completed = subprocess.run(["/bin/bash", str(script), *arguments], input="",
                                       capture_output=True, text=True, timeout=10)
            record = next((json.loads(line) for line in completed.stdout.splitlines()
                           if line.startswith('{"args"')), None)
            if record:
                self.assertFalse(Path(record["stage"]).exists(), "temporary source was not removed")
            return completed, record

    def test_default_install_is_noninteractive_and_forwards_verification(self):
        result, record = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(record["args"], ["install", "--verify-seconds", "12"])

    def test_partial_install_code_is_preserved_and_temporary_files_removed(self):
        result, record = self.run_fixture(result=3)
        self.assertEqual(result.returncode, 3)
        self.assertIsNotNone(record)

    def test_inspect_reads_source_without_running_installer(self):
        result, record = self.run_fixture(arguments=("inspect",))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(record)
        self.assertIn("fixture instructions", result.stdout)

    def test_damaged_payload_fails_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "broken.sh"
            data = package.make_script({"INSTALL.md": b"original"})
            marker = b"__FLOWER_PAYLOAD_BEGIN__\n"
            header, encoded = data.split(marker, 1)
            payload = bytearray(base64.decodebytes(encoded))
            payload[-1] ^= 1
            script.write_bytes(header + marker + base64.encodebytes(payload))
            result = subprocess.run(["/bin/bash", str(script), "inspect"],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn("校验失败", result.stderr)

    def test_release_contains_exact_sources_and_only_delivery_files(self):
        with tempfile.TemporaryDirectory(prefix="朋友 安装包 ") as directory:
            root = Path(directory)
            archive = package.build(root)
            manifest = json.loads((root / "package_manifest.json").read_text())
            self.assertEqual(manifest["version"], package.VERSION)
            self.assertEqual(manifest["zip_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
            script = root / (package.NAME + ".sh")
            encoded = script.read_bytes().split(b"__FLOWER_PAYLOAD_BEGIN__\n", 1)[1]
            with zipfile.ZipFile(io.BytesIO(base64.decodebytes(encoded))) as payload:
                expected = set(package.RUNTIME_FILES) | {"INSTALL.md", "LICENSE"}
                self.assertEqual(set(payload.namelist()), expected)
                for name in package.RUNTIME_FILES:
                    self.assertEqual(payload.read(name), (Path(package.__file__).parent / name).read_bytes())
            with zipfile.ZipFile(archive) as zipped:
                self.assertEqual(set(zipped.namelist()), {
                    package.NAME + "/" + name for name in manifest["files_sha256"]})


if __name__ == "__main__":
    unittest.main()
