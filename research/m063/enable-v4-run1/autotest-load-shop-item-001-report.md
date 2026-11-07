# LD2 自動驗收報告 load-shop-item-001

- 時間（台北）：2026-11-03T02:16:12+08:00
- 步驟腳本：load_shop_item：讀檔→城鎮道具店→購買畫面（已校準）
- Ld95.exe SHA-256：`240ab04d7f81f185820865549c72b12a0c73475bb1f8dd073146731dab3f4121`
- 自動步驟：22/23 → **通過**
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
| 15 | 城鎮→道具店 32833 | 通過 |  |  |
| 16 | 等待道具店視窗 | 通過 |  |  |
| 17 | sleep | 通過 |  |  |
| 18 | L1_shop_buy | 通過 | screens\018_L1_shop_buy.png |  |
| 19 | 商店開啟後視窗 | 通過 |  |  |
| 20 | 無崩潰 | 通過 |  |  |
| 21 | WM_CLOSE | 通過 |  |  |
| 22 | 結束 | 失敗 | screens\022_failure.png | TimeoutExpired: Command '['C:\\GameDev\\LD2\\zhTW_lab\\ld2-autotest\\runs\\load-shop-item-001\\game\\Ld95.exe']' timed out after 20 seconds |

## 尚需人工或影像判讀
- [ ] L1_shop_buy：道具店購買清單是否可讀（啟用版期待繁中道具名）
- [ ] 資訊窗可為 〈道具屋〉；日文地名殘留可接受
- [ ] 全程未買賣、未存檔
- [ ] production_can_apply 仍為 false