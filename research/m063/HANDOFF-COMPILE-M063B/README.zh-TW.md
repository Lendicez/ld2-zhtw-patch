# m063b HANDOFF-COMPILE-M063B：NameTextOut＋ListInsert＋NamePair 改用 v4 catalog 的編譯與 mock（不開遊戲）

最後更新：2026-10-31 04:30（台北）。`production_can_apply=false`、`release_approved=false`。

這一包只在 Win11 上**編譯**三個 helper 物件，並跑三個假 API 的 mock 測試：

- **不會**啟動遊戲
- **不會**讀取或寫入 `Ld95.exe`
- **不會**套用補丁，也不含 loader／啟用驗收

設計見 `research/m063/DESIGN-M063C-CATALOG-V4.zh-TW.md` §7；狀態見 `research/m063/STATUS.zh-TW.md`（阻礙 #6）。

## 為什麼要重新編譯（為什麼是三個物件）

m062 鎖定的 v3 物件（`name_pair_v3.obj`、`list_insert_v3.obj`）與 m063a 的 NameTextOut v3 都讀 v3 catalog。v3 分不開「同一串 bytes 既是道具名又是人名」的情況（Kris 短劍「波刃短劍」vs 女名「克莉絲」、戟斧 2 組、跨地區男名假切分 5 組）。

m063c 的 v4 catalog（`catalog_core_v4.h`）多了地區標籤與 `NAME_ONLY` 查表旗標，在模型與 C 核心層面解掉上面這些。v4 helper 會拒絕 v3 blob（v3 helper 也拒絕 v4），所以**三個用到 catalog 的物件必須一起換成 v4**，用同一套 MSVC 14.44 旗標一次產出，交回 Linux 稽核後才能鎖定 hash。三個 pin（`rehearse_v4_objs.py` 的 `*_V4_OBJECT_SHA256`）目前都是 `None`。

| 物件 | 入口 | 與上一版差異 | 查表旗標 |
|---|---|---|---|
| `name_pair_v4.obj` | `_LD2_NamePair@16` | 繪製路徑、ABI、例外行為、6 個 public 符號都與 m062 v3 相同；只換 v4 核心 | 0：只查 `full_id`（道具，依 stored_id），不查女性名、不拼男性名 |
| `list_insert_v4.obj` | `@LD2_ListInsertV4@24`、`@LD2_ListInsertNameV4@24` | 兩個入口共用一個 body（forceinline）。行為同 m062 ListInsertV3（模式 0／1／2、Unicode 視窗切換） | 道具／未分類清單（7 點）：`ALLOW_ANY\|ALLOW_JOIN`；人名清單（11 點）：再加 `NAME_ONLY` |
| `name_textout_v4.obj` | `@LD2_NameTextOut@24` | 綁定、ABI、public 符號同 m063a NameTextOut v3；只換 v4 核心與旗標 | `ALLOW_ANY\|ALLOW_JOIN\|NAME_ONLY`：人名點永遠不查 `full_id` 道具列 |

三個物件的綁定與 m062／m063a 相同（`_LD2_CatalogBytes`、`_LD2_Catalog` 等），只是 blob 版本換成 4。

## 內容

| 檔案 | 用途 |
|---|---|
| `WINDOWS-COMPILE-M063B.ps1` | 分三步：A＝三個 `cl /c`，不連結；B＝三個 mock 各連結並執行一次；C＝把回傳檔打包到桌面 |
| `native/catalog_core_v4.h` | v4 查表核心，不用 CRT，也不用 heap |
| `native/name_pair_v4.h`、`name_pair_v4.cpp` | NamePair v4 |
| `native/list_core_v4.h`、`list_bindings_v4.h`、`list_insert_v4.cpp` | 清單 helper v4（兩入口） |
| `native/name_textout_v4.h`、`name_textout_v4.cpp` | NameTextOut v4 |
| `native/v4_mock_blob.h` | 只給 mock 用：在執行時組出 v4 blob，可故意放進壞列、壞地區標籤、錯版本 |
| `native/list_mock_test_v4.cpp` | 清單 mock，共 54 案例：m062 的 29 案例原樣對 item 入口重跑，另加 name 入口（`NAME_ONLY`）與兩入口共用的 v4 案例 |
| `native/name_textout_mock_v4.cpp` | NameTextOut mock，共 36 案例：移植 m063a NameTextOut v3 mock（ABI 探針、例外穿透、vtable 替換）＋v4 案例：`NAME_ONLY`（Kris／戟斧型態不得顯示成道具）、只收同地區拼接、v3 標頭與壞地區標籤一律退回原路徑 |
| `native/name_pair_mock_v4.cpp` | NamePair mock，共 45 案例：m062 NamePair v3 mock 全部案例（ABI 探針、例外穿透、vtable 替換）＋v4 案例：旗標維持 0（同 bytes 的女名列被忽略、照畫道具名）、v3 標頭與壞地區標籤一律退回原路徑 |

