# Daisy with attention light: models and printing

[按图下载与3D组成动画 / Visual downloads and 3D animation](VISUAL_GUIDE.md)

[简体中文](README.md) · **English**

This set uses the unbranded daisy, the L2 twist-lock lid and the P4 transparent light cap. **One flower needs 10 physical parts.** On 2026-11-05, the author confirmed that the L2 lid and P4 cap were assembled and both rotation and light operation worked normally.

The package contains 13 STL color meshes, 9 unsliced 3MF projects and 10 editable Blender mesh scenes. It excludes the old unlit T1 lid, unselected fit trials, the N1 flower experiment, third-party manual models and OpenAI/WorkBuddy logo rotors.


The author additionally confirmed that the flower center, transparent cap and stem-to-lid joint use no glue and are not sufficiently secure in the current build. Improving their retention is a planned model iteration. Working rotation and light do not establish secure mechanical retention; check each fit and support the pot when moving the flower.

## Open and slice

Prefer the projects in `print/`: open them as projects in Bambu Studio, then reslice for your printer, nozzle and actual filament. The files contain no G-code. Inspect the sliced model before printing and do not reuse historical printer or filament-slot mappings without checking them.

The original plate layouts have been preserved:

- `P02.3mf` contains one motor rear cover and one wire cover. Both are needed.
- **`P06_2pcs.3mf` contains two lids. One flower needs one lid.** Remove one duplicate instance in your slicer if desired; keep the remaining geometry and scale unchanged.
- **`P09_4pcs.3mf` contains four light caps. One flower needs one cap.** Keep only the quantity needed.

Printing all nine projects exactly as provided yields **14 physical parts**, including one spare lid and three spare caps. The retained filament labels are historical settings. In particular, the purple label in the cap project does not indicate purple material: use **transparent PLA** for the cap.

For two-color STL parts, import both meshes as parts of the same object and preserve their common coordinates. Do not center or drop them onto the bed separately. The black outline is part of the printed object, not a separate decoration to glue on. Other color-production methods on single-material printers have not been validated by this package.

## Bill of printed parts

Use millimeters, 100% scale, PLA, a 0.4 mm nozzle and 0.20 mm layers. These are the existing trial settings. Preserve the project-specific top/bottom layers, supports and support blockers; do not replace all settings with one generic profile.

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

P04 and P07 include support blockers for their bores; keep them. Print P06 face-down and remove sacrificial supports carefully without cutting off the twist-lock detent. P09 prints head-down, post-up, with no supports and a 2 mm brim. Remove burrs before testing the fit. Printer accuracy, PLA and XY/hole compensation affect fit; the nominal dimensions are not universal tolerance guarantees.

## Compatibility and assembly

1. Use P04 adapter 2 from this set. It supersedes the older R2/S2 adapter with three flange holes.
2. Use the D22.00 center cap in P08. The printed trial numbers were not legible, so choose by filename rather than by a number on the physical part.
3. P06 mates with this set's P1 pot. Align its three tabs with the openings, insert it, then turn it approximately 30° clockwise when viewed from above until the stop. Reverse to open. This is the current light-enabled L2, not an older lid for a legacy pot.
4. The selected stem, rear cover, wire cover, daisy and center cap retain their existing interfaces. Fix the motor, boards and light module as described in the [illustrated English assembly guide](../../docs/diy-guide/README.en.md). A separate Type-C bezel is not included.
5. Before closing the pot, test the bare shaft, low-speed rotation with the daisy installed, all operating modes, stop, and light on/off. Route the wires clear of moving parts and the lid tabs, then repeat the test with the lid closed.

## Editable mesh scenes

The files in `source/` correspond to the IDs above; P02 is split into P02A and P02B. They can be opened in Blender and edited at the vertex/mesh level. They are **not STEP solids or parametric CAD feature histories**.

- P02A, P02B, P04, P05, P06, P07 and P08 contain only the selected mesh objects and world transforms extracted from the original Blender files. Unselected variants, old hidden objects, electronics references, scripts and absolute private paths have been excluded. Mesh vertices, faces and world transforms were compared before and after saving and reopening.
- P01, P03 and P09 were originally generated with Python and had no matching native Blender scene. Their editable scenes were created from the exact released STL files, preserving mesh coordinates and triangle faces. This distinction is recorded in the manifest.
- Some original objects retain assembly coordinates and may be away from the origin. Use the STL/3MF files for printing; an editable source scene is not a new print layout.

The complete historical parameterized generation chain has not been rerun or packaged as a standalone build. Source paths and hashes in the manifest are provenance records, not executable dependencies of the download. Editing a mesh requires renewed fit checks.

## Verification and license

All 32 model/project files have SHA256 checksums. STL and 3MF copies are byte-identical to the selected source files. All 13 STL meshes passed closed-edge checks. All 10 Blender scenes were reopened and their geometry/transforms compared. The 3MF build-item counts were inspected and no G-code is embedded. The author confirmed assembled rotation and light behavior on 2026-11-05. Long-term durability and independent reproduction on other printers remain unverified.

Model files are licensed under **CC BY-NC-SA 4.0**, subject to the scope and attribution in the included [model license](../LICENSE.md). See [manifest.json](manifest.json) for file provenance and validation, and [SHA256SUMS.txt](SHA256SUMS.txt) for model checksums. The repository's software MIT license does not automatically apply to these models.
