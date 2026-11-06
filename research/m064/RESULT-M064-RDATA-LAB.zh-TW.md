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

## 2026-11-05 22:10 更新：裝備視窗下拉道具名
- 裝備對話框的 5 個下拉（ID 1014–1018）由 `CB_INSERTSTRING` 填入。m063 已把 `0x46e73a`、`0x47db6a` 導向 v4 **name** 入口（NAME_ONLY，不查道具列）→ 道具名未翻；`0x46bacb`、`0x46c46c`（dialog 151）未 hook。
- `list_reroute.py`：4 點 call rel32 改導 v4 **item** 入口（入口位址由商店 0x4aaf19／教育 0x4735f6 讀出）；`catalog_patch.py` 加 `hook-rows-equip.json`（「無裝備」Big5 鍵）。
- 結果 `m064-reroute-charwin-002`：下拉 = 無裝備／軍刀／軟皮甲／頭巾（全繁中），回歸通過。
- 建置流程更新：rdata → charset → **list_reroute → catalog_patch(equip)** → images。
- 待查：這 4 點在其他對話框（party／birthday 類）是否也列人名；item 入口同樣 ALLOW_ANY|JOIN，人名仍可命中（Kris 類同 bytes 例外）。分頁標籤＝角色名（屬性頁標題）仍未翻。

## 2026-11-05 22:45 更新
- 新流程完整建置（含 list_reroute＋equip catalog）回歸 `m064-full4-*-001` 7 組全通過，改導 4 點未造成人名退化。
- 屬性表分頁（角色名）設計：`DESIGN-EQUIP-TAB.zh-TW.md`（6 處 `mov [eax+0x14],edi` 改呼叫 stub，走 `LD2N_FindCopy`＋CP950 轉換）。

## 2026-11-05 23:30 更新：屬性表分頁標題（角色名）
- `tab_title_patch.py`：6 處 `mov ecx,esi; mov [eax+0x14],edi`（5 B）改 `call stub`；258 B stub 置 `.ld2t` 剩餘空間，緩衝在 `.ld2i`。
- 偵錯（`--debug`＋harness 新 op `read_mem`）：第 1 版 stub 有執行但 FindCopy 查無 → 屬性表標題用**半形片假名**（「ﾀﾞｼﾞﾙﾀｰﾙ」）。第 2 版先 `MultiByteToWideChar(932)`→`LCMapStringW(0x411, LCMAP_FULLWIDTH)`→`WideCharToMultiByte(932)` 正規化再查表；輸出 Big5「達吉爾塔爾」。
- 畫面：裝備視窗分頁「達吉爾塔爾」（`m064-full5-char_windows-001`）。
- 建置流程第 6 步：`tab_title_patch.py`。回歸 `m064-full5-*` 7 組通過（site_inn_days_d10 首跑移動步驟偶發逾時，重跑 -002 通過）。

## 2026-11-06 00:20 更新
- **場景視窗標題**（配線前即亂碼）：進城後遊戲以 `.rdata 0x171fbc`「ビジュアルウインドウ」重設 MDI 子視窗標題 → lab-extra 譯「場景視窗」。harness 新 op `dump_main`（子視窗標題 W／A 原始 bytes）確認進城前後皆「場景視窗」（`m064-probe-titles-002`）。
- **build_lab.py**：6 步一次建置（rdata → charset → list_reroute → catalog(equip) → tab_title → images）。EXE `8b0e81f2…78ba`；回歸 `m064-full6-*` 7 組全通過。
- **讀檔清單**：每列為存檔檔頭文字（角色名、城鎮名＝存檔當時的 CP932），非 EXE 字串；ListBox 1025 為 ANSI → 亂碼。可行方向：該清單填入點導入 v4 helper（查無時 helper 以 CP932 正確解碼，至少顯示日文）；新舊存檔混碼問題待設計。

