# Rotating Flower

**English** · [简体中文](README.zh-CN.md)

A desk flower that moves with local AI tasks. The macOS bridge connects **Codex and WorkBuddy** to an ESP32-controlled motor over USB.

Formerly `codex-rotating-flower`. This small release adds WorkBuddy support and a downloadable Mac installer. New enclosure designs and light notifications are planned separately and are **not included** in this release.

## WorkBuddy for Mac — v0.3.0

**[Download the Mac installer](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.3.0/rotating-flower-workbuddy-macos-v0.3.0.zip)** · [Release notes and checksums](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.3.0) · [Setup / 安装说明](docs/workbuddy-macos.md)

The installer is for an **already assembled, flashed and tested USB flower**. DIY builders should first follow the [hardware and firmware guide](docs/build-guide-en.md).

1. Install and sign in to WorkBuddy on an Apple Silicon Mac, then connect the flower with a USB data cable.
2. Unzip the download. Attach its versioned `.sh` file to WorkBuddy together with `INSTALL.md`, and send the text in `发给WorkBuddy的安装指令.txt` (adapt the attachment reference if using the extracted file).
3. Let WorkBuddy run the installer. Approve any required system prompts yourself. Confirm that both the background service and a fresh USB handshake pass, then check that the flower turns during a task and stops afterward when no other tasks are active.

The package contains its source and instructions; it does not download programs or require an API key. It reuses an available Python 3.9+ runtime, including WorkBuddy's bundled Python. Setup messages and packaged instructions are currently in Chinese; the linked guide includes English instructions.

## What it does

| Source / selection | Motor preset |
| --- | --- |
| Codex | Five presets mapped from the selected reasoning effort |
| WorkBuddy: Fast / 快速 | LOW |
| WorkBuddy: Balanced / 均衡 | HIGH |
| WorkBuddy: Deep / 极致 | ULTRA |
| WorkBuddy: independent or unknown nonempty model | HIGH |
| WorkBuddy: older records with no model selection | LOW |

WorkBuddy tasks pause their motor contribution while waiting for user input, resume when work continues, and stop contributing when completed or cancelled. Multiple active tasks use the highest preset; the motor stops when none remain active. Existing Codex support is preserved by the WorkBuddy installer.

These are **selected-mode mappings**, not measurements of cloud compute, intelligence, tokens per second or physical RPM. A WorkBuddy mode change applies to the next task turn. See the guide for restart and sampling limitations.

## Run from source

With Python 3.9+ on macOS, from the repository root:

```sh
# Read-only state inspection; does not open USB
python3 m1/global_bridge.py --source workbuddy --once

# Follow WorkBuddy, or both apps (run only one bridge at a time)
python3 m1/global_bridge.py --source workbuddy
python3 m1/global_bridge.py --source both
```

The default source remains Codex. For background installation, updates and removal, see the [bridge guide](m1/README.md).

## Scope and validation

- Local macOS tasks only; no Windows or cloud-task support in this release.
- WorkBuddy 5.9.3: three presets, parallel-task fallback, cancellation and wait/resume checked against real controller replies. Earlier 5.8.3 start/stop behavior was also visually confirmed.
- v0.3.0 installation: tested on the maintainer's Apple Silicon Mac with WorkBuddy 5.9.3, including fresh USB handshake and final STOP. Independent installation on another Mac and long-running use remain to be verified; the latest three-preset test did not measure RPM or noise.
- 42 automated tests cover the bridge, installer and package. Tests use temporary fixtures and mocked hardware/service controls.
- The adapters depend on local application data formats and need retesting after application updates. WorkBuddy reads task/worker metadata, not conversation text or credentials, and does not modify its database. The bridge sends no data to a project server.
- A task with no state update for 10 minutes stops contributing. The existing firmware stops after 30 seconds without a `RUN` command.

```sh
python3 -m unittest discover -s m1 -p 'test_*.py' -v
```

## What is open source?

The bridge, installer and ESP32 firmware are [MIT licensed](LICENSE); written guides use CC BY 4.0. **3D models and manufacturing files are not published.** You can use your own decoration or start with a bare motor. See [LICENSES.md](LICENSES.md) for the separate terms covering historical media.

This release adds no images or new hardware design. The [original Codex build guide](docs/build-guide-en.md) remains available as a hardware reference. This is an independent project, not affiliated with or endorsed by OpenAI or WorkBuddy.
