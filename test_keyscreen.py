#!/usr/bin/env python3
"""Tests for keyscreen's key handling.  Run:  python3 -m unittest -v"""
import importlib
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
TOGGLE = os.path.join(HERE, "keyscreen-toggle")


def load_keyscreen():
    """Import the extensionless `keyscreen` script as a module."""
    path = os.path.join(HERE, "keyscreen")
    loader = importlib.machinery.SourceFileLoader("keyscreen", path)
    spec = importlib.util.spec_from_loader("keyscreen", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


try:
    ks = load_keyscreen()
    e = ks.e
except Exception as exc:    # no gi / evdev / GTK on this machine
    raise unittest.SkipTest(f"cannot import keyscreen: {exc}")


class Recorder:
    """Stands in for the overlay: collects what the reader would display."""

    def __init__(self):
        self.events = []

    def __call__(self, text, typing):
        self.events.append((text, typing))

    @property
    def texts(self):
        return [text for text, _ in self.events]


def reading(reader_layout=None):
    recorder = Recorder()
    return ks.KeyReader(recorder, ks.Layout(reader_layout or "us")), recorder


def reap(proc):
    """Kill a helper process and reap it, so the tests leave no zombies or noise."""
    if proc.poll() is None:
        proc.kill()
    proc.wait()


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def needs_xkb(layout):
    if not layout.ok:
        raise unittest.SkipTest("libxkbcommon or its XKB data is unavailable")


class KeyReaderTests(unittest.TestCase):
    def test_plain_letter_is_typing(self):
        reader, rec = reading()
        reader.handle(e.KEY_A, 1)
        self.assertEqual(rec.events, [("a", True)])

    def test_autorepeat_is_ignored(self):
        reader, rec = reading()
        reader.handle(e.KEY_A, 1)
        reader.handle(e.KEY_A, 2)   # held down: evdev keeps sending 2s
        reader.handle(e.KEY_A, 2)
        self.assertEqual(rec.texts, ["a"])

    def test_release_is_ignored(self):
        reader, rec = reading()
        reader.handle(e.KEY_A, 1)
        reader.handle(e.KEY_A, 0)
        self.assertEqual(rec.texts, ["a"])

    def test_shift_types_uppercase(self):
        reader, rec = reading()
        reader.handle(e.KEY_LEFTSHIFT, 1)
        reader.handle(e.KEY_A, 1)
        self.assertEqual(rec.events, [("A", True)])

    def test_shifted_digit(self):
        reader, rec = reading()
        reader.handle(e.KEY_LEFTSHIFT, 1)
        reader.handle(e.KEY_1, 1)
        self.assertEqual(rec.texts, ["!"])

    def test_released_shift_stops_uppercase(self):
        reader, rec = reading()
        reader.handle(e.KEY_LEFTSHIFT, 1)
        reader.handle(e.KEY_A, 1)
        reader.handle(e.KEY_LEFTSHIFT, 0)
        reader.handle(e.KEY_B, 1)
        self.assertEqual(rec.events, [("A", True), ("b", True)])

    def test_combo_is_a_separate_item(self):
        reader, rec = reading()
        reader.handle(e.KEY_LEFTCTRL, 1)
        reader.handle(e.KEY_C, 1)
        self.assertEqual(rec.events, [("Ctrl+C", False)])

    def test_combo_keeps_shift_in_name(self):
        reader, rec = reading()
        reader.handle(e.KEY_LEFTCTRL, 1)
        reader.handle(e.KEY_LEFTSHIFT, 1)
        reader.handle(e.KEY_S, 1)
        self.assertEqual(rec.texts, ["Ctrl+Shift+S"])

    def test_special_key(self):
        reader, rec = reading()
        reader.handle(e.KEY_ENTER, 1)
        self.assertEqual(rec.events, [("⏎", False)])

    def test_space_is_visible(self):
        reader, rec = reading()
        reader.handle(e.KEY_SPACE, 1)
        self.assertEqual(rec.events, [("␣", True)])

    def test_modifier_alone_shows_nothing(self):
        reader, rec = reading()
        reader.handle(e.KEY_LEFTSHIFT, 1)
        reader.handle(e.KEY_LEFTSHIFT, 0)
        self.assertEqual(rec.events, [])


class LayoutTests(unittest.TestCase):
    def test_us_layout(self):
        layout = ks.Layout("us")
        needs_xkb(layout)
        self.assertEqual(layout.text(e.KEY_Q), "q")
        self.assertEqual(layout.base(e.KEY_Q), "q")
        layout.update(e.KEY_LEFTSHIFT, True)
        self.assertEqual(layout.text(e.KEY_Q), "Q")
        self.assertEqual(layout.base(e.KEY_Q), "q")

    def test_ctrl_does_not_pollute_text_state(self):
        layout = ks.Layout("us")
        needs_xkb(layout)
        layout.update(e.KEY_LEFTCTRL, True)
        self.assertEqual(layout.text(e.KEY_C), "c")

    def test_german_altgr(self):
        layout = ks.Layout("de")
        needs_xkb(layout)
        self.assertEqual(layout.text(e.KEY_Q), "q")
        layout.update(e.KEY_RIGHTALT, True)
        self.assertEqual(layout.text(e.KEY_Q), "@")

    def test_azerty_layout_through_reader(self):
        layout = ks.Layout("fr")
        needs_xkb(layout)
        self.assertEqual(layout.text(e.KEY_Q), "a")
        self.assertEqual(layout.text(e.KEY_A), "q")
        rec = Recorder()
        reader = ks.KeyReader(rec, layout)
        reader.handle(e.KEY_Q, 1)
        reader.handle(e.KEY_A, 1)
        self.assertEqual(rec.texts, ["a", "q"])

    def test_unknown_layout_falls_back_to_us(self):
        layout = ks.Layout("not-a-layout")
        rec = Recorder()
        reader = ks.KeyReader(rec, layout)
        reader.handle(e.KEY_A, 1)
        self.assertEqual(rec.texts, ["a"])

    def test_reader_without_layout(self):
        rec = Recorder()
        reader = ks.KeyReader(rec, None)
        reader.handle(e.KEY_A, 1)
        reader.handle(e.KEY_LEFTCTRL, 1)
        reader.handle(e.KEY_C, 1)
        self.assertEqual(rec.events, [("a", True), ("Ctrl+C", False)])


class TextFilterTests(unittest.TestCase):
    def test_printable_text(self):
        for text in ("a", "A", "1", "é", "@", "€"):
            self.assertTrue(ks.printable_text(text), text)
        for text in ("", "\r", "\n", "\t", "\b", " ", "\x00"):
            self.assertFalse(ks.printable_text(text), repr(text))


class SpecialKeyTests(unittest.TestCase):
    def test_specials_render_as_their_own_item(self):
        reader, rec = reading()
        reader.handle(e.KEY_A, 1)
        for code, expected in ((e.KEY_BACKSPACE, "⌫"), (e.KEY_TAB, "⇥"),
                               (e.KEY_ESC, "Esc"), (e.KEY_F5, "F5"),
                               (e.KEY_LEFT, "←"), (e.KEY_UP, "↑"),
                               (e.KEY_DELETE, "Del"), (e.KEY_PAGEUP, "PgUp")):
            rec.events.clear()
            reader.handle(code, 1)
            self.assertEqual(rec.events, [(expected, False)], expected)

    def test_keypad_types_without_a_layout(self):
        rec = Recorder()
        reader = ks.KeyReader(rec, None)
        reader.handle(e.KEY_KP1, 1)
        reader.handle(e.KEY_KPPLUS, 1)
        self.assertEqual(rec.events, [("1", True), ("+", True)])

    def test_keypad_key_name_without_a_layout(self):
        reader, rec = reading(None)
        reader.handle(e.KEY_LEFTCTRL, 1)
        reader.handle(e.KEY_KP1, 1)
        self.assertEqual(rec.events, [("Ctrl+1", False)])


class ComboTests(unittest.TestCase):
    def test_alt_tab_uses_the_tab_glyph(self):
        reader, rec = reading()
        reader.handle(e.KEY_LEFTALT, 1)
        reader.handle(e.KEY_TAB, 1)
        self.assertEqual(rec.events, [("Alt+⇥", False)])

    def test_modifier_order_is_stable(self):
        reader, rec = reading()
        for code in (e.KEY_LEFTMETA, e.KEY_LEFTCTRL, e.KEY_LEFTALT):
            reader.handle(code, 1)
        reader.handle(e.KEY_Q, 1)
        self.assertEqual(rec.events, [("Ctrl+Super+Alt+Q", False)])

    def test_typing_after_a_combo_starts_a_new_item(self):
        reader, rec = reading()
        reader.handle(e.KEY_LEFTCTRL, 1)
        reader.handle(e.KEY_C, 1)
        reader.handle(e.KEY_LEFTCTRL, 0)
        reader.handle(e.KEY_H, 1)
        reader.handle(e.KEY_I, 1)
        self.assertEqual(rec.events, [("Ctrl+C", False), ("h", True), ("i", True)])

    def test_held_modifier_repeats_do_not_duplicate_it(self):
        reader, rec = reading()
        reader.handle(e.KEY_LEFTCTRL, 1)
        reader.handle(e.KEY_LEFTCTRL, 2)
        reader.handle(e.KEY_LEFTCTRL, 2)
        reader.handle(e.KEY_V, 1)
        self.assertEqual(rec.events, [("Ctrl+V", False)])

    def test_caps_lock_uppercases_letters(self):
        layout = ks.Layout("us")
        needs_xkb(layout)
        # XKB applies Lock on a full press/release cycle, as a real caps press does.
        layout.update(e.KEY_CAPSLOCK, True)
        layout.update(e.KEY_CAPSLOCK, False)
        self.assertEqual(layout.text(e.KEY_A), "A")
        layout.update(e.KEY_CAPSLOCK, True)
        layout.update(e.KEY_CAPSLOCK, False)
        self.assertEqual(layout.text(e.KEY_A), "a")


class DetectionTests(unittest.TestCase):
    def test_active_layout_names_returns_a_pair(self):
        layout, variant = ks.active_layout_names()
        for value in (layout, variant):
            self.assertTrue(value is None or isinstance(value, str), value)


class ToggleTests(unittest.TestCase):
    """keyscreen-toggle must start one instance and stop that exact process."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="keyscreen-test-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        bindir = os.path.join(self.dir, "bin")
        self.run = os.path.join(self.dir, "run")
        os.makedirs(bindir)
        os.makedirs(self.run)
        stub = os.path.join(bindir, "keyscreen")
        with open(stub, "w") as fh:
            fh.write("#!/bin/sh\necho $$ > \"$XDG_RUNTIME_DIR/keyscreen.pid\"\n"
                     "while :; do sleep 0.1; done\n")
        os.chmod(stub, 0o755)
        self.pidfile = os.path.join(self.run, "keyscreen.pid")
        self.env = dict(os.environ,
                        PATH=bindir + ":" + os.environ.get("PATH", ""),
                        XDG_RUNTIME_DIR=self.run)

    def toggle(self):
        return subprocess.run([TOGGLE], env=self.env, capture_output=True,
                              timeout=15)

    def start_in_background(self, not_pid=None):
        proc = subprocess.Popen([TOGGLE], env=self.env,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        self.addCleanup(reap, proc)

        def started():
            pid = self.read_pid()
            return pid if pid and pid != not_pid else None

        pid = self.wait(started)
        self.assertIsNotNone(pid, "toggle did not start keyscreen")
        return proc, pid

    def wait(self, fn, timeout=8.0):
        end = time.time() + timeout
        while time.time() < end:
            value = fn()
            if value:
                return value
            time.sleep(0.05)
        return None

    def read_pid(self):
        try:
            with open(self.pidfile) as fh:
                return int(fh.read().strip())
        except (OSError, ValueError):
            return None

    def test_starts_then_stops(self):
        proc, pid = self.start_in_background()
        self.assertTrue(alive(pid))
        self.assertEqual(self.toggle().returncode, 0)
        # poll() also reaps the child, which kill(pid, 0) would still report alive
        self.assertTrue(self.wait(lambda: proc.poll() is not None),
                        "instance still running")
        self.assertFalse(os.path.exists(self.pidfile), "pid file left behind")

    def test_stale_pid_file_is_ignored(self):
        decoy = subprocess.Popen(["sleep", "30"])
        self.addCleanup(reap, decoy)
        with open(self.pidfile, "w") as fh:
            fh.write(f"{decoy.pid}\n")
        proc, pid = self.start_in_background(not_pid=decoy.pid)
        self.assertNotEqual(pid, decoy.pid)
        self.assertTrue(alive(decoy.pid), "toggle killed an unrelated process")


class CairoDependencyTests(unittest.TestCase):
    def test_missing_gi_cairo_gives_an_install_hint(self):
        """The cairo converters ship in python3-gi-cairo; without them GTK's
        callbacks die with a bare KeyError, so startup must name the package."""
        gi = importlib.import_module("gi")
        missing = ImportError("No module named 'gi._gi_cairo'")
        with unittest.mock.patch.object(gi, "require_foreign", side_effect=missing):
            with self.assertRaises(SystemExit) as caught:
                ks.require_cairo()
        self.assertIn("python3-gi-cairo", str(caught.exception.code))


if __name__ == "__main__":
    unittest.main()
