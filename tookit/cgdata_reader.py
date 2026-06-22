#!/usr/bin/env python3
"""
.sum file parser — convert table data files to CSV / JSON.

Usage:
    python cgdata_reader.py path/to/file.sum
    python cgdata_reader.py path/to/file.sum --csv   (CSV output)
    python cgdata_reader.py path/to/file.sum --json  (JSON output)
    python cgdata_reader.py path/to/file.sum --all   (both formats)
"""

import struct
import sys
import os
import json
import csv
from pathlib import Path
import zlib

# ── Binary reader ──

class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def tell(self):
        return self.pos

    def seek(self, pos):
        self.pos = pos

    def skip(self, n):
        self.pos += n

    def read(self, n) -> bytes:
        if self.pos + n > len(self.data):
            raise EOFError(f"Tried to read {n} bytes at pos {self.pos}, but only {len(self.data) - self.pos} left")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def u8(self) -> int:
        v = self.data[self.pos]
        self.pos += 1
        return v

    def u16(self) -> int:
        v = struct.unpack_from("<H", self.data, self.pos)[0]
        self.pos += 2
        return v

    def s16(self) -> int:
        v = struct.unpack_from("<h", self.data, self.pos)[0]
        self.pos += 2
        return v

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return v

    def s32(self) -> int:
        v = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return v

    def s64(self) -> int:
        v = struct.unpack_from("<q", self.data, self.pos)[0]
        self.pos += 8
        return v

    def f32(self) -> float:
        v = struct.unpack_from("<f", self.data, self.pos)[0]
        self.pos += 4
        return v


# ── CBString reader ──

def read_cbstring(r: Reader) -> str:
    """
    CBString: int32 length + Big5 bytes
    """
    length = r.s32()
    if length <= 0:
        return ""
    raw = r.read(length)
    try:
        return raw.decode("big5", errors="replace")
    except:
        return raw.decode("utf-8", errors="replace")


# ── CGameData parser ──

