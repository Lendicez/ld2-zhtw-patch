# m063c：catalog v4（地區標籤＋NAME_ONLY）— Linux 設計、模型與主機測試

最後更新：2026-10-29（台北）。`production_can_apply=false`、`release_approved=false`。
只在 Linux 做：Python 模型、可攜 C 核心、gcc 主機測試、lab 只出數量的摘要。**沒有** MSVC 編譯、沒有寫 EXE、沒有跑遊戲、沒有 Win11 交接包。

## 1. 要解的阻礙（`research/m062/draft3/REVIEW.zh-TW.md`「draft4 後剩下的阻礙」2、3）
| 阻礙 | v3 的行為 | 原因 |
|---|---|---|
| Kris 短劍（extended 28，draft5 定稿「波刃短劍」）與女名「克莉絲」同 bytes | 人名點（id=-1）先查 `full_id`，會顯示道具譯名，所以 v3 不能收短劍 | v3 沒有「只查人名」的查表模式 |
| 男名 2 組（arabic 69+31、69+95）拼起來等於道具「戟斧」 | 道具 exact row 先命中，顯示「戟斧」 | 同上 |
| 男名 5 組跨地區假切分（阿爾頓×2、迪翁、法拉恩、法特恩） | 兩種切法得到不同譯名 → 退回原文 | prefix/suffix 不帶地區，A 地區前段＋B 地區後段也被接受 |

這三項都要改 helper，翻譯端無法解。

## 2. 格式（v4）
- 標頭和 v3 相同，只有 **version = 4**。v3 helper（`LD2C3_VERSION 3`）會拒絕 v4 blob；v4 核心也拒絕 v3 blob（兩邊都 fail closed，測試已鎖）。
- 列仍是 16 B；原本必須是 0 的保留 byte（offset 7）改成**地區標籤**：
  - `full_id`／`full_any`：必須 0；
  - `prefix`／`suffix`：1..4（western、arabic、chinese、japanese）。
  - 不符就視為損毀：Python `make_row` 拒絕；C 核心遇到就回 0（原文路徑）。
- 排序 `(kind, ansi_len, ansi, region, id)`；二分搜尋仍只比 `(kind, len, bytes)`，地區在同鍵列內過濾。
- 去重鍵加上地區：同一段 bytes 在不同地區可以有不同譯名（目前 draft4-sara 沒有這種情形，但格式允許）。

## 3. 查表旗標
| 旗標 | 值 | 意義 |
|---|---|---|
| `ALLOW_ANY` | 1 | 查 `full_any`（女名） |
| `ALLOW_JOIN` | 2 | 男名前後段拼接；**v4 要求前後段同地區** |
| `NAME_ONLY` | 4 | 完全不查 `full_id`；必須 `id=-1`，帶 id 一律回 0 |
| 其他位元 | — | 回 0（fail closed） |

## 4. 呼叫點分類（`catalog_v4.LIST_SITE_CLASS`，測試鎖定與 `enable_plan_m063` 的 18 個清單點完全一致）
| 類別 | 旗標 | 呼叫點 |
|---|---|---|
| `item_by_id` | 0 | NamePair（道具說明，帶 stored_id） |
| `item_list` | ANY\|JOIN（同 v3） | 商店 買 ×2（`0x4aaf19` `0x4ab0fe`）、強化 `0x4b46e4`、賣 `0x4b4df1` |
| `unclassified_list` | ANY\|JOIN（同 v3） | 委託清單 `0x492431`、委託資訊 `0x4b1153`、旅館委託 `0x4b3477`：內容是否含人名未確認，先維持 v3 行為 |
| `name` | ANY\|JOIN\|NAME_ONLY | 酒館 `0x4b2d1f`、m063 新增 10 個整名清單點、NameTextOut 全部 26 點 |

風險：酒館清單若一列有多段（tab 分隔），NAME_ONLY 也會套到非人名段。目前 catalog 只有道具與人名，非人名段本來就查不到，影響是「若某段剛好是道具名，v4 不再翻」。實機觀察時要看。

## 5. Lab 結果（只出數量；`lab_v4_names.summary.json`）
輸入：pristine `Ld95.exe`（`6c817a09…d5d2`）＋ Mina **draft5-kris-24** 完整稿（`13c84914…6a34d0`；draft4-sara＋extended 28「波刃短劍」＋24 筆標籤／說明不一致名字＋說明都收）＋ m051。用完整稿，不是 lab_preview 子集。
| 項目 | v3（清單旗標） | v4 |
|---|---|---|
| 男名 40,000 組 | ok 39,993／退回 5／錯 2 | **ok 40,000**（NAME_ONLY） |
| 女名 600 | ok 599／**錯 1**（克莉絲被短劍搶走） | **ok 600**（NAME_ONLY） |
| 道具 `full_id` 4,851 列（含 Kris 11 列），帶 id 查 | — | 4,851 全對 |
| 道具 4,840 列（Kris 以外），商店清單旗標 | — | 與 v3 完全相同 4,840 |
| Kris 11 列（+0..+10），商店清單旗標 | — | 11 列都顯示短劍 |
| 人名點會回道具譯名 | — | 0 |
| v4 blob | — | 6,148 列、254,096 B、sha256 `bbe4974f…1502` |
| C 核心 vs Python 模型 | — | 50,302 個查詢 **PASS 50,302 FAIL 0** |

