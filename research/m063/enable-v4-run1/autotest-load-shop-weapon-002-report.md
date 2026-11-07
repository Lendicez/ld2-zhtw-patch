# LD2 自動驗收報告 load-shop-weapon-002

- 時間（台北）：2026-11-03T11:15:16+08:00
- 步驟腳本：load_shop_weapon：讀檔→移動至水鏡都市→武器店
- Ld95.exe SHA-256：`240ab04d7f81f185820865549c72b12a0c73475bb1f8dd073146731dab3f4121`
- 自動步驟：41/42 → **通過**
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
| 32 | 武器店 32832 可用 | 通過 |  |  |
| 33 | 城鎮→武器店 32832（SendMessage） | 通過 |  |  |
| 34 | 等待武器店視窗 | 通過 |  |  |
| 35 | sleep | 通過 |  |  |
| 36 | L1_weapon_shop | 通過 | screens\036_L1_weapon_shop.png |  |
| 37 | L1_weapon_shop_union | 通過 | screens\037_L1_weapon_shop_union.png |  |
| 38 | 開店後視窗 | 通過 |  |  |
| 39 | 無崩潰 | 通過 |  |  |
| 40 | WM_CLOSE | 通過 |  |  |
| 41 | 結束 | 失敗 | screens\041_failure.png | TimeoutExpired: Command '['C:\\GameDev\\LD2\\zhTW_lab\\ld2-autotest\\runs\\load-shop-weapon-002\\game\\Ld95.exe']' timed out after 20 seconds |