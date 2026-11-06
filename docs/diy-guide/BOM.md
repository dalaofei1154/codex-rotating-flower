# 采购清单 / Bill of materials

一盆无品牌雏菊带灯版所需数量。材料与接线以实物端子为准；不要求购买某个店铺。 / Quantities for one unbranded daisy with an attention light. Check the actual board connectors before ordering.

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

8 根普通线加一分二线是根据接线拓扑给出的采购方案，不是对原照片线束品牌或焊接工艺的认定。电机自带线不计入这 8 根。若使用另一种分线结构，应实现同一公共地连接，不能把两个母头硬塞进同一根针。 / This jumper count follows the wiring topology. The motor's own cable is separate. A different ground harness is acceptable if it securely joins the same three grounds.

作者补充的商品图已确认 KY-016 为四根预焊直角公排针版，可见三颗板载电阻及 R/G/B/− 丝印；按这个端子形态预留接线空间。图片用于核对模块外形，共阴电气规格仍以项目要求及实物核对为准。若买到未焊版本，需要先完成合适的焊接；本教程没有把焊接工具计入标准装配套件。 / The supplied product photo confirms the KY-016 variant with four pre-soldered right-angle male pins, three visible onboard resistors and R/G/B/− labels. Allow space for this connector arrangement. The photo identifies the physical variant; verify the required common-cathode electrical configuration on the actual module. Unpopulated boards require soldering before assembly, which is outside the standard tool list.

准备一台 Apple 芯片 Mac（macOS 12+）运行 v0.6.0 联动软件，以及带 Arduino-ESP32 支持包的 Arduino IDE 烧录主控。安装包自带 Python，烧录工具须另外准备。 / Use an Apple silicon Mac with macOS 12+ for the v0.6.0 bridge, and Arduino IDE with Arduino-ESP32 support for flashing. The bridge installer includes Python, but does not include the flashing tools.

返回 [中文教程](README.md) · [English guide](README.en.md)
