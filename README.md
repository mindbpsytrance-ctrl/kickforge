# KickForge

A kick drum synth for Bitwig Studio, made especially for psytrance kicks and built as a native Nitro device. You draw the kick's pitch and amp envelopes as curves, layer a click on top, and finish it with drive, EQ and a compressor.

## Demo

https://github.com/user-attachments/assets/ff9ad27a-414e-44da-a19f-265ee4cfe7b6

*1 min 34, with sound. Also in [`media/kickforge-demo.mp4`](media/kickforge-demo.mp4).*

*Français plus bas.*

## Features

- **Pitch and amp curves**: Bitwig's own curve editors draw the kick's pitch sweep and level, over its live waveform. Each curve's length is set in milliseconds or as a note value synced to the tempo. Modulators reach the note value too.
- **Click**: white, pink, brown, blue, violet or grey noise, crackle, or a simulated 909, 808 or 606 hi-hat. The click has its own **PITCH** and **AMP** curves, edited on the main screen. Its pitch works like a transposed sample, ±24 semitones. You can also set its level, length, delay (0 to 5 ms, to sit it on the body's transient), tone and low cut. The CLICK screen shows the body in grey behind the click.
- **Tune** from C0 to C1 with a notched fader. Choose **FIX** to keep the set pitch or **KEY** to follow the played note. Keytrack moves the fundamental only.
- **Phase**: the start phase of the body, which leaves the click as it is.
- **FX**: a mids-only drive, a three-band EQ (80 Hz shelf, 400 Hz bell, 5 kHz shelf, ±15 dB) and a compressor, last in the chain. One switch bypasses all three.
- **Master** tab: an oscilloscope of the whole kick, after the drive, EQ and compressor.
- **DARK** and **LIGHT** panel finishes.

## Requirements

- Bitwig Studio **6.1.7** or later (the device uses compressed Nitro code). It was built and tested on Linux with 6.1.7 only.
- **Patchbay Mod Loader** with **Framework: Nitro Devices** (called **Custom Nitro Registration** in older releases). Bitwig does not load custom Nitro devices on its own.

## Install

1. Download a [Patchbay Mod Loader release](https://github.com/shaboogen-dev/Patchbay/releases) that supports your Bitwig version and follow `INSTALL.md` in the ZIP. On Windows and macOS you can use the [Patchbay Launcher](https://github.com/arius77R/patchbay-launcher/releases) instead.
2. Download this repository and keep the `Bitwig-6.1.7` folder somewhere permanent.
3. Close Bitwig. In Patchbay, enable **Framework: Nitro Devices**, open **Tools → Device Folders** and select the `Bitwig-6.1.7` folder. Click **Load** to start Bitwig.
4. KickForge appears in the device browser under Synth. To get the presets, copy the `Presets` folder's files into `Bitwig Studio/Library/Presets/KickForge`.

Register only one copy of KickForge in Patchbay: every build has the same device ID.

## Updating

1. Close Bitwig and replace `Bitwig-6.1.7/KickForge.bwdevice` with the new one. Copy the new presets too.
2. In projects that already use KickForge, **delete the device and insert it again** (or drag a preset onto an empty slot). Bitwig keeps the waveform drawings a device was created with: loading a preset onto it does not update them, so an old device shows old or empty screens.
3. Do not save presets from an old device before that: they would keep its old drawings.

Your own presets also hold the drawings of the version they were saved with. To bring them up to date, run from `source/` (both tools need the document codec, see *Build from source*, and back up each preset they change; without `--apply` they only say what they would do):

```bash
python3 tools/repair_presets.py --device ../Bitwig-6.1.7/KickForge.bwdevice --apply
```

From 1.1.0 to 1.1.1, the Pitch and Amp note values (Sync mode) became new parameters, so modulators can reach them. Projects and presets saved with 1.1.0 load them at 1/8. To convert your presets, also run `python3 tools/convert_div_presets.py --apply`.

## Presets

Six kicks by MindB: **Anvil** (the device's default sound), **Molten Core**, **Iron Pulse**, **Hammerfall**, **Spark Strike** and **Cold Steel**.

## Tabs

| Tab | What it holds |
| --- | --- |
| MASTER | Tune fader, FIX/KEY, the kick's length, Phase, Level, oscilloscope |
| PITCH | Pitch curve; length (TIME/SYNC), Pitch amount, Time scale, vertical Scale |
| AMP | Amp curve; length (TIME/SYNC), Velocity, Time scale, Lin/dB |
| CLICK | Click curves (PITCH/AMP), noise source, Level, Delay, Length, Tone, Low Cut |
| FX | FX ON/OFF, Drive, Comp, EQ Low/Mid/High |

In a curve editor, drag a point to move it, double-click to add or delete a point, and drag a segment to bend it. The device's maximize button opens a larger editor.

## Build from source

The device's sources are in [`source/`](source): the panel and graph (`build_kick.py`, `theme.py`), the DSP in Nitro (`kick_voice.nitro`, `kick_phase.nitro`, `kick_display.nitro.in`), the waveform shader (`kick_wave.sksl.in`) and the panel art (`knobs/`). Building them gives the same `KickForge.bwdevice` as the one in `Bitwig-6.1.7`.

1. Set up [polarity/bitwig-devices-blueprint](https://github.com/polarity/bitwig-devices-blueprint) as its [BUILD guide](https://github.com/polarity/bitwig-devices-blueprint/blob/main/docs/BUILD.md) says: its Python environment, the Nitro bridge (it uses the compiler from your own Bitwig installation) and the document codec. KickForge looks for it in `~/Patchbay/bitwig-devices-blueprint`; set `KICKFORGE_BLUEPRINT` if it is somewhere else.
2. Build:

   ```bash
   cd source
   <blueprint>/.venv/bin/python build_kick.py --out build/KickForge.bwdevice
   ```

The rendered panel art is included (`source/knobs/out`), so Blender is not needed to build. To change the art, see [`source/knobs/README.md`](source/knobs/README.md): it is rendered with Blender, then cut into SVGs with Python 3 (Pillow, NumPy, OpenImageIO). The legends use the [Inter](https://rsms.me/inter/) font (SIL Open Font License, not included); set `KICKFORGE_FONTS` to its folder.

Contributions are welcome: open an issue or a pull request.

## License

Copyright (C) 2026 MindB.

KickForge (the device, its sources, the presets and the demo) is free software: you can redistribute it and/or modify it under the terms of the [GNU General Public License version 3](LICENSE) (GPL-3.0) as published by the Free Software Foundation. It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the license for details.

Release 1.0.0 was published under CC BY-NC 4.0; later releases are under GPL-3.0.

---

## Français

KickForge est un synthé de kick pour Bitwig Studio, pensé pour les kicks psytrance, sous forme de device Nitro natif. On dessine en courbes le pitch et l'amplitude du kick, on ajoute un clic par-dessus (bruits, hi-hats 909/808/606 simulés, avec ses propres courbes PITCH et AMP), puis on finit avec le drive, l'EQ trois bandes et le compresseur.

**Démo :** la [vidéo](media/kickforge-demo.mp4) en haut de la page.

**Prérequis :** Bitwig Studio 6.1.7 ou plus récent. Il faut aussi Patchbay Mod Loader avec **Framework: Nitro Devices** (anciennement Custom Nitro Registration). Testé seulement sous Linux avec Bitwig 6.1.7.

**Installation :**
1. Installe Patchbay en suivant les étapes ci-dessus.
2. Dans **Tools → Device Folders**, sélectionne le dossier `Bitwig-6.1.7`, puis lance Bitwig avec **Load**.
3. Copie les presets dans `Bitwig Studio/Library/Presets/KickForge`.

**Mise à jour :** remplace le fichier `KickForge.bwdevice` et les presets, puis, dans les projets existants, **supprime KickForge et réinsère-le**. Recharger un preset ne met pas à jour les affichages d'un device déjà présent. Depuis la 1.1.0, la note des longueurs Pitch et Amp (mode Sync) revient à 1/8 dans les anciens projets et presets ; `source/tools/convert_div_presets.py --apply` convertit tes presets, et `source/tools/repair_presets.py --device ../Bitwig-6.1.7/KickForge.bwdevice --apply` met à jour leurs affichages (voir « Updating »).

**Sources :** dans le dossier `source/`. Pour compiler le device, voir « Build from source » plus haut. Les contributions sont les bienvenues (issues et pull requests).

**Licence :** GNU GPL version 3 (GPL-3.0). Tu peux utiliser, partager, modifier et même vendre KickForge, à condition de garder la même licence, de fournir les sources et de citer MindB. La version 1.0.0 était sous CC BY-NC 4.0.
