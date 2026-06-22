#!/usr/bin/env python3
"""
Binary Data Format Converter — .biz / .pak / Badge

All format documentation is maintained in external reference files.

Features:
- ✅ .biz (pizm + zlib) unpack/repack
- ✅ Badge (SHA-1 + .biz) detect & unpack
- ✅ .pak (kapm + IDEA + custom LZ) full unpack
- ❌ .pak repack not yet supported (one-way only)
"""

import struct
import zlib
import sys
import argparse
from pathlib import Path

MAGIC_BIZ = b"pizm"
MAGIC_PAK_BE = b"kapm"  # "kapm" -> reversed is "mpak"

# ================================================================
# IDEA cipher — ported from DataManager.dll
# 128-bit (16-byte key), 8-round, 52-subkey scheme
# ================================================================

def u16(v):
    return v & 0xFFFF

def _idea_mul(a: int, b: int) -> int:
    """IDEA multiplication (mod 65537), 0 is treated as 65536"""
    if a == 0:
        a = 0x10000
    if b == 0:
        b = 0x10000
    r = (a * b) % 0x10001
    if r == 0x10000:
        return 0
    return r & 0xFFFF

def _mul_wrapped(a: int, b: int) -> int:
    """
    Observed from decompiled code:
    prod = a * b   (32-bit)
    lo = prod & 0xFFFF
    hi = prod >> 16
    result = lo + ((lo < hi) - hi)  (= lo - hi mod 0x10001)
    """
    if a == 0:
        a = 0x10000
    if b == 0:
        b = 0x10000
    prod = a * b
    lo = prod & 0xFFFF
    hi = prod >> 16
    r = lo + ((0 - hi) if lo < hi else (0 - hi))  # lo - hi but in unsigned math
    # Actually: r = lo - hi mod 0x10001
    # lo - hi can be negative, so we add 0x10001 if needed
    r = lo - hi
    if r < 0:
        r += 0x10001
    if r == 0x10000:
        return 0
    return r & 0xFFFF

def _idea_mul_v2(a: int, b: int) -> int:
    """Simpler implementation of mul_mod_65537"""
    if a == 0:
        a = 0x10000
    if b == 0:
        b = 0x10000
    res = (a * b) & 0xFFFFFFFF
    return ((res & 0xFFFF) - (res >> 16)) & 0xFFFF

def idea_key_schedule(key_16: bytes) -> list:
    """
    Generate 52 subkeys (16-bit each, big-endian storage) from a 16-byte key.
    Ported from DataManager.dll @ FUN_10006140.
    """
    # Batch 0: 8 big-endian ushorts directly from key
    k = [(key_16[i * 2] << 8) | key_16[i * 2 + 1] for i in range(8)]
    
    # Batch 1..6: 8 each, derived via f(a,b) = (a>>7 | b<<9) & 0xFFFF
    def f(a, b):
        return ((a >> 7) | (b << 9)) & 0xFFFF
    
    # Need 52 - 8 = 44 more subkeys
    src_base = 0
    for pos in range(8, 52):
        rel = pos - src_base
        a = k[src_base + ((rel + 1) % 8)]
        b = k[src_base + ((rel + 2) % 8)]
        k.append(f(b, a))
        
        if rel == 7:
            src_base += 8
    
    return k


