# m062 HANDOFF-COMPILE-M062：NamePair＋清單 helper 改用 v3 catalog 的編譯與 mock（不開遊戲）

最後更新：2026-10-29 05:20（台北）。`production_can_apply=false`、`release_approved=false`。

這一包只在 Win11 上**編譯**兩個 helper 物件，並跑兩個假 API 的 mock 測試：

- **不會**啟動遊戲
- **不會**讀取或寫入 `Ld95.exe`
- **不會**套用補丁

設計見 `research/m062/DESIGN-M062.zh-TW.md`。

## 為什麼要重新編譯

目前鎖定的兩個物件都把 catalog 寫死成最多 264 列、每列 592 位元組：m058 的 `name_pair.EHs.obj` 和 m061b 的 `list_insert_u.obj`。m062 的 v3 catalog 改成標頭加排序列加字串池，最多可放 8192 列，Mina 的消耗品與冒險者名稱草稿也放得進去。

v3 的讀取核心是 `catalog_core_v3.h`，Python 版 `catalog_v3.py` 與它交叉測試過。只要 catalog 格式一變，兩個物件都得用同一套 MSVC 14.44 旗標重新產出，交回 Linux 稽核後才能鎖定 hash。

| 物件 | 入口 | 與舊版差異 | 查表旗標 |
|---|---|---|---|
| `name_pair_v3.obj` | `_LD2_NamePair@16` | `FindEntry`＋`CopyName` 合併成 `LD2_FindCopy@16`。其餘繪製路徑、ABI、例外行為與 m058 相同 | 0：只查 `full_id`（道具，依 stored_id），不查女性名、不拼男性名 |
| `list_insert_v3.obj` | `@LD2_ListInsertV3@24` | m061b v2 行為不變，包括模式 0／1／2 與 Unicode 視窗切換。每個 tab 段改用 v3 查表 | `ALLOW_ANY\|ALLOW_JOIN`：道具、女性名、男性名「前半＋後半」拼接 |

兩個物件的綁定都從 `_LD2_EntryCount`、`_LD2_Entries` 換成 `_LD2_CatalogBytes`、`_LD2_Catalog`，其他綁定不變。

## 內容

| 檔案 | 用途 |
|---|---|
| `WINDOWS-COMPILE-M062.ps1` | 分三步：A＝兩個 `cl /c`，不連結；B＝兩個 mock 各連結並執行一次；C＝把回傳檔打包到桌面 |
| `native/catalog_core_v3.h` | v3 查表核心，不用 CRT，也不用 heap |
| `native/name_pair_v3.h`、`name_pair_v3.cpp` | NamePair v3 |
| `native/list_core_v3.h`、`list_bindings_v3.h`、`list_insert_v3.cpp` | 清單 helper v3 |
| `native/v3_mock_blob.h` | 只給 mock 用：在執行時組出 v3 blob，可故意放進壞列 |
| `native/name_pair_mock_v3.cpp` | NamePair mock，共 38 案例。包含 m058 原有的 ABI 探針、例外穿透與 vtable 替換，另外加測：女性名列與男性拼接必須被忽略、壞標頭、壞列 |
| `native/list_mock_test_v3.cpp` | 清單 mock，共 29 案例。m061b 原有 22 個，另加女性名命中、男性拼接命中、拼接歧義、tab 列、壞 blob、壞列 |

## 預期結果

| 路徑（lab 根目錄底下） | 內容 |
|---|---|
| `runs\m062\compile-only\name_pair_v3.obj`、`.asm` | 步驟 A 產出（交回） |
| `runs\m062\compile-only\list_insert_v3.obj`、`.asm` | 步驟 A 產出（交回） |
| `runs\m062\compile-only\compile-command.json` | 旗標與兩個物件的 sha256（交回） |
| `runs\m062\mock\once-result.json`、`stdout-*.txt`、`stderr-*.txt` | mock 執行結果（交回） |
| `runs\m062\mock\*.once.exe` | mock 診斷 EXE（**不要**傳回） |
| 桌面 `m062-v3-compile-return.zip` | 腳本自動打包上面要交回的 10 個檔案，不含 EXE |

兩個 mock 的最後一行必須符合下面的格式，否則腳本會 throw：

- 清單 mock：`cases=29 assertions=1164 failed=0 game_or_user32_called=false`
- NamePair mock：以 `{"cases":38,` 開頭，含 `"failed":0`，以 `"game_or_gdi_called":false}` 結尾

Linux 預演得到的 assertions 是 25815。若 MSVC 的數字不同，腳本只印黃字提醒，不算失敗。

## Linux 端預演（已完成，2026-10-29 台北）

- 兩個 mock 用 `zig c++ -target x86-linux-musl` 都已全過：
  - 清單 mock：`cases=29 assertions=1164 failed=0`
  - NamePair mock：`cases=38 assertions=25815 failed=0`
  - `-O2` 與 `-O0 -fsanitize=undefined` 兩種組態都測過。
- 變異測試：把 NamePair 的查表旗標改成 3（允許女性名與拼接）後，mock 有 13 項失敗，代表測試確實擋得住這種改動。
- `rehearse_v3_objs.py` 用 clang 以 x86-windows-msvc 編出物件，再做稽核：
  - 清單物件用 m061b 的完整稽核，外加 v3 profile：13 個未定義符號；`ret 16` 正常路徑有 3088 個狀態，全數保住 ESP 與非揮發暫存器；沒有 memcpy、memset、chkstk 或 CRT。
  - NamePair 物件：恰好 6 個未定義符號、6 個公開符號，沒有禁用匯入。
- 以上都是預演，不能鎖定 hash。只有 MSVC 產出的物件可以鎖定。

## 傳回後 Linux 端做什麼

```text
python3 -I -B research/m062/rehearse_v3_objs.py --list-obj list_insert_v3.obj --name-obj name_pair_v3.obj
```

稽核通過後，才把兩個 sha256 寫進合併規劃，再合成 v3 啟用版 delta。那是下一份 handoff，**不在本包**。

## 已知可能的編譯差異

- `/W4 /WX` 下，MSVC 的警告集合和 clang 不同。新程式碼若觸發 MSVC 獨有的警告，步驟 A 或 B 會 throw。這時把整段 PowerShell 輸出貼回來即可，**不要自己改旗標**。
- 若稽核發現 `indirect jump` 或 `memcpy`，由 Linux 端改原始碼，使用者不需處理。

## 明確不做

- 不開遊戲，不讀寫 `Ld95.exe`，不做 loader 驗收，不改呼叫點，不設 `production_can_apply`
