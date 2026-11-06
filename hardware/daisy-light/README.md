# 雏菊带灯版 · 打印与可编辑模型

[按图下载与3D组成动画 / Visual downloads and 3D animation](VISUAL_GUIDE.md)

**简体中文** · [English](README.en.md)

这套文件对应无品牌雏菊、L2 带灯旋扣盖和 P4 透明灯帽。**每套 10 件成品。**2026-11-05，作者确认 L2＋P4 已安装完成，转动及亮灯正常。

目录包括 13 个分色 STL、9 个 3MF 打印工程、10 个 Blender 可编辑网格场景。旧无灯 T1 盖、N1 花形、较松花心、其他连接件试档和品牌标志花盘均未收录。


作者补充确认：花心、透明灯帽、枝干与盆盖连接处均未用胶，目前连接不够稳固，列为后续模型迭代项。转动和亮灯正常只代表功能通过，不代表这些接口的保持力已达标；复现时逐处检查，搬动时托住盆体。

## 先选文件，再切片

优先用 Bambu Studio 的“打开项目”载入 `print/` 中的 3MF，按自己的打印机、喷嘴及实际耗材重新切片。工程不含 G-code，不可跳过切片预览。以下工程仍保留原样排版：

- `P02.3mf` 有后盖与藏线盖各 1 件，正好是一套的需求。
- **`P06_2pcs.3mf` 有 2 个盖子，一套只需 1 个。**可在切片器中删去一个重复实例，勿改变剩余零件比例或几何。
- **`P09_4pcs.3mf` 有 4 个灯帽，一套只需 1 个。**按需保留数量。

若把 9 个工程全部照原盘打印，会得到 **14 件，含 1 个备用盖和 3 个备用灯帽**。工程中的原料槽和色签只是历史配置，尤其灯帽工程的紫色标签不代表应使用紫色耗材；灯帽实际使用透明 PLA。

双色 STL 的两份文件组成同一个零件，必须作为同一对象的多个部件载入、保持共享坐标和对齐，不要分别自动居中、落盘或把黑色描边当成额外零件粘贴。没有多色能力的打印设备需自行制定分色工艺；本包未验证其他分色方案。

## 一套零件与工艺

全部单位为 mm，100% 原比例，主体 PLA、0.4 mm 喷嘴、0.20 mm 层高。以下是现有试打配置；支撑、顶底层和支撑屏蔽体以对应 3MF 为准，不统一覆盖。

| ID / 打印工程 | 成品与版本 | 一套数量 | 颜色 | 墙数 | 填充 |
| --- | --- | ---: | --- | ---: | ---: |
| P01 | B 枝干及两叶 | 1 | 绿＋黑 | 4 | 30% |
| P02 → P02A | 实心 3 号电机后盖 | 1 | 绿 | 4 | 100% |
| P02 → P02B | W1 7.1 mm 藏线盖 | 1 | 绿 | 4 | 100% |
| P03 | 约 120 mm 雏菊，盘厚 6 mm、黑边宽 1.6 mm | 1 | 白＋黑 | 4 | 35% |
| P04 | 2 号无三孔连接件，凸台 Ø16.95×4 mm，轴孔 5.1×3.1 mm | 1 | 米色 | 4 | 100% |
| P05 | P1 一体封底盆 | 1 | 米色 | 4 | 40% |
| P06_2pcs | L2 带灯短安装块旋扣盖，灯孔 Ø6.4 mm | 1 | 米色 | 6 | 40% |
| P07 | 完整电子托盘，四套环内径 6.75 mm | 1 | 米色 | 4 | 40% |
| P08 | Y1 最紧档 D22.00 花心 | 1 | 黄＋黑 | 4 | 100% |
| P09_4pcs | P4 灯帽：柱径 6.2 mm、柱长 6 mm、帽 Ø8×2.4 mm | 1 | 透明 PLA | 2 | 100% |

P04、P07 原工程包含轴孔或套环的支撑屏蔽体，应保留。P06 正面朝下，去除打印支撑时勿剪掉旋扣止退弹片。P09 帽面朝下、柱向上，无支撑，沿用 2 mm brim；打印后清除毛边再试配。不同打印机、材料和孔补偿设置会影响配合，不能把名义尺寸视为通用公差保证。

## 装配兼容

- 这里的 P04 替代旧 R2/S2 三孔连接件；不要把 10 月 29 日旧整包中的连接件混入。
- P08 使用已选最紧档 D22.00，实物背面编号不清楚，按文件选择。
- P06 沿用这套封底盆的三处旋扣；对齐缺口放入，从上方看顺时针约 30° 到限位，反转打开。它替代旧无灯 T1 盖，不与早期旧盆专用 L2 盖混淆。
- 枝干、电机后盖、藏线盖、花盘和花心保持原有选定接口。电机、板卡与灯板依教程固定；独立 Type-C 面框不在本包内。
- 完成后检查空轴起停、带花盘低速及各档转动、灯亮/灭、线束收纳和合盖运行。制作步骤见[图文教程](../../docs/diy-guide/README.md)。

## 可编辑文件的性质

`source/P01.blend` 到 `source/P09.blend` 按上述 ID 对应零件（P02 拆为 A/B）。它们是可直接打开并编辑顶点/网格的 Blender 文件，**不是 STEP 实体或保留全部建模历史的参数化 CAD**。

- P02A、P02B、P04、P05、P06、P07、P08：从原工程仅提取已选网格及其世界变换；未选试档、隐藏旧件、参考电子器件、相机、脚本和绝对路径均未带入。网格与变换经另存、重新打开后比对不变。
- P01、P03、P09：这些分支原为 Python 生成，没有相应原生 `.blend`。此处以发布 STL 建立可编辑网格场景，保留坐标和三角面。来源类型在清单中明确记录。
- 部分原场景保留装配世界坐标，因此打开后零件不一定在原点。打印优先使用 STL/3MF；不要把可编辑场景的坐标误当成一套新排版。

本次没有重跑历史参数化构建链，也没有对改动后的模型作配合保证。原始生成过程的路径和源文件哈希记录在 `manifest.json`，用于追溯；那些历史目录不作为下载包的执行依赖。

## 验证和许可

已核对 32 个模型/工程文件的 SHA256；STL 和 3MF 保持原字节，13 个 STL 的闭合边检查通过；10 个 Blender 场景重新打开后选定网格和变换保持一致。3MF 的实际盘面数量经解析确认，无内置 G-code。作者在 2026-11-05 进一步确认带灯整机已装好且转动、亮灯正常；长期耐久与其他打印设备独立复现仍未验证。

模型使用 CC BY-NC-SA 4.0，适用文件和署名/商用联系以随包许可文件及项目 `LICENSES.md` 为准。原文件来源、版本和检查字段见 [manifest.json](manifest.json)，模型文件校验值见 [SHA256SUMS.txt](SHA256SUMS.txt)。

English: This daisy light set contains 10 physical parts, 13 color meshes, 9 unsliced print projects and 10 editable Blender mesh scenes. The lid project contains two copies and the cap project four; one of each is needed per flower. Reslice for your printer and actual PLA, preserve multi-color alignment and support blockers, and use transparent PLA for the cap despite the retained color labels. The author confirmed assembly, rotation and light operation on 2026-11-05; long-term durability and independent reproduction are not established. Editable scenes are mesh data, not a parametric CAD history. Model terms: CC BY-NC-SA 4.0; consult the included license.