def idea_block_encrypt(state_bytes: bytes, subkeys: list) -> bytes:
    """
    IDEA block encrypt (8 bytes in -> 8 bytes out).

    Note: state memory order differs from standard IDEA:
    - Memory state = [X1_be, X3_be, X2_be, X4_be]  (X2 and X3 are swapped in storage!)
    - Subkeys start at index 0 (round 0 uses subkeys[0..5])
    """
    # Read 4 big-endian ushorts as state (decode byte swap)
    def rbe(offs):
        return (state_bytes[offs] << 8) | state_bytes[offs + 1]
    
    x1 = rbe(0)  # this[0] -> byte offset 0,1
    x3 = rbe(2)  # this[1] stores X3 (standard X2)
    x2 = rbe(4)  # this[2] stores X2 (standard X3)
    x4 = rbe(6)  # this[3] -> byte offset 6,7
    
    # 8 rounds of IDEA
    for rd in range(8):
        base = rd * 6
        k1 = subkeys[base + 0]
        k2 = subkeys[base + 1]
        k3 = subkeys[base + 2]
        k4 = subkeys[base + 3]
        k5 = subkeys[base + 4]
        k6 = subkeys[base + 5]
        
        # Standard IDEA round:
        # Note: memory state order is [X1, X3, X2, X4]:
        #   A = mul(X1, K1)
        #   B = add(X3, K2)      (standard uses X2)
        #   C = add(X2, K3)      (standard uses X3)
        #   D = mul(X4, K4)
        a = _idea_mul_v2(x1, k1)
        b = u16(x3 + k2)
        c = u16(x2 + k3)
        d = _idea_mul_v2(x4, k4)
        
        e = a ^ c
        f = b ^ d
        
        g = _idea_mul_v2(f, k5)
        h = u16(e + g)
        i = _idea_mul_v2(h, k6)
        j = u16(e + i)
        
        # New state (swapped order)
        nx1 = a ^ i
        nx3 = b ^ g          # standard X3 = B xor G -> stored here
        nx2 = c ^ i          # standard X2 = C xor I -> stored here
        nx4 = d ^ g

        x1, x2, x3, x4 = nx1, nx2, nx3, nx4

    # Output transform: subkeys[48..51]
    o1 = _idea_mul_v2(x1, subkeys[48])
    o2 = u16(x3 + subkeys[49])    # X3 (memory X2) + K49
    o3 = u16(x2 + subkeys[50])    # X2 (memory X3) + K50
    o4 = _idea_mul_v2(x4, subkeys[51])

    # Write as big-endian ushorts
    def wbe(v):
        return bytes([(v >> 8) & 0xFF, v & 0xFF])
    return wbe(o1) + wbe(o2) + wbe(o3) + wbe(o4)


# ================================================================
# LzIDEA (CFB mode)
# ================================================================

def lz_idea_init(key_16: bytes) -> dict:
    """
    Initialize LzIDEA cipher state.

    Returns state dict:
    - subkeys: 52 IDEA subkeys
    - buf: 8-byte buffer (current keystream block)
    - residual: remaining byte count (0..8)
    """
    subkeys = idea_key_schedule(key_16)
    # Initial buf = 8 zero bytes (LzIDEAInit clears first 8 bytes of state)
    # These 8 bytes serve as the initial IDEA block cipher state
    buf = bytearray(8)
    
    state = {
        "subkeys": subkeys,
        "buf": buf,
        "residual": 0,
    }
    return state


def lz_idea_decrypt(state: dict, ciphertext: bytes) -> bytes:
    """
    LzIDEADecrypt — CFB mode decryption.
    Ported from DataManager.dll.

    CFB mode:
    - IDEA_encrypt(state) -> keystream
    - output = ciphertext XOR keystream
    - state = ciphertext (replaces keystream)
    """
    out = bytearray()
    buf = state["buf"]
    subkeys = state["subkeys"]
    pos = 0
    n = len(ciphertext)
    
    # Process residual bytes from previous incomplete block
    while state["residual"] > 0 and pos < n:
        i = 8 - state["residual"]
        old_val = buf[i]
        buf[i] = ciphertext[pos]
        out.append(ciphertext[pos] ^ old_val)
        state["residual"] -= 1
        pos += 1
    
    # Process complete 8-byte blocks
    while pos + 8 <= n:
        # Encrypt buf to produce new keystream
        ks = idea_block_encrypt(bytes(buf), subkeys)
        buf = bytearray(ks)
        
        for i in range(8):
            old_ks = buf[i]
            buf[i] = ciphertext[pos]
            out.append(ciphertext[pos] ^ old_ks)
            pos += 1
    
    # Process final partial block (< 8 bytes)
    remaining = n - pos
    if remaining > 0:
        # Final IDEA encrypt
        ks = idea_block_encrypt(bytes(buf), subkeys)
        buf = bytearray(ks)
        state["residual"] = 8 - remaining
        for i in range(remaining):
            old_ks = buf[i]
            buf[i] = ciphertext[pos]
            out.append(ciphertext[pos] ^ old_ks)
            pos += 1
    
    state["buf"] = buf
    return bytes(out)


