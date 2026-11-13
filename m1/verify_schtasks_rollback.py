"""Exercise the real schtasks /XML round trip used by install_windows.

The unit tests mock schtasks, so they never prove the captured XML is accepted
back by schtasks, nor that its localized output decodes. This registers a
throwaway task, exports it through the installer's own helpers, deletes it,
restores it from the export, and deletes it again.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import install_windows


def main() -> int:
    if sys.platform != "win32":
        print("SKIP: Windows only")
        return 0

    original = install_windows.TASK_NAME
    install_windows.TASK_NAME = "RotatingFlowerSelfCheck"
    name = install_windows.TASK_NAME

    install_windows.schtasks("/Delete", "/TN", name, "/F", check=False)

    created = install_windows.schtasks(
        "/Create", "/TN", name, "/TR", "cmd /c exit 0",
        "/SC", "ONLOGON", "/RL", "LIMITED", "/F", check=False)
    print("create:", created.returncode)
    if created.returncode != 0:
        detail = created.stderr.strip() or created.stdout.strip()
        print("  ", detail[:300])
        install_windows.TASK_NAME = original
        if "denied" in detail.lower() or "拒绝访问" in detail:
            print("SKIP: this account cannot register scheduled tasks, so the")
            print("      XML round trip cannot be exercised here.")
            return 0
        return 1

    try:
        definition = install_windows.task_definition()
        print("export:", "ok" if definition else "FAILED",
              "| chars:", len(definition or ""))
        if not definition:
            print("RESULT: FAIL - task_definition() returned nothing")
            return 1
        head = definition.lstrip()[:60].replace("\n", " ")
        print("  starts with:", head)
        if "<Task" not in definition:
            print("RESULT: FAIL - the export does not look like task XML")
            return 1

        install_windows.schtasks("/Delete", "/TN", name, "/F", check=False)
        gone = install_windows.schtasks("/Query", "/TN", name, check=False)
        print("after delete, query returns:", gone.returncode)

        install_windows.restore_task(definition)
        back = install_windows.schtasks("/Query", "/TN", name, check=False)
        print("after restore, query returns:", back.returncode)
        if back.returncode != 0:
            print("RESULT: FAIL - restore_task() did not recreate the task")
            return 1

        print("RESULT: export and restore round-trip through the installer")
        return 0
    finally:
        install_windows.schtasks("/Delete", "/TN", name, "/F", check=False)
        install_windows.TASK_NAME = original
        print("cleanup: task removed, TASK_NAME restored")


if __name__ == "__main__":
    raise SystemExit(main())
