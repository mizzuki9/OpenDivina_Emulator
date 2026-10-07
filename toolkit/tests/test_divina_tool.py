import importlib.util
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "divina_tool.py"
SPEC = importlib.util.spec_from_file_location("divina_tool_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
DIVINA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIVINA)


class TgaRepairTests(unittest.TestCase):
    def test_repairs_headerless_rgba_from_container_dimensions(self):
        info = {"width": 128, "height": 128}
        raw = b"\x10\x20\x30\x40" * (128 * 128)

        repaired = DIVINA.repair_decoded_payload(raw, ".tg_", info)

        self.assertEqual(len(repaired), 18 + len(raw))
        self.assertTrue(DIVINA.has_tga_header(repaired, info))
        self.assertEqual(struct.unpack_from("<HH", repaired, 12), (128, 128))
        self.assertEqual(repaired[16:18], b"\x20\x28")
        # Container payload is R,G,B,A; TGA true-color order is B,G,R,A.
        self.assertEqual(repaired[18:], b"\x30\x20\x10\x40" * (128 * 128))

    def test_repairs_headerless_rgb_from_container_dimensions(self):
        info = {"width": 2, "height": 3}
        raw = b"\x10\x20\x30" * 6

        repaired = DIVINA.repair_decoded_payload(raw, ".tg_", info)

        self.assertTrue(DIVINA.has_tga_header(repaired, info))
        self.assertEqual(repaired[16:18], b"\x18\x20")
        self.assertEqual(repaired[18:], b"\x30\x20\x10" * 6)

    def test_preserves_existing_tga(self):
        info = {"width": 2, "height": 3}
        raw = DIVINA.build_tga_header(info, 2 * 3 * 4) + b"\0" * (2 * 3 * 4)

        self.assertIs(DIVINA.repair_decoded_payload(raw, ".tg_", info), raw)

    def test_rejects_uninferable_headerless_payload(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            DIVINA.repair_decoded_payload(
                b"\0" * 17,
                ".tg_",
                {"width": 128, "height": 128},
            )



if __name__ == "__main__":
    unittest.main()
