#!/usr/bin/env python3
"""
Divina container format parser (.bm_, .dd_, .tg_, .k_, .ni_, .in_).

Format documented from reverse-engineered Divina header and LZO1X stream behavior.
Supports two compression modes within the same container:
  - Mode A (LZO1X): .ni_, .k_, .dd_, .tg_ — built-in LZO1X decoding (QuickBMS fallback)
  - Mode B (XOR-only): .bm_ — XOR 0x99 → JPEG

Container header:
  offset  size    field
  ──────  ────   ──────────────────
  0x00    0x14   Metadata (20 bytes, game-specific)
  0x14    4      NAMESZ (uint32 LE)
  0x18    NS     Filename (XOR with 0x99)
  +0      4      ZSIZE (stored data size)
  +4      4      SIZE (uncompressed/output size)
  +8      12     Padding (zeros)
  +20     ZSIZE  Payload (LZO1X or XOR'd data)
"""

import ctypes
import struct
import subprocess
import os
import sys
from pathlib import Path

M2_MAX_OFFSET = 0x800

XOR_KEY = 0x99
XOR_KEY_IN = 0x97  # XOR key for .in_ files (different format!)

# Extensions that use LZO1X decompression
LZO_EXTENSIONS = {'.ni_', '.k_', '.dd_', '.tg_'}
# Extensions that use XOR-only (no compression)
XOR_ONLY_EXTENSIONS = {'.bm_'}
# Extensions that are raw XOR (no header, different key)
RAW_XOR_EXTENSIONS = {'.in_'}

# Known extension to output mapping
EXT_TO_OUTPUT = {
    '.ni_': '.nif',
    '.k_': '.kf',
    '.dd_': '.dds',
    '.tg_': '.tga',
    '.bm_': '.jpg',
    '.in_': '.ini',  # .in_ decrypts to INI text
}


