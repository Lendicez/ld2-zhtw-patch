# clean_exit 乾淨關閉遊戲 — observations / RESULT 片段

> 來源：Rona Win11 觀測（`Desktop\ld2-cal\`），折入 #26 作為研究證據。僅文字；截圖／EXE／存檔／zip 不入庫。`production_can_apply=false`、所有旗標維持 false。

- 日期：2026-11-03（Asia/Taipei）
- 環境：隔離副本 `game-acceptance\m063d-v4-enable\game`（EXE sha256 `240ab04d…4121`），存檔 fixture `m060\game\Usr`
- production_can_apply：**false**（未變更）

## 背景
舊流程結尾 `close`（WM_CLOSE）會跳出「冒險記錄檔儲存確認」模態框，`expect_exit` 逾時後由 finally 強制結束（force-kill）。

## 新步驟 `clean_exit`
1. 先以 WM_CLOSE 關閉同行程 owned 子視窗（商店等；不關 ToolPalette）。
2. 從「檔案」選單找「離開遊戲(&X)」＝ **WM_COMMAND 57665**（ID_APP_EXIT），PostMessage 送出。
3. 存檔確認框按 **「否(&N)」id=7**（不存檔）；若出現含 ListBox/ComboBox 的檔案框一律按「取消」id=2。
4. 僅在上述失敗時才退回 WM_CLOSE／SC_CLOSE，最後才 force-kill（state 記錄 `force_killed`）。

## 綠燈 run
| run id | 內容 | 結束碼 | force-kill | 判定 |
|---|---|---|---|---|
| `smoke-exit-002` | 讀檔→道具店→clean_exit | 1 | 無 | 通過 |
| `smoke-exit-load-001` | 讀檔後直接 clean_exit | 1 | 無 | 通過 |
| `load-shop-item-cleanexit-001` | 改版 load_shop_item 抽驗 | 1 | 無 | 通過 |

- 遊戲正常離開的結束碼為 **1**（非 0），allow_codes 須含 1。
- smoke-exit-002：隔離副本 Usr 雜湊與 fixture 一致（未寫入存檔）。
- `smoke-exit-001` 為第一版（誤按「是」），**不作依據**。

## 步驟檔更新
六個主要步驟檔結尾 `close`＋`expect_exit` 已換為 `{"op":"clean_exit"}`：
`load_shop_item`、`load_shop_weapon`、`load_shop_weapon_tabs`、`load_inn_tavern_quest`、`load_training_states`、`load_slot2`。
（中途關子視窗的 `close_title` 保留；備份 `steps\_backup_20261103-170231\`）

## 範圍
未買賣／招募／訓練／存檔；未推送 GitHub；不含 EXE／存檔／截圖原檔。
