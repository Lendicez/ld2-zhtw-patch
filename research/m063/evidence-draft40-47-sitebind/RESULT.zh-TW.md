# draft40–47 site-bind harness 結果 — 進點證據

> 來源：Rona Win11 本機 harness（`Desktop\ld2-draft40-47-site\RESULT.zh-TW.md`，2026-11-05 Asia/Taipei）＋ Mina 確認＋ Rona 更正，折入 #26。僅文字；截圖留在 Win11 `Desktop\ld2-draft40-47-site\`，EXE／存檔／zip／lab JSON 不入庫。`production_can_apply=false`、`release_approved=false`、`rendering_verified=false`、`site_binding_confirmed=false`。catalog JSON 未改寫。

## 總結
- draft40–47：**0 行 site-confirmed**；候選維持 `pending_site`／`unconfirmed_candidate_adjacent_rdata`。

## 旅館住宿天數彈窗
- 執行期顯示未譯日文：「宿泊できる日数は1日から30日までです。」（輸入 0／999 天皆同）
- 原文模板＝`0x168dd4` `宿泊できる日数は%d日から%d日までです。`，**已在 draft10**（#26 candidate）譯為「可住宿天數為%d日至%d日。」
- 結論：畫面仍日文／亂碼＝**未配線**，不是漏翻。
- draft47 `0x13c3f0`「休養できる日数は…」（可休養天數為%d～%d日。）＝**住家／休養**用途，非宿泊；另案。
- 截圖：`Desktop\ld2-draft40-47-site\innshop-001-inn-days0-popup.png`（僅 Win11）

## draft46 `0x158f60` 枚數行
- 一般道具店不跳數量框；疑為卡片／卷軸店；仍 unconfirmed。

## harness 附註
- `ui_smoke_wm2_no32880` 改用 `dismiss_chain`；`site4047-uismoke-001` 綠燈。
- 舊 `load_inn_tavern_quest` 若訓練所視窗未關會 force_kill；結尾須補關窗。
  - 2026-11-05：已修，見 `innfix-20261105-001` 綠燈（force_killed=false；clean_exit 左鍵 dismiss，不再 WM_CLOSE）。
