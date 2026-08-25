"""Security regression tests for the tracked ESPHome example.

Purpose: Prevent device credentials from being committed to wallbox.yaml.
Input/Output: Reads tracked YAML/text files and reports unittest assertions.
Invariants: Real values live only in ignored esphome/secrets.yaml.
Debugging: Run `python3 -m unittest discover -s tests -p 'test_*.py' -v`.
"""

from pathlib import Path
import json
import re
import struct
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ESPHomeSecretConfigurationTests(unittest.TestCase):
    """Verify that every credential-bearing ESPHome option uses !secret."""

    def test_wallbox_uses_named_secret_references(self) -> None:
        wallbox = (REPOSITORY_ROOT / "esphome" / "wallbox.yaml").read_text(
            encoding="utf-8"
        )

        expected_references = (
            "key: !secret api_encryption_key",
            "password: !secret ota_password",
            "password: !secret fallback_ap_password",
        )
        for reference in expected_references:
            self.assertIn(reference, wallbox)

        self.assertIsNone(re.search(r"(?:key|password):\s*[\"'][^\"']+[\"']", wallbox))

    def test_local_secret_file_is_ignored_and_example_exists(self) -> None:
        gitignore = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("esphome/secrets.yaml", gitignore)
        self.assertTrue((REPOSITORY_ROOT / "esphome" / "secrets.example.yaml").is_file())

    def test_hacs_brand_icon_is_a_square_256_pixel_png(self) -> None:
        """Keep the local brand asset required by HACS publication checks."""
        icon_path = (
            REPOSITORY_ROOT
            / "custom_components"
            / "wallbox_billing"
            / "brand"
            / "icon.png"
        )
        icon_data = icon_path.read_bytes()

        self.assertEqual(b"\x89PNG\r\n\x1a\n", icon_data[:8])
        self.assertEqual((256, 256), struct.unpack(">II", icon_data[16:24]))

    def test_manifest_declares_recorder_dependency_in_hassfest_order(self) -> None:
        """Declare every imported Home Assistant component explicitly."""
        manifest_path = (
            REPOSITORY_ROOT
            / "custom_components"
            / "wallbox_billing"
            / "manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertIn("recorder", manifest["dependencies"])
        expected_order = ["domain", "name", *sorted(set(manifest) - {"domain", "name"})]
        self.assertEqual(expected_order, list(manifest))


if __name__ == "__main__":
    unittest.main()
