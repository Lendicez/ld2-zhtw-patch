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

## v3 合併與容量閘門（Linux 靜態，2026-10-29 台北）

`production_can_apply=false`、`release_approved=false` 不變。沒有寫出 EXE、沒有執行遊戲、沒有新的 Win11 交接包。

### 新檔
| 檔案 | 作用 |
|---|---|
| `merge_plan_v3.py` | v3 合併：`name_pair_v3.obj`＋`list_insert_v3.obj` 放進同一個 `.ld2t`，兩者共用**同一份** `.ld2c` v3 blob；審核閘門、容量閘門、OriginalDlgItem 非 0 檢查 |
| `build_v3_lab.py` | 實驗室：從 m045 在記憶體中合成惰性版＋啟用版（模式 2／0），並做靜態驗證；只輸出 JSON |
| `make_v3_delta.py` | 實驗室：m045 → 啟用版 delta，只寫到 `lab-deltas/`（**不提交**，含遊戲衍生的 catalog bytes） |
| `test_merge_v3.py` | 17 項：審核閘門 6、容量閘門 5（合成，永遠跑）＋實驗室 6（缺輸入時 skip） |
| `static_verify_v3.summary.json` | 兩種 catalog × 兩種模式的完整靜態驗證輸出（只有 hash／VA／數量，沒有日文或遊戲 bytes） |

m061／m061b 的 `merge_plan.py`、`enable_plan.py` 和已鎖定的 v1／u 路徑都沒改；`enable_plan.apply_enabled`（hook stub＋8 個清單呼叫點）直接沿用，因為 NamePair v3 仍是 `_LD2_NamePair@16(cdc, ansi, count, id)`，ListInsertV3 仍是 fastcall／ret 16。

### `.ld2c` 版面（v3）
| 偏移 | 內容 | 綁定 |
|---|---|---|
| +0 | `CatalogBytes`（u32，等於 blob 長度） | `_LD2_CatalogBytes`（兩個 helper 共用） |
| +4 | `ExpectedTextOutA` = 0x4e13d7 | NamePair |
| +8 | `OriginalDlgItem` = 0x4ea671（**非 0**） | ListInsertV3 |
| +12 | `ListMode`（0／1／2） | ListInsertV3 |
| +16 | v3 blob（`LD2C` header＋rows＋pool） | `_LD2_Catalog`（兩個 helper 共用） |

### 審核閘門（取代 m060 `reviewed_catalog` 的 `len(items)==24`）
- 每個 catalog 都要 hash 釘選；`production_can_apply` 必須是 false、`release_approved` 不能是 true。
- 每一筆都要 `name_status ∈ {translated, identity_preserved}`。
- `review_status`：
  - 政策 `reviewed`（預設）：只接受 `human_reviewed`／`approved`。沒有這個欄位的只限釘選的 m051 基準（24 筆）。
  - 政策 `lab_preview`：另外接受 `mina_draft`，但整個 build 標成 `release_eligible=false`。
- 整個 catalog 一筆不合就整個拒絕，不會偷偷濾掉。筆數不再有上限，只受容量閘門限制。
- m060 的 v1 路徑（餵給舊 helper）保留 24 筆規則不動。

### 容量閘門（拒絕，不截斷）
- `decode_v3` 完整解析（header、extent、排序、嚴格 CP932／UTF-16）；列數 ≤ 8192、pool ≤ 1 MiB、blob ≤ helper 的 `ld2c3_open` 上限 1,179,680 B。
- `.ld2c` 區段（16＋blob）≤ `pe_serializer.MAX_SECTION_BYTES`（1 MiB）。注意 helper 理論上限比區段預算大：合成測試做了一個 8192 列、helper 會接受但超過 1 MiB 的 blob，確認合成前就被拒絕。
- 合成後再讀回 `.ld2c` 區段頭：VirtualSize＝catalog 長度、RawSize 與 PointerToRawData 依檔案對齊、尾端補 0、內容逐 byte 相同、`CatalogBytes` 讀回正確、blob 讀回後解碼結果相同。

### 實驗室結果（m045 為底，hash 都可重現）
| catalog | 列數 | blob | blob sha256 | 區段剩餘 |
|---|---|---|---|---|
| `reviewed`（m051 24 項） | 264 | 12,236 B | `2879e445…7abf` | 1,036,324 B |
| `lab_preview`（m051＋Mina 草稿） | 2,343 | 87,628 B | `69f86cdc…96bb` | 960,932 B |