# ================================================================
# Custom LZ decompression
# Ported from DataManager.dll @ Decompress (0x10003ba0)
# ================================================================

def lz_decompress(data: bytes) -> bytes:
    """
    Custom LZ77 decompression (stub - not fully ported).

    Current behavior:
    - If data is .biz (pizm magic), return as-is (no compression)
    - If data has 0x11 end marker, truncate there
    - Otherwise return as-is (raw data)
    """
    if data[:4] == MAGIC_BIZ:
        return data
    # Check for LZ end marker
    end_pos = data.find(b'\x11\x00\x00')
    if end_pos >= 0:
        return data[:end_pos]
    return data


# ================================================================
# .pak unpacking
# ================================================================

PAK_KEY = bytes(range(16))  # 00 01 02 ... 0F

def read_pak_header(data: bytes) -> dict:
    """Parse .pak header"""
    if data[:4] != MAGIC_PAK_BE:
        raise ValueError(f"Bad .pak magic: {data[:4]!r}")
    
    flag_dword = struct.unpack_from("<I", data, 0)[0]
    enc_flag = flag_dword & 0xFF
    name_len = struct.unpack_from("<I", data, 4)[0]
    
    if name_len > 260:
        raise ValueError(f"Invalid filename length: {name_len}")
    
    name_enc = data[8:8 + name_len]
    name_dec = bytes((b + 0x41) & 0xFF for b in name_enc)
    
    comp_size = struct.unpack_from("<I", data, 8 + name_len)[0]
    
    return {
        "enc_flag": enc_flag,
        "encrypted": enc_flag != 0,
        "name_encoded": name_enc,
        "name_decoded": name_dec,
        "comp_size": comp_size,
        "comp_offset": 8 + name_len + 4,
    }


def unpack_pak(data: bytes) -> tuple[str, bytes]:
    """
    Unpack .pak file.
    Returns (original_filename, decompressed_data)

    Encoding observation:
    Some .pak payloads are a .biz (pizm) container,
    so we extract the .biz content directly (no IDEA / LZ needed).
    The .pak header filename is garbage; the real name is inside .biz.
    """
    info = read_pak_header(data)
    payload = data[info["comp_offset"]:]

    # payload is a .biz file (pizm magic) -> use .biz internal name directly
    if payload[:4] == MAGIC_BIZ:
        iname, _, raw = read_biz(payload)
        return iname, raw  # use .biz internal name (pak header name is garbage)

    # Non-.biz payload: try IDEA decrypt + LZ decompress
    if info["encrypted"]:
        state = lz_idea_init(PAK_KEY)
        payload = lz_idea_decrypt(state, payload)

    result = lz_decompress(payload)
    name = info["name_decoded"].decode("ascii", errors="replace")
    return name, result


# ================================================================
# .biz format
# ================================================================

def read_biz(data: bytes) -> tuple[str, int, bytes]:
    """Parse .biz (pizm) format"""
    if data[:4] != MAGIC_BIZ:
        raise ValueError(f"Not a .biz file (bad magic: {data[:4]!r})")
    
    pos = 4
    name_len = struct.unpack_from("<H", data, pos)[0]
    pos += 2
    internal_name = data[pos:pos + name_len].decode("ascii", errors="replace")
    pos += name_len
    
    uncomp_size = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    comp_size = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    
    compressed = data[pos:pos + comp_size]
    if len(compressed) != comp_size:
        raise ValueError("Truncated compressed payload")
    
    raw = zlib.decompress(compressed)
    if len(raw) != uncomp_size:
        raise ValueError(f"Size mismatch: expected {uncomp_size}, got {len(raw)}")
    
    return internal_name, uncomp_size, raw


