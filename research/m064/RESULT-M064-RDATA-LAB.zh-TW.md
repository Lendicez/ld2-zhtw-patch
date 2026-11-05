# m064：runtime ANSI `.rdata` 原位配線 — lab 首輪結果

> 2026-11-05（台北），Win11 本機 harness，Claude 執行。只在拋棄式 lab 副本（`zhTW_lab\game-acceptance\m064-*`）；EXE／存檔／截圖不入庫。`production_can_apply=false`、`release_approved=false`。

## 前提
- lab 機系統 ANSI code page＝**950**（OEMCP 950、UI 語言 0x404）。遊戲以 ANSI API 顯示 `.rdata` 字串；原 CP932 位元組在 950 下是亂碼，改成 Big5 位元組即直接顯示繁中，**不需 hook**。
- 工具：`research/m064/rdata_ansi.py`（逐列檢查：槽 sha256、NUL 結尾、CP950 嚴格編碼＝catalog hex、容量、格式合約；不覆寫輸入；manifest 旗標 false）。

## 靜態檢查（1081 列：m063 draft7–64）
| 輸入 EXE | 可套 | 跳過 |
|---|---|---|
| m063d 啟用版 `240ab04d…4121` | 1080 | 1 |
| pristine `6c817a09…d5d2` | 1080 | 1 |

- 兩個 EXE 的 `.rdata` 原文槽完全一致（v4 hook 只加 `.ld2t/.ld2c/.ld2i` 區段）。
- 唯一跳過：**`0x166e28`（draft44 尋人回覆）**：譯文多出原文沒有的 `%E` → `contract_mismatch`。需修譯文（多一個替換符會讀到未定義參數）。

## 建置
| lab 建置 | 內容 | 輸出 sha256 |
|---|---|---|
| `m064-rdata-pilot` | 只 `0x168dd4` | `9f049729…02b6` |
| `m064-rdata-all` 第 1 版 | 1080 列 | `ae603dd8…dd66` |
| `m064-rdata-all` 第 2 版 | 1080 列＋`0x125ba4`「確認」 | `052a0743…14af` |

## 回歸（全通過；與配線前同樣的非必要失敗）
| run-id | steps | 判定 |
|---|---|---|
| `m064-pilot-d10-001` | site_inn_days_d10 | 通過 |
| `m064-all-load_inn_tavern_quest-001` | 旅館／酒館／委託／訓練所 | 通過 |
| `m064-all-load_shop_item-001` | 道具店 | 通過 |
| `m064-all-load_shop_weapon-001` | 移動＋武器店 | 通過 |
| `m064-all-tavern_rumor-001` | 傳聞 dismiss | 通過 |
| `m064-all-ui_smoke_wm2_no32880-001` | UI 煙霧 | 通過（步驟 103／110 非必要失敗，與配線前 `site4047-uismoke-001` 相同） |
| `m064-all-site_inn_days_d10-001` | 住宿天數 | 通過 |
| `m064-all2-site_inn_days_d10-001`、`m064-all2-load_inn_tavern_quest-001` | 第 2 版 | 通過 |

無崩潰、無 force-kill。

## 畫面上確認的列（與配線前同款 run 比對，只計「配線後才出現」）
| offset | 來源 | 畫面 | 證據 |
|---|---|---|---|
| `0x168dd4` | draft10 | 旅館住宿天數確認框內文「可住宿天數為1日至30日。」 | 控制項文字＋截圖人工判讀（無缺字／截斷） |
| `0x125ba4` | m064 lab-extra | 確認框標題「確認」（原為 □□） | 截圖判讀；`.text` 有 241 處 push 此字串 |
| `0x17183c` | draft58 | 移動目的地清單格式：列尾「8日」→「8天」 | ListBox 文字 |
| `0x165b90` | draft7 | 訓練所 Static 1024「仍需更多經驗」 | Static 文字 |

不計入：選單「武器店／道具店／訓練所」與「移動」視窗標題——配線前已是中文（資源層），無法歸因於 `.rdata`。

## 新發現的缺口
1. **城鎮／地區名**（例：水鏡都市 `.data` 0x617258、岩塊之町 0x61727a、三角州之村 0x61728b）位於可寫 `.data`，屬遊戲資料表；移動清單的 `%s` 參數仍為日文亂碼。需另行設計（可能被存檔或比較引用），本輪未動。
2. harness `load_shop_weapon`／`site_inn_days_d10` 以 cp932 子字串「鏡都市」選目的地；城鎮名一旦翻譯，選擇條件需同時接受 cp950。
3. `0x166e28` 譯文多 `%E`，需修稿。

## 旗標
- 各 draft 頂層 `site_binding_confirmed`／`rendering_verified` **不改**（一個 draft 19 列，只有個別列被看到）；逐列確認紀錄在 `SITE-LEDGER.json`。
- `production_can_apply`、`release_approved` 全部 false。

