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
