# LD2 自動驗收報告 load-training-states-001

- 時間（台北）：2026-11-03T16:55:51+08:00
- 步驟腳本：load_training_states：讀檔→水鏡→訓練所 4 能力頁＋確認框取消（不存檔）
- Ld95.exe SHA-256：`240ab04d7f81f185820865549c72b12a0c73475bb1f8dd073146731dab3f4121`
- 自動步驟：62/65 → **通過**
- 遊戲結束碼：1
- production_can_apply：false

| # | 步驟 | 結果 | 截圖 | 錯誤 |
|---|---|---|---|---|
| 0 | 等待主視窗 | 通過 |  |  |
| 1 | 固定 1280x800 | 通過 |  |  |
| 2 | sleep | 通過 |  |  |
| 3 | 關閉啟動 splash | 通過 |  |  |
| 4 | sleep | 通過 |  |  |
| 5 | 前景＋AttachThreadInput | 通過 |  |  |
| 6 | title | 通過 | screens\006_title.png |  |
| 7 | 檔案→讀取遊戲 | 通過 |  |  |
| 8 | load_dialog | 通過 | screens\008_load_dialog.png |  |
| 9 | 選存檔第2格 LUNAS001 | 通過 |  |  |
| 10 | sleep | 通過 |  |  |
| 11 | 按讀取 | 通過 |  |  |
| 12 | 讀檔框關閉 | 通過 |  |  |
| 13 | sleep | 通過 |  |  |
| 14 | after_load | 通過 | screens\014_after_load.png |  |
| 15 | 城鎮選單（岩塊之町） | 通過 |  |  |
| 16 | 前往其他城鎮 32840（Post；模態框勿 SendMessage） | 通過 |  |  |
| 17 | 等待「移動」對話框 | 通過 |  |  |
| 18 | sleep | 通過 |  |  |
| 19 | dump 移動框（目的地 ListBox 1000） | 通過 |  |  |
| 20 | travel_dialog | 通過 | screens\020_travel_dialog.png |  |
| 21 | 選目的地 水鏡都市（cp932 含「鏡都市」） | 通過 |  |  |
| 22 | sleep | 通過 |  |  |
| 23 | 按「移動」id=112 | 通過 |  |  |
| 24 | 等待目前位置=水鏡都市（static 1021） | 通過 |  |  |
| 25 | arrived_dialog | 通過 | screens\025_arrived_dialog.png |  |
| 26 | arrived_union | 通過 | screens\026_arrived_union.png |  |
| 27 | 按「進入」id=1 | 通過 |  |  |
| 28 | 移動框關閉 | 通過 |  |  |
| 29 | sleep | 通過 |  |  |
| 30 | in_town | 通過 | screens\030_in_town.png |  |
| 31 | 城鎮選單（水鏡都市） | 通過 |  |  |
| 32 | 訓練所 32835 可用 | 通過 |  |  |
| 33 | 城鎮→訓練所 32835（Post） | 通過 |  |  |
| 34 | 等待訓練所視窗 | 通過 |  |  |
| 35 | sleep | 通過 |  |  |
| 36 | 訓練 tab0 筋力（0x465） | 通過 |  |  |
| 37 | read tab0 | 通過 |  |  |
| 38 | L2_training_tab0 | 通過 | screens\038_L2_training_tab0.png |  |
| 39 | 訓練 tab1 知性（0x465） | 通過 |  |  |
| 40 | read tab1 | 通過 |  |  |
| 41 | L2_training_tab1 | 通過 | screens\041_L2_training_tab1.png |  |
| 42 | 訓練 tab2 敏捷（0x465） | 通過 |  |  |
| 43 | read tab2 | 通過 |  |  |
| 44 | L2_training_tab2 | 通過 | screens\044_L2_training_tab2.png |  |
| 45 | 訓練 tab3 魅力（0x465） | 通過 |  |  |
| 46 | read tab3 | 通過 |  |  |
| 47 | L2_training_tab3 | 通過 | screens\047_L2_training_tab3.png |  |
| 48 | 回 tab0 筋力 | 通過 |  |  |
| 49 | snapshot 訓練前 | 通過 |  |  |
| 50 | 按「訓練」id=1（期待確認框） | 通過 |  |  |
| 51 | 等待確認框 | 失敗 | screens\051_failure.png | RuntimeError: 無新視窗 |
| 52 | read 確認框 | 通過 |  |  |
| 53 | L2_training_confirm | 通過 | screens\053_L2_training_confirm.png |  |
| 54 | L2_training_confirm_union | 通過 | screens\054_L2_training_confirm_union.png |  |
| 55 | 取消 id=2 | 通過 |  |  |
| 56 | いいえ id=7 | 失敗 | screens\056_failure.png | RuntimeError: 找不到按鈕 id=7 |
| 57 | sleep | 通過 |  |  |
| 58 | 取消後視窗 | 通過 |  |  |
| 59 | 重新綁定訓練所 | 通過 |  |  |
| 60 | read 取消後（核對 1003/1044 未變） | 通過 |  |  |
| 61 | L2_training_after_cancel | 通過 | screens\061_L2_training_after_cancel.png |  |
| 62 | 無崩潰 | 通過 |  |  |
| 63 | WM_CLOSE | 通過 |  |  |
| 64 | 結束（可強制） | 失敗 | screens\064_failure.png | TimeoutExpired: Command '['C:\\GameDev\\LD2\\zhTW_lab\\ld2-autotest\\runs\\load-training-states-001\\game\\Ld95.exe']' timed out after 5 seconds |