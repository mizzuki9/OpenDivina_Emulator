# OpenDivina_emulator (經典遊戲服務端模擬與相容性研究計畫)

Language / 語言切換:
* 🌐 [English Version](#-english-version)
* 🌐 [繁體中文版本](#-繁體中文版本)

---

> [!WARNING]
> **This is a 100% original, asset-free server framework. DO NOT post leaked files.**
> **本專案為完全獨立開發之無資產服務端框架。本儲存庫嚴禁提交或分享任何非法外流之原廠數據。**

---

## 🌐 English Version

Welcome to **OpenDivina_emulator**, an open-source, clean-room reverse engineering and software preservation project dedicated to network protocol research for a 2010s classic MMORPG.

### ⚖️ LEGAL DISCLAIMER (CRITICAL)
* **No Copyrighted Assets Hosted:** This repository DOES NOT host, distribute, or leak any original game assets, server binaries, leaked source codes, or client files belonging to the original copyright holders or any of their affiliates. 
* **Independent Creation:** All code in this repository is 100% original, written from scratch based purely on black-box network protocol analysis and functional specifications. It does not use, reference, or copy any proprietary software logic.
* **Interoperability & Fair Dealing:** This project is conducted strictly for educational, research, and historical preservation purposes under the interoperability, reverse engineering, and fair use/fair dealing exemptions governed by international copyright frameworks. 
* **Trademarks & Affiliation:** Any product names, logos, or brands mentioned remain the property of their respective historical copyright holders. This independent project is completely unaffiliated with, and has not been authorized, sponsored, or otherwise approved by the original copyright owners or any of their successors.

### 🌌 Project Overview & Goals
The goal of this project is to build a modern, high-performance server emulator that understands the legacy network protocol of the game, allowing the software to be preserved for local single-player and educational environments.
* **Target Engine:** Compatibility research for Gamebryo 1.2 network packages.
* **Development Language:** C++ (for core server and loader) / Python (for tools and extraction).
* **Current Status:** Pure clean-room specification definitions. **Zero leaked files are used or welcomed.**

### 🏢 Current Status of the Software History
According to public records, the original official infrastructure and live services of this software were permanently terminated years ago. Since official channels no longer exist, community-driven network emulation is the only viable path to study and preserve this piece of gaming history before it is permanently lost to time.

### ⚙️ How It Works (The Legal Standard)
Following the industry-standard legal precedents of successful emulators (like *TrinityCore* or *OpenRA*), this project enforces a strict **separation of code and assets**:
1. **The Emulator is Blank:** This repository contains only the clean-room server architecture. It has no game databases, text strings, or NPC dialogues.
2. **Client-Side Hooking:** We utilize a custom, open-source Loader written in C++ (API Hooking) to dynamically redirect network traffic from a local client to `127.0.0.1` at runtime inside the system memory. **We DO NOT distribute modified client binaries (.exe/.bin).**
3. **Data Extraction:** Users must provide their own legally acquired legacy game client archive. A Python-based data extraction script (Extractor) will be provided to allow users to parse asset structures on their local machines into an empty database shell.

### 🛠️ Project Roadmap & Current Progress
We are currently analyzing the black-box behavior of the network layer and formatting the packet structures:
* [x] **Network Architecture Design:** Setup the basic TCP server skeleton in C++.
* [ ] **Packet Analysis (Black-box):** Defining the transport layer protocol reverse engineering (debugging the Finite State Machine (FSM) of the connection).
* [ ] **Client Loader Module:** Developing an asynchronous memory-hooking DLL in C++ to safely redirect client traffic without breaking file integrity.
* [x] **Data Extraction Script:** Preliminary Python toolkit available — parses `.biz` / `.pak` / `.sum` binary containers into CSV/JSON. See [`tools/For Output/tookit/README.md`](tools/For%20Output/tookit/README.md). Currently supports only a small subset of client files; work is ongoing.

### 🤝 Call for Collaboration (Clean-Room Standards)
We welcome anyone passionate about networking, reverse engineering, and game preservation to contribute! 
* **DO NOT** submit or share any leaked server files, original source code, or proprietary tools.
* **DO** share black-box packet documentation, wirelogs (Wireshark `.pcap` files), or custom loader hooking logic.
* If you are experienced with Asynchronous C++ Networking, Python data parsing, or DLL Hooking, please feel free to open an Issue or submit a Pull Request!

---

[⬆ Back to Top / 回到頂部](#opendivina_emulator-經典遊戲服務端模擬與相容性研究計畫)

---

## 🌐 繁體中文版本

歡迎來到 **OpenDivina_emulator**。本計畫是一個完全基於「乾淨房設計（Clean-Room Design）」的開源逆向工程與數位軟體歷史保存專案，致力於對 2010 年代一款經典 MMORPG 的網絡傳輸協定進行相容性與重組研究。

### ⚖️ 免責聲明 (至關重要)
* **絕不託管具版權之資產：** 本儲存庫（Repository）專案絕不託管、分發或洩漏任何屬於原開發商、營運商或版權持有人所有的原廠遊戲資產、伺服器執行檔、外流原始碼或客戶端檔案。
* **獨立原創代碼：** 本專案中的所有程式碼皆為 100% 獨立原創。所有技術實作皆完全基於網絡傳輸協定之黑箱逆向分析（Black-box Protocol Reverse Engineering）與客觀功能規格編寫，未複製或使用任何原廠專有軟體邏輯。
* **互通性與合理使用：** 本計畫之開展完全出於教育、學術研究及歷史保存目的。此逆向工程與技術相容性開發行為，完全符合國際版權法架構中關於軟體互通性、合理使用與軟體保存之法定免責條款。
* **商標權益說明：** 本文中所提及之所有遊戲名稱、標誌（Logo）或品牌，其歷史版權均歸原版權持有人所有。本獨立技術專案與原開發商、其母公司或任何現行資產清理團隊無任何商業、法律、授權、贊助或背書關聯。

### 🌌 專案概述與目標
本計畫的終極目標是打造一個現代、高效能的開源服務端模擬器，使其能夠理解並回應相關引擎時期的舊版網絡通訊協定，從而讓這款經典遊戲得以在本地單機或教學環境中被保存與研究。
* **核心目標：** 針對舊版網絡封包結構進行相容性與重組研究。
* **開發語言：** C++（用於服務端核心與引導模組）/ Python（用於工具與數據提取腳本）。
* **目前狀態：** 純粹的乾淨房通訊規格定義。**本專案不歡迎、亦絕不使用任何非法外流之原廠檔案。**

### 🏢 原廠軟體歷史現況
根據公開紀錄，該軟體的原廠官方伺服器與相關營運基礎設施多年前已完全終結。由於官方管道已完全終結，社群導向的網絡服務端模擬，已成為在時間洪流中研究並保存這段數位遊戲歷史的唯一合法可行途徑。

### ⚙️ 運作原理（嚴格遵守法律標準）
本專案仿效國際知名開源模擬器（如 *TrinityCore* 或 *OpenRA*）的成功經驗，嚴格執行**「程式碼與遊戲資產徹底分離」**的黃金標準：
1. **模擬器本體完全空白：** 本儲存庫僅包含原創的服務端架構代碼，內部不含任何遊戲資料庫、劇情文字、NPC 對白或美術資源。
2. **客戶端動態引導（Hooking）：** 我們採用外置、開源並由 C++ 編寫的引導程式（Loader），在系統記憶體運行期間動態將網絡流量導向本地端 `127.0.0.1`。**我們絕不分發任何經修改的原廠二進位檔案（.exe/.bin）。**
3. **資產本地提取（Extractor）：** 使用者必須自行準備合法取得的舊版遊戲客戶端。本專案將提供基於 Python 的數據提取指令碼（Extractor），由使用者在個人電腦上運行，自行將本地 Client 檔案中的文字與數值結構轉換並填入空白的資料庫中。

### 🛠️ 開發藍圖與目前進度
我們目前正專注於對網絡傳輸層進行黑箱分析，並為封包結構定義相容的規格模型：
* [x] **網絡底層架構設計：** 使用 C++ 完成基本 TCP 服務端骨架搭建。
* [ ] **封包結構分析（黑箱）：** 正在解析並定義網絡握手階段之有限狀態機（Finite State Machine, FSM）通訊結構。
* [ ] **客戶端動態引導模組：** 正在開發基於 C++ 異步網絡與動態鏈結庫（DLL Hooking）攔截的引導模組，以在不破壞檔案完整性的前提下，安全地導引連線流量。
* [x] **數據提取腳本：** 初步 Python 工具包已就緒 — 可解析 `.biz` / `.pak` / `.sum` 二元容器並匯出 CSV / JSON。詳見 [`tools/For Output/tookit/README.md`](tools/For%20Output/tookit/README.md)。目前僅支援少量客戶端檔案，持續開發中。

### 🤝 誠邀技術合作（乾淨房開發標準）
我們非常歡迎對網絡編程、逆向工程與遊戲數位保存感興趣的朋友一同貢獻智慧！
* **請勿** 提交或分享任何非法外流的服務端檔案、原廠原始碼或專有破解工具。
* **歡迎** 分享黑箱封包分析文件、網絡側錄檔案（Wireshark `.pcap` 檔）或原創的動態引導（Hooking）邏輯。
* If you are experienced with Asynchronous C++ Networking, Python data parsing, or DLL Hooking, please feel free to open an Issue or submit a Pull Request!

---

[⬆ Back to Top / 回到頂部](#opendivina_emulator-經典遊戲服務端模擬與相容性研究計畫)