## 2026-11-05 17:00 更新：hook 路徑退化與排除
- 現象：第 1／2 版 lab 建置中，資訊視窗地點欄由「〈広場〉」變成半形片假名亂碼。
- 原因：資訊視窗經 m063 v4 TextOut hook 繪製，hook 以 **CP932** 解碼 ANSI 原文 → 原位改成 Big5 會被誤解。
- 處置：`rdata_ansi.py --exclude-subcategory place_ui --exclude-subcategory road_name`（12＋29 列）。第 3 版 lab 建置（`65f91564…1d7e`，1040 列）`m064-all3-innfix-001` 通過，地點欄恢復與配線前相同。
- 後續：這兩類改加入 v4 catalog（hook 端查表換繁中），不走 `.rdata` 原位。
- 既有問題（非本次造成）：訓練所後場景視窗標題亂碼，配線前 `innfix-20261105-003` 即如此。

## 圖像（lab；圖檔不入庫）
- `research/m064/bmh.py`：BMH（HF Huffman）編解碼；本機 518 個 RES BMH 解碼＋重壓往返全過。
- 有字圖片盤點：EXE RT_BITMAP＋RES BMP 46 張（按鈕 9 種字 × 狀態），BMH 51 張（移動地圖 17、狀態面板 7、片尾 3、標題 2…）。
- 按鈕：本機 Codex 以原調色盤重繪 23 張（確定／取消／下一頁／返回／能 力／家 系／物品1／物品2／戰力），檔頭與調色盤逐位元組不變；「系」仍需手繪修正。已套入 lab 建置（RES 23＋EXE 資源 23），回歸通過。
- 地名詞彙表：`PLACE-NAMES.zh-TW.json`（49 筆），供地圖圖片與 `.data` 城鎮表（0x617258 起 17 B×18）共用。

## 2026-11-05 19:10 更新：hook 路徑實驗（m064-hook-test）
- 作法：place_ui 原位 Big5＋`catalog_patch.py` 在 `.ld2c` v4 blob 追加 32 列 FULL_ANY（鍵＝原 CP932 與新 Big5 位元組，各含去空白版）。
- 第 1 次（`m064-hook-innfix-001`）：**整份 catalog 失效**（角色名退回日文）。原因：`.ld2c` +0 CatalogBytes 未更新（helper 以它開 blob，不符即 fail closed）。工具已修（`4f7c65c`）。
- 第 2 次（`m064-hook-innfix-002`）：catalog 正常，但資訊視窗地點欄仍亂碼「〈ｼｮｳ･〉」→ hook 收到的不是單詞，推測是「〈」＋地點＋「〉」組合字串（`〈%s〉` 格式字串未譯、仍為 CP932）。
- 第 3 次（排隊中）：加入組合鍵「81 71＋地點＋81 72」→「〈廣場〉」。
- 其他：場景視窗標題亂碼在配線前即存在。

## 地圖與面板
- 移動地圖 17 張：地名全依 PLACE-NAMES 換字、箭頭與道路線保留；第 2 版修擦除殘留並統一城鎮名為原圖粗黑字（Codex 處理中）。
- 狀態面板 8 張：第 7 版 WI_STAB「惡」改用定稿字形；其餘 7 張已定稿。
- `0x166e28`（draft44）已修；lab-extra 新增 `0x1398c4`「無裝備」。裝備視窗下拉為道具名（非 hook 清單點）、分頁標籤來自對話框資源，另案處理。

## 2026-11-05 21:20 更新：真因＝字型字集；完整 lab 建置回歸全綠
- **資訊視窗／移動對話框亂碼真因**：這些視窗以 `lfCharSet=128`（SHIFTJIS）建字型，TextOutA 一律以 CP932 解讀（與 ACP、hook 無關）。組合鍵 catalog 實驗（`m064-hook-innfix-003`）證實與 hook 無關。
- **修補**：`charset_patch.py` 把 3 處 LOGFONT 字集改 136（CHINESEBIG5）；搭配 `lab-places.zh-TW.json`（17 城鎮 `.data`、4 國名 `.rdata`、「国」2 處）與全部 place_ui／road_name。
- **完整建置**（m063d 啟用版 → rdata 1106 列 → charset → 按鈕 23＋面板 8＋地圖 17）：
  - 回歸 `m064-full-*-001`（7 組）、`m064-full2-*-001`（3 組）全通過；**無新退化**。
  - 畫面確認：資訊視窗「伊爾塔爾國 岩塊鎮」、地點〈廣場〉〈旅館〉〈道具店〉〈武器店〉〈寺院〉〈訓練所〉〈鎮外〉；移動對話框目前位置／通行證／6 目的地；地圖視窗「水鏡都市／崖岸道／岩塊鎮／白夜村／雪嵐道」；裝備欄「無裝備」。
- 地名統一：PLACE-NAMES 與 m063 路名一致（去「之」；砂／岳／冰融／嶺；登高嶺道、流砂鎮）；place_ui「情報屋」→「情報所」。
- 剩餘：裝備視窗分頁（角色名）與下拉（道具名）為未 hook 的 ANSI 控制項；場景視窗標題亂碼（配線前即有）；地圖 6 張細部殘點（第 4 版處理中）；改字集後字型為細明體（可評估改 face）。
