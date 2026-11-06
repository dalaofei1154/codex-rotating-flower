# 打印与干装 / Printing and dry fitting

下载 [无品牌雏菊带灯版模型](../../hardware/README.md)，按其最终清单选件。共 **10 件成品**；黑边是同一件的颜色部件，分色 STL 不应各自挪动、缩放或当作额外成品。 / Use the final manifest in the model package. There are **10 finished parts**. Black outlines are aligned color components, not extra finished parts.

## 已有配置 / Recorded settings

下表来自旧 10 月 31 日商家包、L2 说明及 P4 工程，不是对所有新打印机的成功保证，也不是证明教程照片全部来自这组文件。 / These are recorded project settings, not a universal printer profile or proof that every photographed part came from the exact release file.

**PLA，0.4 mm 喷嘴，0.20 mm 层高，单位 mm，100% 原尺寸。 / PLA, 0.4 mm nozzle, 0.20 mm layers, millimeters, 100% scale.**

| 成品 / Finished part | 数量 / Qty | 墙数 / Walls | 填充 / Infill | 颜色及记录 / Color and record |
| --- | --- | --- | --- | --- |
| 枝干含叶片 / Stem and leaves | 1 | 4 | 30% | 绿＋黑 / Green + black; P01 |
| 电机后盖 / Motor cover | 1 | 4 | 100% | 绿 / Green; P02 |
| 藏线盖 / Wire cover | 1 | 4 | 100% | 绿 / Green; P02 |
| 雏菊花盘 / Daisy rotor | 1 | 4 | 35% | 白＋黑 / White + black; P03 |
| 2号传动连接件 / Adapter 2 | 1 | 4 | 100% | 自选颜色 / Any color; P04, D16.95, no three holes |
| 花盆 / Pot | 1 | 4 | 40% | 自选颜色 / Any color; P05 |
| L2 带灯盆盖 / Light lid | 1 | 6 | 40% | 自选颜色 / Any color; **替换旧P06 / Replaces old P06** |
| 四套环电子托盘 / Electronics tray | 1 | 4 | 40% | 自选颜色 / Any color; P07 |
| Y1 花心 / Center | 1 | 4 | 100% | 黄＋黑 / Yellow + black; P08 |
| P4 透明灯帽 / Clear cap | 1 | 2 | 100%, zig-zag | 透明 PLA / Transparent PLA; D6.2 |

花盆红色或米色只影响外观；孔、卡扣与接口不可因配色改变。 / Red or beige changes appearance, not mating geometry.

## 切片前 / Before slicing

1. 在 Bambu Studio 用“打开项目”载入提供的 3MF，保持各色部件对齐。不要把它们逐个导入后自动排布。使用其他切片器时，导入分色 STL 必须保留共同坐标。 / Open the 3MF as a project. Preserve alignment of color components; do not auto-arrange separate color meshes.
2. 为实际打印机、喷嘴、耗材重新切片，并重新核对配色、温度、顶底层和支撑。现有 3MF 的预设和料槽编号不能代表你的机器。 / Reslice for your own printer, nozzle and filament. Recheck colors, temperatures, top/bottom layers and supports. Slot numbers are machine-specific.
3. 普通件保留已提供工程中的摆放与支撑屏蔽；先看逐层预览，确认没有悬空岛或误填的配合孔。 / Preserve project orientation and support painting where provided; inspect the layer preview for unsupported islands and blocked holes.
4. L2 盖正面朝下；背面短安装块及旋扣朝上。删除旧支架不等于切片支撑可全部关闭，旋扣的悬空处仍需在预览中检查。 / Print L2 top face down. Inspect the tabs for support needs; removal of permanent brackets does not imply support-free printing.
5. P4 灯帽帽面朝下、柱朝上；记录为无支撑、2 mm brim。工程预览色可能是紫色，实际耗材选透明 PLA。P4 工程中若排有四份，只需要每盆一件。 / Print the P4 head down, post up; recorded settings use no supports and a 2 mm brim. Use transparent PLA even if the preview is purple. Four copies in a plate are spares; one cap is used per flower.
6. 不要直接使用他人机器的 G-code。打印完成与“发送到打印机”是两个状态，记下实际结果。 / Do not use another machine's G-code. A submitted job is not evidence of a completed print.

## 装配前干装 / Dry fit before assembly

下表是每台复现件的检查目标，不表示作者现有接口全部通过。花心、透明灯帽、枝干与盆盖连接处已确认未用胶且不够稳固，列为后续模型迭代项。 / These are checks for each build, not claims that every existing interface has passed. The author confirmed unglued, insufficiently secure fits at the center, transparent cap and stem-to-lid joint; these are planned model improvements.

| 检查 / Check | 通过条件 / Pass condition |
| --- | --- |
| 托盘→盆体 / Tray → pot | 套环落到定位柱；USB 口对准盆侧开口 / Locating sleeves engage; USB aligns with side opening |
| 盆盖→盆体 / Lid → pot | 三处旋扣轻放可锁；没有蛮力弯折 / Tabs engage without force |
| 枝干→盆盖 / Stem → lid | 稳定落位，电机插头可先穿过方孔 / Stem seats; motor plug passes through first |
| 电机→安装腔 / Motor → housing | 轴孔不摩擦；出线向下，后盖不夹线 / Shaft clears housing; wires route down without pinching |
| 2号连接件→花盘→轴 / Adapter → rotor → shaft | 连接件同心稳固；扁孔与轴匹配，花盘不擦壳 / Adapter is centered, flat shaft engages, rotor clears housing |
| Y1 花心→花盘 / Center → rotor | 正面贴合、不松脱 / Seats and stays in place |
| 灯板及帽→L2盖 / LED and cap → L2 lid | 灯对准孔，帽不顶住LED，不挡枝干通道；为平行于PCB的直角排针与母头留空间 / LED aligns; cap clears LED and stem passage; leave room for right-angle headers and female connectors parallel to the PCB |

P4 沿用 P3 D6.2 的基本配合尺寸。作者确认 L2＋P4 已装好、转动亮灯正常，随后补充灯帽等三处无胶连接不够稳固；应以这条最新反馈记录当前保持力问题，而不只写“长期未验”。先逐接口检查并记录松动，不把补胶列为本版已验证工艺；搬动时托住盆体，不提枝干或花盘。不同打印机上的完整独立复现仍待验。配合过紧时先去毛边并检查打印补偿，不要对整套模型随意缩放。 / P4 uses the P3 D6.2 mating dimensions. The author confirmed working L2 + P4 motion and light, then reported insufficient retention at the three unglued interfaces. Record this current issue rather than only marking long-term retention untested. Check each interface and record looseness; adding glue is not a validated fix in this version. Carry the assembly by supporting the pot, not by the stem or rotor. Full independent reproduction on another printer remains unverified. Deburr and investigate fit before changing dimensions; do not scale the whole assembly arbitrarily.

通过干装后，回到 [中文装配步骤](README.md) 或 [English assembly guide](README.en.md)。
