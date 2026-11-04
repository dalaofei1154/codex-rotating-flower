# Unified bridge source · v0.6.0

For normal use, follow the [Mac installation guide](../../docs/install-macos.md).

The seven runtime modules in this folder combine Codex and WorkBuddy into one USB writer. Working sources contribute their highest speed; attention is combined independently. An unavailable source does not stop the other healthy source.

Codex uses local desktop IPC subscriptions and task metadata. The observer sends discovery/subscription messages, but does not start tasks, submit answers or approve commands. WorkBuddy reads local SQLite task/worker metadata and bounded notifier metadata. No API key or project server is used. Status, caches and logs stay in the current user's support/log directories; they can contain task IDs and must not be published.

## Validate source

From the repository root, with a development Python (the release uses 3.13):

```sh
python3 -B -m unittest discover -s m1/integrated -p 'test_*.py'
python3 -B -m unittest discover -s m1 -p 'test_*.py'
```

These tests use synthetic tasks and temporary files. They do not install a service, connect real desktop IPC or drive USB hardware.

## Build the offline installer

Download the official Python archive recorded by `PYTHON_URL` in [`package_workbuddy_integrated.py`](../package_workbuddy_integrated.py), then run:

```sh
python3 m1/package_workbuddy_integrated.py --output /tmp/flower-build --python-archive /path/to/python-arm64.tar.gz
```

The builder verifies the pinned Python SHA256 and packages only the runtime allowlist, installer and notices. The Python runtime retains its original licenses. Tests and local runtime data are excluded. The network entry [`install_unified_release.sh`](../install_unified_release.sh) pins the published ZIP's SHA256; update that pin only for an intentionally new release.

The lower-level runtime defaults to WorkBuddy for historical compatibility. End users should use the installer, which detects Codex/WorkBuddy and saves the appropriate source. Do not run a second bridge against an installed service's USB port.
