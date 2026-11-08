# versions.json 依 profile 讀取：研究／設計草稿（m061 研究線，DRAFT）

> 純研究文件，**不改任何程式或閘門**。`production_can_apply=false`、`release_approved=false` 皆維持；頂層 `patches/versions.json` 不動。

## 1. 現況（2026-11-03 盤點）

| 來源 | schema | 預期輸出 | size | 位置數 |
|---|---|---|---|---|
| 頂層 `patches/versions.json` | 1（欄位 `historical_m020_sha256/size`） | m020 `a15bf731…3c81` | 7,102,464 | 239 |
| `patches/m045/versions.json`（m045 分支） | 2（欄位 `expected_output_sha256/size`） | m045 `4a091024…9da7` | 7,118,848 | 554 |

- 兩者 `source_sha256` 相同（原版 `6c817a09…40d5d2`／7,090,176）。
- `src/ld2patch/planner.py::_versions` 只收 schema 1，且只認 `historical_m020_*` 欄位；`controller.py` 也直接用 `_versions(self.config)` 判斷「原版／已 patch」。
- `profiles.py::preview_versions` 已能把 schema 2 投影成 schema 1 欄位名（唯讀）。
- **size 不唯一**：m042 與 m045 都是 7,118,848 → 只能以 hash 判斷。

## 2. 已有進度：PR #23（`feature/versions-gate-m062`）

PR #23 已新增 `profiles.planner_config(profile, root)`：走 `load_bundle` 驗 pin → `preview_versions` 投影 → 再比對 `PINS[profile]`、`release_approved is False` → 交給 `_versions` 嚴格檢查；附 12 個合成測試（m020/m045 不混用、合併 allowlist 被拒、竄改被拒）。
因此本項「讀取層」主體已在 #23；本文件只補**剩餘接線設計**，不重做。

## 3. 剩餘缺口

1. `controller.py`、`tools/run_disposable.py`、安裝器正式路徑仍讀頂層檔，未改走 `planner_config(selected_profile)`。
2. 頂層檔要「保留 m020 歷史」還是「升 schema 2 多 profile」尚未決定（需 Win11 集中驗收後）。
3. schema 2 正式支援 `_versions`（而非靠投影）尚未做。

## 4. 建議 API／行為（草案）

- 單一入口：`resolve_versions(profile: str, root) -> list[dict]`（= #23 `planner_config` 的薄包裝）。
  - `profile` 必須明確給；**沒有**預設回退到頂層檔、**沒有** allow-unknown。
  - 未知 profile → `unknown_profile`；pin 不符 → `pinned_versions_mismatch`。
- controller／planner 改收 `resolve_versions` 結果，不再自行開頂層檔。
- 頂層檔兩案（擇一，之後再定）：
  - A（建議、最小）：頂層維持 schema 1 m020，標為 historical；正式路徑一律 per-profile。
  - B：頂層升 schema 2，`profiles: {m020: {...}, m045: {...}}`，見 `versions-by-profile.DRAFT.json`（**未接線**）。B 需同步改 tripwire 測試，風險較大。
- 每筆記錄 `release_approved` 必為 `false`；讀取端遇 `true` 一律拒（tripwire，不是開關）。

## 5. 測試計畫

- 沿用 #23 的 12 測試；新增：
  - controller 以 m045 profile：m045 產物＝already_patched、m020 產物＝unsupported_hash、原版＝release_not_approved。
  - controller 不帶 profile → 拒絕（不靜默讀頂層）。
  - 原始碼掃描：正式路徑不得再出現直接 `open(...'versions.json')` 頂層讀取。
  - 頂層檔 tripwire：仍 m020、`release_approved=false`。
- 全部 Linux 合成；需合法原檔的整合測試缺檔時 SKIPPED，不算通過。

## 6. 非目標

- 不翻 `release_approved`／`production_can_apply`。
- 不 merge #23，不改頂層 `patches/versions.json`。
- 不接安裝器寫入路徑；不碰翻譯 delta（#25）。

## 7. 排序

#23 review → controller/run_disposable 改走 per-profile（新小 PR）→ Win11 驗收 → 再決定頂層 A/B。