`native/` 內 12 個檔案與 `research/m063/native-v4/` 同名檔逐位元組相同（未新增任何 helper 邏輯）。

## 預期結果

| 路徑（lab 根目錄底下） | 內容 |
|---|---|
| `runs\m063b\compile-only\name_pair_v4.obj`、`.asm` | 步驟 A 產出（交回） |
| `runs\m063b\compile-only\list_insert_v4.obj`、`.asm` | 步驟 A 產出（交回） |
| `runs\m063b\compile-only\name_textout_v4.obj`、`.asm` | 步驟 A 產出（交回） |
| `runs\m063b\compile-only\compile-command.json` | 旗標與三個物件的 sha256（交回） |
| `runs\m063b\mock\once-result.json`、`stdout-*.txt`、`stderr-*.txt` | mock 執行結果（交回） |
| `runs\m063b\mock\*.once.exe` | mock 診斷 EXE（**不要**傳回） |
| 桌面 `m063b-v4-compile-return.zip` | 腳本自動打包上面要交回的 14 個檔案，不含 EXE |

三個 mock 的最後一行必須符合下面的格式，否則腳本會 throw：

- 清單 mock：`cases=54 assertions=… failed=0 game_or_user32_called=false`
- NameTextOut mock：以 `{"cases":36,` 開頭，含 `"failed":0,` 與 `"catalog_version":4,`，以 `"game_or_gdi_called":false}` 結尾
- NamePair mock：以 `{"cases":45,` 開頭，含 `"failed":0,` 與 `"catalog_version":4,`，以 `"game_or_gdi_called":false}` 結尾

Linux 預演的 assertions：清單 2301、NameTextOut 12398、NamePair 25959。若 MSVC 的數字不同，腳本只印黃字提醒，不算失敗（m062 時 MSVC 與 Linux 數字完全相同）。

## Linux 端預演（已完成，2026-10-29／10-31 台北）

- 三個 mock 用 `zig c++ -target x86-linux-musl` 都已全過（2026-10-31 打包前重跑確認）：
  - 清單 mock：`cases=54 assertions=2301 failed=0 game_or_user32_called=false`
  - NameTextOut mock：`{"cases":36,"assertions":12398,"failed":0,…,"catalog_version":4,"game_or_gdi_called":false}`
  - NamePair mock：`{"cases":45,"assertions":25959,"failed":0,…,"flags":0,"catalog_version":4,"game_or_gdi_called":false}`
- `rehearse_v4_objs.py`（clang，x86-windows-msvc，暫存目錄）：
  - 清單物件：兩個入口各 1839 個 CFG 狀態、3 個正常返回，全部 `ret 16`，ESP 與非揮發暫存器保住；13 個未定義符號、2 個 public。
  - NameTextOut 物件：完整 CFG 稽核通過，6 個未定義、3 個 public。
  - NamePair 物件：符號集合（6 未定義／6 public）正確；完整 CFG 稽核只對 MSVC 物件做（同 m062）。
- 以上都是預演，不能鎖定 hash。只有 MSVC 產出的物件可以鎖定。

## 傳回後 Linux 端做什麼

```text
python3 -I -B research/m063/rehearse_v4_objs.py --list-obj list_insert_v4.obj --textout-obj name_textout_v4.obj --name-obj name_pair_v4.obj
```

稽核通過後，才把三個 sha256 寫進 `rehearse_v4_objs.py` 與 `merge_plan_v4.py`，再合成 v4 啟用版 delta。那是下一份 handoff（loader／實機觀察，需另外同意），**不在本包**。

## 已知可能的編譯差異

- `/W4 /WX` 下，MSVC 的警告集合和 clang 不同。v4 程式碼若觸發 MSVC 獨有的警告，步驟 A 或 B 會 throw。這時把整段 PowerShell 輸出貼回來即可，**不要自己改旗標**。
- 兩個 JSON mock 用了 MSVC x86 inline `__asm`（ABI 探針，與 m062 NamePair mock 同一種寫法）；Linux 端以 `-fasm-blocks` 預演過。
- 若稽核發現 `indirect jump`、`memcpy` 或新的堆疊槽寫法，由 Linux 端改原始碼或稽核器，使用者不需處理。

## 明確不做

- 不開遊戲，不讀寫 `Ld95.exe`，不碰存檔，不做 loader 驗收，不改呼叫點，不設 `production_can_apply`
- 不回傳 EXE、遊戲檔、存檔、截圖或記憶體傾印