## 2026-11-06 00:50 更新
- **委託一覽**：控制項 dump 為「委託一覽」「狀態」等繁體正字（`m064-full6-char_windows-001`）；先前截圖判讀的「一覧／状態」為低解析度誤判，**不需修**。
- **讀檔清單（擱置）**：讀檔 dialog 152 的 ListBox 1025 在 `m061/list_sites.json` 沒有 ADDSTRING 點（填入走未解析的包裝），且有 `LB_GETTEXT` 讀回（0x47fd1e；存檔 dialog 153 亦有 0x499671）。若改成 Unicode 清單，遊戲讀回的 ANSI 可能變動 → 讀檔風險。效益僅限舊存檔（檔頭 CP932）；新存檔檔頭混合 Big5 城鎮名與 CP932 角色名。另案設計（可能做法：存檔時把檔頭角色名正規化為 Big5，或只在顯示層轉換且讀回點同步攔截）。
- **張數框 `0x158f60`（draft46）**：唯一引用在 `0x4812df`（sprintf 進 CString）；相鄰字串為「購入する宝くじの番号は、」「入力した枚数」等 → 為**彩票（宝くじ）購買張數**，不是卡片／卷軸店。需建國紀念彩票期間的存檔才能觸發；譯文維持 candidate（「可購買張數為%d～%d張」語意正確）。

## 2026-11-06 02:00 更新：角色詳情視窗
- 開啟路徑：選單「視窗 → 角色詳情 → 全部開啟」（cmd 32805；「角色狀態 → 全部開啟」為 32803）。各隊員項目為動態 id（例 32901／32908）。harness 新 op：`menu_path_command`（依位置路徑送子選單指令）、`dblclick_screen`、`rclick_screen`；`dump_main` 加 `all`（含無標題子視窗與座標）。
- 畫面（`m064-char-status-001` 025）：**WI_STA00 面板標籤全部繁中清楚**（性別、年齡、特徵、狀態、秩善惡混、體力…魅力、武盾盔鎧他、持有金錢）；底部分頁「能 力／戰力／家 系／物品1／物品2」繁中。
- 新缺口：視窗標題「ステータス」（`0x1730ac`，lab-extra 譯「角色詳情」）；詳情內角色名欄亂碼、「特徵」值「??」、性別值空白（數值文字的繪製路徑待查）；選單「角色狀態／角色詳情」子項的隊員名亂碼（AppendMenu／ModifyMenu 類 ANSI）。

## 2026-11-06 03:20 更新
- **FindCopyNorm**：NameTextOut v4 內唯一的 `call LD2N_FindCopy`（0xae598d）改導 186 B 包裝（先原樣查；查無則半形→全形再查）；預設隨 `tab_title_patch` 安裝（`--no-norm` 可關）。位置 0xae5c80（`--debug` 版會記錄最近 8 筆輸入於 `.ld2i 0xb25d60`）。
- 角色詳情視窗標題「角色詳情」已生效（`m064-char-status-002`）。
- 詳情視窗**名字欄仍亂碼**：偵錯紀錄（`m064-char-dbg-002`）顯示 NameTextOut 只收到全形「ダジルタール」4 次（隊伍小窗），詳情名字欄**不經 NameTextOut**。性別空白、特徵「??」亦同類。待確認是否為 charset_patch 的副作用（比對未改字型的 m063d 啟用版：`m063d-char-status-001`，排隊中），再找該視窗的繪製呼叫點。

## 2026-11-06 04:15 更新：charset_patch 對角色詳情視窗的副作用
- 比對未改字型的 m063d 啟用版（`m063d-char-status-001`）：詳情名字欄「速戦即決の ダジルタール」、性別「男」、特徵「グルメ」、狀態「正常」皆為正常日文；套 charset_patch 後變亂碼／空白 → **確定為 charset_patch 副作用**。
- 逐點測試（`m064-cs-v1..v4-001`）：

| LOGFONT | 資訊視窗 | 角色詳情視窗 |
|---|---|---|
| A `0xd0b5c` | 國名＋城鎮行 | 名字欄（稱號＋名字） |
| B `0xd0bbc` | 地點欄〈…〉 | 性別／特徵／狀態值 |
| `0x31dbe` | （本次畫面無可見差異） | （無） |

- 兩字型兩視窗共用 → 無法以縮小修補範圍兩全。暫維持全修補（資訊視窗常駐優先）。
- 計畫：(1) 性別／特徵／狀態／稱號等字串表原位 Big5（找表位置，比照 lab-places）；(2) 名字欄＝稱號＋名字組字後以字型 A 繪製、不經 NameTextOut → 在組字前把名字轉 Big5（沿用 tab_title stub 的「半形→全形→FindCopy→CP950」轉換，做成可呼叫函式並 hook 組字呼叫點）。

