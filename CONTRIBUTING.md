# Contributing

[简体中文](#中文说明)

Made a flower, found a problem or have an improvement? Open an issue or pull request.

## Report a problem

Tell us what you expected, what happened, and how to reproduce it. Include the details relevant to the problem:

- **Software:** macOS version, AI app version, flower software version and a short log excerpt.
- **Electronics:** board, motor and driver models, wiring, power supply and firmware version.
- **Printed parts:** part ID, printer, filament, nozzle, layer height and slicer settings. Photos and measured dimensions help with fit problems.

Remove private information from logs and screenshots before sharing them.

## Change the code or models

Describe what you changed and how you checked it. For Mac software changes, run:

```sh
python3 -m unittest discover -s m1/integrated -p 'test_*.py' -v
python3 -m unittest discover -s m1 -p 'test_*.py' -v
node --test m1/dsh/*.test.mjs
```

The observer tests require a current Node.js LTS release. These automated checks use simulated task and device data; report physical USB testing separately, including the app version and board used.

For firmware changes, include the board and motor you used and the behavior you observed. For model changes, include the part ID, dimensions you changed, and a photo of a test print if available.

Code uses MIT, written guides use CC BY 4.0, and the models and media use CC BY-NC-SA 4.0. Credit any sources you use and describe your modifications. See [license details](LICENSES.md).

## 中文说明

欢迎分享你做的小花、反馈问题，或提交改进。

### 反馈问题

说清楚预期结果、实际现象和复现步骤，再补充与问题有关的信息：

- **软件问题：** macOS、AI 应用和小花软件版本，以及一小段相关日志。
- **电路问题：** 控制板、电机和驱动板型号，接线、供电方式和固件版本。
- **打印问题：** 零件编号、打印机、耗材、喷嘴、层高和切片设置。接口松紧问题最好附上照片和测量尺寸。

分享日志和截图前，请删去私人信息。

### 修改代码或模型

提交时说明改了什么、怎么检查的。修改 Mac 程序后，运行上面的 Python 和 Node 测试命令（observer 测试使用当前 Node.js LTS）。自动化测试使用模拟任务和设备数据；实机 USB 验证请另外记录应用版本、控制板和观察到的行为。修改固件时，写明使用的控制板、电机和实际表现。修改模型时，写明零件编号、调整的尺寸，有试打照片的话也一起附上。

代码采用 MIT，教程文字采用 CC BY 4.0，模型与图片、视频采用 CC BY-NC-SA 4.0。使用其他来源的内容时保留署名，并说明自己的修改。[查看许可范围](LICENSES.md)
