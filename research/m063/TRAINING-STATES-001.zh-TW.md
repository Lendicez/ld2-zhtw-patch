# 訓練所三態 run `load-training-states-001`（部分結果）

- Run：`C:\GameDev\LD2\zhTW_lab\ld2-autotest\runs\load-training-states-001\`
- 桌面：`Desktop\ld2-cal\load-training-states-001\`（截圖不入庫）
- 報告／log：`enable-v4-run1/autotest-load-training-states-001-report.md`、`-run.log`

## 已確認
- **經驗不足**：四個訓練頁 Static 1024 皆為 `もっと、経験が必要です`（CP932 原文）；訓練按鈕 disabled，點擊無確認窗。
- 對應 draft7 `ansi:0x165b90` → 仍需更多經驗（見 [TRAINING-STATIC-1024](TRAINING-STATIC-1024.zh-TW.md)、[LAB-RDATA](LAB-RDATA-TRAINING-STATIC-1024.zh-TW.md)）。本 run 未套譯文，觀察到的是日文原文 → 證明顯示位置（site），非譯文顯示效果。

## 未確認（需和良提供存檔）
- **可訓練／已達上限**：m060 三槽同一人皆經驗不足 → 需「經驗足夠」與「已達上限」存檔。`0x165b74`／`0x165ba8`／`0x165bc4`／`0x165bd4` 仍未綁定。
- **委託對話**：清單空，無交付／中止／付款／謝謝原文 → draft8 site 綁定受阻，需「進行中委託」存檔。

## 安全
未執行訓練、未寫存檔；production_can_apply=false；所有旗標 false；NOT WIRED。
