# Binary Data Toolkit

A set of clean-room Python tools for parsing legacy binary container formats from a 2010s classic MMORPG client. All format knowledge was derived through black-box hex analysis — no proprietary code was referenced or included.

---

> [!WARNING]
> **This toolkit is a work in progress.** Currently only a small subset of client data files can be successfully decompressed. Many formats remain unhandled. See [Known Limitations](#-known-limitations) below.

---

## 📦 What's Included

| File | Type | Description |
|---|---|---|
| `biz_tool.py` | CLI | Command-line converter for `.biz`, `.pak`, and Badge binary containers |
| `biz_gui.py` | GUI | Tkinter graphical frontend with batch extraction, re-pack, and `.sum` → CSV export |
| `cgdata_reader.py` | CLI | `.sum` database file parser — exports game data tables to CSV / JSON |

## 🔣 Supported Formats

| Format | Magic | Method | Status |
|---|---|---|---|
| **`.biz`** | `pizm` | zlib compression | ✅ Pack / Unpack |
| **`.pak`** | `kapm` | IDEA cipher (CFB) + custom LZ | ⚠️ Unpack only (repack not yet supported) |
| **Badge** | SHA-1 header + `.biz` | SHA-1 → `.biz` → zlib | ⚠️ Detect & extract only |
| **`.sum`** | `newdiac` | CGameData serialized tables (v1–v5+) | ✅ Parse → CSV / JSON |

## ▶️ CLI Usage

### `biz_tool.py`

```bash
# Unpack a .biz container
python biz_tool.py decrypt item_data.biz -o ./output/

# Show file info
python biz_tool.py info file.pak

# Deep scan a directory for known formats
python biz_tool.py deep-scan ./data_folder/

# Re-pack raw data into .biz
python biz_tool.py encrypt raw_file.bin --name "internal_filename"
```

### `cgdata_reader.py`

```bash
# Show .sum file overview
python cgdata_reader.py extracted.sum

# Export to CSV
python cgdata_reader.py extracted.sum --csv

# Export to JSON
python cgdata_reader.py extracted.sum --json

# Export to both
python cgdata_reader.py extracted.sum --all
```

### `biz_gui.py`

```bash
python biz_gui.py
```

A window will open. Select files → choose output folder → click **Extract**. Use the `.sum → CSV` button to export extracted tables to spreadsheets.

## 🧠 Technical Notes

- **IDEA Cipher**: A clean-room Python port of the IDEA block cipher (128-bit key, 8 rounds, 52 subkeys) in CFB mode, reverse-engineered from the client binary.
- **Custom LZ Decompression**: Partial stub — currently only handles `.biz`-wrapped payloads and a simple end-marker truncation. The full LZ77 variant is not yet implemented.
- **CGameData Parser**: Handles format versions v1 through v5+, supporting CBString (Big5-encoded text), CGTable, CGRecord, CGContainer, CGNumber, CGBigNumber, and CGFloat typed objects.
- **Big5 Encoding**: All in-game Traditional Chinese text (item names, NPC dialogue, system messages) is decoded via the Big5 codec.

## ⚠️ Known Limitations

- **`.pak` repack not supported** — one-way extraction only.
- **Custom LZ decompression is incomplete** — many `.pak` payloads with non-trivial LZ compression will fail to decompress.
- **Only a small fraction of client data files are currently parseable.** Most binary blobs in the game client use formats that are not yet reverse-engineered.
- **Badge format** — only detection and content extraction; no verification or signing capability.
- **CGameData v5+** — partially supported; some newer container structures may cause parse errors.

## 📁 Workflow

```
  Game Client Files                Output
  ─────────────────────────────────────────
  .biz / .pak / Badge  ──→  biz_tool.py decrypt  ──→  .sum (raw table data)
  .sum                 ──→  cgdata_reader.py       ──→  .csv / .json
  .csv / .json         ──→  biz_tool.py encrypt    ──→  .biz (repackaged)
```

## ⚖️ Clean-Room Statement

- **Zero leaked data**: This toolkit contains only format parsers. No game assets, database content, original source code, or client binaries are included.
- **User-provided client required**: The tools read binary files that the user must supply from their own legally acquired game client.
- **All format knowledge independently derived**: Every magic byte, structure offset, and cipher round was determined through black-box hex analysis — not from any leaked source code, server files, or proprietary tools.

## 📄 License

MIT License — see [LICENSE](./LICENSE).
