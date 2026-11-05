# ld2-zhtw-patch

《Lunatic Dawn II》（`Ld95.exe`，Steam／本機版）的**繁體中文化補丁**與 Win11 執行調整之開發庫。

> **目前不是可安裝發行版。** 所有成果仍在 lab（拋棄式遊戲副本）驗證階段；
> `production_can_apply=false`、`release_approved=false`。本庫不含任何遊戲檔案（EXE、圖檔、存檔）。

## 現況（2026-11）

| 層 | 內容 | 狀態 |
|---|---|---|
| 資源文字（選單／對話框） | m020 已審核 239 處 | lab 建置中顯示繁中 |
| 道具／冒險者名稱 | catalog v4＋NameTextOut／ListInsert／NamePair hook（m063d 啟用版） | 商店、清單、裝備下拉、屬性表分頁顯示繁中 |
| 執行期 ANSI 字串（`.rdata`／`.data`） | m063 draft7–64＋地名表＋lab 補充：**1107 列原位 Big5**（m064） | 回歸全綠；畫面逐列確認中 |
| 字型 | 3 處 SHIFTJIS 字型改 CHINESEBIG5（資訊視窗、移動對話框等） | lab |
| 圖片內嵌文字 | 按鈕 23、狀態面板 8、移動地圖 17 重繪（m064） | lab |
| 地名 | 49 筆詞彙表，地圖／遊戲文字一致 | 已定案 |

開發主線在 **PR #26**（branch `research/m062-catalog-capacity`，Draft）。

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
| `research/m064/` | `.rdata` 原位配線、BMH 編解碼、地名表、逐列畫面確認（`SITE-LEDGER.json`） |
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
- 正式套用、安裝器與發行需專案擁有者明確批准。公開授權尚未選定，不主張擁有遊戲資產權利。

接續工作見 [HANDOFF](docs/HANDOFF.md)；其他文件：[架構](docs/ARCHITECTURE.md)、
[安裝器規格](docs/INSTALLER-SPEC.md)、[驗證缺口](docs/VALIDATION-GAPS.md)。
