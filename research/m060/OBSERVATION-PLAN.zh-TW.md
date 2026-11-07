# m060 可丟棄副本：遊戲／字型／例外／存讀檔 觀察計畫（run1：B 後誤判停止；run2：C～F＋G 完成）

狀態：**使用者已於 2026-10-28 批准「可丟棄副本單次觀察」，只限一次（one run only）**；交接包：`HANDOFF-OBSERVE/`（`WINDOWS-ONCE.ps1`、`USER-STEPS.zh-TW.md`）；重跑或第二次觀察需另外授權；仍不授權正式套用。`production_can_apply=false`、`release_approved=false` 不變。回傳證據後將同步 GitHub 並改以 GitHub 為主作業。

> **執行紀錄（2026-10-28）**：已執行一次。步驟 A、B 完成，B 結束碼 `0x00000001` 觸發 §3 停止；無 0xC0000409、無 WER 事件、無 dump，且已正常建檔——判讀為很可能是正常退出的誤判。C～F（m045 字型／UI／存讀檔）**未執行、仍未測**；G 收尾確認原安裝未變。詳見 `research/m060/observe-run1/RESULT.zh-TW.md（公開版；本機原件在 zhTW_lab/runs/m060-observe/）`。本次核准已用畢，續跑 C～F 需另行批准。

> **第二次觀察（run2）**：使用者 2026-10-28（訊息 t33u「請繼續」）批准續跑，**只跑 C～F＋G**，沿用 run1 的副本與第 1 格存檔；交接包 `HANDOFF-OBSERVE-CF/`（`WINDOWS-ONCE.ps1 -Run2`）。腳本已改：結束碼 1 在「無錯誤／WER 事件、無新 dump、有存檔」時為**軟警告**（見 §2b、§3）。仍不授權正式套用。

> **run2 執行紀錄（2026-10-28）**：R、C、D、E、F、G 全部完成，無硬停；C、F 結束碼 1 皆判為軟警告（0 事件、0 dump、有新存檔）。m045 靜態 UI（選單、狀態列、對話框標籤）在 Win11 正確顯示繁中；對話框清單中的遊戲動態字串（道具名、冒險者、委託）顯示 `?`／亂碼，已以位元組驗證為 Shift-JIS 資料被當 CP950 解讀（既有碼頁問題，非 m045 回歸）。原版↔m045 存讀檔往返在檔案層級成立。原安裝未變。詳見 `research/m060/observe-run2/RESULT.zh-TW.md（公開版；本機原件在 zhTW_lab/runs/m060-observe-run2/）`。依 §5：基本可用、仍非 release-gate；下一步進入 helper 合併鏈。`production_can_apply=false`、`release_approved=false`。

## 0. 這輪要回答的問題（只三題）

1. **字型**：m045 資源版（554 位置、71 字型指定）在 Win11 實機的選單、對話框、狀態列是否正常顯示繁中（無豆腐字、無 `?`、無明顯截斷／重疊）。
2. **例外路徑**：遊戲啟動→標題→進入遊戲→正常退出，過程中是否出現 `0xC0000409`、MFC 錯誤框、WER 崩潰紀錄。
3. **存讀檔**：在副本中「原版建檔→m045 版讀檔→存檔→原版再讀回」是否成立，且存檔 bytes 格式不因中文化改變（顯示時轉語言策略）。

**不在本輪**：m058／m060 原生 helper（TextOutW、道具名稱 Unicode）**不會**被注入或接入遊戲——目前沒有可用的 PE section／import 序列化器，且記憶體 plan 只接受原版、不接受 m045。道具名稱仍會是原版日文，屬預期結果，不算失敗。Win11 優化（LDWMM.dll 等其他 mod）也不納入。

## 1. 前置條件（任一不符即不開始）