## 2026-11-06 04:25 更新：角色詳情視窗完成
- **畫面（`m064-cs-detail-005` 025）**：名字欄「速戰速決的 達吉爾塔爾」、性別「男」、特徵「美食家」、狀態「正常」——全部繁中。
- **性別／特徵／狀態（`gen_lab_detail.py` → `lab-detail.zh-TW.json`，51 列原位 Big5）**：性別 `0x173340` 女／`0x173344` 男（程式以索引取字，非稱號表旁的「男」）；狀態 `0x12eff8`–`0x12f030` 8 列；特徵 `.data 0x345c0b` 起 17 B 槽 41 列（其後是隨機人名音節表，不動）。這些都以索引顯示、不寫入存檔。
- **稱號（376 個指標的表 `.data 0x349700`，{char*, flags}）**：生成角色時被**複製進角色記錄 +0x19（存檔）**，名字在 +0x08。所以**稱號表不原位改**（避免把 Big5 寫進存檔），改用 `detail_name_patch.py`：
  - 繪製函式兩處（`0x4d77a0`、`0x4dbd..`）以「稱號 getter `0x44dab0`＋" "＋名字 getter `0x44d870`」組字後 TextOut。4 個 getter 呼叫點（`0x4d78a1/0x4d78bc`、`0x4dbdba/0x4dbdd8`）改導 thiscall 透傳 stub：稱號 → 查「CP932→Big5」對照表（建置時由使用者 EXE 產生、附加在 `.ld2i` 檔尾 0xb26000，371 對、7134 B，不入庫）；名字 → FindCopyNorm → CP950。查無即原樣。
  - 第 1 版 epi stub 誤用 pushad 內 edi（被 `repe cmpsb` 用掉）→ 視窗不繪；改以 ebp 保存 CString* 後正常。
- 稱號譯文 379 條（含女性／複合職業、「武術達人」等）在 `gen_lab_detail.py`，`build()` 會核對表內 376 條全覆蓋。
- **選單隊員名**：`0x488c73 call 0x46cc50`（隊員名 by slot → AppendMenuA）改導同一型名字 stub（`MENU_STUB 0xae5e40`）。`m064-cs-detail-006`：「角色狀態」「角色詳情」子項皆為「達吉爾塔爾」。
- **回歸 `m064-full7-*`**（含稱號／名字 stub、未含選單 stub）：7 組全通過（旅館／酒館／任務、商店物品、武器、謠言、UI smoke、角色視窗、住宿天數 d10）。

## 2026-11-06 04:40 更新：CDC::TextOut 全域後備＋詳情視窗各分頁
- **`cdc_textout_patch.py`**：MFC `CDC::TextOut`（0x4e13d7；CDC／CPaintDC／CClientDC／CWindowDC 四個 vtable +0x5c 共用）開頭改 `jmp TO_HOOK`（0xae5ec0，246 B）。字串 1–64 B 且含 0x81–0x9F 位元組（＝CP932 日文；cp950 繁中不會出現 0x80–0xA0）時：
  1. 先查 v4 catalog（helper 內部 `0xae5620` 開表＋`0xae4f60` 查表，flags＝ANY|JOIN，**不含 NAME_ONLY → 物品 FULL_ID 列也查得到**）→ TextOutW 繁中；
  2. 查無 → `MultiByteToWideChar(932)` → TextOutW 顯示日文原文（不再亂碼）。
  其他（Big5 譯文、ASCII、半形）走原 TextOutA。NameTextOut 查無時走 vtable → 同樣進這裡，所以先前的 `nto_fallback_patch` 不再建置（保留原始碼）。
