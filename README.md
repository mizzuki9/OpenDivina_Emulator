# Binary Data Toolkit / 二進制數據工具包

A set of Python tools for inspecting, extracting and rebuilding supported HYZG binary containers. The toolkit contains the source code and documentation for the supported formats.

一組用於檢查、解包與重建受支援 HYZG 二進制容器的 Python 工具。本工具包包含受支援格式的原始碼與說明文件。

---

Language / 語言切換:

* [English Version](#english-version)
* [繁體中文版本](#繁體中文版本)

---

> [!WARNING]
> **This toolkit is a work in progress.** It supports the formats listed below, but only a subset of client data can currently be parsed or rebuilt successfully. Non-standard payloads, malformed files and formats not listed here may fail closed.
>
> **本工具包仍在開發中。** 工具支援下列格式，但目前只有部分客戶端資料可以成功解析或重建。非標準 payload、損壞檔案及未列出的格式可能會直接失敗。

## English Version

### What's Included
biz_gui.exe   click to use no python need

| File | Type | Description |
|---|---|---|
| `biz_tool.py` | CLI / Library | Inspect, unpack and rebuild `.biz`, `.pak` and Badge containers |
| `biz_gui.py` | GUI | Tkinter frontend for batch extraction, supported re-pack operations and `.sum` export |
| `divina_tool.py` | CLI / Library | Divina extraction for `.ni_`, `.k_`, `.dd_`, `.tg_`, `.bm_` and raw `.in_` files |
| `cgdata_reader.py` | CLI / Library | Parse `.sum` tables and export CSV or JSON |
| `run_gui.bat` | Windows launcher | Starts the GUI with the local Python interpreter |
| `LICENSE` | License | Current source-code license notice |

### Requirements

* Python 3.10 or later.
* Tkinter for the GUI; standard Windows Python installations normally include it.
* No external dependency is required for the built-in Python Divina LZO1X decoder.
* An optional native LZO2 library may be supplied as `lzo2.dll`, `liblzo2.so.2` or `liblzo2.dylib`.
* `HYZG_LZO_LIBRARY` may point to a custom native LZO2 library.
* `quickbms.exe` and `divina.bms` are optional legacy fallbacks and are not bundled.

The Divina extractor tries the optional native LZO2 backend first when available, then the built-in Python LZO1X decoder, and finally QuickBMS when both in-process paths fail. The QuickBMS fallback needs both `quickbms.exe` and `divina.bms`.

### Quick Start

On Windows, start the GUI with:

```text
toolkit\run_gui.bat
```

Or run it directly:

```bash
python toolkit/biz_gui.py
```

The tools can be run independently. Install QuickBMS or an optional native LZO2 library separately only when the corresponding fallback is needed.

### Supported Formats and Current Behavior

| Format | Current behavior | Limitation |
|---|---|---|
| `.biz` | zlib unpack and rebuild | A valid `pizm` container is required |
| `.pak` | Multi-entry unpack and rebuild | Non-`.biz` encrypted payloads use the implemented IDEA/LZ path and remain best-effort |
| Badge | Detect and unpack the wrapped `.biz` payload | Verification, signing and re-packing are unsupported |
| `.sum` | Parse and export CSV/JSON; `.biz` wrappers can be loaded | The input must contain a valid `newdiac` CGameData stream |
| `.ni_` | LZO1X extraction to NIF | Malformed or unsupported LZO streams may require the QuickBMS fallback |
| `.k_` | LZO1X extraction to KF | Malformed or unsupported LZO streams may require the QuickBMS fallback |
| `.dd_` | LZO1X extraction to DDS with DDS header repair when needed | Unsupported FourCC or invalid dimensions are rejected |
| `.tg_` | LZO1X extraction to TGA | Headerless RGB/RGBA payloads receive a TGA header and BGR/BGRA channel ordering; existing TGA streams are preserved |
| `.bm_` | XOR `0x99` extraction to JPEG | Container-specific malformed images may remain unreadable |
| `.in_` | Raw XOR `0x97` extraction to INI | Detection is extension-based because this format has no Divina header |
| Pizm variants | `.wa_`, `.og_`, `.scnz`, `.tilz` and `.ttxz` are handled as `pizm` variants where detected | Extension support still depends on a valid container header and payload |

### CLI Usage

#### `biz_tool.py`

```bash
# Inspect a container
python biz_tool.py info file.pak

# Unpack a .biz, .pak or Badge container
python biz_tool.py decrypt item_data.biz -o ./output/
python biz_tool.py decrypt archive.pak -o ./output/

# Deep scan a directory for known formats
python biz_tool.py deep-scan ./data_folder/

# Rebuild a .biz container
python biz_tool.py encrypt raw_file.bin --name "internal_filename" -o output.biz

# Rebuild a multi-entry .pak container
python biz_tool.py encrypt raw_file.bin --name "internal_filename" --pak -o output.pak
```

`--compress-level` accepts values from `0` through `9` and defaults to `9`. Badge re-packing is not implemented.

#### `divina_tool.py`

```bash
# Inspect a Divina container or raw .in_ file
python divina_tool.py info model.ni_
python divina_tool.py info settings.in_

# Extract a model, animation or texture
python divina_tool.py extract model.ni_ -o ./output/
python divina_tool.py extract animation.k_ -o ./output/
python divina_tool.py extract texture.dd_ -o ./output/
python divina_tool.py extract settings.in_ -o ./output/
```

#### `cgdata_reader.py`

```bash
# Show a .sum file overview
python cgdata_reader.py extracted.sum

# Export CSV
python cgdata_reader.py extracted.sum --csv

# Export JSON
python cgdata_reader.py extracted.sum --json

# Export both formats
python cgdata_reader.py extracted.sum --all

# Choose an output directory
python cgdata_reader.py extracted.sum --all -o ./exports/
```

For CGameData v5+ tables, serialized column metadata includes the positional `column_index`. CSV and JSON export use that index rather than metadata serialization order. This is also the mapping used by the GUI `.sum -> CSV` action.

### GUI

The GUI supports:

* Batch file selection and format detection.
* Extraction of supported `.biz`, `.pak`, Badge, Divina and raw `.in_` inputs.
* `.biz` and `.pak` re-packing where the current implementation supports it.
* `.sum -> CSV` export after successful extraction.
* Copying or removing selected rows from the file list.

The GUI does not re-pack Badge files. The `.sum -> CSV` action only processes `.sum` files that were successfully extracted into the selected output directory; it does not recover missing or failed extraction results.

### Technical Notes

* **IDEA cipher:** `biz_tool.py` contains the client-derived IDEA CFB decryption path used for encrypted `.pak` payloads.
* **Custom LZ:** The non-`.biz` `.pak` LZ path is not a complete general-purpose LZ77 implementation. Payloads using an unhandled variant may fail or remain unavailable for rebuilding.
* **CGameData:** `cgdata_reader.py` supports the observed v1 through v5+ structures, including length-prefixed strings, typed values, records, tables and checksum blocks where present.
* **Big5:** Parsed game text is decoded as Big5 where the serialized data identifies that encoding. Coverage depends on the input table.
* **Divina LZO1X:** The extractor has an in-process Python decoder and can use an optional native LZO2 library. QuickBMS is the legacy fallback, not the normal first step.
* **DDS repair:** `.dd_` output receives a DDS header when the decoded payload is raw texture data rather than an existing `DDS ` stream.
* **Raw `.in_`:** This is an extension-selected XOR format with no Divina header, so a renamed or incorrectly identified file may be processed incorrectly.

### Practical Limitations

* A successful header detection does not prove that the payload can be decoded, converted or rebuilt.
* Non-`.biz` `.pak` entries with custom encrypted or compressed payloads remain best-effort.
* Divina LZO extraction can fail for malformed streams, incorrect declared output sizes, unsupported stream variants or truncated input.
* If the built-in Divina decoders fail, the fallback requires user-provided `quickbms.exe` and the matching `divina.bms`; neither is included here.
* Badge files can be detected and unpacked, but cannot be verified, signed or re-packed by the current tools.
* `.sum` export requires a valid extracted `.sum` file. The tools do not infer missing table schemas from arbitrary binary data.
* `.in_` detection is based on the filename extension and does not have a self-identifying header.
* Output model, animation and texture files still require compatible downstream consumers such as NIF/KF readers or a Godot asset pipeline.

### Workflow

```text
  Game Client Files                    Output
  ─────────────────────────────────────────────
  .biz / .pak / Badge  ──> biz_tool.py decrypt  ──> .sum or extracted payload
  .sum                 ──> cgdata_reader.py     ──> .csv / .json
  raw data             ──> biz_tool.py encrypt   ──> .biz / .pak
  .ni_ / .k_           ──> divina_tool.py        ──> .nif / .kf
  .tg_ / .dd_          ──> divina_tool.py        ──> .tga / .dds
  .bm_                 ──> divina_tool.py        ──> .jpg
  .in_                 ──> divina_tool.py        ──> .ini
```

### Data Serialization Note
- For CGameData v5+ tables, serialization metadata also includes positional column_index. CSV and JSON exports use that index instead of metadata serialization order; GUI .sum -> CSV uses the same mapping.

## Legal Notice

This project is an independent, open-source reimplementation created for interoperability, preservation, research, and educational purposes.

It is not affiliated with, endorsed by, or sponsored by the original game developers, publishers, or rights holders.

No original game client, server binaries, copyrighted artwork, audio, maps, trademarks, or other proprietary game assets are included or licensed by this project. Users must obtain any required original game files from lawful sources.

The GNU Affero General Public License applies only to the original source code and other materials for which the project contributors hold the necessary rights.

### License

The source code is licensed under AGPL-3.0-or-later. See [LICENSE](./LICENSE).

---

[Back to Top / 回到頂部](#binary-data-toolkit--二進制數據工具包)

## 繁體中文版本

### 包含的工具
biz_gui.exe   點開免安裝python直接使用

| 檔案 | 類型 | 說明 |
|---|---|---|
| `biz_tool.py` | CLI / Library | 檢查、解包與重建 `.biz`、`.pak` 及 Badge 容器 |
| `biz_gui.py` | GUI | Tkinter 圖形介面，支援批次解包、目前可用的重打包操作及 `.sum` 匯出 |
| `divina_tool.py` | CLI / Library | 處理 `.ni_`、`.k_`、`.dd_`、`.tg_`、`.bm_` 及 raw `.in_` 檔案的 Divina 工具 |
| `cgdata_reader.py` | CLI / Library | 解析 `.sum` 表格並匯出 CSV 或 JSON |
| `run_gui.bat` | Windows launcher | 使用本機 Python 啟動 GUI |
| `LICENSE` | 授權文件 | 目前原始碼授權聲明 |

### 需求

* Python 3.10 或更新版本。
* GUI 需要 Tkinter；標準 Windows Python 通常已包含它。
* 內建 Python Divina LZO1X 解碼器不需要外部套件。
* 可選 native LZO2 library：`lzo2.dll`、`liblzo2.so.2` 或 `liblzo2.dylib`。
* 可使用 `HYZG_LZO_LIBRARY` 指定自訂 native LZO2 library 路徑。
* `quickbms.exe` 與 `divina.bms` 只是可選的 legacy fallback，本工具不附帶。

Divina extractor 會先嘗試可用的 native LZO2，再使用內建 Python LZO1X，最後才在兩條 in-process 路徑失敗時使用 QuickBMS。QuickBMS fallback 必須同時有 `quickbms.exe` 與 `divina.bms`。

### 快速開始

Windows 執行 GUI：

```text
toolkit\run_gui.bat
```

或直接執行：

```bash
python toolkit/biz_gui.py
```

各工具也可以獨立執行。只有在需要相應 fallback 時，才須另外安裝 QuickBMS 或可選的 native LZO2 library。

### 支援格式與目前行為

| 格式 | 目前行為 | 限制 |
|---|---|---|
| `.biz` | zlib 解包與重建 | 必須是有效的 `pizm` 容器 |
| `.pak` | 多 entry 解包與重建 | 非 `.biz` 加密 payload 使用目前 IDEA/LZ 路徑，仍屬 best-effort |
| Badge | 偵測並解出包裝的 `.biz` payload | 不支援驗證、簽章與重打包 |
| `.sum` | 解析並匯出 CSV/JSON；可以載入 `.biz` wrapper | 輸入必須是有效的 `newdiac` CGameData stream |
| `.ni_` | LZO1X 解出 NIF | 損壞或不支援的 LZO stream 可能需要 QuickBMS fallback |
| `.k_` | LZO1X 解出 KF | 損壞或不支援的 LZO stream 可能需要 QuickBMS fallback |
| `.dd_` | LZO1X 解出 DDS，必要時修補 DDS header | 不支援的 FourCC 或無效尺寸會被拒絕 |
| `.tg_` | LZO1X 解出 TGA | 無檔頭 RGB／RGBA payload 會補上 TGA 檔頭並轉為 BGR／BGRA；既有 TGA 保留原樣 |
| `.bm_` | XOR `0x99` 解出 JPEG | 特定容器的損壞圖片可能仍無法讀取 |
| `.in_` | raw XOR `0x97` 解出 INI | 因為沒有 Divina header，偵測依副檔名進行 |
| Pizm variants | 偵測到有效 `pizm` 時可處理 `.wa_`、`.og_`、`.scnz`、`.tilz`、`.ttxz` | 仍須有有效容器 header 與 payload |

### CLI 用法

#### `biz_tool.py`

```bash
# 檢查容器
python biz_tool.py info file.pak

# 解包 .biz、.pak 或 Badge
python biz_tool.py decrypt item_data.biz -o ./output/
python biz_tool.py decrypt archive.pak -o ./output/

# 深度掃描已知格式
python biz_tool.py deep-scan ./data_folder/

# 重建 .biz
python biz_tool.py encrypt raw_file.bin --name "internal_filename" -o output.biz

# 重建多 entry .pak
python biz_tool.py encrypt raw_file.bin --name "internal_filename" --pak -o output.pak
```

`--compress-level` 接受 `0` 至 `9`，預設為 `9`。Badge 目前不支援重打包。

#### `divina_tool.py`

```bash
# 檢查 Divina container 或 raw .in_ 檔案
python divina_tool.py info model.ni_
python divina_tool.py info settings.in_

# 解出模型、動畫或貼圖
python divina_tool.py extract model.ni_ -o ./output/
python divina_tool.py extract animation.k_ -o ./output/
python divina_tool.py extract texture.dd_ -o ./output/
python divina_tool.py extract settings.in_ -o ./output/
```

#### `cgdata_reader.py`

```bash
# 顯示 .sum 檔案概覽
python cgdata_reader.py extracted.sum

# 匯出 CSV
python cgdata_reader.py extracted.sum --csv

# 匯出 JSON
python cgdata_reader.py extracted.sum --json

# 同時匯出兩種格式
python cgdata_reader.py extracted.sum --all

# 指定輸出目錄
python cgdata_reader.py extracted.sum --all -o ./exports/
```

對於 CGameData v5+ 表格，序列化欄位 metadata 同時包含 positional `column_index`。CSV 與 JSON 匯出會使用該索引，而不是 metadata 序列化順序；GUI 的 `.sum -> CSV` 也使用相同 mapping。

### GUI

GUI 支援：

* 批次選檔與格式偵測。
* 解包受支援的 `.biz`、`.pak`、Badge、Divina 及 raw `.in_` 輸入。
* 在目前實作支援範圍內重打包 `.biz` 與 `.pak`。
* 成功解包後執行 `.sum -> CSV` 匯出。
* 複製或移除檔案清單中的選取列。

GUI 不會重打包 Badge。`.sum -> CSV` 只會處理已成功解包到所選輸出目錄的 `.sum`，不會補救遺失或解包失敗的結果。

### 技術說明

* **IDEA cipher：** `biz_tool.py` 包含從客戶端行為推導的 IDEA CFB 解密路徑，用於加密 `.pak` payload。
* **Custom LZ：** 非 `.biz` `.pak` 的 LZ 路徑不是完整通用的 LZ77 實作；使用未處理變體的 payload 可能失敗，也可能無法重建。
* **CGameData：** `cgdata_reader.py` 支援目前觀察到的 v1 至 v5+ 結構，包括長度前綴字串、型別化數值、records、tables，以及存在時的 checksum block。
* **Big5：** 序列化資料標示為 Big5 時，解析出的遊戲文字會以 Big5 解碼；覆蓋範圍取決於輸入表格。
* **Divina LZO1X：** extractor 具有 in-process Python decoder，也可以使用可選 native LZO2 library。QuickBMS 是 legacy fallback，不是正常的第一步。
* **DDS repair：** `.dd_` 解碼 payload 不是既有 `DDS ` stream 時，工具會補上 DDS header。
* **Raw `.in_`：** 這是由副檔名選擇的 XOR 格式，沒有自我識別 header；改名或誤判檔案可能導致錯誤處理。

### 實際限制

* 成功偵測 header 不代表 payload 一定能解碼、轉換或重建。
* 含有自訂加密或壓縮 payload 的非 `.biz` `.pak` 仍屬 best-effort。
* Divina LZO 解包可能因 stream 損壞、宣告輸出尺寸錯誤、不支援的 stream 變體或輸入截斷而失敗。
* 內建 Divina decoder 失敗時，fallback 需要使用者自行提供 `quickbms.exe` 與相符的 `divina.bms`；本工具不附帶這兩個檔案。
* Badge 可以偵測及解包，但目前工具不能驗證、簽章或重打包。
* `.sum` 匯出需要有效且已成功解出的 `.sum`；工具不會從任意二進位資料猜測缺少的 table schema。
* `.in_` 偵測依檔名副檔名進行，格式本身沒有 self-identifying header。
* 模型、動畫與貼圖輸出仍需要相容的下游 consumer，例如 NIF/KF reader 或 Godot asset pipeline。

### 工作流程

```text
  遊戲客戶端檔案                    輸出結果
  ─────────────────────────────────────────────
  .biz / .pak / Badge  ──> biz_tool.py decrypt  ──> .sum 或解出 payload
  .sum                 ──> cgdata_reader.py     ──> .csv / .json
  raw data             ──> biz_tool.py encrypt   ──> .biz / .pak
  .ni_ / .k_           ──> divina_tool.py        ──> .nif / .kf
  .tg_ / .dd_          ──> divina_tool.py        ──> .tga / .dds
  .bm_                 ──> divina_tool.py        ──> .jpg
  .in_                 ──> divina_tool.py        ──> .ini
```

### 匯出映射註記
- 對於 CGameData v5+ 表格，序列化欄位 metadata 同時包含 positional column_index。CSV 與 JSON 匯出會使用該索引，而不是 metadata 序列化順序；GUI 的 .sum -> CSV 也使用相同 mapping。

## 法律聲明

本專案為獨立製作的開源重建實作，目的為互通、保存、研究與教育用途。

它與原遊戲開發商、發行商或權利人無隸屬、背書或贊助關係。

本專案未包含、也未授權任何原遊戲客戶端、伺服器二進位檔、受著作權保護的美術、音訊、地圖、商標或其他專有遊戲資產。使用者須自行自合法來源取得任何必要的原遊戲檔案。

GNU Affero General Public License 僅適用於專案貢獻者依法擁有權利的原始碼與其他相關材料。

### 授權條款

原始碼採用 AGPL-3.0-or-later 授權，詳見 [LICENSE](./LICENSE)。

---

[Back to Top / 回到頂部](#binary-data-toolkit--二進制數據工具包)


### Updated extraction and table handling / 解包與表格更新

Headerless TGA repair preserves alpha and fixes red/blue ordering. DDS repair handles supported mip layouts and rejects invalid payloads. The source-byte API supports explicit in-process decoder policies and structured failures. CGameData containers use signed last indices (-1 means empty), are read once, and named empty tables export header-only CSV.

無檔頭 TGA 修補會保留透明度並修正紅藍順序。DDS 修補處理支援的 mip 配置並拒絕無效 payload。來源位元組 API 提供明確的程序內解碼策略與結構化失敗結果。CGameData 容器使用有號末筆索引（-1 表示空容器），避免重複讀取，具欄位名稱的空表可匯出只有標頭的 CSV。

Tests use synthetic data only / 測試僅使用人工合成資料：

```text
python -B -m unittest discover -s toolkit/tests -v
```
