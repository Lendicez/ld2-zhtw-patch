# 酒館聽傳聞（1013）關閉 + clean_exit — rumor-dismiss 證據

> 來源：Rona Win11 觀測（`Desktop\ld2-rumor-dismiss\RUMOR-DISMISS-NOTE.md`，2026-11-03 Asia/Taipei），折入 #26 作為研究證據。僅文字；截圖留在 Win11 `Desktop\ld2-rumor-dismiss\`，EXE／存檔／zip 不入庫。`production_can_apply=false`、所有旗標維持 false。

## 綠燈 run
- `rumor-dismiss-003`、`rumor-dismiss-004`；steps `tavern_rumor.json`；**52/52 pass**
- clean_exit：選單 57665 → 存檔詢問按「否」；`force_killed=false`；exit code 1（與先前 smoke-exit-002 相同）
- 未邀請、未存檔

## 根因（harness，非翻譯）
- 1013 開啟 Afx 彈窗，其內有自己的 message loop → 舊的 `SendMessage BM_CLICK` 會阻塞 harness
- 傳聞彈窗為多頁；對其送 WM_CLOSE 會使遊戲主迴圈卡住 → 程序殘留／偶發 0xC000041D

## 修正
- 1013 改用 `dialog_post_click`（PostMessage BM_CLICK）
- 新 op `dismiss_chain`：左鍵點頁面中心，於 2.5 秒內逐頁翻頁直到關閉
- **這類彈窗禁止 WM_CLOSE**
- 另新增 probe op `dismiss_popup`

## 標題證據（GetWindowTextA 原始 CP932 hex；此處僅列繁中釋義）
| CP932 hex | 繁中釋義 |
|---|---|
| `92ac82cc895c202d2096608caf8ed2` | 鎮上傳聞 - 冒險者 |
| `92ac82cc895c202d2090c2944e` | 鎮上傳聞 - 青年 |
| （老人頁） | 鎮上傳聞 - 老人 |

- 格式推測：「鎮上傳聞」標題前綴 + ` - ` + 說話者
- 對應 draft38 候選 `0x16edf4`（site 仍未確認；catalog 旗標不變）

## 正文
- GDI 繪製；無子控制項、WM_GETTEXT 取不到
- 正文需截圖 OCR 或 EXE／資料溯源（不在本次範圍）

## 翻譯缺口提醒
1. 傳聞標題執行期仍為未譯 CP932
2. 傳聞正文需另行取得來源

## 截圖位置
截圖只保留在 Win11 `Desktop\ld2-rumor-dismiss\`，本 repo 不附檔。
