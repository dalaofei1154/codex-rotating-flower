# 装配验收表 / Build verification checklist

复制本页，为每一盆小花填一份。串口回应和目视观察分别记录；“有回应”不能代替“实物正常转动”。 / Copy this page for each build. Record serial responses and physical observations separately.

## 作者已有记录 / Existing author verification

| 日期 / Date | 记录 / Evidence | 范围 / Scope |
| --- | --- | --- |
| 2026-11-04 | v0.6.0 在作者 Apple 芯片 Mac 双击安装，Codex＋WorkBuddy 并行、问题等待、回答后解除提醒有状态与控制板回执 / Installer and dual-source task/wait/resume checks | 作者本机；不等于另一台 Mac 首次安装 / Maintainer's Mac, not independent installation |
| 2026-11-05 | 新组装设备完成五档、STOP/IDLE、灯 ON/OFF、6秒灯超时、30秒电机超时串口检查，作者确认转动和呼吸灯正常 / New device passed serial checks and observed rotation/breathing light | 短时运行；未测实际 RPM、温升或耐久 / Short runs, no RPM, thermal or endurance measurement |
| 2026-11-05 | 作者在本次整理中确认 L2＋P4 已装好，转动和亮灯正常 / Author confirmed assembled L2 + P4 with working rotation and light | 作者实装确认；不是异机独立复现 / Author's assembled build, not independent reproduction |
| 2026-11-05 | 作者补充商品图确认 KY-016 四根预焊直角公排针版，排针平行 PCB / Product photo identifies four pre-soldered right-angle male pins parallel to the PCB | 外形与采购版本核对，不是共阴电气实测 / Physical variant identification, not an electrical polarity test |

**当前已知配合问题：** 作者确认花心、透明灯帽、枝干与盆盖连接处均未用胶，连接不够稳固，后续拟迭代模型。旋转与亮灯已通过，不代表这些接口保持力通过。 / **Known fit issue:** The author confirmed that the center, transparent cap and stem-to-lid joint are unglued and do not hold securely enough. Model improvements are planned. Working rotation and light do not mean these retention checks have passed.

长期运行、真实系统审批弹窗、异机首次安装、不同打印机的整套复现仍保留待验。 / Long runs, real system permission prompts, first installation on another Mac and full reproduction on another printer remain unverified.

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
| 保持力 / Retention | 分别记录花心、透明灯帽、枝干与盆盖是否松动/易脱；不以功能正常代替稳固检查 / Separately record looseness or easy withdrawal of the center, cap and stem-to-lid joint | |
| 断电检查 / Unpowered | 5V、公共地、IN1–4、RGB逐针核对；无裸线短接 / Supply, grounds and signals checked | |
| 固件 / Firmware | `DEVICE INFO` → `FLOWER_COMBINED_V1 PWM=OK`；`PING` → `PONG` | |
| 空轴 / Bare shaft | `RUN LOW` 后实际转动；`STOP` 后实际停止 / Physical start/stop | |
| 提醒灯 / Light | `ATTENTION ON` 可见呼吸；`LED STATUS` 为 ON；`ATTENTION OFF` 后灭 / Observed breathing and off | |
| 超时 / Timeout | 单次 ON 无续期约6秒熄灯；单次 RUN 无续期约30秒停转 / 6 s LED and 30 s motor fail-safes | |
| 带花盘 / Rotor fitted | LOW短测：无擦壳、松脱或明显偏摆 / No rubbing, looseness or obvious wobble | |
| 五档 / Presets | 逐档 LOW/MEDIUM/HIGH/XHIGH/ULTRA；每档后STOP，记录异常 / Short runs, STOP between each | |
| 合盖 / Closed enclosure | 线不夹、USB可拔插、提醒灯清晰、驱动指示灯不混淆 / Clearances, access, visible light | |
| 安装 / Installation | v0.6.0 来源和新USB协议检查均通过 / Source readiness and fresh USB checks pass | |
| 任务 / Task | 工作转、全部结束停 / Rotate while working, stop when all done | |
| 问题卡 / Question card | 等待亮灯，回答后相应提醒解除 / Waiting light clears after answer | |
| 并行 / Parallel | 一任务等待、另一任务工作时，可转且亮；全部结束停且灭 / Work + wait can rotate + light | |
| 收尾 / Finish | `IDLE`、`LED_STATE=OFF` 或联动任务已全部结束 / Idle/off, or all linked tasks finished | |

未测试项目填“未测”，不要勾为通过。出现异常先记录复现步骤，停止转动并断电排查，再复测受影响项目。 / Mark untested items as untested. Record failures, stop and disconnect power before making corrections, then repeat the affected checks.

返回 [中文教程](README.md) · [English guide](README.en.md)
