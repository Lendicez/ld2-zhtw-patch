# m062 結果：v3 helper 物件（NamePair＋清單）Win11 MSVC 編譯回傳與 Linux 靜態稽核

日期：2026-10-29（Asia/Taipei）。`production_can_apply=false`、`release_approved=false` 不變。
設計見 `DESIGN-M062.zh-TW.md`；交接包見 `HANDOFF-COMPILE-M062/`。

## 總結：**通過**（編譯＋mock＋Linux 靜態稽核），兩個物件 hash 已鎖定

| 物件 | 入口 | 大小 | sha256（已鎖定） |
|---|---|---|---|
| `name_pair_v3.obj` | `_LD2_NamePair@16` | 6,865 B | `8a70e6cde5254d65aae4bf9d65fce6ee2b8065807af5741bc7092f37776c0242` |
| `list_insert_v3.obj` | `@LD2_ListInsertV3@24` | 7,584 B | `5ceba5a64b6e43d8f0f2e519cd91c076280656c7c1d1dd52c0f7025a62c3a037` |

鎖定值寫在 `rehearse_v3_objs.py` 的 `NAME_V3_OBJECT_SHA256`／`LIST_V3_OBJECT_SHA256`。
`.obj`／`.asm` 只留在實驗室（`compile-return-run1/`，不提交）；倉庫只放去識別化摘要 `compile-v3-run1/`。

## Win11 回傳（HANDOFF-COMPILE-M062，一次）

回傳 zip `m062-v3-compile-return.zip` sha256 `69c9cd561d371f7cdb33a005d7a40e9759e18cbb1ce82e54a9906c8a0325e3a4`（約 40 KB，2026-10-29 約 11:09 台北收到）。不含 EXE、存檔或截圖。

| 判定項 | 結果 | 依據 |
|---|---|---|
| 步驟 A 旗標 | `/c /W4 /WX /O2 /Oi /Oy- /GS /Gy /Zl /EHs`；catalog `LD2C v3`；`linked=false`、`native_executed=false`、`game_touched=false` | `compile-command.json` |
| SDK | 10.0.26100.0 | `once-result.json` |
| 清單 mock（步驟 B） | exit 0：`cases=29 assertions=1164 failed=0 game_or_user32_called=false`（含 `v3-mode0-female-any-hit-w`、`v3-mode0-male-join-hit-w`、`v3-mode0-ambiguous-join-original`、`v3-mode2-ambiguous-join-decoded`、`v3-mode0-tab-row-all-hits-w`、`v3-corrupt-blob-original`、`v3-bad-row-text-original`） | `stdout.txt` |
| NamePair mock（步驟 B） | exit 0：38 案例／25,815 assertions／0 失敗；`normal_abi_iterations=1000`、`four_parameter_helper=true`、`game_or_gdi_called=false`。assertions 與 Linux 預演相同 | `stdout.txt` |
| mock EXE | 只留在使用者 Win11，未回傳；hash 記錄在 `once-result.json` | — |

## Linux 靜態稽核（capstone；不載入、不連結、不執行）

`audit.json` 為完整輸出。

### `list_insert_v3.obj`（`audit_list_obj_v3.py`，profile v3）
- 未定義符號正好 13 個：v3 綁定 `_LD2_Catalog`、`_LD2_CatalogBytes`＋`_LD2_ListMode`＋8 個函式綁定＋cookie 二件組；沒有 memcpy／memset／chkstk／heap／EH／CRT。
- 唯一 public 符號是 `@LD2_ListInsertV3@24`。`.drectve` 為空（無 DEFAULTLIB；`.asm` 列表裡的 `INCLUDELIB` 已被 `/Zl` 擋掉）。
- 沒有 FS（SEH 註冊）、`std`／`enter`／`leave`；重定位只有 DIR32／REL32。
- 18 個正常返回、1,347 個 CFG 狀態：每條路徑都是 `ret 16`，ESP 與 EBX／EBP／ESI／EDI 都有保存；內部 cdecl 函式（`ld2c3_*`、`LD2C3_Lookup`、`LD2_ListPrepareV3`）遞迴稽核為 `ret 0`。
- 資料綁定（`_LD2_Catalog*`、`_LD2_ListMode`、cookie）從未被當成 call 目標。

