# 旋转＋提醒灯固件

[flower_integrated.ino](flower_integrated/flower_integrated.ino) 同时控制电机与提醒灯，设备身份为 `FLOWER_COMBINED_V1`。采用 [MIT 许可](../LICENSE)。

| 连接 | ESP32-C3 引脚 |
| --- | --- |
| ULN2003 IN1／IN2／IN3／IN4 | GPIO4／5／6／7 |
| 共阴 RGB 灯板 R／G／B | GPIO0／1／3 |
| 驱动板电源 | 5V 和 GND，共地 |

RGB 通道必须有合适的限流，不能把无电阻裸 LED 直接接到 GPIO。接线和装配见 [DIY 教程](../docs/diy-guide/README.md)。

已用的编译配置：Arduino-ESP32 **3.3.11**，`ESP32C3 Dev Module`，`USB CDC On Boot = Enabled`，`Flash Mode = DIO`，`Upload Speed = 115200`。Arduino IDE 打开本目录下同名文件夹中的 `.ino` 后按该配置编译；不需要外部 Arduino 库。

```sh
arduino-cli compile \
  --fqbn 'esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashMode=dio,UploadSpeed=115200' \
  firmware/flower_integrated
```

串口为 115200，每条命令以换行结束。`PING` → `PONG`；`DEVICE INFO` 应返回 `FLOWER_COMBINED_V1 PWM=OK MOTOR_PINS=4,5,6,7 LED_PINS=0,1,3`。`RUN LOW`、`RUN MEDIUM`、`RUN HIGH`、`RUN XHIGH`、`RUN ULTRA` 为五档，`STOP` 停转。`ATTENTION ON/OFF` 控制呼吸灯，`LED STATUS` 查询灯状态。

电机 30 秒未收到 `RUN` 续期会停止，提醒灯 6 秒未收到 `ATTENTION ON` 续期会熄灭。Mac 联动软件会自动续期；手动测试时，每条命令只运行到相应超时。

首次烧录后，按 [制作教程](../docs/diy-guide/README.md#四-固件与首次测试) 测试启停、各档转速和灯光，再安装 Mac 软件。
