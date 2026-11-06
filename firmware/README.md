# 旋转＋提醒灯固件

入口：[flower_integrated.ino](flower_integrated/flower_integrated.ino)。协议身份为 `FLOWER_COMBINED_V1`；这是 2026-11-03 组合原型源码的原字节副本，2026-11-05 烧录记录核对过同一源码与应用二进制哈希。采用项目 [MIT 许可](../LICENSE)。

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

电机 30 秒未收到 RUN 续期会停止，提醒灯 6 秒未收到 ATTENTION ON 续期会熄灭；手工单条命令不是持续联动。`TEST FAST` 等命令是历史研发试验，不用于新手装机验收。

11 月 5 日新装设备已通过五档、灯光状态和双超时保护的控制板回执检查；作者在逐档加速与呼吸灯测试期间现场确认“转动和呼吸灯都正常”。这是该设备的短时实测，未测量实际 RPM、长期温升或耐久，也不替代其他新装设备逐台验收。Mac v0.6.0 是配套软件版本，不是固件版本；旧 `m0/motor_control/` 固件只有电机功能。

本目录仅发布源码，不附芯片完整闪存备份或含本机路径的编译输出。源码 SHA256：`04ae4a1f6bda1e1e24e8ea6288690fdaffb8a1a1c0cac1c14083c451f9ccd26a`。