**稽核器修正（本次新增）**：m061 的 `audit_list_obj.py` 第一次對 MSVC v3 物件報 `unreviewed call -> dword ptr [ebp - 0x210]`。原因是 MSVC 把 `LD2_OriginalDlgItem` 指標先存到堆疊槽（`_LD2_OriginalDlgItem$1$`，ebp-0x210），在 `ld2c3_open` 失敗路徑再 `call [ebp-0x210]`。clang 預演沒有這種寫法，所以 m061 稽核器沒處理。
- 新檔 `audit_list_obj_v3.py`（m061 稽核器的副本，m061／m061b 原檔與已鎖定物件都不動）加上 EBP 堆疊槽追蹤。只接受「從已追蹤綁定的暫存器 `mov [ebp-X], reg`」；同一槽被其他指令寫入，或被 `lea` 取址，就立刻失效。
- 這個槽和 `_misses$`（`LD2_ListPrepareV3` 的輸出參數）共用。稽核器在 `lea eax,[ebp-0x210]` 時就讓它失效，間接呼叫只發生在共用之前。
- 追蹤期間另外取址的區域有 `_view$`（-0x22c，16 B）、`_owned$`（-0x208，514 B）、`_misses$`。依 MSVC frame 配置核對過，都沒有和存活中的槽重疊。
- 負面測試：把 spill 改成存 ecx（=lp）時，稽核必須拒絕，實測確實拒絕（`test_m062_objs.py`）。

### `name_pair_v3.obj`（`audit_name_pair_v3.py`，移植自 m056 的 name_pair 稽核）
- 未定義符號正好 6 個：`_LD2_Catalog`、`_LD2_CatalogBytes`、`_LD2_ExpectedTextOutA`、`_LD2_TextOutW`＋cookie 二件組。
- public 正好 6 個：`NamePair@16`、`LoadMethod@4`、`OriginalOne@16`、`OriginalPair@12`、`FindCopy@16`、`Wipe@8`。
- 每個 public 函式的 `ret N` 都等於它的 stdcall 位元組數，ESP 與 non-volatile 暫存器在所有正常路徑都有保存。
- `OriginalOne` 經 `call eax` 呼叫原虛擬方法（ret 16）；`OriginalPair` 只呼叫兩次 `OriginalOne`；`TextOutW` 為 stdcall ret 20。
- 內部 cdecl：`ld2c3_open`／`ld2c3_find`／`ld2c3_cmp`／`ld2c3_u32`／`LD2C3_Lookup`。
- `.drectve` 為空；沒有 FS、`std`／`enter`／`leave`；重定位只有 DIR32 9 個、REL32 25 個。
- 負面測試：把 `Wipe@8` 的 `ret 8` 改成 `ret 12` 時必須拒絕，實測確實拒絕。

### 已知、不算失敗的觀察
- `ListInsertV3` 入口的保護條件含 `!LD2_OriginalDlgItem`，但這個分支仍會呼叫 `LD2_OriginalDlgItem`（m061b 原始碼也一樣）。綁定由合成器填入原 `CWnd::SendDlgItemMessage` 的位址，建構時就保證非 NULL；合併時要繼續核對這個綁定非 0。
- 例外／unwind 行為仍只在設計上推論，沒有在實機證明（與 m058／m061b 相同）。

## 測試
- `test_m062_objs.py`（新）5 項：hash 鎖定、兩個稽核通過、兩個負面測試。實驗室有物件時才跑，倉庫內會 skip。
- `test_m062.py` 8 項（2 項需要授權輸入，skip）；m061 `test_m061b.py` 13 項仍全過（m061 稽核器未改）。

## 下一步（Linux，不改發布旗標）
1. `merge_plan`／`enable_plan` 加入 v3 綁定：`_LD2_Catalog`、`_LD2_CatalogBytes` 取代 Entries／Count。NamePair v3 與 ListInsertV3 共用同一份 catalog blob，合成時把兩個物件併進同一個 helper 區段，再做雙物件重定位稽核。
2. 容量閘門：v3 blob 大小（目標 ≤8192 列）對照新區段的 RawSize／VirtualSize 與檔案對齊。超過預算時拒絕合成；`reviewed_catalog` 的 24 筆限制改成依審核狀態放行。
3. 合成 v3 惰性版＋啟用版（模式 2／模式 0）delta，Linux 靜態驗證後，才做下一次 Win11 可丟棄副本驗收包。
4. Mina 消耗品／冒險者名譯稿要人工審核；委託資訊視窗（156／388）的非清單 `?` 另案追蹤。
