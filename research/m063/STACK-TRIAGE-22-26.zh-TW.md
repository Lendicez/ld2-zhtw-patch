# LD2 Draft/Open PR #22–#26 堆疊盤點（m063）

資料來源：`gh pr view`／`gh pr list`（2026-11-03 16:45 UTC+8 擷取）。repo：Lendicez/ld2-zhtw-patch。

> **未經和良同意不得 merge 任何 PR。** `production_can_apply` 與 `release_approved` 一律維持 `false`。

## 各 PR 一覽

| PR | 標題 | base ← head | 狀態 | 規模 | 內容 |
|---|---|---|---|---|---|
| #22 | Research/m061 list unicode merge chain | `research/m060-observe-run2-notes` ← `research/m061-list-unicode-merge-chain` | Open（非 draft） | +11198/-0 | m061 動態 ListBox Unicode 合併鏈研究（名稱 TextOut／list 物件路徑） |
| #23 | Feature/versions gate m062 | `feature/candidate-profile-m047` ← `feature/versions-gate-m062` | Open（非 draft） | +227/-0 | versions.json 版本閘門，接在單 EXE 鏈 #19（m047）之上 |
| #24 | docs: dynamic list string inventory | `feature/versions-gate-m062` ← `docs/list-strings-inventory` | Draft | +53/-0 | 動態 list 字串清單，對齊 m061 優先對話框 |
| #25 | Research/m061 translation draft consumables adventurers | `main` ← `research/m061-translation-draft-consumables-adventurers` | Draft | +1831/-0 | 消耗品／工具 72 列＋冒險者譯名升級 523 列（machine_translit 0） |
| #26 | Research/m062 catalog capacity | `main` ← `research/m062-catalog-capacity` | Draft | +36889/-2 | m062 catalog 容量、v4 catalog／lab_preview、m063a–d 編譯／啟用驗收文字證據 |

## 舊堆疊 #1–#19
#1–#19 為單 EXE 安裝器／UI 翻譯串鏈（Steam 偵測 → 交易式備份還原 → 離線單檔產生器 → Windows 驗證 → m036–m047 UI 資源翻譯與候選 profile），依序互為 base，`#1` 以 `main` 為 base。#20、#21 已 merge（m060 observe notes）。

## 建議審查／合併順序（僅建議，須和良決定）
1. **#1→#19 單 EXE 鏈**：由底往上審；#23 依賴 #19 的 head（m047）。
2. **#23 → #24**：#24 base 為 #23，只是文件，跟在 #23 之後。
3. **#22**：base 是 m060 observe 分支（#20/#21 已併入的延伸），屬研究；可獨立審，不阻擋產品。
4. **#25**：base `main`、純譯文資料，可獨立審；與 #26 的 lab_preview 名稱需一致（サラ→薩拉 已對齊）。
5. **#26**：最大、研究性質；建議最後，或拆分後再審。

理由：先固定版本閘門與安裝器基礎（#1–#19、#23），再上資料（#25），研究類（#22、#26）不阻擋主線。

## 卡點
### 「可試玩 lab 繁中」(lab_preview, Mode 2)
- 已達成：m063d Win11 啟用驗收（讀檔／道具店／武器店／旅館／酒館／委託／訓練所自動綠燈），原安裝未被改動。
- 剩餘缺口：
  1. **動態 CP932 字串清單**：EXE `.rdata` 由程式碼 SetWindowText 的字串（例：訓練所 Static 1024，見 `TRAINING-STATIC-1024.zh-TW.md`）尚未全面盤點／翻譯。
  2. **約 44 項延後的 UI context 項目**（需 runtime 上下文確認）。
  3. 冒險者 polish draft6（約 10 列）另行由 Mina 提交、Mona 審。
- 道具表實際 slot 已完整（441），placeholder 刻意不譯，**不是缺口**。

### 「production 單 EXE」
- #1–#19、#23 未審未 merge；版本閘門未定案。
- v4 catalog（#26）尚未併入單 EXE 產生器，也沒有 production profile。
- 動態字串需容量策略（cp950 長度 ≤ 原 cp932 容量，或改 hook）。
- 和良人工驗收＋明確同意；在此之前 `production_can_apply=false`、`release_approved=false`。
