# m062：versions.json 依 profile 的版本閘門（m020 ≠ m045）

> 命名：ROADMAP 原把本項暫稱 m061；m061 已改給「清單動態字串」研究，本項順延為 **m062**，內容不變。
> 本里程碑**不改**任何發行閘門：`production_can_apply=false`、`release_approved=false`，頂層 `patches/versions.json` 仍指向 m020。

## 問題

- 頂層 `patches/versions.json`（schema 1）只列 m020 預期輸出 `a15bf731…3c81`／7,102,464 bytes（239 位置）。
- 預設 trial profile 已是 **m045**，輸出 `4a091024…9da7`／7,118,848 bytes（554 位置），pin 只在 `patches/m045/versions.json`（schema 2）。
- 若 planner／安裝器一律讀頂層檔，就會拿 m020 的 hash 去判斷 m045 產物，造成「m045 產物被當未知版本」或（更糟）把 m020 記錄誤用於 m045 發行判斷。

## 本次變更

- `src/ld2patch/profiles.py` 新增 `planner_config(profile, root)`：
  先走既有 `load_bundle`（recipe／catalog／versions 全部對 pin 驗證），再以 `preview_versions` 投影成 planner 可讀的 schema 1，
  並再次確認 `id`、預期輸出 hash、size 與 `PINS[profile]` 一致、`release_approved is False`，最後交給 planner `_versions` 嚴格檢查。
  這只是唯讀設定來源，**不是**安裝能力，也不會改寫任何檔案。
- `tests/test_versions_gate_m062.py`（12 個測試，全部 Linux 合成、不需遊戲）：
  - m020 與 m045（以及所有 profile）輸出 hash 互不相同；size 不唯一（m042＝m045），因此必須以 hash 判斷。
  - 每個 profile 的 `planner_config` 都對應自己的 pin；m020 的結果與頂層 `versions.json` 完全相同。
  - 預設 m045 記錄 ≠ 頂層 m020 記錄（同一原版 source，不同預期輸出）。
  - 頂層檔仍是 m020 且所有 `versions.json` 的 `release_approved` 皆為 false（tripwire）。
  - m020＋m045 合併成同一份 allowlist 會被拒（`invalid_or_ambiguous_version_hash`），不會「誰排前面用誰」。
  - 竄改 m045 記錄（`release_approved=true`、塞入 m020 hash、改成 m020 id、只改 size）全部被拒；未知 profile 被拒。
  - 用合成 bytes 驗證 planner：m045 記錄下 m020 產物＝`unsupported_hash`；m045 產物＝`already_patched`；原版仍停在 `release_not_approved`。

## 刻意不做

- 不把頂層 `versions.json` 改成 m045，也不接到 `tools/run_disposable.py`／安裝器正式路徑：要等 Win11 集中驗收（ROADMAP §3 第 5 步）後再決定 pin m045 或之後的輸出。
- 不碰 `research/m061-*`（清單 Unicode 合併鏈，另一條研究線）。

## 驗證

```
python -B tools/check.py
python -B -m unittest tests.test_versions_gate_m062 -v
```

缺合法原檔時整合測試保持 SKIPPED，不算通過。
