import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("reader_under_test", Path(__file__).resolve().parents[1] / "cgdata_reader.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)

class TableTests(unittest.TestCase):
    def test_signed_empty_indices(self):
        for version, fmt in [(4, "<i"), (5, "<h")]:
            self.assertEqual(reader._read_last_index(reader.Reader(struct.pack(fmt, -1)), version), -1)

    def test_signed_nonempty_indices(self):
        for version, fmt in [(4, "<i"), (5, "<h")]:
            self.assertEqual(reader._read_last_index(reader.Reader(struct.pack(fmt, 2)), version), 2)

    def test_header_reads_container_only_once(self):
        def string(value):
            return struct.pack("<I", len(value)) + value
        data = struct.pack("<I", 1024) + string(b"newdiac") + struct.pack("<ii", 5, 0)
        data += string(b"") + struct.pack("<ii", 0, 0) + string(b"") + string(b"")
        data += struct.pack("<iBh", 950, 0, -1)
        with patch.object(reader.CGameData, "_read_container_objects", autospec=True) as call:
            reader.CGameData(data)
        self.assertEqual(call.call_count, 1)

    def test_named_empty_table_exports_header(self):
        table = SimpleNamespace(table_name="synthetic", column_names=["id"], items=[], to_csv_rows=lambda: [["id"]])
        with tempfile.TemporaryDirectory() as tmp:
            reader.export_csv(SimpleNamespace(tables=[table]), Path(tmp))
            self.assertEqual((Path(tmp) / "synthetic.csv").read_text(encoding="utf-8-sig"), "id\n")

if __name__ == "__main__":
    unittest.main()