def find_quickbms():
    """Locate quickbms.exe. Checks common paths."""
    candidates = [
        r'quickbms.exe',
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            return str(p)
    return None


def find_divina_bms():
    """Locate divina.bms script."""
    candidates = [
        r'divina.bms',
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            return str(p)
    return None


def parse_divina_header(data: bytes) -> dict:
    """
    Parse the divina container header.

    Returns dict with keys: namesz, filename, zsize, size, header_size, ext
    Raises ValueError on invalid format.
    """
    if len(data) < 0x14 + 4:
        raise ValueError(f"File too small ({len(data)} bytes, need at least 24)")

    # Read NAMESZ at offset 0x14
    namesz = struct.unpack_from('<I', data, 0x14)[0]

    if namesz == 0 or namesz > 260:
        raise ValueError(f"Invalid NAMESZ: {namesz}")

    name_start = 0x18
    if name_start + namesz > len(data):
        raise ValueError(f"Truncated filename: need {namesz} bytes at offset {name_start}")

    # Decode filename (XOR 0x99)
    name_xor = data[name_start:name_start + namesz]
    filename = bytes(b ^ XOR_KEY for b in name_xor).decode('ascii', errors='replace')

    # Read ZSIZE and SIZE
    off = name_start + namesz
    if off + 8 > len(data):
        raise ValueError("Truncated header: cannot read ZSIZE/SIZE")

    zsize = struct.unpack_from('<I', data, off)[0]
    size = struct.unpack_from('<I', data, off + 4)[0]

    metadata_offset = off + 8
    if metadata_offset + 12 > len(data):
        raise ValueError("Truncated header: cannot read Divina metadata")

    _, mip_count = struct.unpack_from('<II', data, metadata_offset)
    fourcc = data[metadata_offset + 8:metadata_offset + 12]

    # Header size = 0x14 + 4 + NAMESZ + 4 + 4 + 12
    header_size = metadata_offset + 12
    if header_size + zsize > len(data):
        raise ValueError("Divina payload is truncated")

    width, height = struct.unpack_from('<II', data, 0x0C)

    # Get extension from filename
    ext = Path(filename).suffix.lower()
    if not ext:
        # Try to infer from the first few bytes
        ext = ''

    return {
        'namesz': namesz,
        'filename': filename,
        'zsize': zsize,
        'size': size,
        'header_size': header_size,
        'ext': ext,
        'width': width,
        'height': height,
        'mip_count': max(mip_count, 1),
        'fourcc': fourcc,
    }


def detect_divina(data: bytes) -> bool:
    """Check if data is a divina container (has valid NAMESZ and structure)."""
    if len(data) < 32:
        return False
    try:
        info = parse_divina_header(data)
        # Verify header_size + zsize roughly equals file size
        total = info['header_size'] + info['zsize']
        if abs(total - len(data)) > 16:
            return False
        # Verify filename looks reasonable
        if not info['filename'] or len(info['filename']) > 260:
            return False
        # Check that NAMESZ is reasonable
        if info['namesz'] < 1 or info['namesz'] > 260:
            return False
        return True
    except (ValueError, struct.error):
        return False


def detect_in_(filepath: str) -> bool:
    """Check if a file is a raw XOR .in_ file (by extension)."""
    return Path(filepath).suffix.lower() in RAW_XOR_EXTENSIONS


def extract_xor_only(data: bytes, info: dict) -> bytes:
    """Extract XOR-only payload (for .bm_ files, Divina header + XOR 0x99)."""
    header_size = info['header_size']
    zsize = info['zsize']
    payload = data[header_size:header_size + zsize]
    return bytes(b ^ XOR_KEY for b in payload)


def extract_raw_xor(filepath: str, xor_key: int = XOR_KEY_IN) -> bytes:
    """
    Extract a raw XOR-obfuscated file with no header (for .in_ files).

    The entire file content is XOR'd byte-wise with a fixed key (0x97).
    No header, no metadata - just pure XOR.
    """
    data = Path(filepath).read_bytes()
    return bytes(b ^ xor_key for b in data)


class LZO1XDecodeError(RuntimeError):
    """Raised when internal LZO1X decoding fails."""


def _load_native_lzo() -> ctypes.CDLL | None:
    """Load an optional native LZO2 library used by the Godot asset pipeline."""
    candidates = [
        os.environ.get("HYZG_LZO_LIBRARY"),
        "liblzo2.so.2",
        "liblzo2.dylib",
        "lzo2.dll",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            library = ctypes.CDLL(candidate)
        except OSError:
            continue
        library.lzo1x_decompress_safe.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p,
        ]
        library.lzo1x_decompress_safe.restype = ctypes.c_int
        return library
    return None


def _decompress_lzo1x_native(source: bytes, capacity: int, library: ctypes.CDLL) -> bytes:
    source_buffer = ctypes.create_string_buffer(source, len(source))
    destination = ctypes.create_string_buffer(capacity)
    destination_size = ctypes.c_size_t(capacity)
    result = library.lzo1x_decompress_safe(
        source_buffer,
        len(source),
        destination,
        ctypes.byref(destination_size),
        None,
    )
    if result != 0:
        raise LZO1XDecodeError(f"native LZO1X decompression failed with code {result}")
    if destination_size.value != capacity:
        raise LZO1XDecodeError(
            "native LZO1X decoded size does not match declared output size: "
            f"{destination_size.value} != {capacity}"
        )
    return destination.raw[:destination_size.value]


def _decompress_lzo1x(source: bytes, capacity: int) -> bytes:
    input_offset = 0
    output = bytearray()

    def read_byte() -> int:
        nonlocal input_offset
        if input_offset >= len(source):
            raise LZO1XDecodeError("LZO input overrun")
        value = source[input_offset]
        input_offset += 1
        return value

    def read_little_u16() -> int:
        return read_byte() | (read_byte() << 8)

    def ensure_output(count: int) -> None:
        if count < 0 or len(output) + count > capacity:
            raise LZO1XDecodeError("LZO output overrun")

    def copy_literals(count: int) -> None:
        nonlocal input_offset
        if input_offset + count > len(source):
            raise LZO1XDecodeError("LZO literal input overrun")
        ensure_output(count)
        output.extend(source[input_offset : input_offset + count])
        input_offset += count

    def copy_match(position: int, count: int) -> None:
        if position < 0 or position >= len(output):
            raise LZO1XDecodeError("LZO lookbehind overrun")
        ensure_output(count)
        for _ in range(count):
            if position < 0 or position >= len(output):
                raise LZO1XDecodeError("LZO overlapping lookbehind overrun")
            output.append(output[position])
            position += 1

    def read_extended_length(base: int) -> int:
        extension = 0
        while True:
            value = read_byte()
            if value:
                return extension + base + value
            extension += 255

    if not source:
        raise LZO1XDecodeError("empty LZO stream")

    state = "outer"
    token = 0
    if source[0] > 17:
        input_offset = 1
        token = source[0] - 17
        if token < 4:
            state = "match_next"
        else:
            copy_literals(token)
            state = "first_literal"

    while True:
        if state == "outer":
            if input_offset >= len(source):
                raise LZO1XDecodeError("LZO end marker not found")
            token = read_byte()
            if token >= 16:
                state = "match"
                continue
            if token == 0:
                token = read_extended_length(15)
            copy_literals(token + 3)
            state = "first_literal"
            continue

        if state == "first_literal":
            token = read_byte()
            if token >= 16:
                state = "match"
                continue
            position = (
                len(output)
                - 1
                - M2_MAX_OFFSET
                - (token >> 2)
                - (read_byte() << 2)
            )
            copy_match(position, 3)
            state = "match_done"
            continue

        if state == "match":
            if token >= 64:
                position = (
                    len(output)
                    - 1
                    - ((token >> 2) & 7)
                    - (read_byte() << 3)
                )
                copy_match(position, ((token >> 5) - 1) + 2)
            elif token >= 32:
                length_code = token & 31
                if length_code == 0:
                    length_code = read_extended_length(31)
                position = len(output) - 1 - (read_little_u16() >> 2)
                copy_match(position, length_code + 2)
            elif token >= 16:
                position = len(output) - ((token & 8) << 11)
                length_code = token & 7
                if length_code == 0:
                    length_code = read_extended_length(7)
                position -= read_little_u16() >> 2
                if position == len(output):
                    if input_offset != len(source):
                        raise LZO1XDecodeError("LZO input not fully consumed")
                    if len(output) != capacity:
                        raise LZO1XDecodeError(
                            "decoded size does not match declared output size: "
                            f"{len(output)} != {capacity}"
                        )
                    return bytes(output)
                copy_match(position - 0x4000, length_code + 2)
            else:
                position = (
                    len(output) - 1 - (token >> 2) - (read_byte() << 2)
                )
                copy_match(position, 2)
            state = "match_done"
            continue

        if state == "match_done":
            token = source[input_offset - 2] & 3
            state = "outer" if token == 0 else "match_next"
            continue

        if state == "match_next":
            copy_literals(token)
            token = read_byte()
            state = "match"
            continue

        raise LZO1XDecodeError(f"invalid LZO decoder state: {state}")


def decode_divina_lzo1x(filepath: str, info: dict) -> tuple[bytes, str]:
    """
    Decode LZO1X payload from a Divina container using in-process decoder.
    """
    data = Path(filepath).read_bytes()
    header_size = info["header_size"]
    zsize = info["zsize"]
    payload_end = header_size + zsize
    if payload_end > len(data):
        raise LZO1XDecodeError("Divina payload is truncated")

    expected_size = info["size"]
    if expected_size <= 0:
        raise LZO1XDecodeError(f"invalid declared output size: {expected_size}")

    payload = data[header_size:payload_end]
    library = _load_native_lzo()
    if library is not None:
        try:
            decoded = _decompress_lzo1x_native(payload, expected_size, library)
            backend = 'native'
        except LZO1XDecodeError:
            decoded = _decompress_lzo1x(payload, expected_size)
            backend = 'python'
    else:
        decoded = _decompress_lzo1x(payload, expected_size)
        backend = 'python'
    if len(decoded) != expected_size:
        raise LZO1XDecodeError(
            f"decoded size mismatch: {len(decoded)} != {expected_size}"
        )
    return decoded, backend


def build_dds_header(info: dict, raw_size: int) -> bytes:
    """Build the DDS header used by the Godot asset pipeline."""
    fourcc = info['fourcc']
    if fourcc not in {b'DXT1', b'DXT3', b'DXT5'}:
        raise ValueError(f"Unsupported DDS FourCC: {fourcc!r}")
    width = info['width']
    height = info['height']
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid DDS dimensions: {width}x{height}")
    block_size = 8 if fourcc == b'DXT1' else 16
    linear_size = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block_size
    if raw_size < linear_size:
        raise ValueError(f"DDS payload too small: {raw_size} < {linear_size}")
    flags = 0x00081007
    caps = 0x00001000
    if info['mip_count'] > 1:
        flags |= 0x00020000
        caps |= 0x00400008
    header = b'DDS ' + struct.pack(
        '<7I11I8I5I',
        124,
        flags,
        height,
        width,
        linear_size,
        0,
        info['mip_count'],
        *([0] * 11),
        32,
        4,
        struct.unpack('<I', fourcc)[0],
        0,
        0,
        0,
        0,
        0,
        caps,
        0,
        0,
        0,
        0,
    )
    if len(header) != 128:
        raise AssertionError(f"Invalid DDS header length: {len(header)}")
    return header


def repair_decoded_payload(raw: bytes, src_ext: str, info: dict) -> bytes:
    if src_ext == '.dd_' and not raw.startswith(b'DDS '):
        return build_dds_header(info, len(raw)) + raw
    return raw


def extract_lzo_quickbms(filepath: str, output_dir: str, info: dict) -> str:
    """
    Extract LZO1X-compressed file using QuickBMS (legacy fallback).

    Returns path to extracted file.
    Raises RuntimeError on failure.
    """
    qbms = find_quickbms()
    bms = find_divina_bms()

    if not qbms:
        raise RuntimeError(
            "quickbms.exe not found. Please install QuickBMS from:\n"
            "  http://quickbms.aluigi.org\n"
            "Or place quickbms.exe in the same directory as this script."
        )
    if not bms:
        raise RuntimeError(
            "divina.bms not found. Please ensure divina.bms is in the same\n"
            "directory as quickbms.exe or this script."
        )

    # Call quickbms: quickbms.exe -o script.bms input_file output_dir
    cmd = [qbms, '-o', bms, filepath, output_dir]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("QuickBMS timed out after 30 seconds")
    except FileNotFoundError:
        raise RuntimeError(f"quickbms.exe not found at: {qbms}")

    # QuickBMS creates file named by the internal filename
    out_name = info['filename']
    out_path = os.path.join(output_dir, out_name)

    if not os.path.exists(out_path):
        # Try case-insensitive match
        out_dir = Path(output_dir)
        for f in out_dir.iterdir():
            if f.name.lower() == out_name.lower():
                out_path = str(f)
                break
        else:
            raise RuntimeError(
                f"QuickBMS output not found: {out_name}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

    return out_path


def extract_divina(filepath: str, output_dir: str) -> dict:
    """
    Extract a divina container file or raw XOR file.

    Returns dict: {filename, output_path, size, format}
    Raises ValueError on parse failure, RuntimeError on extraction failure.
    """
    src_ext = Path(filepath).suffix.lower()
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # --- Handle .in_ files (raw XOR, no header) ---
    if src_ext in RAW_XOR_EXTENSIONS:
        raw = extract_raw_xor(filepath)
        out_ext = EXT_TO_OUTPUT.get(src_ext, '.ini')
        out_stem = Path(filepath).stem
        out_name = out_stem + out_ext
        out_path = os.path.join(output_dir, out_name)
        counter = 1
        while os.path.exists(out_path):
            out_name = f"{out_stem}_{counter}{out_ext}"
            out_path = os.path.join(output_dir, out_name)
            counter += 1
        Path(out_path).write_bytes(raw)
        return {
            'filename': out_name,
            'output_path': out_path,
            'size': len(raw),
            'format': 'xor_raw',
        }

    # --- Handle standard Divina containers ---
    data = Path(filepath).read_bytes()
    info = parse_divina_header(data)

    # Determine output extension
    out_ext = EXT_TO_OUTPUT.get(src_ext, info['ext'] if info['ext'] else '.dat')
    out_stem = Path(filepath).stem
    out_name = out_stem + out_ext

    # Ensure unique filename
    out_path = os.path.join(output_dir, out_name)
    counter = 1
    while os.path.exists(out_path):
        out_name = f"{out_stem}_{counter}{out_ext}"
        out_path = os.path.join(output_dir, out_name)
        counter += 1

    if src_ext in XOR_ONLY_EXTENSIONS:
        # XOR-only mode (JPEG for .bm_)
        raw = extract_xor_only(data, info)
        Path(out_path).write_bytes(raw)
        return {
            'filename': out_name,
            'output_path': out_path,
            'size': len(raw),
            'format': 'xor_only',
        }

    elif src_ext in LZO_EXTENSIONS:
        # LZO1X mode: native LZO2, built-in Python decoder, then QuickBMS fallback.
        try:
            raw, backend = decode_divina_lzo1x(filepath, info)
            raw = repair_decoded_payload(raw, src_ext, info)
            Path(out_path).write_bytes(raw)
            return {
                'filename': out_name,
                'output_path': out_path,
                'size': os.path.getsize(out_path),
                'format': f'lzo1x_{backend}',
            }
        except LZO1XDecodeError:
            qbms_out = extract_lzo_quickbms(filepath, output_dir, info)
            raw = Path(qbms_out).read_bytes()
            raw = repair_decoded_payload(raw, src_ext, info)
            Path(out_path).write_bytes(raw)
            if qbms_out != out_path:
                try:
                    os.remove(qbms_out)
                except OSError:
                    pass
            return {
                'filename': out_name,
                'output_path': out_path,
                'size': os.path.getsize(out_path),
                'format': 'lzo1x_quickbms_fallback',
            }

    else:
        raise ValueError(f"Unsupported divina extension: {src_ext} (internal: {info['ext']})")


def cmd_info(filepath: str):
    """Print divina container / raw XOR file info."""
    src_ext = Path(filepath).suffix.lower()

    # Handle .in_ files (raw XOR, no header)
    if src_ext in RAW_XOR_EXTENSIONS:
        data = Path(filepath).read_bytes()
        print(f"Format:    Raw XOR (XOR 0x97, no header)")
        print(f"File:      {Path(filepath).name}  ({len(data):,} B)")
        print(f"Method:    XOR 0x97")
        print(f"Decrypts:  INI text (Big5/ASCII)")
        return

    # Standard Divina containers
    data = Path(filepath).read_bytes()
    info = parse_divina_header(data)
    method = 'LZO1X' if src_ext in LZO_EXTENSIONS else ('XOR 0x99' if src_ext in XOR_ONLY_EXTENSIONS else 'unknown')

    print(f"Format:    Divina container (Gamebryo resource)")
    print(f"File:      {Path(filepath).name}  ({len(data):,} B)")
    print(f"Internal:  {info['filename']}")
    print(f"Method:    {method}")
    print(f"Stored:    {info['zsize']:,} B")
    print(f"Output:    {info['size']:,} B")
    print(f"Header:    {info['header_size']} B")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Divina container extractor")
    sub = parser.add_subparsers(dest='command')

    p = sub.add_parser('extract', help='Extract divina container / raw XOR file')
    p.add_argument('input', help='Input file (.bm_, .ni_, .tg_, .k_, .dd_, .in_)')
    p.add_argument('-o', '--output', default='.', help='Output directory')

    p = sub.add_parser('info', help='Show container info')
    p.add_argument('input')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    if args.command == 'info':
        try:
            cmd_info(args.input)
        except Exception as e:
            print(f"[ERR] {e}")
            return 1
    elif args.command == 'extract':
        try:
            result = extract_divina(args.input, args.output)
            print(f"[OK] {Path(args.input).name} -> {result['filename']}")
            print(f"     format={result['format']}, size={result['size']:,} B")
        except Exception as e:
            print(f"[ERR] {e}")
            return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
