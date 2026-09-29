# Rotating Flower for Codex

**English** · [简体中文](README.zh-CN.md)

I made a small desk flower that spins while Codex is working. It stops when the task finishes. On my Mac, it also spins faster when I choose a higher reasoning setting.

[![Watch a 10-second preview of the rotating flower](publish-assets/demo-preview.gif)](https://raw.githubusercontent.com/dalaofei1154/codex-rotating-flower/main/publish-assets/rotating-flower-demo-en-60s.mp4)

**[Watch or download the full 60-second demo](https://raw.githubusercontent.com/dalaofei1154/codex-rotating-flower/main/publish-assets/rotating-flower-demo-en-60s.mp4)** · [Build it step by step](docs/build-guide-en.md)

This repository shows how to make the **motor respond to Codex**. It includes the ESP32 code and the Mac program that links Codex to the motor. The flower decoration in the video is a purchased piece; there is no printable flower model here. You can use your own decoration or start with a bare motor.

> This is my personal, non-commercial DIY project. It is not affiliated with, sponsored by, or endorsed by OpenAI. The OpenAI logo on the purchased decoration belongs to OpenAI. This repository does not provide a model of that decoration or permission to use the logo. [Read the license details](LICENSES.md).

## How it works

```text
Local Codex task → Python program on the Mac → USB cable → ESP32-C3 → motor driver → motor
```

The Python program reads **local** Codex task records. When a task starts, it tells the ESP32 to turn the motor. When the task ends, it tells the motor to stop. If several tasks run at once, it uses the fastest of their selected settings.

## What you need

| Part | Quantity |
| --- | ---: |
| Mac running local Codex tasks | 1 |
| ESP32-C3 SuperMini board | 1 |
| ULN2003 motor driver board | 1 |
| 5 V 28BYJ-48 five-wire stepper motor | 1 |
| Female-to-female jumper wires | 6 |
| USB-C **data** cable | 1 |

The ESP32-C3 is the controller; you do not need another microcontroller. The motor's built-in five-pin plug goes into the ULN2003 board. You will also need Arduino IDE to upload the firmware and Python 3.9 or newer on the Mac. The Python program uses only the standard library.

My prototype uses a roughly 1:16 geared motor. I tested this setup for short runs; a different motor or a heavier flower may behave differently.

## Get it running

The [full build guide](docs/build-guide-en.md) has detailed wiring, setup, and troubleshooting steps. Start with the motor before attaching a flower.

1. **Wire the boards with USB unplugged.** Connect `5V → +`, `G/GND → -`, and `GPIO4–7 → IN1–IN4` in order. Check the labels on *your* boards and the motor's 5 V rating before powering anything.
2. **Upload the firmware.** Open [`m0/motor_control/motor_control.ino`](m0/motor_control/motor_control.ino) in Arduino IDE, select your ESP32-C3 board and port, then upload. I tested with Espressif's Arduino-ESP32 core 3.3.11.
3. **Test the motor.** In Serial Monitor at 115200 baud, send `PING` and look for `PONG`. Send `RUN LOW` to turn the motor, then `STOP`. Close Serial Monitor before the next step so the Python program can use the same port.
4. **Start the Mac program** from this repository's root folder:

   ```sh
   python3 m1/global_bridge.py --once
   python3 m1/global_bridge.py
   ```

   The first command only reports what Codex task state it sees; it does not connect to the motor. Leave the second command running and start a **local** Codex task. Press Ctrl+C to stop the program and send `STOP`. If automatic port detection fails, add `--port /dev/cu.usbmodemXXXX` with the actual port name on your Mac.

After the manual test works, you can [set it to start when you log in](m1/README.md).

## What can you reuse?

The [ESP32 firmware](m0/motor_control/motor_control.ino) and [Mac program](m1/global_bridge.py) are here for you to try on similar hardware. The Mac program does not contain my username or a fixed USB port. It looks under your `CODEX_HOME` folder (or `~/.codex` by default) and finds the board through a `PING`/`PONG` reply.

The Codex connection reads a **local file format that may change**. If a Codex update breaks it, that part of the program may need updating. Cloud tasks and Windows are not supported by this version. If you use different hardware or a different Codex setup, the [build guide](docs/build-guide-en.md#5-what-transfers-to-another-setup) explains which pieces to change. You can begin with just two states: spinning while a task runs and stopped when it ends.

The five speed names set delays between motor steps; they are **not measured RPM**. I have not tested long-term continuous use or every motor and load combination. [See the test notes](debug_log.md).

The program reads local task state and sends commands over USB. It does not need an OpenAI API key or send your conversation to a project server. Please do not upload your own Codex session files, logs, or credentials to GitHub.

## Tests and licenses

Run the software tests from the repository root:

```sh
python3 -m unittest discover -s m1 -p 'test_*.py' -v
```

The code is under [MIT](LICENSE), and the written guides are under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode). The video and third-party logo are **not** covered by those licenses. See [LICENSES.md](LICENSES.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
