# SUPERSEDE：load-inn-tavern-quest-004（2026-11-03，台北）

> production_can_apply = false；release_approved = false。

- 2026-11-03：Rona 報告 harness `sheet_tab` 誤用 WM 0x466（刪頁）而非 0x465（切換）。
- 因此 `enable-v4-run1/autotest-load-inn-tavern-quest-004-report.md` 及 observations／RESULT-M063D 中旅館／酒館／委託部分 **暫不當最終依據**。
- 舊檔保留不刪，僅標記 superseded；等 Rona 以修復後 harness 重跑，新 run 路徑另補。

## 武器店綠燈（load-shop-weapon-tabs-003）
- 出售 044／強化 047（桌面 `ld2-cal\load-shop-weapon-tabs-003\`）。
- 未執行任何買賣。
- 主畫面地名仍為日文「イルタール国 水鏡都市」。
- 該存檔隊伍僅 1 人（達古爾塔爾）。

## 替代：load-inn-tavern-quest-005（canonical，2026-11-03 16:48 台北）
- 004 → **superseded**；旅館／酒館／委託／訓練證據以 **005** 為準。
- Run：`C:\GameDev\LD2\zhTW_lab\ld2-autotest\runs\load-inn-tavern-quest-005\`
- 桌面：`C:\Users\lendicez\Desktop\ld2-cal\load-inn-tavern-quest-005\`
- Ld95.exe（enabled lab）SHA-256：`240ab04d7f81f185820865549c72b12a0c73475bb1f8dd073146731dab3f4121`
- 結果：66/67 通過；唯一失敗為已知 WM_CLOSE 後 `TimeoutExpired`（結束等待 5 秒），非功能問題。
- 確認：sheet_tab 使用 0x465；旅館 tabs 維持 5、情報所 3；切換回傳 1；未住宿／招募／買賣／存檔。
- 關鍵圖（僅名稱，不入庫）：038 旅館、041／042 酒館、049 資訊、052／053 委託、062／063 訓練。
- Repo 文字：`enable-v4-run1/autotest-load-inn-tavern-quest-005-report.md`、`-state.json`、`-run.log`。
- 未重新 Finalize／Pack 證據 zip（docs-only）。
