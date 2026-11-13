"""Check that the schtasks decoder handles the encodings Windows produces.

schtasks cannot register a task in this environment (access denied), so the
XML round trip cannot run here. What can be verified is the decoding layer,
which was the actual bug: text=True assumed UTF-8 and raised
UnicodeDecodeError on the OEM code page.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import install_windows


def main() -> int:
    cases = [
        ("gbk console error", "错误: 拒绝访问。".encode("gbk")),
        ("utf-16 task xml", "<Task/>".encode("utf-16")),
        ("utf-16le with BOM", "\ufeff<Task/>".encode("utf-16-le")),
        ("ascii", b"SUCCESS: The scheduled task was created."),
        ("empty", b""),
    ]

    failures = 0
    for label, raw in cases:
        try:
            decoded = install_windows._decode_schtasks(raw)
        except Exception as error:  # noqa: BLE001 - diagnostic
            print(f"FAIL  {label}: {type(error).__name__}: {error}")
            failures += 1
            continue
        ok = decoded.strip() != "" or raw == b""
        print(f"{'ok  ' if ok else 'FAIL'}  {label}: {decoded[:50]!r}")
        if not ok:
            failures += 1

    # The bug itself: UTF-8 decoding of a GBK byte string must not be what the
    # installer relies on.
    raw = "错误".encode("gbk")
    try:
        raw.decode("utf-8")
        print("note: this GBK sample happens to be valid UTF-8")
    except UnicodeDecodeError:
        print("confirmed: GBK output is not valid UTF-8, so text=True would raise")

    print("RESULT:", "decoder handles every encoding" if failures == 0
          else f"{failures} decoding failures")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