- **詳情視窗分頁（`m064-detail-tabs-005`）**：能力／戰力／家系／物品1 全部繁中——物品「軍刀／頭巾／軟皮甲／火把」、父母「卡德爾南多／芙特娜」（catalog 人名）、特殊技能「背刺」、家／配偶／子女「無」。`lab-detail` 增特殊技能 4 列（背刺、全體祝福、破陣、衝鋒攻擊）與「無」（`0x12f80c`）。
- 家系分頁名字 getter 4 處（`0x4d9268/0x4d9435/0x4dd7fc/0x4dd9db`）也接上名字 stub。
- 意義：charset_patch 的副作用（未譯 CP932 → Big5 亂碼）從此**全域降級為「顯示日文」**；catalog 有的直接顯示繁中。
- **回歸 `m064-full8-*`**（含 CDC::TextOut 全域後備、稱號／名字／選單／家系 stub、lab-detail 56 列）：**7/7 通過**。巡檢截圖（旅館各頁、情報所、訓練所、道具店、武器店、寺院、謠言、住宿）全為繁中。

## 2026-11-06 12:00 更新：未走到場景的靜態翻譯＋讀檔清單
- **範圍**：遊戲文字幾乎全在 EXE（目錄無劇本檔）。抽出尚未翻譯、確定是給玩家看的字串 2,986 條（`.rdata` 2,284：戰鬥台詞、事件／劇情、隊友對話、道具說明、系統訊息；`.data` 固定 0x80 槽對話 702：招募、拒絕、偷竊被抓等）。排除被複製進存檔的物品名（存檔掃描確認：物品名、稱號、存檔標頭在存檔內；對話不在）。
- **流程**：本機 Codex 分 25 批初譯（附 4,530 條 catalog 譯名＋地名表、cp950 長度上限、替換符合約）→ Codex 第二輪審稿（207 處修正：誤譯、名詞一致、口吻、拼接片段、保留版面空白）→ `gen_lab_tx.py` 由使用者 EXE 讀原文槽 sha／合約，逐條核對 → `research/translations/m064-tx-dialogue.zh-TW.json`（2,985 列，1 列替換符不符而排除；只含繁中）。rdata 總計 4,149 列。
- **派工器修正**：`codex.cmd` 是批次檔，命令列參數中的換行會截斷 → 派工時壓成單行（第一輪審稿因此只收到第一行而沒做事）。第一輪初譯 Codex 經 PowerShell 寫檔使中文變 `?`，validate 改為拒收。
- **讀檔清單（`savelist_patch.py`）**：存檔標頭說明字串（CP932）在 LB_ADDSTRING／LB_INSERTSTRING 前轉換（4 個呼叫點：0x460974、0x476a0e、0x480150、0x480403；以空白切詞→catalog（人名＋新增 23 個 CP932 地名列）→ 否則照字形 cp950）。存檔不改。畫面：「000:  971年 7月12日 達吉爾塔爾  岩塊鎮」，讀檔照常。
- **harness**：`wait_static_text` 支援 `retry_click`（移動框偶發沒吃到第一次點擊），20 個 step 檔自動加上。
- **回歸 `m064-full10-*` 7/7 通過**＋`m064-cs-tx-003` 通過。
- 說明書：Codex 已將 `マニュアル` 71 檔譯為繁中 UTF-8（lab：`m064-lab\manual\zh`，`check_manual.py` 0 問題）。屬遊戲文件衍生物，不入庫；之後由安裝器在使用者端產生或另議。