- 使用者在對話中明確批准「m060 單次觀察」。
- 以**全新**資料夾作為副本，例如 `<LD2_ROOT>\zhTW_lab\game-acceptance\m060\game\`；資料夾已存在就停止（不覆蓋、不沿用 m043／m046）。
- 副本來源：已安裝的 `LunaticDawnPotB` **只讀複製**；複製前後記錄原目錄 `Ld95.exe` SHA-256 必須是 `6c817a0978cd9f02b66a7f15e6e46b752e490eaffaa520e18d360d296d40d5d2`。不符就停止。
- 副本內的 `Ld95.exe` 由既有離線產生器以 **m045 profile** 生成，產物 SHA-256 必須是 `4a0910243d159af8007b5e77369c21f262d9e7a402bcb92a991e4c368ccd9da7`（7,118,848 bytes）；不符就停止。
- **不**複製使用者的 `Usr\`、`LUNAS`、私人存檔；副本中的存檔一律在副本內新建。
- 不放入 `LDWMM.dll` 或其他 mod（避免混淆變因）；若副本來源本來就含其他 mod 檔，列出檔名＋hash 後停止詢問。
- 遊戲本體（Steam 安裝目錄）沒有在執行中；Steam 不在本輪做「驗證完整性」或更新。
- 不關閉 Defender／SAC、不加排除、不改 ACL／locale／系統字型設定。若被安全軟體封鎖：停止並截圖，不嘗試繞過。

## 2. 單次流程（嚴格順序，每步一次）

| 步 | 動作 | 觀察／蒐證 |
| --- | --- | --- |
| A | 建立副本、計算並記錄所有 hash（原目錄 Ld95.exe、副本原版、m045 產物） | `hashes-before.json` |
| B | 以**副本中的原版**（先暫名 `Ld95.orig.exe` 或另一個副本資料夾）啟動，開新遊戲、存到第 1 格後正常退出 | 截圖：標題、存檔畫面；記錄新建存檔檔名＋hash |
| C | 換成 m045 版 `Ld95.exe` 啟動，觀察標題與主選單 | 截圖：主選單、檔案選單、F1 說明、狀態列 |
| D | 讀第 1 格存檔，進入遊戲，開角色／道具／設施／戰鬥 UI 各一次（到得了才看，不刻意找） | 每個畫面一張截圖；註記豆腐字／`?`／截斷位置 |
| E | 存到第 2 格（不覆蓋第 1 格），正常退出 | 存檔檔名＋hash；退出碼 |
| F | 再用原版讀第 2 格存檔 | 截圖；能否讀入、日期欄是否仍是既知的「問號」現象（既有問題，不算新失敗） |
| G | 收尾：記錄副本與原目錄所有 hash | `hashes-after.json`；原目錄 Ld95.exe 必須與 A 相同 |

全部步驟只操作副本；不使用正式安裝器、不碰 Steam 安裝目錄的寫入。

## 2b. 第二次觀察（run2）：只跑 C～F＋G

- 前置（腳本 `-Run2` 步驟 R 自動檢查，任一不符就停止、不啟動遊戲）：run1 `state.json` 停在 `step B exit 0x00000001` 且未跑 C／F；run1 的 B 依新規則屬軟警告（結束碼 1、無事件、無 dump、有 `Usr\LUNAS000.LDP`）；來源 `Ld95.exe` hash 與原安裝全部檔案（略過 `Usr\`）和 run1 `hashes-before.json` 相同；`exe-store\` 兩版 hash 正確；`game\Ld95.exe` 為原版；副本 `Usr\` 與 run1 B 結束時相同；副本內無其他 dll／exe。
- 證據寫到新的 `evidence-run2\`（已存在就拒絕）；run1 `evidence\` 不動。
- 流程：C／D／E 同上表（m045 一次啟動），F 讀第 2 格後**另存第 3 格**再從選單結束（讓結束碼 1 有存檔佐證），G 收尾。
- 回傳到 `zhTW_lab/runs/m060-observe-run2/`。
- run1 副本已不存在時：停止回報；全新副本（A→G）需另行批准。

## 3. 立即停止條件（發生任一就停，不重試、不換方法）

- 任一前置 hash 不符，或副本資料夾已存在。
- 原目錄任何檔案 hash／修改時間改變。
- 遊戲崩潰、`0xC0000409`、MFC／C++ runtime 錯誤框、無回應超過約 60 秒。→ 只截圖與匯出事件紀錄，不再啟動第二次。
- **結束碼判定（run2 起）**：0＝成功。結束碼 1 **同時**符合「無 Ld95 相關 Application Error／WER／Application Hang／錯誤等級事件」「無本次新增 Ld95 dump／WER 報告」「本次有新增或改變 `Usr\LUNAS*.LDP`」→ **軟警告**（記錄 `exit_policy=soft-warn-exit1`，繼續下一步，使用者須在 observations.md 註明是否從選單正常結束）。`0xC0000409`、其他非 0 碼、或結束碼 1 但缺任一佐證 → 硬停。使用者看到錯誤框時，不論腳本顏色一律停止。
- 安全軟體封鎖、UAC 要求非預期權限。
- 存檔無法讀入或讀入後資料明顯錯亂（角色名／金錢／道具異常）。
- 出現要寫入副本以外位置的跡象（例如登錄或其他資料夾被改，若有觀察到）。

停止後只做蒐證，**不**修補、不重跑；回到 Linux 端分析後再另訂里程碑。

## 4. 要帶回的證據（放在 `zhTW_lab/runs/m060-observe/`，打包回傳）

- `hashes-before.json`、`hashes-after.json`（原目錄 Ld95.exe、副本內兩版 EXE、所有新建存檔）。
- 截圖（PNG，檔名以步驟開頭，例如 `C-main-menu.png`、`D-item-window.png`）。
- `observations.md`：每步「看到什麼／是否符合預期」一行；字型問題請寫畫面＋大概位置。
- 結束碼與時間（若有用 PowerShell 啟動：`Start-Process -Wait -PassThru` 的 `ExitCode`）。
- 崩潰時：`Get-WinEvent -LogName Application` 中 Ld95 相關的 Application Error／WER 項目（文字匯出即可），以及 `%LOCALAPPDATA%\CrashDumps` 若有 Ld95 dump **只記檔名與大小**，dump 本身先不要上傳（可能含記憶體內容）。
- 不要帶回：遊戲本體、原版／m045 EXE、私人存檔、RES／音樂等素材。

## 5. 判讀標準

| 結果 | 意義 | 下一步 |
| --- | --- | --- |
| B–G 全過、無崩潰、字型可讀 | m045 資源版在 Win11 副本上「基本可用」；**仍不是**全遊戲或 release-gate 通過 | 進入 helper 合併鏈（m045 輸入版記憶體 plan＋PE 序列化器）與擴翻譯 |
| 字型有問題但無崩潰 | 字型指定／字寬需調整 | 依截圖修 profile，下一輪再觀察 |
| 崩潰或存讀失敗 | 停止任何安裝器推進 | Linux 端分析證據，另立診斷里程碑 |

本輪結束後無論結果，`production_can_apply` 與 `release_approved` 都維持 false。
