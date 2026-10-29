# m063c：catalog v4（地區標籤＋NAME_ONLY）— Linux 設計、模型與主機測試

最後更新：2026-10-29（台北）。`production_can_apply=false`、`release_approved=false`。
只在 Linux 做：Python 模型、可攜 C 核心、gcc 主機測試、lab 只出數量的摘要。**沒有** MSVC 編譯、沒有寫 EXE、沒有跑遊戲、沒有 Win11 交接包。

## 1. 要解的阻礙（`research/m062/draft3/REVIEW.zh-TW.md`「draft4 後剩下的阻礙」2、3）
| 阻礙 | v3 的行為 | 原因 |
|---|---|---|
| Kris 短劍（extended 28）與女名「克莉絲」同 bytes | 人名點（id=-1）先查 `full_id`，會顯示道具譯名，所以短劍目前不收 | v3 沒有「只查人名」的查表模式 |
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
輸入：pristine `Ld95.exe`（`6c817a09…d5d2`）＋ Mina draft4-sara 完整稿（`33f63c04…0f8e`）＋ m051。用完整稿，不是 lab_preview 子集。
| 項目 | v3（清單旗標） | v4 |
|---|---|---|
| 男名 40,000 組 | ok 39,993／退回 5／錯 2 | **ok 40,000**（NAME_ONLY） |
| 女名 600 | ok 600 | ok 600（NAME_ONLY） |
| 道具 `full_id` 4,840 列，帶 id 查 | — | 4,840 全對 |
| 道具 4,840 列，商店清單旗標 | — | 與 v3 完全相同 4,840 |
| 人名點會回道具譯名 | — | 0 |
| v4 blob | — | 6,137 列、253,644 B、sha256 `b1a3d256…5304` |
| C 核心 vs Python 模型 | — | 50,280 個查詢 **PASS 50,280 FAIL 0** |

**Kris 假設測試**（`lab_v4_names.kris_hypothetical.summary.json`；用 REVIEW 裡的建議譯名當暫代文字，**不是**翻譯定稿）：加入 extended 28 的 11 列（含 +1..+10）後，人名點顯示女名、道具帶 id 顯示短劍、商店清單 11 列都顯示短劍；v3 在人名點會顯示短劍（重現原阻礙）。C 交叉 50,302 PASS。

## 6. 測試
- `test_catalog_v4.py`（掛進 `tests/test_m063_research.py`，`tools/check.py` 會跑）：
  - 模型 10 項：三種阻礙的合成重現（v3 失敗、v4 正確）、同地區雙切法仍退回、NAME_ONLY 帶 id 拒絕、未知旗標、地區標籤合約、跨地區同 bytes 異譯、版本互斥、決定性。
  - C 交叉 4 項：gcc 編 `native-v4/catalog_v4_host_test.c`，基本＋60 組隨機合成 catalog（>5,000 查詢）、v3 blob 被拒、地區標籤損毀時 fail closed。沒有 C 編譯器就 skip。
  - 呼叫點分類 2 項。
  - lab 1 項：設 `LD2_M063C_LAB` 才跑，重算後必須與入庫摘要逐欄相同；否則 skip。
- 合成資料只用 CP932 片假名區的編碼位置，沒有遊戲 bytes。

## 7. 對 m063b（Win11 一次編譯）的影響 — 尚未改 native helper 原始碼
v4 核心入庫後，m063b 打包前還要（全部 Linux 可做，下一輪）：
1. `list_core_v4.h`：`LD2_ListPrepareV4(..., flags)`；`list_insert_v4.cpp` 匯出兩個入口 `LD2_ListInsertV4`（item／unclassified）和 `LD2_ListInsertNameV4`（name），共用本體。
2. `name_textout_v4.cpp`：旗標改 `ALLOW_ANY|ALLOW_JOIN|NAME_ONLY`；`name_pair_v4.cpp` 旗標 0，只換核心。
3. `merge_plan`／`enable_plan`：清單點依 `LIST_SITE_CLASS` 指向兩個入口；`.ld2c` blob 改 v4；稽核腳本的公開符號集合、ret 數更新。
4. mock 測試（i386 clang 預演）與 COFF 稽核更新，再把 m063b 的 MSVC 編譯一次涵蓋 NameTextOut＋ListInsert v4＋NamePair v4。
做完 1–4 之前，**不要**打包 m063b；打包也要先取得使用者同意。
