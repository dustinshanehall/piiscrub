"""Tests for piiscrub.core redaction / leak-check behavior."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from piiscrub import core


class LeakCheckTests(unittest.TestCase):
    def test_no_leak_when_a_coincidental_substring_exists_elsewhere(self):
        """A short value (e.g. a postal code) that also happens to appear
        embedded inside unrelated text (a reference number) must not block
        the save when the only real, detected occurrence was ticked and
        redacted. The leaked-looking substring was never itself a finding."""
        text = "Ship to zip 90210. See attached file REF-90210-INV for billing."
        findings = [
            core.Finding(12, 17, "POSTAL_CODE", 0.6, "90210", selected=True),
        ]
        result = core.redact(text, findings)
        self.assertTrue(result.ok, f"unexpected leaks: {result.leaks}")

    def test_leak_when_some_occurrences_of_a_value_are_unticked(self):
        """If a value has two findings and only one is selected, the
        unselected occurrence really does survive in the output and must be
        reported."""
        text = "Order date: 2026-09-04. Ship date: 2026-09-04."
        findings = [
            core.Finding(12, 22, "DATE_TIME", 0.85, "2026-09-04", selected=True),
            core.Finding(35, 45, "DATE_TIME", 0.85, "2026-09-04", selected=False),
        ]
        result = core.redact(text, findings)
        self.assertFalse(result.ok)
        self.assertIn("2026-09-04", result.leaks)

    def test_leak_when_a_bare_surname_survives_a_missed_occurrence(self):
        """Defense in depth: if a PERSON full-name occurrence is redacted but
        a bare surname elsewhere in the document was never detected as its
        own finding at all, that must still be reported as a leak."""
        text = "Priya Raghunathan called. Later, Raghunathan called again."
        findings = [
            core.Finding(0, 18, "PERSON", 1.0, "Priya Raghunathan", selected=True),
        ]
        result = core.redact(text, findings)
        self.assertFalse(result.ok)
        self.assertIn("raghunathan", [leak.lower() for leak in result.leaks])


class EntityConfigTests(unittest.TestCase):
    def test_date_time_is_not_detected(self):
        self.assertNotIn("DATE_TIME", core.ENTITIES)
        self.assertNotIn("DATE_TIME", core.supported_entities())


class EntityFilterTests(unittest.TestCase):
    TEXT = "Priya Raghunathan called about the invoice. Reach her at 555-123-4567."

    def test_disabled_entity_is_not_detected(self):
        enabled = [e for e in core.supported_entities() if e != "PHONE_NUMBER"]
        findings = core.analyze(self.TEXT, entities=enabled)
        self.assertFalse(any(f.entity_type == "PHONE_NUMBER" for f in findings))

    def test_enabled_entity_still_detected(self):
        enabled = [e for e in core.supported_entities() if e != "PHONE_NUMBER"]
        findings = core.analyze(self.TEXT, entities=enabled)
        self.assertTrue(any(f.entity_type == "PERSON" for f in findings))

    def test_default_entities_is_all_supported(self):
        findings = core.analyze(self.TEXT)
        self.assertTrue(any(f.entity_type == "PHONE_NUMBER" for f in findings))


if __name__ == "__main__":
    unittest.main()
