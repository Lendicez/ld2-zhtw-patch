# 俠客遊 前途道標 繁體中文化補丁（ld2-zhtw-patch）

[![release](https://img.shields.io/github/v/release/Lendicez/ld2-zhtw-patch)](https://github.com/Lendicez/ld2-zhtw-patch/releases/latest)

《俠客遊 前途道標》（Lunatic Dawn: Passage of the Book，`Ld95.exe`，Steam 版）的**繁體中文化補丁**開發庫。

## 安裝（玩家）

**最新版 1.0.0**：到 [Releases](https://github.com/Lendicez/ld2-zhtw-patch/releases/latest) 下載 `LD2-zhTW-Patch-1.0.0.exe`，執行後按「安裝」。

- 對象：Steam 版《俠客遊 前途道標》（Lunatic Dawn: Passage of the Book，`Ld95.exe` 1.0.3.16，sha256 `6c817a09…d5d2`）。其他版本會被拒絕，不做任何修改。
- 需求：Windows 10／11，「非 Unicode 程式語言」為**中文（繁體，台灣）**（代碼頁 950）。
- 安裝程式自動尋找 Steam 遊戲資料夾（也可手動選擇），原檔備份到遊戲資料夾的 `_zhTW_backup`；可隨時「解除安裝」還原。**不修改存檔（Usr）與設定檔**。
- 安裝程式只含差異資料（譯文、修補程式碼、重繪圖片區塊），不含完整遊戲檔，必須搭配合法持有的原版。
- 安裝程式未簽章，Windows 可能顯示安全性提示；若被系統政策（如「智慧型應用程式控制」）封鎖則無法使用。
- Steam「驗證遊戲檔案完整性」或遊戲更新會還原原版；重新執行安裝程式即可。

已知限制見 [docs/RELEASE-1.0.0.zh-TW.md](docs/RELEASE-1.0.0.zh-TW.md)。

## 1.0.0 涵蓋範圍

| 層 | 內容 |
|---|---|
| 選單／對話框／字串表 | m020 239 處＋其餘 145 處（右鍵選單、彩票／名字輸入等對話框、狀態列與 MFC 訊息） |
| 執行期文字（`.rdata`／`.data`） | 約 4,900 列原位 Big5：對話、事件、傳聞、委託、商店、戰鬥訊息、UI 標籤、迷宮名、怪物表 512 筆 |
| 會寫進存檔的名稱 | 道具、角色、稱號、地名：顯示時查 v4 catalog 轉繁中（存檔仍為原格式，可與原版互通） |
| 顯示後備 | TextOut／DrawText／清單插入／`%A` 展開／視窗標題：未翻到的日文以 Unicode 正確顯示；隨機人名假名音譯為漢字 |
| 字型 | 遊戲字型改繁中字集＋微軟正黑體（找不到時由 Windows 改用預設繁中字型）；對話框 Microsoft JhengHei |
| 圖片 | 按鈕 23、狀態面板 8、移動地圖 17、結局 3、國名標籤、啟動畫面 |
| 說明書 | 遊戲資料夾 HTML 說明書 70 頁（`ld95.chm` 維持原版） |

原始碼以 `main` 為主線；1.0.0 對應標籤 `v1.0.0`。實玩發現未翻譯或亂碼，請到 [Issues](https://github.com/Lendicez/ld2-zhtw-patch/issues) 附截圖與所在畫面回報。

## 技術路線

- **執行期字串**：lab 機系統 ANSI code page 為 950（zh-TW）。遊戲以 ANSI API 顯示 `.rdata` 字串，
  在原位址改寫為 Big5（CP950）位元組即可直接顯示繁中，不需 hook。工具：`research/m064/rdata_ansi.py`
  （逐列檢查原文槽 sha256、NUL 結尾、CP950 編碼、容量、printf／`%A` 類替換符合約；只寫 lab 複本）。
- **字型字集**：部分視窗以 SHIFTJIS_CHARSET 建字型，位元組一律以 CP932 解讀；`research/m064/charset_patch.py`
  改為 CHINESEBIG5 後 Big5 字串正確顯示（同視窗的日文須同步翻譯）。
- **hook 擴充**：`list_reroute.py`（清單填入點改導 v4 item 入口）、`catalog_patch.py`（`.ld2c` 追加查表列）、
  `tab_title_patch.py`（屬性表分頁標題：半形→全形→人名查表→Big5 的小型 stub）。完整 lab 建置：`research/m064/build_lab.py`。
- **圖片**：EXE `RT_BITMAP`、`RES\*.BMP`，以及遊戲自訂 `.BMH`（Huffman 區塊格式，`research/m064/bmh.py`
  已逆向，518 檔往返驗證）。重繪時維持原尺寸、原調色盤、原格式，字形用 Windows GDI 細明體點陣（無反鋸齒）。
- **驗證**：Win11 本機 harness（`zhTW_lab\ld2-autotest`，不在本庫）在隔離副本中自動讀檔、走 UI、截圖；
  畫面文字由人工／模型判讀，不自動宣稱通過。

## 目錄

| 路徑 | 用途 |
|---|---|
| `src/ld2patch/` | 可攜核心：翻譯合約、catalog、PE 資源、Steam VDF |
| `patches/` | m020 資源譯文、詞彙、版本 |
| `research/m060`–`m063` | 觀察紀錄、catalog v3／v4、native helper、啟用交接 |
| `research/m064/` | `.rdata` 原位配線、顯示後備 hook、BMH 編解碼、怪物表、建置（`build_lab.py`） |
| `research/release/` | 發行：差分 payload（`make_delta.py`）、安裝程式原始碼（C#）、組裝與自我測試（`make_release.py`） |
| `research/translations/` | 候選譯文 JSON（只含繁中＋來源雜湊／offset，不含原文全文） |
| `docs/` | 交接、架構、安裝器規格、驗證缺口 |
| `tests/`、`tools/check.py` | 單元測試入口 |

## 重跑測試

Python 3.11+，只用標準函式庫：

```sh
python -B tools/check.py
```

持有合法原檔時可加 `--game-exe "你的遊戲副本/Ld95.exe"` 做記憶體內比對（不寫入、不啟動遊戲）。
缺原檔或非 Windows 時，相關測試顯示 SKIPPED，不算通過。

## 原則

- 只上傳原始碼、合成測試資料與文字紀錄；不上傳遊戲 EXE、圖檔、存檔或其衍生物。新檔需同時列入
  `.gitignore` 白名單與 `UPLOAD_ALLOWLIST.json`，並通過 `tools/audit_upload.py`。
- 不修改使用者的 Steam 原安裝；所有寫入都在拋棄式 lab 副本。
- 1.0.0 發行經專案擁有者批准（2026-11-08）。公開授權尚未選定，不主張擁有遊戲資產權利。

接續工作見 [HANDOFF](docs/HANDOFF.md)；其他文件：[架構](docs/ARCHITECTURE.md)、
[安裝器規格](docs/INSTALLER-SPEC.md)、[驗證缺口](docs/VALIDATION-GAPS.md)。
