# 動態清單名稱字串盤點（對齊 m061 8 個優先清單點）

> 狀態：Linux 靜態盤點，2026-10-29。**未在遊戲內驗證**；HANDOFF-LOADER-ENABLED 的 Win11 結果回來前，「顯示什麼」欄都是推定。
> `production_can_apply=false`、`release_approved=false` 不變。本文件只列繁中譯名與雜湊，不含日文原文、EXE、截圖或存檔。

## 1. 管線（m061 啟用版實際走的路）

1. 遊戲經 MFC `CWnd::SendDlgItemMessage`（`0x4ea671`）→ `SendDlgItemMessageA` 把 CP932 bytes 塞進清單；不經 `LoadStringA`，所以 **m045 的 554 個資源翻譯蓋不到這些清單**。
2. m061 把 8 個呼叫點改指向 `LD2_ListInsert`：依 Tab 分段 → 每段在 `.ld2c` catalog **完整 bytes 比對**（歧義不譯）→ 沒命中就 `MultiByteToWideChar(932, MB_ERR_INVALID_CHARS)` → `SendDlgItemMessageW`。
3. `.ld2c` 與 TextOutW helper（m056/m058，道具說明視窗）**共用同一份 catalog**：
   - 來源：`m051-items.zh-TW.json`（sha256 `afe520f3…3147`，24 個道具；22 翻譯＋2 保留原中文字）
   - 展開：24 名稱 × 11 種強化後綴（空、` +1`…` +10`）＝ **264 列**，每列 592 bytes（`LD2NameEntry`）
   - 展開程式：lab `research/m060/memory_plan.py::reviewed_catalog`（會核對 record／名稱 sha256）

## 2. 8 個優先清單點 × catalog 覆蓋

| 對話框 | 角色 | 呼叫點 | 推定內容 | catalog 覆蓋 | 預期顯示（未驗證） |
|---|---|---|---|---|---|
| 137 | 商店・購買 | `0x4aaf19`、`0x4ab0fe` | 道具名（可能帶 Tab＋價格） | 24／446 道具 | 24 種為繁中，其餘為正確日文 |
| 138 | 商店・出售 | `0x4b4df1` | 角色持有道具名（實例副本） | 同上，須 bytes 與原表一致 | 同上 |
| 139 | 商店・強化 | `0x4b46e4` | 道具名＋` +N` | 同上，含 +1～+10 | 同上 |
| 140 | 旅館・委託 | `0x4b3477` | 委託標題 | **0** | 日文 |
| 143 | 酒館 | `0x4b2d1f` | 冒險者／人名 | **0** | 日文 |
| 169 | 委託一覽 | `0x492431` | 委託標題 | **0** | 日文 |
| 156（＋388） | 委託資訊 | `0x4b1153` | 委託明細行 | **0** | 日文；**同函式也服務對話框 388** |

道具表規模（m048／m049）：primary 302＋extended 144＝446 slot、442 個不同名稱、record 216 B、名稱窗 ≤36 B（含 NUL）。

## 3. 缺口（依優先序）

1. **catalog 只有 24／446 道具（約 5%）**：商店三清單大多會顯示日文。下一步是擴充 `m051-items` 同格式詞條（按商店常見品項優先），不需改 helper。
2. **catalog 來源未進公開 repo**：`m051-items.zh-TW.json` 只在本機 `ld2-zhtw-patch-m051`（`research/item-sidecar-m051`，**尚無 commit**）。建議另開 PR 只收繁中欄位與 sha256（不含日文原文），讓 `.ld2c` 可重現。
3. **委託（140／156／169）與人名（143）沒有任何詞條**：委託標題可能是範本組字（`wsprintfA`），完整 bytes 比對難命中；需先追來源再決定範本級翻譯或保留日文。人名建議第一階段保留日文。
4. **長度**：中文名稱在 Tab 分段後仍受 257 UTF-16 units 緩衝上限；道具窗 36 B 對 W 路徑無影響（只在顯示層）。
5. **歧義**：同 bytes 對到不同譯文會不譯；目前 24 項無衝突，擴充時要有測試。

## 4. 第二波候選（同 catalog 可受惠，尚未啟用）

phase1 共 83 點，扣掉優先 8 點，與道具名直接相關者：道具頁 177／178／185（16 點）、整理 225（2）、倉庫 159（2）、偷竊 188（2）。
排除（有讀回）：存讀檔 152／153 的 1025／1026、分配 172 的 1071。

## 5. 相關檔案

- `research/m061/list_sites.json`、`research/m061/PLAN.zh-TW.md` §1–§9（`research/m061-list-unicode-merge-chain`）
- `research/m061/native/list_core.h`（比對／解碼核心）、`native/host_test.c`
- lab：`zhTW_lab/research/m060/memory_plan.py`、`m061/merge_plan.py`
- 本機：`ld2-zhtw-patch-m051/research/translations/m051-items.zh-TW.json`、`research/text/m048–m051*.json`

---

**EN summary.** The m061 list shim translates via exact-bytes lookup in a shared `.ld2c` catalog built from `m051-items` (24 items × 11 strengthen suffixes = 264 rows), else falls back to strict CP932→UTF-16. Of the 8 priority sites, shop buy/sell/strengthen (137/138/139) get zh-TW for 24 of 446 items; inn/commission (140/156/169) and tavern (143) have no catalog entries and will show correct Japanese at best. Gaps: expand the item catalog, publish the catalog source (zh-TW + hashes only), trace commission-title composition, and note that site `0x4b1153` also serves dialog 388. Static inventory only; not game-verified.
