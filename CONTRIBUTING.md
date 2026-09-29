# Contributing

[简体中文](#中文说明)

Thanks for trying this project. If something does not work, please open an issue with enough detail for someone else to reproduce it:

- Your macOS and Python versions, ESP32 board, Arduino-ESP32 core version, motor, and driver board.
- How you wired and powered the boards, what command you sent, what you expected, and what happened.
- A short piece of the relevant serial or bridge log.

Please remove names, device IDs, private paths, conversation text, and credentials from screenshots and logs. Do not upload Codex session files. If the motor gets hot, stalls, or rubs against another part, unplug it before checking the wiring.

For code changes, say whether you changed the ESP32 firmware, the Mac program, or the guide. If you change the Mac program, run:

```sh
python3 -m unittest discover -s m1 -p 'test_*.py' -v
```

If you change motor pins, speed, or power wiring, tell us which hardware you tested and for how long. A speed calculated from step timing is not a measured RPM. For images or other media, include the source and redistribution rights. The flower decoration in the demo was purchased; its 3D model is not included here.

## 中文说明

欢迎复现、提问或改进。如果遇到问题，请尽量说明：

- macOS 和 Python 版本、ESP32 开发板、Arduino-ESP32 core 版本、电机和驱动板型号。
- 接线与供电方式、执行的命令、预期结果和实际现象。
- 一小段相关串口或桥接器日志。

提交截图或日志前，删去用户名、设备编号、私人路径、对话内容和密钥。不要上传 Codex 任务文件。电机发烫、卡住或擦碰时，先断电再检查。

修改代码时，请说明改的是 ESP32 固件、Mac 程序还是教程。修改 Mac 程序后，请运行上面的测试命令。修改电机引脚、速度或供电时，请说明使用的硬件、负载、运行时间和观察结果。按步进间隔计算的速度不等于实测转速。提交图片或视频时，请注明来源和再分发权限。演示中的花朵装饰件是购买的成品，仓库没有它的 3D 模型。
