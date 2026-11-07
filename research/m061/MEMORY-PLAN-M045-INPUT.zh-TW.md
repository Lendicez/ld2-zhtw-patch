# 記憶體 plan 接受 m045 輸出作為輸入：研究筆記（DRAFT）

> 只寫研究／安全文件，**不實作 PE section／import serializer、不動正式閘門**；`production_can_apply=false`、`release_approved=false`。

## 1. 目前接受的 hash

| 層 | 接受輸入 | helper 物件 |
|---|---|---|
| m060 `memory_plan`（記憶體／靜態） | 只收原版 `6c817a09…40d5d2` | 只收 m058 `/EHs` `5819838a…ac8c92`（m056 `0faa3fe5…` 已退役拒收） |
| m061 `source_profile.derive` | `original` 或 `m045` profile | — |
| m061 `merge_inert_dual`／m063 `merge_plan_v4` | 經 `source_profile.derive`，已含 `m045` profile 摘要 | m058 helper／v4 pinned objects |

m045 輸出：`4a0910243d159af8007b5e77369c21f262d9e7a402bcb92a991e4c368ccd9da7`，7,118,848 bytes，SizeOfImage `0x6e3000`（原版 `0x6dc000`），554 位置。

## 2. 重點

研究合併鏈（m061/m063）**已**能證明 m045 只差 `.rsrc` 與允許的 header 欄位（`.text/.rdata/.data` hash 與原版相同），並以 `first_free_rva=0x6e3000` 規劃。缺的是 **m060 記憶體 plan** 這一層仍只認原版。

## 3. 需要的 planner 變更（研究層級）

1. `memory_plan` 輸入改為「`source_profile.derive(original, candidate)` 回傳的 profile」，不再硬比原版 hash；仍需同時提供原版以驗共享 sections。
2. 新 VA 依 profile 的 `first_free_rva` 計算（m045 不可沿用原版 `0x6dc000`）。
3. helper 物件 pin 不變（`5819838a…`）；profile 與 object 兩組 pin 都要精確符合，無 bypass。
4. 輸出摘要加 `profile`、`source_sha256`；讀回驗證（`verify_readback`）比對對應 profile 的 sections。
5. 預期輸出 hash 從 per-profile versions（見 `VERSIONS-BY-PROFILE.zh-TW.md`）取得，不讀頂層 m020。

## 4. 風險

- m042 與 m045 同 size：誤判只能靠 hash 防，不得用 size。
- `.rsrc` 位移後若有 code 引用 `.rsrc` 內 RVA（目前未見），plan 會錯 → 需 derive 的共享 section 證明持續通過。
- CheckSum／SizeOfImage 被兩階段改寫：須定義「m045 → +helper」的單一序列化順序，避免雙重改寫。
- profile 混用（m020 records + m045 input）→ 由 versions-by-profile 閘門拒絕。

## 5. 排序

1. versions-by-profile（PR #23 + 接線）先完成。
2. 本項：memory_plan 改收 derive profile（純記憶體，Linux 合成＋合法原檔 SKIPPED 測試）。
3. 之後才是 PE section/import serializer 正式化（**不在本任務**）。
4. Win11 集中驗收後才討論任何閘門。

## 6. 範圍備註

道具實際欄位 441 筆已完成（placeholder 不譯），不在本項；剩餘文字缺口是動態 CP932 物品欄與約 44 筆延後的 UI 情境字串，與本項無關。
