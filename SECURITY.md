# Security

## Reporting a problem

If you find a security problem in KickForge (the device, its sources or the build tools in `source/`), please report it privately: open the repository's **Security** tab and click **Report a vulnerability**. Please do not open a public issue for it.

Say what you found, which version (release or commit) it affects and how to reproduce it. You will get an answer as soon as possible; KickForge is maintained by one person in their spare time.

## Supported versions

Only the latest release gets fixes.

## Checking a download

Each release has a `SHA256SUMS.txt` file. To check a download, put it in the same folder and run:

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing
```

You can also rebuild the device from `source/` (see the README): the result is the same file, byte for byte, as the one in `Bitwig-6.1.7`.

## What the device can do

KickForge runs inside Bitwig Studio as a Nitro device. It reads MIDI notes and its own parameters, and writes audio. It does not use the network or read or write files. A guard at its output turns any invalid value into silence.
