# ld2-zhtw-patch

《Lunatic Dawn II》（`Ld95.exe`，Steam／本機版）的**繁體中文化補丁**與 Win11 執行調整之開發庫。

> **目前不是可安裝發行版。** 所有成果仍在 lab（拋棄式遊戲副本）驗證階段；
> `production_can_apply=false`、`release_approved=false`。本庫不含任何遊戲檔案（EXE、圖檔、存檔）。

## 現況（2026-11）

| 層 | 內容 | 狀態 |
|---|---|---|
| 資源文字（選單／對話框） | m020 已審核 239 處 | lab 建置中顯示繁中 |
| 道具／冒險者名稱 | catalog v4＋NameTextOut／ListInsert／NamePair hook（m063d 啟用版） | lab 建置中商店／清單顯示繁中 |
| 執行期 ANSI 字串（`.rdata`） | 1081 列候選譯文（m063 draft7–64）；**1040 列已在 lab 原位配線**（m064） | 回歸全綠；畫面逐列確認中 |
| 圖片內嵌文字 | 按鈕 23 張、狀態面板 8 張已重繪；移動地圖 17 張待做（m064） | lab |
| 地名 | 49 筆詞彙表（`research/m064/PLACE-NAMES.zh-TW.json`） | 已定案 |

開發主線在 **PR #26**（branch `research/m062-catalog-capacity`，Draft）。

## 技術路線

- **執行期字串**：lab 機系統 ANSI code page 為 950（zh-TW）。遊戲以 ANSI API 顯示 `.rdata` 字串，
  在原位址改寫為 Big5（CP950）位元組即可直接顯示繁中，不需 hook。工具：`research/m064/rdata_ansi.py`
  （逐列檢查原文槽 sha256、NUL 結尾、CP950 編碼、容量、printf／`%A` 類替換符合約；只寫 lab 複本）。
- **hook 路徑例外**：經 m063 v4 TextOut hook 顯示的字串（hook 以 CP932 解碼）不可原位改 Big5，
  改由 v4 catalog 在 hook 端換成 UTF-16 繁中。
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
