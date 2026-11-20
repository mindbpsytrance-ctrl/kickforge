# KickForge

A kick drum synth for Bitwig Studio, made especially for psytrance kicks and built as a native Nitro device. You draw the kick's pitch and amp envelopes as curves, layer a click on top, and finish it with drive, EQ and a compressor.

## Demo

https://github.com/user-attachments/assets/ff9ad27a-414e-44da-a19f-265ee4cfe7b6

*1 min 34, with sound. Also in [`media/kickforge-demo.mp4`](media/kickforge-demo.mp4).*

*Français plus bas.*

## Features

- **Pitch and amp curves**: Bitwig's own curve editors draw the kick's pitch sweep and level, over its live waveform. Each curve's length is set in milliseconds or as a note value synced to the tempo.
- **Click**: white, pink, brown, blue, violet or grey noise, crackle, or a simulated 909, 808 or 606 hi-hat. The click has its own **PITCH** and **AMP** curves, edited on the main screen. Its pitch works like a transposed sample, ±24 semitones. You can also set its level, length, delay (to sit it on the body's transient), tone and low cut.
- **Tune** from C0 to C1 with a notched fader. Choose **FIX** to keep the set pitch or **KEY** to follow the played note. Keytrack moves the fundamental only.
- **Phase**: the start phase of the body, which leaves the click as it is.
- **FX**: a mids-only drive, a three-band EQ (80 Hz shelf, 400 Hz bell, 5 kHz shelf, ±15 dB) and a compressor, last in the chain. One switch bypasses all three.
- **Master** tab: an oscilloscope of the whole kick.
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

## License

[Creative Commons Attribution-NonCommercial 4.0 International](LICENSE) (CC BY-NC 4.0). You may share and adapt KickForge and its presets with credit to MindB, but not for commercial purposes.

---

## Français

KickForge est un synthé de kick pour Bitwig Studio, pensé pour les kicks psytrance, sous forme de device Nitro natif. On dessine en courbes le pitch et l'amplitude du kick, on ajoute un clic par-dessus (bruits, hi-hats 909/808/606 simulés, avec ses propres courbes PITCH et AMP), puis on finit avec le drive, l'EQ trois bandes et le compresseur.

**Démo :** la [vidéo](media/kickforge-demo.mp4) en haut de la page.

**Prérequis :** Bitwig Studio 6.1.7 ou plus récent. Il faut aussi Patchbay Mod Loader avec **Framework: Nitro Devices** (anciennement Custom Nitro Registration). Testé seulement sous Linux avec Bitwig 6.1.7.

**Installation :**
1. Installe Patchbay en suivant les étapes ci-dessus.
2. Dans **Tools → Device Folders**, sélectionne le dossier `Bitwig-6.1.7`, puis lance Bitwig avec **Load**.
3. Copie les presets dans `Bitwig Studio/Library/Presets/KickForge`.

**Licence :** CC BY-NC 4.0. Le partage et la modification sont autorisés en citant MindB, sans usage commercial.
