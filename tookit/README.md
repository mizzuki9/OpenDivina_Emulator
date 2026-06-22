# Binary Data Toolkit / 二進制數據工具包

A set of Python tools for parsing legacy binary container formats from a 2010s classic MMORPG client. All format knowledge was derived through static disassembly analysis of the legacy client binary — no proprietary source code was copied or referenced.

一組用於解析 2010 年代經典 MMORPG 客戶端舊版二進制容器格式的 Python 工具。所有格式知識均透過對原廠舊版客戶端二進位檔案之靜態反組譯與結構分析獨立推導——未複製或參考任何專有原始碼。

---

Language / 語言切換:
* 🌐 [English Version](#-english-version)
* 🌐 [繁體中文版本](#-繁體中文版本)

---

> [!WARNING]
> **This toolkit is a work in progress.** Currently only a small subset of client data files can be successfully decompressed. Many formats remain unhandled. See [Known Limitations](#-known-limitations) below.
>
> **本工具包仍在開發中。** 目前僅有少量客戶端數據檔案可成功解壓。大量格式尚未處理。詳見下方[已知限制](#-已知限制)。

---

## 🌐 English Version

### 📦 What's Included

| File | Type | Description |
|---|---|---|
| `biz_tool.py` | CLI | Command-line converter for `.biz`, `.pak`, and Badge binary containers |
| `biz_gui.py` | GUI | Tkinter graphical frontend with batch extraction, re-pack, and `.sum` → CSV export |
| `cgdata_reader.py` | CLI | `.sum` database file parser — exports game data tables to CSV / JSON |

### 🔣 Supported Formats

| Format | Magic | Method | Status |
|---|---|---|---|
| **`.biz`** | `pizm` | zlib compression | ✅ Pack / Unpack |
| **`.pak`** | `kapm` | IDEA cipher (CFB) + custom LZ | ⚠️ Unpack only (repack not yet supported) |
| **Badge** | SHA-1 header + `.biz` | SHA-1 → `.biz` → zlib | ⚠️ Detect & extract only |
| **`.sum`** | `newdiac` | CGameData serialized tables (v1–v5+) | ✅ Parse → CSV / JSON |

### ▶️ CLI Usage

#### `biz_tool.py`

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

#### `cgdata_reader.py`

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

#### `biz_gui.py`

```bash
python biz_gui.py
```

A window will open. Select files → choose output folder → click **Extract**. Use the `.sum → CSV` button to export extracted tables to spreadsheets.

### 🧠 Technical Notes

- **IDEA Cipher**: A Python port of the IDEA block cipher (128-bit key, 8 rounds, 52 subkeys) in CFB mode, reverse-engineered from the client binary.
- **Custom LZ Decompression**: Partial stub — currently only handles `.biz`-wrapped payloads and a simple end-marker truncation. The full LZ77 variant is not yet implemented.
- **CGameData Parser**: Handles format versions v1 through v5+, supporting length-prefixed strings, key-value containers, typed values (integer, float, bigint), records, and tables.
- **Big5 Encoding**: Game text strings found in successfully parsed `.sum` files are encoded in Big5 (Traditional Chinese). Confirmed on extracted table data; broader coverage depends on further format reverse engineering.

### ⚠️ Known Limitations

- **`.pak` repack not supported** — one-way extraction only.
- **Custom LZ decompression is incomplete** — many `.pak` payloads with non-trivial LZ compression will fail to decompress.
- **Only a small fraction of client data files are currently parseable.** Most binary blobs in the game client use formats that are not yet reverse-engineered.
- **Badge format** — only detection and content extraction; no verification or signing capability.
- **CGameData v5+** — partially supported; some newer container structures may cause parse errors.

### 📁 Workflow

```
  Game Client Files                Output
  ─────────────────────────────────────────
  .biz / .pak / Badge  ──→  biz_tool.py decrypt  ──→  .sum (raw table data)
  .sum                 ──→  cgdata_reader.py       ──→  .csv / .json
  .csv / .json         ──→  biz_tool.py encrypt    ──→  .biz (repackaged)
```

### ⚖️ Interoperability Statement

- **Zero leaked data**: This toolkit contains only format parsers. No game assets, database content, original source code, or client binaries are included.
- **User-provided client required**: The tools read binary files that the user must supply from their own legally acquired game client.
- **All format knowledge independently derived**: Every magic byte, structure offset, and cipher round was determined through static disassembly analysis of the legacy client binary — not from any leaked source code, server files, or proprietary tools.

### 📄 License

MIT License — see [LICENSE](./LICENSE).

---

[⬆ Back to Top / 回到頂部](#binary-data-toolkit--二進制數據工具包)

---

## 🌐 繁體中文版本

### 📦 包含的工具

| 檔案 | 類型 | 說明 |
|---|---|---|
| `biz_tool.py` | CLI | `.biz` / `.pak` / Badge 二進制容器的命令列轉換工具 |
| `biz_gui.py` | GUI | 基於 Tkinter 的圖形化界面，支援批量提取、重新打包與 `.sum` → CSV 匯出 |
| `cgdata_reader.py` | CLI | `.sum` 數據庫檔案解析器——將遊戲數據表匯出為 CSV / JSON |

### 🔣 支援的格式

| 格式 | 魔術字 | 方法 | 狀態 |
|---|---|---|---|
| **`.biz`** | `pizm` | zlib 壓縮 | ✅ 打包 / 解包 |
| **`.pak`** | `kapm` | IDEA 加密（CFB 模式）+ 自訂 LZ | ⚠️ 僅解包（重新打包尚未支援） |
| **Badge** | SHA-1 頭部 + `.biz` | SHA-1 → `.biz` → zlib | ⚠️ 僅檢測與提取 |
| **`.sum`** | `newdiac` | CGameData 序列化表（v1–v5+） | ✅ 解析 → CSV / JSON |

### ▶️ 命令列用法

#### `biz_tool.py`

```bash
# 解包 .biz 容器
python biz_tool.py decrypt item_data.biz -o ./output/

# 查看檔案資訊
python biz_tool.py info file.pak

# 深度掃描目錄中的已知格式
python biz_tool.py deep-scan ./data_folder/

# 將原始數據重新打包為 .biz
python biz_tool.py encrypt raw_file.bin --name "內部檔案名稱"
```

#### `cgdata_reader.py`

```bash
# 顯示 .sum 檔案概覽
python cgdata_reader.py extracted.sum

# 匯出為 CSV
python cgdata_reader.py extracted.sum --csv

# 匯出為 JSON
python cgdata_reader.py extracted.sum --json

# 同時匯出兩種格式
python cgdata_reader.py extracted.sum --all
```

#### `biz_gui.py`

```bash
python biz_gui.py
```

將開啟圖形化視窗。選取檔案 → 選擇輸出目錄 → 點選 **Extract**。使用 `.sum → CSV` 按鈕將提取的表格匯出為電子試算表。

### 🧠 技術說明

- **IDEA 加密演算法**：從客戶端二進位檔逆向工程而來的 IDEA 分組密碼 Python 實作（128 位元密鑰，8 輪，52 子密鑰），使用 CFB 模式。
- **自訂 LZ 解壓縮**：部分實作（stub）——目前僅處理 `.biz` 包裝的負載與簡單的結束標記截斷。完整 LZ77 變體尚未實作。
- **CGameData 解析器**：支援 v1 至 v5+ 格式版本，可處理長度前綴字串、鍵值容器、型別化數值（整數、浮點、大整數）、記錄與表格。
- **Big5 編碼**：在已成功解析的 `.sum` 檔案中發現的遊戲文字字串均採用 Big5（繁體中文）編碼。已在提取的表格數據上驗證；更廣泛的覆蓋範圍取決於後續格式逆向工程進度。

### ⚠️ 已知限制

- **`.pak` 重新打包尚未支援**——僅支援單向提取。
- **自訂 LZ 解壓縮不完整**——大量含有非平凡 LZ 壓縮的 `.pak` 負載將無法成功解壓。
- **目前僅有少量客戶端數據檔案可解析。** 遊戲客戶端中的大多數二進位資料塊使用了尚未被逆向工程的格式。
- **Badge 格式**——僅支援檢測與內容提取；不具備驗證或簽章功能。
- **CGameData v5+**——部分支援；某些較新的容器結構可能導致解析錯誤。

### 📁 工作流程

```
  遊戲客戶端檔案                    輸出結果
  ─────────────────────────────────────────
  .biz / .pak / Badge  ──→  biz_tool.py decrypt  ──→  .sum（原始表格數據）
  .sum                 ──→  cgdata_reader.py       ──→  .csv / .json
  .csv / .json         ──→  biz_tool.py encrypt    ──→  .biz（重新封裝）
```

### ⚖️ 互通性聲明

- **零外流數據**：此工具包僅包含格式解析器，不含任何遊戲資產、數據庫內容、原始碼或客戶端二進位檔案。
- **須由使用者自行提供客戶端**：工具讀取的二進位檔案必須由使用者從自己合法取得的遊戲客戶端中提供。
- **所有格式知識均為獨立推導**：每一個魔術字、每一個結構偏移量、每一輪加密，皆透過對原廠舊版客戶端二進位檔案之靜態反組譯與結構分析獨立確定——絕未參考任何外流原始碼、伺服器檔案或專有工具。

### 📄 授權條款

MIT License — 詳見 [LICENSE](./LICENSE)。

---

[⬆ Back to Top / 回到頂部](#binary-data-toolkit--二進制數據工具包)
