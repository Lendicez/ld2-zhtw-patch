# m060 可丟棄副本觀察：結果分析（2026-10-28）

證據來源：使用者回傳的 `m060-observe-evidence.zip`，解壓於本機 `zhTW_lab/runs/m060-observe/evidence/`。公開版路徑以 `<LD2_ROOT>` 取代私人機器路徑；`hashes-before.json` 只放摘要（`hashes-before.summary.json`，略去 1,029 檔完整清單）；JSON 去除 BOM、換行改 LF，其餘數值未改。
截圖（`screens/B-title.jpg`、`screens/B-save.jpg`）只留在本機分析，**不上傳 GitHub**（遊戲畫面版權）。

## 一句話結論

步驟 A、B 完成；B 結束後腳本因結束碼 `0x00000001` 依計畫 §3 停止。證據顯示**這很可能是誤判的正常退出（false positive），不是確認的崩潰**。
**m045 在 Win11 上的 UI／字型／存讀檔往返（C～F）完全沒有跑到，仍屬未測。** `production_can_apply=false`、`release_approved=false` 不變。

## 各步結果

| 步 | 結果 | 依據 |
| --- | --- | --- |
| A 副本＋hash | ✅ 通過 | `hashes-before.json`：來源 `Ld95.exe` 7,090,176 bytes、sha256 `6c817a09…40d5d2`，複製前後一致；副本原版同 hash；m045 產物 7,118,848 bytes、`4a091024…9da7`；排除 `Usr`、`LUNAS`；`saves_created=[]`；Windows `10.0.26200.0` |
| B 原版新遊戲→存第 1 格→退出 | ⚠️ 遊戲行為正常，但腳本判停 | `launch-B.json`：原版 EXE、執行 533.2 秒、`exit_code=1`、`is_0xC0000409=false`、`crash_dumps_names_only=[]`；`launch-B-events.txt` 只有 BOM＋換行（0 筆 Ld95 相關 Application 事件）；新存檔 `Usr\LUNAS000.LDP` 3,032,781 bytes、sha256 `ae945041…27cec`（14:05:19Z 寫入，約在退出前 4 分鐘）；截圖可見標題畫面與存檔對話框第 000 格已有資料 |
| C m045 主選單等 | ⛔ 未執行 | `state.json`：`steps_done=["A","B"]`、`stopped="step B exit 0x00000001"` |
| D m045 讀第 1 格＋UI | ⛔ 未執行 | 同上 |
| E m045 存第 2 格 | ⛔ 未執行 | 同上 |
| F 原版讀第 2 格 | ⛔ 未執行 | 同上 |
| G 收尾 hash | ✅ 通過 | `hashes-after.json`：`source_exe_same_as_before=true`、`source_manifest_changes=[]`（原安裝 1,029 個檔案全部未變）；store 中原版／m045 hash 皆符合預期；副本目前作用中的 EXE 仍是原版；`finalized=true` |

## 為什麼判讀為「誤判的正常退出」

1. 腳本（`WINDOWS-ONCE.ps1` 第 245 行）把**任何非 0 結束碼**都當崩潰：`$crash = ($code -ne 0)`。
2. 這款 1990 年代末的 MFC 遊戲，從選單「結束」離開時回傳非 0 碼並不罕見；本次：
   - 沒有 `0xC0000409`（STATUS_STACK_BUFFER_OVERRUN）；
   - Application 事件記錄沒有任何 Ld95 相關的 Application Error／WER 項目；
   - `%LOCALAPPDATA%\CrashDumps` 沒有 Ld95 dump；
   - 執行了約 9 分鐘、正常建檔並存檔、截圖顯示 UI 正常。
3. 因此最可能是正常退出。**但**：`observations.md` 使用者未填，沒有「是用選單正常結束」的直接證詞，所以只能寫「很可能」，不能寫「確認」。

## 次要觀察（不改變結論）

- **路徑記錄**：`hashes-before.json` 的 `source_dir` 為 `<LD2_ROOT>\LunaticDawnPotB`（C 槽）；存檔對話框中顯示的副本路徑在截圖中被讀作 E 槽的 `<LD2_ROOT>\zhTW_lab\game-acceptance\m060\…`（截圖解析度低，磁碟代號不易確認）。兩者都記下；若真的是 E:，可能是對應磁碟／符號連結，下輪請使用者確認 `-DisposableRoot` 實際磁碟。
- **原版本身的「?」**：截圖中（原版 EXE，非 m045）存檔對話框標題／欄位標籤與狀態列有多處顯示為 `?`，日期欄也為 `?`。這是原版在此系統地區設定下的既有現象（與計畫 §2 F 所說「日期欄問號屬既知問題」一致），**不是**中文化造成；C 步驟比對時應以此為基準。

## 對計畫三個問題的回答

| 問題 | 答案 |
| --- | --- |
| 1. m045 字型在 Win11 是否正常 | **未知（未測）** |
| 2. 例外路徑（0xC0000409／MFC／WER） | 原版：本次無崩潰跡象；m045：**未測** |
| 3. 存讀檔往返 | 原版建檔成功；m045 讀／存與原版讀回：**未測** |

## 安全狀態

- 原安裝目錄未被改動（G 驗證）。
- 沒有上傳 EXE、遊戲素材、存檔內容或截圖。
- `production_can_apply=false`、`release_approved=false`。
- 計畫只核准「一次」：本次已用掉。**重跑或續跑 C～F 需要使用者另外批准。**

## 建議的下一步（需使用者批准）

1. 使用者另行批准「m060 第二次觀察，只跑 C～F」（或重新從 A 開始的全新副本，視使用者偏好）。
2. 在批准後才修改腳本（下方「未來修補備註」），讓**有文件依據的** exit 1 在「無 WER 事件、無 dump、非 0xC0000409、且存檔有新增／更新」時判為 **soft-warn（警告但繼續）**，其他非 0 碼仍硬停。
3. 請使用者在每步結束後填 `observations.md` 一行（特別是「是否用選單正常結束」）。

## 未來修補備註（本任務僅記錄，未改動腳本行為）

```text
WINDOWS-ONCE.ps1 / launch 判定（未實作）：
  hard_stop  = code == 0xC0000409 or WER/Application Error 有 Ld95 項目 or 有 Ld95 dump
               or (code != 0 and code != 1)
  soft_warn  = code == 1 and events 空 and dumps 空 and usr_after 有新增或 hash 改變
  -> soft_warn：寫入 launch-X.json "exit_policy":"soft-warn-exit1"，不設 stopped，提示使用者在 observations.md 確認是正常退出
```
