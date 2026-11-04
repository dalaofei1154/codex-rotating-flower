# Rotating Flower

**English** · [简体中文](README.zh-CN.md)

A USB desk flower that rotates with local **Codex and WorkBuddy** tasks and breathes light when your input is needed. Formerly `codex-rotating-flower`.

## Install v0.6.0

**[Download the Mac installer](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.6.0/RotatingFlower-Mac-v0.6.0.zip)** · [Installation guide / 安装说明](docs/install-macos.md) · [Release](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.6.0)

Requires an **Apple silicon Mac with macOS 12+**, Codex and/or WorkBuddy installed, and an assembled flower already flashed with combined rotation + attention-light firmware.

1. Connect the flower with a USB data cable.
2. Extract the ZIP and double-click **安装小花.command**.
3. Open and sign in to your AI app, then start a task.

New installations and upgrades detect Codex, WorkBuddy, or both. If you install the other app later, run the installer again. Python is included; no system Python, Homebrew or Node is required. The installer does not install AI apps or flash firmware. It starts the background service at Mac login.

You can install before opening or initializing an app. Exit code **5** means “installed, waiting for the app”; open it and begin a task. The service retries automatically, so no reinstall is needed. Damaged or incompatible data produces an explicit error. The package is unsigned and unnotarized; macOS may require confirmation.

The [guide](docs/install-macos.md) also provides a pinned network installer that downloads to disk before execution and verifies the release ZIP's SHA256:

```text
a82b64865092d03672e4340752c0c574078149b9dbcfa028f9f3e3e995dd0c01
```

## Behavior

| State | Flower |
| --- | --- |
| Working | Rotates at the selected mode's preset |
| Blocked waiting for an answer or approval | Reminds with breathing light; that task stops contributing speed |
| One task waits while another works | Rotates and lights up together |
| All tasks finish, no pending input | Stops and turns the light off |

Working tasks across both apps use the highest preset; reminders stay on while a connected source reports pending input. An asynchronous Codex question can leave the same task working and the light on; a disconnected source stops contributing outputs while its pending-state cache is retained. WorkBuddy Fast / Balanced / Deep map to LOW / HIGH / ULTRA. Independent or unknown models use HIGH; missing model metadata uses LOW. Codex retains its five reasoning-effort presets. These are selected-mode mappings, not measurements of cloud compute or physical RPM.

Double-click **卸载小花.command** to remove the entire background service for both apps. Backups and logs remain.

## Verified scope

Tested on one Mac with **Codex 26.1027.61615** and **WorkBuddy 5.9.3**: double-click installation, concurrent-task arbitration, a real waiting question card, and clearing the light after answering. The user visually confirmed the breathing light.

This package does not support Intel Macs. Every app version and a second Mac installation have not been verified. Real permission-approval prompts and long continuous use remain unverified. The bridge follows local tasks and depends on application data formats; retest after app updates. No API key is required, and the bridge does not send data to a project server.

## Source and hardware reference

The bridge, installer and ESP32 firmware use the [MIT license](LICENSE); guide text uses CC BY 4.0. See [LICENSES.md](LICENSES.md) for media and other terms. Current 3D models and manufacturing files are not published.

The historical motor-only build guides remain available in [English](docs/build-guide-en.md) and [中文](docs/从零搭建.md). Their older firmware and installation commands are not the combined light-enabled setup required by this release.

This is an independent project, not affiliated with or endorsed by OpenAI or WorkBuddy.