| 組合 | 惰性版 sha256 | 啟用版 sha256 | delta sha256（大小） |
|---|---|---|---|
| reviewed 模式 2 | `99f4ae54…5e47` | `67ef9bac…c01a` | `99969b5c…ad9b`（24,749 B） |
| reviewed 模式 0 | `043efdd6…c140` | `7a51d870…15be` | `b4ec4ee5…9bad`（24,749 B） |
| lab_preview 模式 2 | `1d0a97a6…f6e2` | `2e6dca9c…91b0` | `69ba0bd3…0e7b`（102,575 B） |
| lab_preview 模式 0 | `caede6e0…4146` | `969f5c7b…03b9` | `cba1131b…4735`（102,575 B） |

完整 hash 在 `static_verify_v3.summary.json`；delta 與 manifest 只在實驗室 `lab-deltas/`。

### 靜態驗證（四個組合全部通過）
- 物件稽核先跑：`audit_list_obj_v3`（profile v3，含 EBP spill 追蹤）＋`audit_name_pair_v3`。
- **重定位獨立重算**：從物件重新解析每一筆 relocation，對照影像中的值。NamePair 34 筆（DIR32 9＋REL32 25）、ListInsertV3 43 筆全部相符；非 fixup 的 code bytes 與物件逐 byte 相同；每個 undefined 符號都至少被用到一次。
- **綁定目標讀回**：6 個 USER32 IAT、KERNEL32!MultiByteToWideChar、GDI32!TextOutW 都指到正確名稱；兩個 helper 的 `_LD2_Catalog`／`_LD2_CatalogBytes`／cookie 位址相同（共用一份 blob）；`OriginalDlgItem` 槽讀回 **0x4ea671（非 0）**；ListMode、ExpectedTextOutA 讀回正確；blob sha 讀回相符。
- **間接呼叫掃描**（重定位後的 ListInsertV3）：8 個呼叫目標都是函式綁定槽（含 `call [ebp-0x210]` 經 spill 追回 OriginalDlgItem 槽 0xae5008）；沒有資料綁定被當成呼叫目標；NamePair 只有一個 `call eax`（`LD2_OriginalOne` 的原虛擬方法，物件稽核已審）。
- m061 共用檢查：hook stub 反組譯、沒有分支跳進 hook 區間內部、8 個清單呼叫點 `call 0x4ea671 → call ListInsertV3`、PE CheckSum（pefile 也通過）。新匯入只有 TextOutW＋5 個 USER32 *W API，沒有禁止的 API。
- 負面測試：OriginalDlgItem 設成 0、物件 hash 不符或互換、區段超過預算、`reviewed` 政策下放入草稿，都會拒絕。

### Win11 交接
**這一輪不準備交接包。** 靜態驗證全過，delta 也已在實驗室備好；但 reviewed catalog 只有 m051 的 24 項，遊戲內看起來跟 m061b 差不多，實機驗收的新資訊有限；lab_preview 含未審核草稿。等以下其中一項成立再做：(a) Mina 草稿有一批改成 `human_reviewed`；(b) 使用者同意用 `lab_preview` 做一次可丟棄副本的觀察（模式 2 優先、模式 0 備用）。

## 測試
- `test_merge_v3.py` 17 項、`test_m062.py` 8 項（給授權輸入時全跑）、`test_m062_objs.py` 5 項：全過。
- m061 `test_m061.py`／`test_m061b.py`／`test_merge_lab.py` 共 38 項：全過（m061 原始碼未改）。
- 公開倉庫：`merge_plan_v3.py` 內嵌 m061 的常數（m061 `merge_plan.py` 依賴實驗室專用的 m060 `memory_plan.py`，不在倉庫裡），`build_v3_lab.py` 在實驗室會逐項比對兩邊常數不漂移。`tests/test_m062_research.py` 加跑 `test_merge_v3.py`；倉庫 `tools/check.py` 64 項通過（20 項因缺授權輸入 skip），`tools/audit_upload.py` 無發現。

## 下一步（Linux，不改發布旗標）
1. 冒險者名的顯示點還沒追蹤到（DESIGN §5-2）；lab_preview 裡的 1400 筆人名要等找到顯示點才有意義。
2. Mina 消耗品／冒險者名譯稿人工審核，審過的改成 `human_reviewed`，就能進 `reviewed` 政策。
3. 委託資訊視窗（156／388）的非清單 `?` 另案追蹤。
4. 例外／unwind 行為仍只有設計推論，等實機驗收。
