"""Probe whether schtasks parses the XML before failing on privileges.

schtasks /Create is access-denied on this machine, so a successful round trip
cannot be exercised. This compares the failure for a well-formed task XML with
a deliberately broken one: if the messages differ, schtasks read the file
before rejecting it, which at least tells us the encoding is accepted.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

TASK = "RotatingFlowerXmlProbe"

VALID = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>/c exit 0</Arguments>
    </Exec>
  </Actions>
</Task>
"""

BROKEN = "this is not xml at all <<<>>>"


def create(xml_path: Path) -> tuple[int, str]:
    result = subprocess.run(
        ["schtasks", "/Create", "/TN", TASK, "/XML", str(xml_path), "/F"],
        capture_output=True, timeout=30,
    )
    raw = result.stderr or result.stdout
    try:
        text = raw.decode("mbcs")
    except (UnicodeDecodeError, LookupError):
        text = raw.decode("utf-8", errors="replace")
    return result.returncode, text.strip()


def main() -> int:
    if sys.platform != "win32":
        print("SKIP: Windows only")
        return 0

    results = {}
    for label, body in (("valid", VALID), ("broken", BROKEN)):
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-16")
        handle.write(body)
        handle.close()
        path = Path(handle.name)
        try:
            code, message = create(path)
        finally:
            path.unlink(missing_ok=True)
        results[label] = message
        print(f"{label:8} rc={code}  {message[:120]}")

    if results["valid"] == results["broken"]:
        print("RESULT: indistinguishable - schtasks rejects before reading the file,")
        print("        so this probe says nothing about the XML encoding.")
        return 0

    print("RESULT: the messages differ, so schtasks read the file before rejecting")
    print("        it. The UTF-16 encoding is accepted; only the privilege check")
    print("        remains untested here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