class CGameData:
    """Root parser for .sum files"""

    def __init__(self, data: bytes):
        self.r = Reader(data)
        self.version = 0
        self.signature = ""
        self.timestamp = ""
        self.tables = []
        self.raw_tables = []

        self._parse_header()
        if self.signature == "newdiac":
            self._read_container_objects()

    def _parse_header(self):
        r = self.r

        # Format (from CGameData::Save/Load):
        # [int32]    FileSize (optional, written by CBFile when param_2=true)
        # [CBString] Signature ("newdiac")
        # [int32]    Version
        # [int32]    this+0x40 field
        # [CBString] Timestamp
        # ... version-specific fields ...

        first_u32 = r.u32()
        sig_len = r.u32()

        # Heuristic: if first_u32 looks like a CBString length (<100), it IS the signature length
        if 0 < first_u32 < 100:
            self.signature = r.read(first_u32).decode("ascii", errors="replace")
        else:
            # Format: [int32] FileSize + [CBString] Signature
            self.file_size = first_u32
            if 0 < sig_len < 100:
                self.signature = r.read(sig_len).decode("ascii", errors="replace")
            else:
                return

        if self.signature != "newdiac":
            return

        self.version = r.s32()
        self.field_40 = r.s32()
        self.timestamp = read_cbstring(r)

        if self.version > 2:
            self.extra1 = r.s32()
            self.extra2 = r.s32()
        else:
            self.extra1 = 0
            self.extra2 = 0

        if self.version < 5:
            # Older: CBString class names for each table type
            table_name_count = r.s32()
            self._table_name_map = []
            for _ in range(table_name_count):
                name = read_cbstring(r)
                type_val = r.s32()
                self._table_name_map.append((name, type_val))
        else:
            # Newer (v5+): Map key/value strings, then container data
            self.map_key = read_cbstring(r)
            self.map_value = read_cbstring(r)
            self.some_const = r.s32()  # default 950 (Big5 cp)
            self.has_flag = r.u8()

        # Read table container via CGContainer::Read
        self._read_container_objects()

        # Checksum block after container (path in CGameData::Load param_2)
        if self.r.tell() < len(self.r.data):
            remaining = len(self.r.data) - self.r.tell()
            if remaining >= 20 + 1:
                self.checksums = [self.r.u32() for _ in range(5)]
                is_checksummed = self.r.u8()
                if is_checksummed and remaining > 20 + 1 + 400:
                    self.r.skip(400)
                return
        self.checksums = []

    def _read_container_objects(self):
        """
        Read container items. The stored value is max_index;
        C code uses do-while (i <= max_index), so we iterate max_index+1 times.
        """
        r = self.r
        ver = self.version

        try:
            if ver >= 5:
                max_index = r.u16()
            else:
                max_index = r.u32()
        except (EOFError, IndexError, struct.error):
            return

        for slot_idx in range(max_index + 1):
            try:
                if r.tell() >= len(r.data):
                    break
                if ver < 4:
                    present = r.u32()
                    has_data = present != 0
                else:
                    present = r.u8()
                    has_data = present != 0

                if not has_data:
                    self.raw_tables.append(None)
                    continue

                if ver < 5:
                    class_name = read_cbstring(r)
                    obj = self._create_object_by_name(class_name, slot_idx)
                else:
                    type_id = r.u8()
                    obj = self._create_object_by_type(type_id, slot_idx)

                self.raw_tables.append(obj)
            except (EOFError, IndexError, struct.error):
                break

    def _create_object_by_type(self, type_id: int, slot_idx: int):
        """Create typed object from type ID byte (v5+)"""
        if type_id == 0x01:
            return CGBase()
        elif type_id == 0x02:
            return CGString(read_cbstring(self.r))
        elif type_id == 0x03:
            return CGNumber(self.r.s32())
        elif type_id == 0x04:
            return CGBigNumber(self.r.s64())
        elif type_id == 0x05:
            return CGFloat(self.r.f32())
        elif type_id == 0x06:
            return CGContainer("CGContainer", self.r, self.version)
        elif type_id == 0x07:
            try:
                tbl = CGTable(self.r, self.version)
                self.tables.append(tbl)
                return tbl
            except Exception as e:
                import sys as _sys
                _sys.stderr.write(f"  [WARN] Skip CGTable at slot {slot_idx}: {e}\n")
                _sys.stderr.flush()
                return CGBase()
        elif type_id == 0x08:
            try:
                return CGRecord(self.r, self.version)
            except Exception as e:
                import sys as _sys
                _sys.stderr.write(f"  [WARN] Skip CGRecord at slot {slot_idx}: {e}\n")
                _sys.stderr.flush()
                return CGBase()
        else:
            import sys as _sys
            _sys.stderr.write(f"  [WARN] Unknown type_id={type_id} at slot {slot_idx}\n")
            _sys.stderr.flush()
            return CGBase()

    def _create_object_by_name(self, name: str, slot_idx: int):
        """Create object by CBString class name (pre-v5)"""
        if name == "CGTable":
            tbl = CGTable(self.r, self.version)
            self.tables.append(tbl)
            return tbl
        elif name == "CGRecord":
            return CGRecord(self.r, self.version)
        elif name == "CGNumber":
            return CGNumber(self.r.s32())
        elif name == "CGBigNumber":
            return CGBigNumber(self.r.s64())
        elif name == "CGFloat":
            return CGFloat(self.r.f32())
        elif name == "CGString":
            return CGString(read_cbstring(self.r))
        elif name == "CGContainer":
            return CGContainer(name, self.r, self.version)
        else:
            return CGBase()


# ── CGBase subclasses ──

class CGBase:
    def __init__(self):
        self.type_name = "CGBase"

    def value(self):
        return None

    def __repr__(self):
        return f"<{self.type_name}>"


class CGNumber(CGBase):
    def __init__(self, val: int):
        super().__init__()
        self.type_name = "CGNumber"
        self._val = val

    def value(self):
        return self._val


class CGBigNumber(CGBase):
    def __init__(self, val: int):
        super().__init__()
        self.type_name = "CGBigNumber"
        self._val = val

    def value(self):
        return self._val


class CGFloat(CGBase):
    def __init__(self, val: float):
        super().__init__()
        self.type_name = "CGFloat"
        self._val = val

    def value(self):
        return self._val


class CGString(CGBase):
    def __init__(self, val: str):
        super().__init__()
        self.type_name = "CGString"
        self._val = val

    def value(self):
        return self._val