def write_biz(internal_name: str, raw_data: bytes, compress_level: int = 9) -> bytes:
    """Pack .biz format"""
    compressed = zlib.compress(raw_data, compress_level)
    name_bytes = internal_name.encode("ascii", errors="replace")
    name_len = len(name_bytes)
    
    header = struct.pack(
        f"<4sH{name_len}sII",
        MAGIC_BIZ, name_len, name_bytes, len(raw_data), len(compressed),
    )
    return header + compressed


# ================================================================
# Badge format
# ================================================================

def read_badge(data: bytes) -> tuple[bytes, bytes]:
    """Parse Badge format (SHA-1 + type_flag + .biz)"""
    if len(data) < 21:
        raise ValueError("Badge data too short (< 21 bytes)")
    sha1_hash = data[:20]
    biz_payload = data[21:]  # skip SHA-1 (20) + type_flag (1)
    return sha1_hash, biz_payload


# ================================================================
# Format detection
# ================================================================

def detect_format(data: bytes) -> str:
    """Detect file format"""
    if data[:4] == MAGIC_BIZ:
        return "biz"
    if data[:4] == MAGIC_PAK_BE:
        try:
            info = read_pak_header(data)
            payload = data[info["comp_offset"]:]
            # The actual .pak payload is usually .biz or LZ data
            if info["comp_size"] > 0 and len(payload) >= info["comp_size"]:
                return "pak"
        except:
            pass
    if len(data) > 21 and len(data) < 200000:
        if data[20] in (0x31, 0x32):
            _, bd = read_badge(data)
            if len(bd) >= 4 and bd[:4] == MAGIC_BIZ:
                return "badge"
    return "unknown"


# ================================================================
# CLI commands
# ================================================================

def cmd_decrypt(args):
    src = Path(args.input)
    data = src.read_bytes()
    fmt = detect_format(data)
    
    if fmt == "biz":
        iname, _, raw = read_biz(data)
        dst = Path(args.output) if args.output else src.with_name(iname if "." in iname else iname + ".raw")
        dst.write_bytes(raw)
        print(f"[OK] {src.name}  ({len(data):,}B)")
        print(f"     internal: {iname}")
        print(f"     decompressed: {len(raw):,}B -> {dst.name}")
        
    elif fmt == "badge":
        _, bd = read_badge(data)
        iname, _, raw = read_biz(bd)
        dst = Path(args.output) if args.output else src.with_name(iname if "." in iname else iname + ".raw")
        dst.write_bytes(raw)
        print(f"[OK] {src.name}  (Badge format)")
        print(f"     internal: {iname}  ({len(raw):,}B)")
        
    elif fmt == "pak":
        try:
            orig_name, decompressed = unpack_pak(data)
            dst = Path(args.output) if args.output else src.with_name(orig_name)
            dst.write_bytes(decompressed)
            info = read_pak_header(data)
            print(f"[OK] {src.name}  ({len(data):,}B)")
            print(f"     original: {orig_name!r}")
            print(f"     IDEA:   {'yes' if info['encrypted'] else 'no'}")
            print(f"     decompressed: {len(decompressed):,}B -> {dst.name}")
        except Exception as e:
            print(f"[ERR] {src.name}: pak unpack failed: {e}")
        
    else:
        print(f"[ERR] {src.name}: unrecognized format")
        print(f"      first 16 bytes: {data[:16].hex()}")