## 2026-11-06 15:00 更新：迷宮、替換符展開、Codex 改用 GPT-6-Astra
- **迷宮名稱表**（`.data 0x37b778`，16 B 槽 70 個，`0x45f3e0 GetDungeonName` 以索引取用、44 處呼叫）原位 Big5（`lab-dungeon-names.zh-TW.json`）。「前往迷宮」清單畫面：魔術師之塔／火焰洞窟／背德城址。
- **`fmt_expand_patch.py`**：遊戲自訂替換符展開 `0x4014b0 Expand(fmt, dest, ctx)`（`%0`–`%9` 整數、`%A`–`%Z` 字串 = `ctx[ch-0x37]`）。在 `%A`–`%Z` 複製點 `0x401520` 改 `call CONV`：插入值含 CP932 → catalog（ANY|JOIN）→ 否則照字形 → cp950 靜態緩衝。解決「繁中模板＋日文名字」混碼。
- **實機迷宮探測**（`m064-probe-dungeon2-001`）：進入魔術師之塔、「確認：點亮了燈。」繁中、資訊視窗「魔術師之塔」。發現「地上 1 層」的「地上／地下」仍為 CP932 短漢字 → 與 Big5「 %d 層」拼接後被 TextOut 後備整串當 CP932 解 → 「層」變亂碼。根因：第一輪抽取濾掉了**純漢字短字串**（無假名、無標點）。
- **補抽純漢字字串 712 條**（UI 標籤、道具分類、怪物名、NPC 稱呼、戰鬥統計、製作人員名…），交 Codex（`m064-lab\tx2`）。
- **Codex 模型**：依和良指示改用 `gpt-6-astra`、推理 `max`（`dispatch.py` 預設，job 可覆寫）。並以 Astra 對 2,985 條對話做第三輪終審（`fixb-*.json`）。
- 回歸 `m064-full11-*` 7/7 通過（含 fmt_expand 與迷宮名）。
- **15:50**：Astra 終審 165 處＋純漢字 147 條（只取 `.rdata`；`.data` 的人名用字表 565 條不改，因生成後寫入存檔，顯示時走 catalog／後備）入 `m064-tx-kanji.zh-TW.json`。迷宮資訊欄「地上 1 層」修正確認（`m064-probe-dungeon2-002`）。回歸 `m064-full12-*` 7/7 通過。
- harness 新 op `explore_until_battle`（迷宮內輪流移動、左鍵關訊息彈窗、偵測戰鬥選單「攻擊」啟用）。

## 2026-11-06 19:00 更新：剩餘資源＋DrawText 後備
- **`res_extra.py`**：m020 之後仍為日文的資源 145 處（右鍵選單 130／131、對話框 24＋標題 8、字串表 103：狀態列／工具提示、MFC 系統與錯誤訊息），Codex（gpt-6-astra/max）翻譯＋`validate_res.py`（cp950、替換符、`\n`、`&` 快速鍵）→ `res-extra.zh-TW.json`（只含繁中＋原文 UTF-16 sha＋定位）。套用：38 個資源原位覆寫（新內容不大於原大小），0 個需搬移；對話框日文字型名改 MingLiU（同 m020）。套用後 `extract` 掃描剩餘假名 0。
- **`drawtext_patch.py`**：`CDC::DrawText`（0x4e1450，四個 vtable 共用）比照 TextOut：含 0x81–0x9F → MultiByteToWideChar(932) → DrawTextW（未匯入，首次以 GetModuleHandleA／GetProcAddress 取得並快取）。程式碼在 .ld2i 尾。
- `.rdata` 含假名而未翻的字串只剩 22 條（怪物／精靈名，會被複製進世界資料／存檔，走 catalog）。
- rdata 總列數 4,366。回歸 `m064-full13-*` 7/7、讀檔清單、迷宮探測皆通過。

## 2026-11-06 23:00：攻擊閃退（已修）
- **現象**（和良回報＋`m064-probe-attack-001` 重現）：迷宮內下「攻擊」後偶發閃退（0xC0000005，EIP＝`0x72a650` 落在 .data 空白區）。
- **二分＋重複統計**：m063d 0/3、無 m064-tx 0/4、完整版 2/6（含和良一次）、無 cdc_textout 3/4、無 fmt_expand 1/1、無 drawtext 1/1 → 元兇為 m064-tx 翻譯資料。
- **根因**：第一輪抽取把**二進位資料偶然解碼成 CP932** 的片段當成字串（`.rdata` 0x174000 以後的數值表、`@・`／`` `ス ``／`Pォ` 類短片段、`.data` 結構前綴 `×4`＋文字），Codex「翻譯」後寫回，破壞資料表；攻擊時隨機讀到 → 偶發。
- **修正**：`gen_lab_tx.is_junk`（`.rdata` ≥0x174000 一律不碰；含私用碼／U+FFFD／`@`\``<>&=\{}|^~[]`／控制字元；≤3 字且半形全形混雜或含英文字母）。重產：對話 2,957（排除 29）＋純漢字 147。rdata 4,338 列。
- **驗證**（build_lab19）：迷宮內攻擊 5/5 存活；`m064-full14-*` 7/7 通過。
- 教訓：自動抽字串時，「能解碼成日文」不等於「是字串」；之後新增的抽取一律先過 is_junk，並優先只收有直接參照或位於確定文字表內的字串。
