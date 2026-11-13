<div align="center">
  <img src="docs/media/flower-mark.svg" width="64" alt="Rotating Flower" />
  <h1>Rotating Flower</h1>
  <p><strong>A little flower that moves with your AI.</strong></p>
  <p>It spins while your AI is working and lights up when it needs you.<br />Plug it into your Mac over USB, then get on with something else.</p>
  <p><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a></p>
  <p><a href="#watch">Watch</a> · <a href="#start">Get started</a> · <a href="#compatibility">Supported apps</a> · <a href="#models">Models</a> · <a href="#faq">FAQ</a></p>
</div>

<a id="watch"></a>
## Meet the flower

https://github.com/user-attachments/assets/f6ea34b5-76c4-4571-9aa7-4811f79ccf80

46 seconds with the real flower: spinning, different speeds, a reminder light, and work resuming after a reply. English narration with Chinese and English subtitles.

[Download the original video](docs/media/rotating-flower-demo-en-zh.mp4) · [中文页面](README.zh-CN.md#watch) · [Model redesign status](hardware/README.md)

## What it tells you

| Your AI task | Your flower |
| --- | --- |
| Working | The flower head spins |
| Paused for your answer or approval | The light pulses; the flower pauses too, unless another task is working |
| Some tasks work while another waits | The flower spins with the light on |
| Everything is done, with nothing waiting for you | The flower stops and the light turns off |

Each mode has a speed preset. When several tasks run together, the flower uses the fastest active preset. Some questions let work continue while you answer, so the light can come on while the flower keeps turning.

<a id="start"></a>
## Start with what you have

| Already have a flower? | Want to make one? |
| --- | --- |
| Connect it to your Mac and install the software. | Review the build guide; model downloads are paused during the redesign. |
| **[Install Mac software](#install)** | **[Build the daisy edition](docs/diy-guide/README.en.md)** |
| Start with an assembled flower running the combined motor + light firmware. | [Materials list](docs/diy-guide/BOM.md) · [Model status](#models) · [Wiring](docs/diy-guide/WIRING.md) |

<a id="compatibility"></a>
## Supported apps and versions

| App | Flower software | Mac support |
| --- | --- | --- |
| Codex | [v0.7.0 — available now](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.7.0) | Apple silicon · macOS 12+ |
| WorkBuddy | [v0.7.0 — available now](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.7.0) | Apple silicon · macOS 12+ |
| [DeepSeek Harness (DSH)](docs/dsh-macos.md) | [v0.7.0 — available now](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.7.0) | Apple silicon · macOS 13+ |
| [Qoder CN](docs/qodercn.md) | Source build / Windows trial package | Windows · macOS (source) |


<a id="install"></a>
### Install on your Mac

**[Download v0.7.0 for Apple silicon](https://github.com/dalaofei1154/rotating-flower/releases/download/v0.7.0/RotatingFlower-Mac-v0.7.0.zip)** · [Release notes](https://github.com/dalaofei1154/rotating-flower/releases/tag/v0.7.0)

1. Connect the flower with a USB data cable and extract the ZIP.
2. Double-click **安装小花.command** and follow the prompts.
3. Open and sign in to Codex, WorkBuddy or DSH, then start a task. Restart DSH after installation to load its plugin.

The installer includes Python and automatically enables installed apps. Open DSH at least once before installing so that it creates its profile. See the [installation guide](docs/open-release/INSTALL.md#en) for setup, upgrades and uninstalling, and the [DSH notes](docs/dsh-macos.md#english) for its tested version and behavior.

<a id="models"></a>
## Build the daisy edition

**CNY 53.92 for the listed materials**: CNY 22.42 for electronics and wiring, plus CNY 31.50 for 3D printing (210 g × CNY 0.15/g). Prices shared on November 6, 2026; USB cable, tools, glue, tape and shipping are extra. [Cost breakdown and parts list](docs/diy-guide/BOM.md#costs)

The previous daisy models have been withdrawn from the current version. Model downloads will return after the visible design is redrawn.

**模型重新设计中 / Models being redesigned**

**[Model availability](hardware/README.md)** · [Print files temporarily unavailable](hardware/README.md) · [Complete DIY materials](docs/open-release/README.en.md)

| Step | What to do |
| --- | --- |
| 1. Prepare | Check the [materials list](docs/diy-guide/BOM.md) and [print guide](docs/diy-guide/PRINTING.md) |
| 2. Assemble | Follow the [illustrated tutorial](docs/diy-guide/README.en.md) and [wiring table](docs/diy-guide/WIRING.md) |
| 3. Connect | Flash the [combined motor + light firmware](firmware/README.md), then install the Mac software |
| 4. Check | Run through the [build checklist](docs/diy-guide/CHECKLIST.md) |

You'll need to buy the electronics separately. The existing build and printing notes document the previous version and will be updated for the redesigned models.

My current build uses the L2 pot lid and P4 clear cap, and both rotation and lighting work. The flower center, clear cap and stem-to-lid connections are fitted without glue and are still a little loose. I'll keep improving those fits; for now, pick it up by the pot. [Build notes](docs/diy-guide/README.en.md)

## How it works

```mermaid
flowchart LR
    A[Codex / WorkBuddy / DSH] --> B[Mac bridge: local task state]
    B -->|USB| C[ESP32: combined firmware]
    C --> D[Motor + attention light]
```

The Mac software reads local task status and sends commands to the ESP32 over USB. The controller runs the motor and the reminder light.

| Explore | Entry |
| --- | --- |
| Source for the download | [v0.7.0 source](https://github.com/dalaofei1154/rotating-flower/tree/v0.7.0/m1) |
| DSH setup | [Adapter notes](docs/dsh-macos.md) |
| Qoder CN setup | [Adapter notes](docs/qodercn.md) |
| Hardware and firmware | [Model files](hardware/README.md) · [Combined firmware](firmware/README.md) |
| Build updates | [DIY release notes](docs/open-release/RELEASE_NOTES.md) |

<a id="faq"></a>
## A few practical questions

**Does it need an internet connection or an API key?** The flower connects over USB and uses your apps' local task status. It needs no separate API key and sends no task records to a project server. Use your usual account to sign in to each AI app. [More about local data](docs/open-release/INSTALL.md#data)

**Are model files available?** Model downloads are temporarily unavailable while the visible design is redrawn independently. [Redesign status](hardware/README.md)

## Share your build

If you make one, I'd love to see it. Post a photo in [Issues](https://github.com/dalaofei1154/rotating-flower/issues), along with your printer and filament. Fit improvements and bug reports are welcome too. [Contribution guide](CONTRIBUTING.md)

Made by **Flynn**, with help from AI tools for modeling and code. [Inspiration and acknowledgements](docs/open-release/ATTRIBUTION.md). This is a personal project. Formerly `codex-rotating-flower`.

## License

| Material | License |
| --- | --- |
| Software and firmware | MIT |
| Written guides | CC BY 4.0 |
| Models, photos, renders and videos | CC BY-NC-SA 4.0 |

See [LICENSES.md](LICENSES.md) for the scope of each license and third-party credits. Please contact me about commercial use of the models or media.
