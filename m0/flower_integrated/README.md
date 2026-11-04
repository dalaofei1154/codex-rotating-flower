# Combined rotation + attention firmware

[`flower_integrated.ino`](flower_integrated.ino) is the firmware used by the v0.6.0 Mac installer. Gift recipients receive a board already flashed and tested; the Mac installer never flashes it.

Reference hardware: ESP32-C3 SuperMini, ULN2003 and 5 V 28BYJ-48. Motor IN1/IN2/IN3/IN4 use GPIO 4/5/6/7. The common-cathode KY-016 RGB module used for verification has onboard current-limiting resistors: R/G/B use GPIO 0/1/3 and common ground. A bare LED requires suitable current-limiting components; do not assume another module has the same circuit. Use an Arduino-ESP32 3.x core for the pin-based LEDC API.

Serial baud: 115200. `DEVICE INFO` reports `FLOWER_COMBINED_V1 PWM=OK`; `PING` replies `PONG`. The normal motor commands are `RUN LOW`, `RUN MEDIUM`, `RUN HIGH`, `RUN XHIGH`, `RUN ULTRA`, `STOP`. Light commands are `ATTENTION ON` and `ATTENTION OFF`. Motor and light heartbeats are separate: missing motor refresh stops after 30 seconds, and missing attention refresh clears the light after 6 seconds. The desktop bridge handles these refreshes.

The firmware also retains experimental `TEST` commands; normal use only sends the five established RUN presets. Step timing is not a measured RPM. Close serial monitors before running the Mac bridge.

The older [hardware guide](../../docs/build-guide-en.md) describes the motor wiring; this folder supplies the additional light-enabled firmware. No 3D models or manufacturing files are included.
