# m060 第二次觀察（只跑 C～F）：Win11 交接包

使用者已於 **2026-10-28（t33u）批准續跑 C～F**。這只是在可丟棄副本上觀察，**不是**安裝；`production_can_apply=false`、`release_approved=false` 不變。權威計畫：`OBSERVATION-PLAN.zh-TW.md`（§2b；zip 內附副本，repo 版在上一層 `../`）。逐步清單：[USER-STEPS.zh-TW.md](USER-STEPS.zh-TW.md)。

## 為什麼可以只跑 C～F
第一次（run1）A、B 已完成：副本、`exe-store\` 的原版／m045 EXE、以及原版在第 1 格建立的存檔 `Usr\LUNAS000.LDP`（sha256 `ae945041…27cec`）都還在副本裡；G 也確認原安裝未變。B 的結束碼 `0x00000001` 經分析是這款遊戲正常結束的回傳碼（無事件、無 dump、有存檔），被舊版腳本誤判停止。

`-Run2`（步驟 R）會先**重新核對**，任一不符就停止，不會啟動遊戲：
- run1 `state.json` 正是停在 `step B exit 0x00000001`、且 C／F 沒跑過；run1 的 B 依新規則判定為軟警告（結束碼 1、無事件、無 dump、有存檔）。
- 來源 `Ld95.exe` 仍是 `6c817a09…d5d2`，且原安裝全部檔案（略過 `Usr\`）與 run1 的 `hashes-before.json` 完全相同。
- `exe-store\` 兩版 EXE hash 正確；`game\Ld95.exe` 是原版；副本 `Usr\` 與 run1 B 結束時完全相同（第 1 格沒被動過）；副本內沒有其他 dll／exe。
通過後才建立新的 `evidence-run2\`（已存在就拒絕）；run1 的 `evidence\` 不動。

若 run1 副本已被刪除：腳本會停止。屆時需要改走全新副本流程（A→B→C→F→G，搭配新的 `-DisposableRoot`），請先回報。

## 結束碼判定（新）
| 結束碼 | 條件 | 結果 |
| --- | --- | --- |
| 0 | — | 成功 |
| 1 | 無 Ld95 相關 Application Error／WER／Application Hang／錯誤等級事件，**且**無本次新增 Ld95 dump／WER 報告，**且**本次有新增或改變 `Usr\LUNAS*.LDP` | **軟警告**（黃字，記錄 `exit_policy=soft-warn-exit1`，可繼續） |
| 1 | 缺少上列任一項 | 硬停 |
| `0xC0000409` 或其他非 0 | — | 硬停 |

所以 F 步驟請在讀第 2 格後**存到第 3 格**再退出——沒有存檔就無法區分「正常結束碼 1」與異常。軟警告不等於「確認正常」，請在 `observations.md` 寫明是否用選單結束。

## 寫入範圍
只寫 `<LD2_ROOT>\zhTW_lab\game-acceptance\m060\`：`game\Ld95.exe`（在原版／m045 之間切換）、`game\Usr\`（遊戲自己的存檔）、`evidence-run2\`。來源（遊戲安裝）只讀。

## 執行（每個指令只跑一次）
```powershell
cd <LD2_ROOT>\zhTW_lab\research\m060\HANDOFF-OBSERVE-CF
Unblock-File .\WINDOWS-ONCE.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Run2 -CheckOnly   # 只檢查
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Run2              # R
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Run2 -LaunchStep C  # C+D+E 一次
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Run2 -LaunchStep F
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Run2 -Finalize     # G
```
遊戲不在系統磁碟（例如 E 槽）時，每行加 `-LD2Root "<磁碟>:\GameDev\LD2"`（把 `<磁碟>` 換成實際磁碟代號，例如 E）。

## 檔案編碼注意
zip 內的 `WINDOWS-ONCE.ps1` 是 **UTF-8 含 BOM**（Windows PowerShell 5.1 需要 BOM 才能正確讀中文）。GitHub 上的同名檔依 repo 規則為 UTF-8 無 BOM，**請用 zip 版執行**；若要用 GitHub 版，請用 PowerShell 7（`pwsh`）或先另存為「UTF-8 含 BOM」。

## 回傳證據
把 `evidence-run2\` 的全部內容複製到 **`<LD2_ROOT>\zhTW_lab\runs\m060-observe-run2\`**，壓成 `m060-observe-run2-evidence.zip` 回傳。**不要**放入：任何 EXE、遊戲素材、存檔本體、crash dump 本體。截圖只在本機分析，不會上傳 GitHub。