class CGContainer(CGBase):
    def __init__(self, name: str, r: Reader, version: int):
        super().__init__()
        self.type_name = name
        self.items = []
        self._read_container(r, version)

    def _read_container(self, r: Reader, ver: int):
        if ver >= 5:
            max_index = r.u16()
        else:
            max_index = r.u32()

        for _ in range(max_index + 1):
            try:
                if ver < 4:
                    present = r.u32()
                    has_data = present != 0
                else:
                    present = r.u8()
                    has_data = present != 0

                if not has_data:
                    self.items.append(None)
                    continue

                if ver < 5:
                    class_name = read_cbstring(r)
                    obj = self._create_named(class_name, r, ver)
                else:
                    type_id = r.u8()
                    obj = self._create_typed(type_id, r, ver)

                self.items.append(obj)
            except (EOFError, IndexError, struct.error):
                break

    def _create_typed(self, type_id: int, r: Reader, ver: int):
        if type_id == 0x01:
            return CGBase()
        elif type_id == 0x02:
            return CGString(read_cbstring(r))
        elif type_id == 0x03:
            return CGNumber(r.s32())
        elif type_id == 0x04:
            return CGBigNumber(r.s64())
        elif type_id == 0x05:
            return CGFloat(r.f32())
        elif type_id == 0x06:
            return CGContainer("CGContainer", r, ver)
        elif type_id == 0x07:
            return CGTable(r, ver)
        elif type_id == 0x08:
            return CGRecord(r, ver)
        else:
            return CGBase()

    def _create_named(self, name: str, r: Reader, ver: int):
        if name == "CGTable":
            return CGTable(r, ver)
        elif name == "CGRecord":
            return CGRecord(r, ver)
        elif name == "CGNumber":
            return CGNumber(r.s32())
        elif name == "CGBigNumber":
            return CGBigNumber(r.s64())
        elif name == "CGFloat":
            return CGFloat(r.f32())
        elif name == "CGString":
            return CGString(read_cbstring(r))
        elif name == "CGContainer":
            return CGContainer(name, r, ver)
        else:
            return CGBase()

    def value(self):
        return [item.value() if item else None for item in self.items]


class CGRecord(CGContainer):
    """A single row of data = container of cells"""

    def __init__(self, r: Reader, version: int):
        super().__init__("CGRecord", r, version)

    def to_dict(self, column_names: list = None) -> dict:
        """Export record as dict with optional column names"""
        result = {}
        for idx, item in enumerate(self.items):
            col_name = column_names[idx] if column_names and idx < len(column_names) else f"col{idx}"
            result[col_name] = item.value() if item else None
        return result


class CGTable(CGContainer):
    """Table = collection of CGRecords + metadata"""

    def __init__(self, r: Reader, version: int):
        save_pos = r.tell()
        super().__init__("CGTable", r, version)

        try:
            self.table_name = read_cbstring(r)
            self.type_val = r.s32()
            self.digit_base = r.s32()

            if version > 0:
                self.sheet_name = read_cbstring(r)
            else:
                self.sheet_name = ""

            if version > 4:
                self.is_text_table = r.u8()
                self.text_table_name = read_cbstring(r)
            else:
                self.is_text_table = 0
                self.text_table_name = ""

            # Cell name map (column name -> column index)
            self.column_names = []
            if version > 4:
                count = r.u16()
                for _ in range(count):
                    col_name = read_cbstring(r)
                    col_idx = r.u16()
                    self.column_names.append(col_name)
        except Exception:
            # Metadata read failed -> table is invalid
            if r.tell() < len(r.data):
                import sys as _sys
                _sys.stderr.write(f"  [WARN] Failed to read table metadata at pos {r.tell()}, "
                                  f"discarding table ({len(self.items)} rows)\n")
                _sys.stderr.flush()
            self.items = []
            self.table_name = ""
            self.type_val = 0
            self.digit_base = 0
            self.sheet_name = ""
            self.is_text_table = 0
            self.text_table_name = ""
            self.column_names = []

    def to_csv_rows(self) -> list:
        """Return CSV rows: [header_row, data_row1, data_row2, ...]"""
        rows = []

        if self.column_names:
            header = self.column_names[:]
        else:
            max_cells = 0
            for rec in self.items:
                if rec and isinstance(rec, CGRecord) and rec.items:
                    max_cells = max(max_cells, len(rec.items))
            header = [f"col{i}" for i in range(max_cells)]
        header = ["id"] + header
        rows.append(header)

        for idx, rec in enumerate(self.items):
            if rec is None or not isinstance(rec, CGRecord):
                continue
            row_id = self.type_val * self.digit_base + idx
            row = [str(row_id)]
            for col_idx, cell in enumerate(rec.items):
                if cell is None:
                    row.append("")
                else:
                    val = cell.value()
                    if val is None:
                        row.append("")
                    elif isinstance(val, str):
                        row.append(val)
                    elif isinstance(val, float):
                        row.append(f"{val:.6g}")
                    else:
                        row.append(str(val))
            rows.append(row)

        return rows


# ── Main flow ──


def load_sum(path: str) -> CGameData:
    """Load .sum file (auto-decompress .biz wrapper if present)"""
    raw = Path(path).read_bytes()

    if raw[:4] == b"pizm":
        name_len = struct.unpack_from("<H", raw, 4)[0]
        uncomp_size = struct.unpack_from("<I", raw, 6 + name_len)[0]
        comp_size = struct.unpack_from("<I", raw, 6 + name_len + 4)[0]
        compressed = raw[6 + name_len + 8:6 + name_len + 8 + comp_size]
        raw = zlib.decompress(compressed)

    return CGameData(raw)


