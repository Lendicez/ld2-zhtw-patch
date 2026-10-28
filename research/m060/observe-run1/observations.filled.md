# m060 觀察紀錄（依回傳證據填寫；使用者原 `observations.md` 為空白範本）

> 本檔由 Linux 端依 `evidence/*.json`、`launch-B-events.txt` 與兩張截圖填寫。未觀察到的事項標為「無資料」，不推測。

- 日期／時間：2026-10-28，A 於 14:00:26Z；B 14:00:27Z～14:09:20Z；G 於 14:16:43Z
- Windows 版本：`Microsoft Windows NT 10.0.26200.0`（hashes-before.json；`winver` 顯示名稱無資料）
- 遊戲來源資料夾（-SourceDir）：`<LD2_ROOT>\LunaticDawnPotB`（C 槽；hashes-before.json）；存檔對話框顯示的副本路徑在截圖中讀作 E 槽的 `<LD2_ROOT>\zhTW_lab\game-acceptance\m060\…`（磁碟代號因解析度不易確認，兩者並記）
- 顯示縮放／解析度：無資料
- 有沒有觸發停止條件？：有——步驟 B，腳本因 `exit_code=1`（0x00000001）停止；無崩潰事件、無 dump，判讀為很可能是正常退出的誤判（見 `../RESULT.zh-TW.md`）

| 步 | 結果（OK／問題／停止） | 看到什麼 | 截圖檔名 |
| --- | --- | --- | --- |
| A 副本＋hash | OK | hashes-before.json 已產生；來源／副本原版 `6c817a09…40d5d2`、m045 `4a091024…9da7`；Usr／LUNAS 排除 | — |
| B 原版新遊戲→存第 1 格→退出 | 停止（腳本判定）／遊戲本身看似正常 | 標題畫面正常；存檔對話框第 000 格有資料；`Usr\LUNAS000.LDP` 3,032,781 bytes、`ae945041…27cec`；執行 533.2 秒；exit 1 | B-title.jpg、B-save.jpg（本機保留，不上傳） |
| C m045 標題／主選單／檔案選單／F1／狀態列 | 未執行 | — | — |
| D 讀第 1 格→角色／道具／設施／戰鬥 UI | 未執行 | — | — |
| E 存第 2 格→正常退出 | 未執行 | — | — |
| F 原版讀第 2 格 | 未執行 | （B 截圖中原版存檔對話框日期欄已顯示 `?`，屬既知現象） | — |
| G 收尾 hash | OK | `source_exe_same_as_before=true`、`source_manifest_changes=[]`；原目錄未變動 | — |

## 字型問題
- m045 未執行，無資料。
- 基準備註：原版（未中文化）在此系統上，存檔對話框標題／欄位標籤與狀態列已有部分文字顯示為 `?`。

## 例外／崩潰
- `launch-B.json`：`exit_code_hex=0x00000001`、`is_0xC0000409=false`。
- Application 事件（Ld95 相關）：0 筆（`launch-B-events.txt` 僅 BOM＋換行）。
- `%LOCALAPPDATA%\CrashDumps` 的 Ld95 dump：無。

## 存讀檔
- 第 1 格（原版建）：已建立 `LUNAS000.LDP`；m045 讀取：未測。
- 第 2 格（m045 存）原版讀回：未測。
- 寫到副本以外的地方：原安裝目錄 1,029 檔無變動；登錄檔等其他位置無資料。

## 其他備註
- 使用者未填寫「是否用選單正常結束」；下輪請補。
