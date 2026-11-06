# Daisy with attention light: models and printing

[简体中文](README.md) · **English** · [Choose models by picture](VISUAL_GUIDE.md)

One flower needs **10 printed parts**, including the L2 light lid and P4 clear cap. The set contains 9 3MF print projects, 13 color-separated STL meshes and 10 editable Blender mesh files.

## Before printing

Open the files in `print/` as projects in Bambu Studio. Choose your printer, nozzle and filament, reslice, then check the layer preview.

- `P02.3mf` contains one motor cover and one wire cover. Use both.
- `P06_2pcs.3mf` contains two lids. Use one per flower.
- `P09_4pcs.3mf` contains four light caps. Use one per flower.

Printing all plates as supplied gives 14 parts, including one spare lid and three spare caps. Adjust the quantities while keeping the original scale. Update the filament slots and color labels for your materials; use transparent PLA for the light cap.

For two-color STL parts, import both meshes as parts of the same object and preserve their common coordinates. The black outlines print together with their main bodies.

## Parts and print settings

**PLA · 0.4 mm nozzle · 0.20 mm layers · millimeters · 100% scale**

The table lists the project colors. Choose your own colors if you like; my finished flower has a red pot, ivory petals and lid, green leaves, a yellow center and black outlines.

| ID / project | Selected part and version | Per flower | Color | Walls | Infill |
| --- | --- | ---: | --- | ---: | ---: |
| P01 | B stem and leaves | 1 | Green + black | 4 | 30% |
| P02 → P02A | Motor rear cover, solid variant 3 | 1 | Green | 4 | 100% |
| P02 → P02B | W1 full wire cover, 7.1 mm tongue | 1 | Green | 4 | 100% |
| P03 | Approximately 120 mm daisy; 6 mm body, 1.6 mm black edge | 1 | White + black | 4 | 35% |
| P04 | Adapter 2, no three flange holes; boss Ø16.95 × 4 mm, shaft bore 5.1 × 3.1 mm | 1 | Beige | 4 | 100% |
| P05 | P1 pot with integral bottom | 1 | Beige | 4 | 40% |
| P06_2pcs | L2 light lid with short board mount; Ø6.4 mm light opening | 1 | Beige | 6 | 40% |
| P07 | Electronics tray, four Ø6.75 mm sleeves | 1 | Beige | 4 | 40% |
| P08 | Y1 center cap, selected tightest D22.00 fit | 1 | Yellow + black | 4 | 100% |
| P09_4pcs | P4 diffuser cap: Ø6.2 mm × 6 mm post, Ø8 mm × 2.4 mm head | 1 | Transparent PLA | 2 | 100% |


Keep the support blockers for the P04 and P07 bores. Print P06 face-down and leave the twist-lock detent intact when removing supports. Print P09 head-down, post-up, with no supports and a 2 mm brim. Remove burrs before testing each fit.

## Assembly

- Use the P04 adapter and P08 D22.00 center from this set.
- Align the three P06 lid tabs with the pot openings, insert the lid and turn about 30° clockwise from above until the stop. Reverse to open.
- My flower center, clear cap and stem-to-lid joint are fitted without glue and are still a little loose. Check each fit and carry the flower by the pot.
- Test the bare motor shaft first, then fit the daisy and check LOW followed by the other presets. Tidy the wires, close the lid and test again.

Follow the [illustrated build guide](../../docs/diy-guide/README.en.md) for the full assembly.

## Edit the models

The Blender files in `source/` use the part IDs above; P02 is split into P02A and P02B. They contain editable vertices and meshes, without a parametric CAD feature history. Some parts retain assembly coordinates and may sit away from the origin. Use `stl/` or `print/` for printing, and test the fit after changing an interface.

## Files and license

[manifest.json](manifest.json) maps parts to their specifications and files. Use [SHA256SUMS.txt](SHA256SUMS.txt) to check downloaded files.

Models use [CC BY-NC-SA 4.0](../LICENSE.md): credit the project, use them noncommercially and share adaptations under the same license.
