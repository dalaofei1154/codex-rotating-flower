# Build the Rotating Flower electronics and Codex bridge

This guide helps a DIY beginner reproduce the **electronics and software behavior** shown in the [60-second demo](../publish-assets/rotating-flower-demo-en-60s.mp4). Start with a bare motor; the purchased decorative flower and its 3D files are not supplied.

Tested scope: one macOS computer running local Codex tasks, an ESP32-C3 SuperMini, a ULN2003 driver, and a 5 V 28BYJ-48 stepper motor. This is a short-run prototype, not a validated design for continuous operation or every board and motor variation.

## 1. Parts and tools

| Item | Count | Notes |
| --- | ---: | --- |
| Mac with local Codex | 1 | Runs the bridge and connects to the board over USB. Windows has not been adapted. |
| ESP32-C3 SuperMini | 1 | This board **is** the microcontroller. Check that yours exposes `5V`, `G`, and GPIO4–7. |
| ULN2003 driver board | 1 | Must have IN1–IN4, power terminals, and the motor's five-pin socket. |
| 5 V 28BYJ-48 five-wire stepper motor | 1 | The current physical build uses an approximately 1:16 version. Read the voltage on your motor label. |
| Female-to-female jumper wires | **6** | Four signal wires plus power and ground; use a different connector type if your boards require it. |
| USB-C **data** cable | 1 | Powers and connects the current ESP32 board. Match the computer end to your Mac. |

The motor's built-in five-pin plug goes into the ULN2003 socket and does not require five more jumper wires. Install Arduino IDE and Espressif's Arduino-ESP32 board support using the [official installation instructions](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html). The project has been tested with core version **3.3.11**. Install Python 3.9 or newer for the Mac bridge; no third-party Python packages are required.

Power off and unplug USB before changing wires. Do not connect a 5 V motor to a 3.3 V pin. Recheck power capacity, polarity, and common ground if you change the motor, add load, or use a separate supply. Keep moving pieces clear of fixed parts and begin at LOW.

## 2. Wire the boards

With USB **disconnected**, verify the labels printed on your specific hardware and connect:

| ESP32-C3 SuperMini | ULN2003 driver |
| --- | --- |
| `5V` | power `+` |
| `G` / `GND` | power `-` |
| `GPIO4` | `IN1` |
| `GPIO5` | `IN2` |
| `GPIO6` | `IN3` |
| `GPIO7` | `IN4` |

Plug the motor's five-pin connector into the ULN2003 motor socket. After checking the six connections, attach the USB-C data cable to the Mac. Test without a heavy flower attached to the shaft.

## 3. Upload and test the firmware

1. In Arduino IDE, open [`m0/motor_control/motor_control.ino`](../m0/motor_control/motor_control.ino). Choose the ESP32-C3 board definition and USB serial port appropriate for **your** board; compile and upload.
2. Open Serial Monitor at **115200 baud** and configure it to send a newline. Send `PING`; the board should reply `PONG`.
3. Send `RUN LOW` and observe a short period of rotation. Send `STOP` and verify that the motor stops. If it does not rotate, disconnect USB before inspecting the wiring and motor connector.
4. **Close Serial Monitor** before running the bridge. It and the bridge cannot own the same serial port at the same time.

The firmware also understands `RUN MEDIUM`, `RUN HIGH`, `RUN XHIGH`, and `RUN ULTRA`. These set step intervals, not measured output RPM. Motor gearing and load change the actual motion.

## 4. Connect to local Codex

Download this repository and open a Mac terminal at its root. Check Python and take a state-only snapshot:

```sh
python3 --version
python3 m1/global_bridge.py --once
```

`--once` does **not** open USB. `STOP` is expected when no local Codex task is currently running. Then run the live bridge:

```sh
python3 m1/global_bridge.py
```

Keep that terminal open and start a **local** Codex task. The bridge reads local task start, finish, and reasoning-effort events, maps them to serial commands, and probes for an ESP32 that responds to `PING`. A successful connection prints `Motor connected` and later `Motor: RUN ...`. Press **Ctrl+C** to exit and send `STOP`.

If several devices appear as serial ports, specify the real device path from your Mac:

```sh
python3 m1/global_bridge.py --port /dev/cu.usbmodemXXXX
```

`XXXX` is only an example. After manual testing works, [`m1/README.md`](../m1/README.md) explains the optional macOS login service (`python3 m1/install_macos.py install`), updates, removal, and logs.

```text
Local Codex records → Python bridge on the Mac → USB serial → ESP32-C3 → ULN2003 → motor
```

No OpenAI API key is required. The bridge reads local state records and does not upload conversation content to a project server. **Do not upload your Codex session records or personal logs to GitHub**; they may contain private content.

## 5. What transfers to another setup?

- **Same Mac and hardware family:** Try the included [firmware](../m0/motor_control/motor_control.ino), [bridge](../m1/global_bridge.py), and [installer](../m1/install_macos.py). The bridge uses the current user's `CODEX_HOME` (or default `~/.codex`) and probes serial ports; it does not hard-code the author's username or USB port.
- **Different boards or motors:** Recheck pins, supply, motor type, and acceleration. A four-wire bipolar motor and a different driver cannot run this ULN2003 firmware unchanged. You can retain the `RUN ...` / `STOP` serial protocol and replace the motor-control code.
- **Different Codex environment:** This Mac bridge reads an **internal** transcript format. [OpenAI's Hooks documentation](https://learn.chatgpt.com/docs/hooks) says that format is not stable. Retest after upgrades. [Local and Worktree tasks run on the computer, while Cloud tasks run remotely](https://learn.chatgpt.com/docs/environments/modes). Windows serial access and service installation have not been implemented.

For a port, first get `PING`, `RUN LOW`, and `STOP` working between the computer and ESP32. Next provide a reliable task-start and task-finish event source. Add reasoning-effort mapping only when that information is available; a simpler running/stopped indicator still reproduces the core idea.

## 6. Troubleshooting

| Symptom | Check first |
| --- | --- |
| Arduino IDE shows no port | Confirm the USB-C cable carries **data**, the board powers on, and the adapter works. |
| `PING` gets no `PONG` | Check board selection, upload, port, 115200 baud, and newline setting. |
| `PING` works but the motor is still | Disconnect USB; verify all six wires, driver polarity, and five-pin motor plug. Retry `RUN LOW`. |
| Bridge cannot find the ESP32 | Close Serial Monitor; check whether the port changed; use `--port` if necessary. |
| Motor responds manually but not to Codex | Confirm the task is local, inspect `--once`, and retest the transcript adapter after Codex updates. |

The [prototype log](../debug_log.md) records what was physically observed and what remains unverified.