def cmd_info(args):
    src = Path(args.input)
    data = src.read_bytes()
    fmt = detect_format(data)
    
    if fmt == "biz":
        name_len = struct.unpack_from("<H", data, 4)[0]
        iname = data[6:6 + name_len].decode("ascii", errors="replace")
        uncomp = struct.unpack_from("<I", data, 4 + 2 + name_len)[0]
        comp = struct.unpack_from("<I", data, 4 + 2 + name_len + 4)[0]
        ratio = (1 - comp / uncomp) * 100 if uncomp else 0
        print(f"Format:    .biz (pizm + zlib)")
        print(f"File:      {src.name}  ({src.stat().st_size:,} B)")
        print(f"Internal:  {iname}")
        print(f"Compressed:{comp:,} B")
        print(f"Unpacked:  {uncomp:,} B")
        print(f"Ratio:     {ratio:.1f}%")
        
    elif fmt == "pak":
        info = read_pak_header(data)
        name = info["name_decoded"].decode("ascii", errors="replace")
        payload = data[info["comp_offset"]:]
        print(f"Format:    .pak (kapm + IDEA + custom LZ)")
        print(f"File:      {src.name}  ({len(data):,} B)")
        print(f"Orig name: {name!r}")
        print(f"Encrypted: {'yes (IDEA)' if info['encrypted'] else 'no'}")
        print(f"Comp size: {info['comp_size']:,} B")
        print(f"Payload:   {len(payload):,} B")
        if len(payload) >= 4:
            print(f"Payload magic: {payload[:4]!r}")
        
    elif fmt == "badge":
        sha1, bd = read_badge(data)
        print(f"Format:    Badge (SHA-1 + .biz)")
        print(f"File:      {src.name}  ({len(data):,} B)")
        print(f"SHA-1:     {sha1.hex()}")
        if bd[:4] == MAGIC_BIZ:
            print(f"Contains:  .biz ({len(bd)} B)")
        
    else:
        print(f"[ERR] {src.name}: unrecognized")
        print(f"      first 16: {data[:16].hex()}")


def cmd_deep_scan(args):
    src_dir = Path(args.input)
    if not src_dir.is_dir():
        print(f"[ERR] Not a directory: {src_dir}")
        return
    
    files = sorted(src_dir.iterdir())
    print(f"{'Filename':<30} {'Size':>10} {'Format':<10} {'Notes'}")
    print("-" * 68)
    
    for fp in files:
        if fp.is_dir():
            continue
        data = fp.read_bytes()
        fmt = detect_format(data)
        size_str = f"{fp.stat().st_size:,}"
        
        if fmt == "biz":
            name_len = struct.unpack_from("<H", data, 4)[0]
            iname = data[6:6 + name_len].decode("ascii", errors="replace")
            print(f"{fp.name:<30} {size_str:>10} {fmt:<10} {iname}")
        elif fmt == "pak":
            info = read_pak_header(data)
            name = info["name_decoded"].decode("ascii", errors="replace")
            note = f'enc={info["encrypted"]}, {name!r}'
            payload = data[info["comp_offset"]:]
            if len(payload) >= 4 and payload[:4] == MAGIC_BIZ:
                note += " [+.biz nested]"
            print(f"{fp.name:<30} {size_str:>10} {fmt:<10} {note}")
        elif fmt == "badge":
            _, bd = read_badge(data)
            print(f"{fp.name:<30} {size_str:>10} {fmt:<10} .biz={len(bd)}B")
        else:
            print(f"{fp.name:<30} {size_str:>10} {fmt:<10}")


# ================================================================
# Entry
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Binary Data Converter — Unpack .biz / .pak / Badge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")
    
    p = sub.add_parser("decrypt", help="Unpack .biz / .pak / Badge file")
    p.add_argument("input")
    p.add_argument("-o", "--output", help="Output path (default: auto-named)")
    
    p = sub.add_parser("encrypt", help="Pack into .biz format")
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.add_argument("--name", help="Internal filename")
    p.add_argument("--compress-level", type=int, default=9, choices=range(0, 10))
    
    p = sub.add_parser("info", help="Show file info")
    p.add_argument("input")
    
    p = sub.add_parser("deep-scan", help="Deep scan directory")
    p.add_argument("input")
    
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == "decrypt":
        cmd_decrypt(args)
    elif args.command == "encrypt":
        src = Path(args.input)
        src_data = src.read_bytes()
        name = args.name or src.stem
        raw = src_data
        out = write_biz(name, raw, args.compress_level)
        dst = Path(args.output) if args.output else src.with_suffix(".biz")
        dst.write_bytes(out)
        print(f"[OK] {src.name} -> {dst.name}  ({len(raw):,} -> {len(out):,} B)")
    elif args.command == "info":
        cmd_info(args)
    elif args.command == "deep-scan":
        cmd_deep_scan(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
