# 打印与干装 / Printing and dry fitting

下载[雏菊带灯版模型](../../hardware/README.md)。一朵花共 **10 个打印件**，双色 STL 按共同坐标组合导入。 / Download the [daisy model set](../../hardware/README.md). One flower needs **10 printed parts**; import color meshes together, preserving their shared coordinates.

## 打印设置 / Print settings

按下表作为打印起点，再为自己的打印机与耗材重新切片。 / Start with these settings, then reslice for your printer and filament.

**PLA，0.4 mm 喷嘴，0.20 mm 层高，单位 mm，100% 原尺寸。 / PLA, 0.4 mm nozzle, 0.20 mm layers, millimeters, 100% scale.**

| 成品 / Finished part | 数量 / Qty | 墙数 / Walls | 填充 / Infill | 颜色与零件 / Color and part |
| --- | --- | --- | --- | --- |
| 枝干含叶片 / Stem and leaves | 1 | 4 | 30% | 绿＋黑 / Green + black; P01 |
| 电机后盖 / Motor cover | 1 | 4 | 100% | 绿 / Green; P02 |
| 藏线盖 / Wire cover | 1 | 4 | 100% | 绿 / Green; P02 |
| 雏菊花盘 / Daisy rotor | 1 | 4 | 35% | 白＋黑 / White + black; P03 |
| 2号传动连接件 / Adapter 2 | 1 | 4 | 100% | 自选颜色 / Any color; P04, D16.95, no three holes |
| 花盆 / Pot | 1 | 4 | 40% | 自选颜色 / Any color; P05 |
| L2 带灯盆盖 / Light lid | 1 | 6 | 40% | 自选颜色 / Any color; P06 |
| 四套环电子托盘 / Electronics tray | 1 | 4 | 40% | 自选颜色 / Any color; P07 |
| Y1 花心 / Center | 1 | 4 | 100% | 黄＋黑 / Yellow + black; P08 |
| P4 透明灯帽 / Clear cap | 1 | 2 | 100%, zig-zag | 透明 PLA / Transparent PLA; D6.2 |

## 切片前 / Before slicing

1. 在 Bambu Studio 用“打开项目”载入提供的 3MF，保持各色部件对齐。不要把它们逐个导入后自动排布。使用其他切片器时，导入分色 STL 必须保留共同坐标。 / Open the 3MF as a project. Preserve alignment of color components; do not auto-arrange separate color meshes.
2. 为实际打印机、喷嘴、耗材重新切片，并重新核对配色、温度、顶底层和支撑。现有 3MF 的预设和料槽编号不能代表你的机器。 / Reslice for your own printer, nozzle and filament. Recheck colors, temperatures, top/bottom layers and supports. Slot numbers are machine-specific.
3. 普通件保留已提供工程中的摆放与支撑屏蔽；先看逐层预览，确认没有悬空岛或误填的配合孔。 / Preserve project orientation and support painting where provided; inspect the layer preview for unsupported islands and blocked holes.
4. L2 盖正面朝下，短安装块及旋扣朝上，在预览中检查旋扣悬空处的支撑。 / Print L2 top face down, with the mounting block and tabs up. Check the tab supports in the preview.
5. P4 灯帽帽面朝下、柱朝上；记录为无支撑、2 mm brim。工程预览色可能是紫色，实际耗材选透明 PLA。P4 工程中若排有四份，只需要每盆一件。 / Print the P4 head down, post up; recorded settings use no supports and a 2 mm brim. Use transparent PLA even if the preview is purple. Four copies in a plate are spares; one cap is used per flower.
6. 切片后导出自己打印机的 G-code。 / Export G-code for your own printer after slicing.

## 装配前干装 / Dry fit before assembly

先逐处试装。我的花心、灯帽和枝干与盆盖连接没有用胶，还有些松，后续会继续改进。 / Test each fit before assembly. My center, cap and stem-to-lid joint are fitted without glue and are still a little loose; I plan to improve them.

| 检查 / Check | 通过条件 / Pass condition |
| --- | --- |
| 托盘→盆体 / Tray → pot | 套环落到定位柱；USB 口对准盆侧开口 / Locating sleeves engage; USB aligns with side opening |
| 盆盖→盆体 / Lid → pot | 三处旋扣轻放可锁；没有蛮力弯折 / Tabs engage without force |
| 枝干→盆盖 / Stem → lid | 稳定落位，电机插头可先穿过方孔 / Stem seats; motor plug passes through first |
| 电机→安装腔 / Motor → housing | 轴孔不摩擦；出线向下，后盖不夹线 / Shaft clears housing; wires route down without pinching |
| 2号连接件→花盘→轴 / Adapter → rotor → shaft | 连接件同心稳固；扁孔与轴匹配，花盘不擦壳 / Adapter is centered, flat shaft engages, rotor clears housing |
| Y1 花心→花盘 / Center → rotor | 正面贴合、不松脱 / Seats and stays in place |
| 灯板及帽→L2盖 / LED and cap → L2 lid | 灯对准孔，帽不顶住LED，不挡枝干通道；为平行于PCB的直角排针与母头留空间 / LED aligns; cap clears LED and stem passage; leave room for right-angle headers and female connectors parallel to the PCB |

配合过紧时，先清除毛边并检查孔补偿设置；保留整套模型的原比例。搬动时托住花盆。 / If a fit is too tight, remove burrs and check hole compensation before adjusting dimensions. Keep the overall scale unchanged and carry the flower by the pot.

通过干装后，回到 [中文装配步骤](README.md) 或 [English assembly guide](README.en.md)。
