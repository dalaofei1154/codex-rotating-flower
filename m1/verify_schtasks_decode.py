"""Check that the schtasks decoder handles the encodings Windows produces.

schtasks cannot register a task in every environment (access denied without the
right privileges), so the XML round trip is not always available. The decoding
layer is what was broken, so that is what this checks: text=True assumed UTF-8
and raised UnicodeDecodeError on the OEM code page.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import install_windows


def main() -> int:
    cases = [
        ("utf-16 task xml", "<Task/>".encode("utf-16")),
        ("utf-16le no bom", "<Task/>".encode("utf-16-le")),
        ("ascii", b"SUCCESS: The scheduled task was created."),
        ("empty", b""),
        ("undecodable bytes", b"\xff\xfe\x00\xd8"),
    ]
    if sys.platform == "win32":
        cases.insert(0, ("gbk console error", "错误: 拒绝访问。".encode("gbk")))

    failures = 0
    for label, raw in cases:
        try:
            decoded = install_windows._decode_schtasks(raw)
        except Exception as error:  # noqa: BLE001 - diagnostic
            print(f"FAIL  {label}: {type(error).__name__}: {error}")
            failures += 1
            continue
        if not isinstance(decoded, str):
            print(f"FAIL  {label}: returned {type(decoded).__name__}")
            failures += 1
            continue
        print(f"ok    {label}: {decoded[:48]!r}")

    if sys.platform == "win32":
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
