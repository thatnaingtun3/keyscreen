# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Keyscreen is a single-file Python 3 / GTK3 app that shows pressed keys in a transparent, click-through, always-on-top overlay. It is a screenkey replacement that works on Wayland. It is shipped as a `.deb` for Debian/Ubuntu-family distros.

## Commands

```sh
./keyscreen                                   # run from source (Ctrl+C to quit)
./keyscreen --position top-left --size 20     # try options; see main() for the full list
python3 -m py_compile keyscreen               # syntax check (there is no test suite or linter)
./build-deb.sh                                # builds dist/keyscreen_<version>_all.deb
sudo apt install ./dist/keyscreen_*_all.deb   # install the build locally
```

To run it, your user must be in the `input` group. Otherwise it exits with "No readable keyboard found".

## Architecture

All runtime logic is in `keyscreen` (an extensionless Python script):

- **Why it works on Wayland.** Wayland won't let an app read global keystrokes, so `KeyReader` reads `/dev/input` directly through `python3-evdev`. It runs in a daemon thread, selects on every device that looks like a keyboard, and rescans every 3 s to pick up hot-plugged keyboards. The overlay window forces `GDK_BACKEND=x11` (XWayland) so it can be positioned and kept on top. This must stay set before GTK is imported.
- **Thread boundary.** `KeyReader` turns raw key codes into display strings (`CHARS` / `SPECIAL` / `MODS` tables, with modifiers ordered by `MOD_ORDER`). It hands them to the GTK main loop via `GLib.idle_add(overlay.add, ...)`. Never touch GTK objects from the reader thread.
- **Overlay.** `Overlay` is a `Gtk.Window` of type POPUP with an empty input shape, which makes it click-through. Plain typing is merged into the last item. Combos (for example `Ctrl+C`) become separate items. `relayout()` resizes the window to fit the text and positions it from `--position` / `--margin` on the primary monitor. `tick()` (every 50 ms) fades it out after `--timeout`. `on_draw` paints the rounded background with cairo.

Packaging is separate from the code:

- `keyscreen-toggle` is what the app-menu entry (`keyscreen.desktop`) launches. It kills a running instance (matching `bin/keyscreen( |$)`) or else starts one, so the same icon toggles it on and off. The pattern must not match `keyscreen-toggle` itself.
- `packaging/DEBIAN/control` is the single source of truth for the version, which `build-deb.sh` reads. `packaging/DEBIAN/postinst` adds the installing user (`SUDO_USER` or `PKEXEC_UID`) to the `input` group. That change only takes effect after the user logs out and back in.
- `build-deb.sh` assembles the files into a temp tree with installed paths (`/usr/bin`, `/usr/share/applications`) and runs `dpkg-deb --root-owner-group`. If you add a new installed file, add it to the script.

## Releasing

1. Bump `Version:` in `packaging/DEBIAN/control`.
2. Run `./build-deb.sh`, then commit and push.
3. Run `gh release create v<version> dist/keyscreen_<version>_all.deb`.

`dist/` and `*.deb` are gitignored. The `.deb` is distributed only through GitHub Releases.
