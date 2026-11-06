# 采购清单 / Bill of materials

制作一朵带提醒灯的雏菊，需要以下材料。 / Materials for one daisy with an attention light.

<a id="costs"></a>

## 制作材料参考成本 / Reference material costs

以下是我在 **2026-11-06** 提供的材料价格，金额均为人民币。 / These are the material prices I shared on **2026-11-06**, in Chinese yuan (CNY).

| 项目 / Item | 本次金额（元） / Reported amount (CNY) |
| --- | ---: |
| 1P 一母分两母杜邦线 / Three-female-terminal Y splitter | 0.59 |
| KY-016 三色 LED 模块 / RGB LED module | 1.10 |
| 10 cm 母对母杜邦线 / Female-to-female jumpers | 1.70 |
| ULN2003 驱动板 / Motor driver | 1.63 |
| 1:16、5 V、四相五线步进电机 / 5 V, 1:16, four-phase, five-wire stepper motor | 3.40 |
| ESP32-C3 SuperMini 开发板 / Development board | 14.00 |
| 3D 打印件：210 g × 0.15 元/g / 3D printing: 210 g × CNY 0.15/g | 31.50 |
| **所列项目合计 / Total for the listed items** | **53.92** |

电子配件与线材共 **22.42 元**，打印件按上述重量和单价计算为 **31.50 元**。USB 数据线、工具、胶和胶带、运费未计入，实际采购价格会有所不同。 / Electronics and wiring total **CNY 22.42**; printing comes to **CNY 31.50** at the weight and rate above. The USB data cable, tools, glue, tape and shipping are not included. Local purchase prices may vary.

## 材料与规格 / Parts and specifications

| 配件 / Part | 数量 / Qty | 规格 / Specification |
| --- | --- | --- |
| ESP32-C3 SuperMini | 1 | USB-C，已焊公排针 / USB-C, soldered male headers |
| ULN2003 电机驱动板 / Motor driver | 1 | 带 28BYJ-48 五针插座，端子含 IN1–4、+、− / 5-pin motor socket, IN1–4 and power terminals |
| 28BYJ-48 步进电机 / Stepper motor | 1 | **5 V、1:16**，五线插头；不要仅凭外形选 12 V 或 1:64 版本 / 5 V, 1:16 gearbox, five-wire connector |
| KY-016 RGB 灯板 / RGB module | 1 | 共阴、板载限流电阻；R/G/B/− 四根预焊直角公排针，沿板边平行于PCB伸出 / Common cathode, onboard resistors; four pre-soldered right-angle male R/G/B/− pins extending parallel to the PCB |
| 母对母杜邦线 / Female-to-female jumpers | 8 | 10 cm：4 路电机控制、1 路 5 V、3 路 RGB / Four motor signals, 5 V and three RGB signals |
| 共地一分二线 / Y-shaped ground splitter | 1 | 三个母端，分别接主控、驱动和灯的公针 / Three female terminals for the controller, driver and LED grounds |
| USB-C 数据线 / USB data cable | 1 | 接 Mac 与主控，同时供电和串口通信 / Data-capable cable for power and serial communication |
| 打印件 / Printed parts | 10 | [模型文件](../../hardware/README.md)；分色 STL 数量不等于成品数量 / Model files; colored mesh count differs from finished-part count |
| 普通 PLA / Opaque PLA | 按切片 / Per slicer | 绿、黑、白、黄、盆体颜色 / Green, black, white, yellow and a pot color |
| 透明 PLA / Transparent PLA | 按切片 / Per slicer | 透明灯帽 / Light cap |
| 热熔胶、绝缘胶带 / Hot glue and insulating tape | 适量 / As needed | 固定板卡、电机和遮光片 / Secure boards, motor and light shield |
| 修边工具、镊子 / Deburring tool and tweezers | 各1 / 1 each | 清支撑、整线 / Remove supports and route wires |

电机自带的五针线不计入 8 根杜邦线。用一分二线将主控、驱动板和灯板接到公共地。 / The motor's five-wire cable is separate from the eight jumpers. Use the splitter to join the controller, driver and LED grounds.

购买灯板时选择预焊直角公排针、带限流电阻的共阴 KY-016，为排针和杜邦母头留出空间。 / Choose a common-cathode KY-016 with onboard resistors and pre-soldered right-angle male headers. Leave space for the headers and jumper connectors.

准备一台 Apple 芯片 Mac（macOS 12+）运行 v0.6.0 联动软件，以及带 Arduino-ESP32 支持包的 Arduino IDE 烧录主控。安装包自带 Python，烧录工具须另外准备。 / Use an Apple silicon Mac with macOS 12+ for the v0.6.0 bridge, and Arduino IDE with Arduino-ESP32 support for flashing. The bridge installer includes Python, but does not include the flashing tools.

返回 [中文教程](README.md) · [English guide](README.en.md)