**Kris（draft5 實列，2026-10-29 使用者經 Mina 定稿「波刃短劍」）**：draft 內含 extended 28 時 `lab_v4_names.py` 自動跑 Kris 檢查（`kris_draft_row_included: true`）：人名點顯示女名、道具帶 id 顯示短劍、v3 在人名點會顯示短劍（重現原阻礙，所以 v3 lab_preview 仍排除這 1 列）。
舊的 `lab_v4_names.kris_hypothetical.summary.json` 是 draft5 之前用暫代文字跑的，只留作歷史（只有數量，不含譯名）。

## 6. 測試
- `test_catalog_v4.py`（掛進 `tests/test_m063_research.py`，`tools/check.py` 會跑）：
  - 模型 10 項：三種阻礙的合成重現（v3 失敗、v4 正確）、同地區雙切法仍退回、NAME_ONLY 帶 id 拒絕、未知旗標、地區標籤合約、跨地區同 bytes 異譯、版本互斥、決定性。
  - C 交叉 4 項：gcc 編 `native-v4/catalog_v4_host_test.c`，基本＋60 組隨機合成 catalog（>5,000 查詢）、v3 blob 被拒、地區標籤損毀時 fail closed。沒有 C 編譯器就 skip。
  - 呼叫點分類 2 項。
  - lab 1 項：設 `LD2_M063C_LAB` 才跑，重算後必須與入庫摘要逐欄相同；否則 skip。
- 合成資料只用 CP932 片假名區的編碼位置，沒有遊戲 bytes。

## 7. 對 m063b（Win11 一次編譯）的影響 — native helper v4 已在 Linux 完成（2026-10-29 台北）
§7 原列的 1–4 都已在 Linux 做完（`research/m063/native-v4/`、`*_v4.py`）。仍**未**打包 m063b，也沒有任何 MSVC 物件。
1. **ListInsert v4**：`list_core_v4.h` 的 `LD2_ListPrepareV4(..., flags)`（只接受 `LD2_LIST_FLAGS_ITEM`=ANY|JOIN 與 `LD2_LIST_FLAGS_NAME`=ANY|JOIN|NAME_ONLY，其他旗標一律不翻）；`list_insert_v4.cpp` 兩個 fastcall 入口共用 `__forceinline` 本體：
   - `@LD2_ListInsertV4@24`：shop 4（0x4aaf19、0x4ab0fe、0x4b46e4、0x4b4df1）＋commission 3（0x492431、0x4b1153、0x4b3477）＝ v3 行為；
   - `@LD2_ListInsertNameV4@24`：酒館 0x4b2d1f＋m063 的 10 個整名清單點。
2. **NameTextOut v4**：同 v3 公開符號（`@LD2_NameTextOut@24`、`_LD2N_FindCopy@12`、`_LD2N_Wipe@8`），旗標 `ALLOW_ANY|ALLOW_JOIN|NAME_ONLY`（26 點：pair5×25＋tail8×1）。**NamePair v4**：同 v3 的 6 個公開符號，旗標 0，只換 v4 核心。v3／v4 物件靠 sha256 pin 與 blob 版本互相拒絕（v3 helper 拒 v4 blob，v4 helper 拒 v3 blob）。
3. **合併／啟用計畫**：`merge_plan_v4.py`（`capacity_gate_v4` 只收 version 4 blob；三個 v4 pin 目前皆 `None`，只能用明示的 rehearsal pin，報告 `rehearsal=True`、`handoff_eligible=False`；拒絕 m062/m063a 的 v3 pin）；`enable_plan_v4.py` 依 `LIST_SITE_CLASS` 分流（7 點 → item 入口、11 點 → name 入口），pair5／tail8／hook 與 m063a 相同。
4. **稽核與測試**：
   - `audit_list_obj_v4.py`：公開符號必須正好是兩個入口，兩個入口各自走 m062 v3 CFG 稽核（ret 16、ESP／非揮發暫存器、資料綁定不可被呼叫）；新增 opt-in 規則「clang 的 cookie 失敗尾端 call 不往下一個函式掉」（m062 預設不變，測試鎖定）。
   - `rehearse_v4_objs.py`：Linux clang 預演三個物件（暫存目錄，不 pin、不提交）。NameTextOut 走完整 CFG 稽核；NamePair 預演只查符號集合（clang 會把 OriginalOne 的 legacy `call eax` 內聯進 NamePair，完整稽核留給 MSVC 物件，與 m062 預演相同）。
   - mock（x86-linux-musl，只驗邏輯與 i386 ABI，不是 MSVC 物件）：List 54 cases／2301 assertions、NameTextOut 36／12398、NamePair 45／25959，全部 0 failed。反向驗證：把 name 入口改成 item 旗標 → 93 失敗；NameTextOut 拿掉 NAME_ONLY → 7 失敗；NamePair 旗標改 1 → 7 失敗。
   - `test_native_v4.py`（已接到 `tests/test_m063_research.py`）：原始碼旗標鎖定、計畫拒絕路徑、mock、預演稽核；lab 測試（box 上 lab 鏡像）以 m051 v4 blob＋預演物件建 inert＋enabled 影像：pair5 25、tail8 1、清單 18（item 7／name 11），每個清單點 rel32 指向正確入口；v3 物件／v3 blob／對調物件／改 1 byte 物件皆拒絕。

剩下（不是 Linux 能做的）：m063b 的 MSVC 一次編譯（NameTextOut＋ListInsert v4＋NamePair v4，**需使用者同意**後才打包交接），回來的物件用 `rehearse_v4_objs.py --list-obj/--textout-obj/--name-obj` 完整稽核後才填 pin。
