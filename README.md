# Keyscreen

Show the keys you press on screen — a small overlay in the corner, made for screen recordings and tutorials. Works on **Wayland** and X11 (Ubuntu / Debian / Linux Mint / Pop!_OS).

## Install (easy way)

1. Download `keyscreen_x.x_all.deb` from the [Releases](../../releases) page.
2. Install it:
   ```
   cd ~/Downloads
   sudo apt install ./keyscreen_*_all.deb
   ```
3. **Log out and log back in** (one time only — this activates keyboard access).
4. Press the Super key, type **Keyscreen**, and click it. Click it again to stop.

Uninstall: `sudo apt remove keyscreen`

## Options

Run from a terminal for custom settings (`keyscreen -h` prints this list):

```
keyscreen --position bottom-right   # bottom-left, bottom, top-right, top-left, top, center
keyscreen --size 16                 # text size
keyscreen --max-chars 20            # how many characters to show
keyscreen --margin 40               # gap from the screen edge
keyscreen --timeout 2.5             # seconds before it fades
keyscreen --opacity 0.8             # background opacity 0-1
keyscreen --layout de               # keyboard layout (default: auto-detect)
keyscreen --variant nodeadkeys      # layout variant, used with --layout
```

Key names follow your real keyboard layout: AZERTY and QWERTZ keys, Shifted
symbols and AltGr combinations such as `@` or `€` show what you actually typed.
The layout is detected from the running X keymap (through `setxkbmap`); use
`--layout` if it picks the wrong one, for example on a Wayland session without
XWayland.

## Requirements

`python3`, `python3-evdev`, `python3-gi`, `python3-gi-cairo`, `python3-cairo`, `gir1.2-gtk-3.0` (installed automatically with the .deb). Your user must be in the `input` group (the .deb installer adds it).

Keyboard-layout support additionally uses `libxkbcommon` (present on any normal desktop; without it keyscreen falls back to a US key map).

> Note: being in the `input` group lets programs you run read the keyboard. Only install where that is acceptable.

## Build the .deb yourself

```
./build-deb.sh          # creates dist/keyscreen_<version>_all.deb
```

To release a new version, bump `Version:` in `packaging/DEBIAN/control`, then build.

## Project files

| File | Purpose |
|---|---|
| `keyscreen` | Main program (Python) |
| `keyscreen-toggle` | Start/stop helper used by the app icon |
| `keyscreen.desktop` | App-menu entry |
| `packaging/DEBIAN/` | .deb metadata and install script |
| `build-deb.sh` | Builds the .deb |

## License

MIT — see [LICENSE](LICENSE).
