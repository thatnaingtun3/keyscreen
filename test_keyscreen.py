#!/usr/bin/env python3
"""Tests for keyscreen's key handling.  Run:  python3 -m unittest -v"""
import importlib.machinery
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


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


if __name__ == "__main__":
    unittest.main()
