# 装配检查表 / Build checklist

打印、装配完成后，按表逐项检查并记录结果。 / After printing and assembly, work through these checks and note the results.

## 本次成品 / This build

| 记录项 / Field | 填写 / Value |
| --- | --- |
| 日期、制作人 / Date, builder | |
| 模型版本、所用文件清单 / Model revision and file manifest | |
| 打印机、喷嘴、切片器 / Printer, nozzle, slicer | |
| 每件材料与层高、墙数、填充 / Material, layers, walls, infill per part | |
| 电机铭牌与减速比 / Motor voltage and gearbox | |
| 固件身份、源码版本 / Firmware identity and source revision | |
| Mac 芯片、macOS、应用版本 / Mac chip, macOS, app versions | |
| 安装器版本 / Installer version | |

## 操作与结果 / Actions and results

| 阶段 / Stage | 检查 / Check | 结果或现象 / Result or observation |
| --- | --- | --- |
| 干装 / Dry fit | 10 件齐全，孔、盖、卡扣、轴和 USB 对位 / All 10 parts fit; USB aligns | |
| 保持力 / Retention | 检查花心、透明灯帽、枝干与盆盖是否松动或容易脱落 / Separately record looseness or easy withdrawal of the center, cap and stem-to-lid joint | |
| 断电检查 / Unpowered | 5V、公共地、IN1–4、RGB逐针核对；无裸线短接 / Supply, grounds and signals checked | |
| 固件 / Firmware | `DEVICE INFO` → `FLOWER_COMBINED_V1 PWM=OK`；`PING` → `PONG` | |
| 空轴 / Bare shaft | `RUN LOW` 后实际转动；`STOP` 后实际停止 / Physical start/stop | |
| 提醒灯 / Light | `ATTENTION ON` 可见呼吸；`LED STATUS` 为 ON；`ATTENTION OFF` 后灭 / Observed breathing and off | |
| 超时 / Timeout | 单次 ON 无续期约6秒熄灯；单次 RUN 无续期约30秒停转 / 6 s LED and 30 s motor fail-safes | |
| 带花盘 / Rotor fitted | LOW短测：无擦壳、松脱或明显偏摆 / No rubbing, looseness or obvious wobble | |
| 五档 / Presets | 逐档 LOW/MEDIUM/HIGH/XHIGH/ULTRA；每档后STOP，记录异常 / Short runs, STOP between each | |
| 合盖 / Closed enclosure | 线不夹、USB可拔插、提醒灯清晰、驱动指示灯不混淆 / Clearances, access, visible light | |
| 安装 / Installation | 安装器识别应用和 USB 小花 / Installer detects the apps and USB flower | |
| 任务 / Task | 工作转、全部结束停 / Rotate while working, stop when all done | |
| 问题卡 / Question card | 等待亮灯，回答后相应提醒解除 / Waiting light clears after answer | |
| 并行 / Parallel | 一任务等待、另一任务工作时，可转且亮；全部结束停且灭 / Work + wait can rotate + light | |
| 收尾 / Finish | `IDLE`、`LED_STATE=OFF` 或联动任务已全部结束 / Idle/off, or all linked tasks finished | |

出现异常时，停转并断电排查，处理后再测试。记录问题和解决方法，方便之后维护。 / If something goes wrong, stop and disconnect power before making adjustments, then test again. Note the problem and fix for future maintenance.

返回 [中文教程](README.md) · [English guide](README.en.md)
