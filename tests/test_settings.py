"""Tests for piiscrub.settings — small persisted user preferences."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from piiscrub import settings


class SettingsTests(unittest.TestCase):
    def test_load_returns_defaults_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "does-not-exist.json"
            loaded = settings.load(path)
        self.assertEqual(loaded, settings.DEFAULTS)

    def test_save_then_load_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            settings.save(path, {"threshold": 0.25, "extra_terms": "Monty, Acme Corp"})
            loaded = settings.load(path)
        self.assertEqual(loaded["threshold"], 0.25)
        self.assertEqual(loaded["extra_terms"], "Monty, Acme Corp")

    def test_load_returns_defaults_on_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("not valid json {{{", encoding="utf-8")
            loaded = settings.load(path)
        self.assertEqual(loaded, settings.DEFAULTS)

    def test_all_entities_enabled_by_default(self):
        self.assertTrue(all(settings.DEFAULTS["enabled_entities"].values()))

    def test_disabling_an_entity_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            values = dict(settings.DEFAULTS)
            values["enabled_entities"] = {**settings.DEFAULTS["enabled_entities"], "PHONE_NUMBER": False}
            settings.save(path, values)
            loaded = settings.load(path)
        self.assertFalse(loaded["enabled_entities"]["PHONE_NUMBER"])

    def test_new_entity_type_defaults_enabled_for_an_old_settings_file(self):
        """A settings file saved before a new entity type existed shouldn't
        silently disable that type - it must fail open (enabled)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            settings.save(path, {"threshold": 0.4, "extra_terms": "",
                                  "enabled_entities": {"PERSON": True}})
            loaded = settings.load(path)
        self.assertTrue(loaded["enabled_entities"]["EMAIL_ADDRESS"])

    def test_theme_mode_defaults_to_system(self):
        self.assertEqual(settings.DEFAULTS["theme_mode"], "system")

    def test_theme_mode_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            settings.save(path, {**settings.DEFAULTS, "theme_mode": "dark"})
            loaded = settings.load(path)
        self.assertEqual(loaded["theme_mode"], "dark")

    def test_auto_scan_defaults_to_true(self):
        self.assertTrue(settings.DEFAULTS["auto_scan"])

    def test_auto_scan_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            settings.save(path, {**settings.DEFAULTS, "auto_scan": False})
            loaded = settings.load(path)
        self.assertFalse(loaded["auto_scan"])


if __name__ == "__main__":
    unittest.main()