def export_csv(gdata: CGameData, out_dir: Path):
    """Export all tables as CSV files"""
    out_dir.mkdir(parents=True, exist_ok=True)

    total_exported = 0
    for t_idx, table in enumerate(gdata.tables):
        if not table.table_name and not table.items:
            continue
        safe_name = table.table_name if table.table_name else f"table_{t_idx}"
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in safe_name)
        csv_path = out_dir / f"{safe_name}.csv"

        rows = table.to_csv_rows()
        if len(rows) <= 1:
            print(f"  [SKIP] {table.table_name} (empty, no rows)")
            continue

        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        print(f"  [OK]   {csv_path.name}  ({len(rows)-1} rows x {len(rows[0])} cols)")
        total_exported += 1

    print(f"  => exported {total_exported} tables to {out_dir}")


def export_json(gdata: CGameData, out_path: Path):
    """Export all tables as JSON"""
    result = {
        "signature": gdata.signature,
        "version": gdata.version,
        "timestamp": gdata.timestamp,
        "tables": [],
    }

    for t_idx, table in enumerate(gdata.tables):
        col_names = table.column_names if table.column_names else []
        rows = []

        for idx, rec in enumerate(table.items):
            if rec is None or not isinstance(rec, CGRecord):
                continue
            row_id = table.type_val * table.digit_base + idx
            row = {"_id": row_id}
            for col_idx, cell in enumerate(rec.items):
                col_name = col_names[col_idx] if col_idx < len(col_names) else f"col{col_idx}"
                row[col_name] = cell.value() if cell else None
            rows.append(row)

        result["tables"].append({
            "name": table.table_name,
            "type": table.type_val,
            "digit_base": table.digit_base,
            "sheet_name": table.sheet_name,
            "columns": col_names,
            "rows": rows,
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  [OK]   {out_path.name}  ({len(result['tables'])} tables)")


def cmd_info(path: str):
    """Print .sum file overview"""
    gdata = load_sum(path)

    print(f"\n{'='*60}")
    print(f"  File:    {Path(path).name}")
    print(f"  Sig:     {gdata.signature!r}")
    print(f"  Version: {gdata.version}")
    print(f"  Time:    {gdata.timestamp}")
    print(f"  Tables:  {len(gdata.tables)}")
    print(f"{'='*60}\n")

    shown = 0
    for t_idx, table in enumerate(gdata.tables):
        if not table.table_name and not table.items:
            continue
        rows = table.to_csv_rows()
        record_count = len(rows) - 1 if len(rows) > 1 else 0
        col_count = len(rows[0]) - 1 if len(rows) > 1 else 0
        print(f"  [{t_idx}] \"{table.table_name}\"")
        print(f"        type={table.type_val}  digitBase={table.digit_base}")
        print(f"        sheet={table.sheet_name!r}")
        print(f"        text_table={bool(table.is_text_table)}  text_name={table.text_table_name!r}")
        print(f"        columns ({col_count}): {table.column_names}")
        print(f"        records: {record_count}")

        if record_count > 0:
            print(f"        preview:")
            for r in rows[:min(4, len(rows))]:
                preview = " | ".join(str(c)[:30] for c in r[:8])
                print(f"          {preview}")
        print()
        shown += 1
        if shown >= 5:
            print(f"  ... showing first 5 of {len(gdata.tables)} tables")
            break


def main():
    import argparse
    parser = argparse.ArgumentParser(description=".sum file parser -> CSV / JSON")
    parser.add_argument("input", help=".sum or .biz file path")
    parser.add_argument("--csv", action="store_true", help="Export CSV")
    parser.add_argument("--json", action="store_true", help="Export JSON")
    parser.add_argument("--all", action="store_true", help="Export both CSV and JSON")
    parser.add_argument("-o", "--output", help="Output directory (default: same as input)")

    args = parser.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"[ERR] File not found: {src}")
        return 1

    out_dir = Path(args.output) if args.output else src.parent / (src.stem + "_export")
    want_csv = args.csv or args.all or not (args.json or args.all)
    want_json = args.json or args.all

    print(f"Parsing: {src.name}...")
    try:
        gdata = load_sum(str(src))
    except Exception as e:
        print(f"[ERR] Parse failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    cmd_info(str(src))

    if want_csv:
        csv_dir = out_dir / "csv"
        print(f"Exporting CSV to: {csv_dir}")
        export_csv(gdata, csv_dir)

    if want_json:
        json_path = out_dir / (src.stem + ".json")
        print(f"Exporting JSON to: {json_path}")
        export_json(gdata, json_path)

    print(f"\nDone! All files in: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
