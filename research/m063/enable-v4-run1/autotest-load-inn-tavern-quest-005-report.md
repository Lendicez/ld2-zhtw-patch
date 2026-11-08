# LD2 自動驗收報告 load-inn-tavern-quest-005

- 時間（台北）：2026-11-03T16:48:13+08:00
- 步驟腳本：load_inn_tavern_quest：讀檔→水鏡都市→旅館/酒館/委託(+訓練所)
- Ld95.exe SHA-256：`240ab04d7f81f185820865549c72b12a0c73475bb1f8dd073146731dab3f4121`
- 自動步驟：66/67 → **通過**
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
| 32 | 旅館 32831 可用 | 通過 |  |  |
| 33 | 城鎮→旅館 32831（Post） | 通過 |  |  |
| 34 | 等待旅館視窗 | 通過 |  |  |
| 35 | sleep | 通過 |  |  |
| 36 | 旅館 tab0 住宿 | 通過 |  |  |
| 37 | 頁=旅館 | 通過 |  |  |
| 38 | L1_inn | 通過 | screens\038_L1_inn.png |  |
| 39 | 旅館 tab1 酒館 | 通過 |  |  |
| 40 | 頁=酒館（冒險者清單 ListBox 1000） | 通過 |  |  |
| 41 | L1_tavern_adventurers | 通過 | screens\041_L1_tavern_adventurers.png |  |
| 42 | L1_tavern_union | 通過 | screens\042_L1_tavern_union.png |  |
| 43 | 關旅館（WM_CLOSE，不住宿） | 通過 |  |  |
| 44 | 情報所 32837 可用 | 通過 |  |  |
| 45 | 城鎮→情報所 32837（Post） | 通過 |  |  |
| 46 | 等待情報所視窗 | 通過 |  |  |
| 47 | sleep | 通過 |  |  |
| 48 | 情報所 tab0 資訊 | 通過 |  |  |
| 49 | L1_info | 通過 | screens\049_L1_info.png |  |
| 50 | 情報所 tab1 委託資訊 | 通過 |  |  |
| 51 | 頁=委託資訊 | 通過 |  |  |
| 52 | L1_quest_board | 通過 | screens\052_L1_quest_board.png |  |
| 53 | L1_quest_union | 通過 | screens\053_L1_quest_union.png |  |
| 54 | 關情報所 | 通過 |  |  |
| 55 | 訓練所 32835 可用 | 通過 |  |  |
| 56 | 城鎮→訓練所 32835（Post） | 通過 |  |  |
| 57 | sleep | 通過 |  |  |
| 58 | 訓練所後視窗 | 通過 |  |  |
| 59 | 等待訓練所視窗 | 通過 |  |  |
| 60 | 頁=訓練所（筋力頁；sheet 標題不穩定） | 通過 |  |  |
| 61 | dump 訓練所 | 通過 |  |  |
| 62 | L1_training | 通過 | screens\062_L1_training.png |  |
| 63 | L1_training_union | 通過 | screens\063_L1_training_union.png |  |
| 64 | 無崩潰 | 通過 |  |  |
| 65 | WM_CLOSE | 通過 |  |  |
| 66 | 結束（可強制） | 失敗 | screens\066_failure.png | TimeoutExpired: Command '['C:\\GameDev\\LD2\\zhTW_lab\\ld2-autotest\\runs\\load-inn-tavern-quest-005\\game\\Ld95.exe']' timed out after 5 seconds |