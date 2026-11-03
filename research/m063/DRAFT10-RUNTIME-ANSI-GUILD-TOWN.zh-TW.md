# m063 draft10：runtime ANSI 公會／城鎮字串（候選 catalog）

- 檔案：`research/translations/m063-draft10-runtime-ansi-guild-town.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `13b56cbb2d4813892f6b8b5f2631a72fa6e1f4876068cbdbbf28c1497906908a`
- 本檔 sha256：`da7d2d282ecca5d712d8e6142a6209b6ce0b3e6340903868cb34a08b06b556d5`
- 19 列：店名2／確認5／旅店天數／系統2／公會考試入會／城鎮英雄／放棄%s／競技／戰鬥指令等
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）：尚未 xref 呼叫點確認，也未在 Win11 實機綁定畫面。
- 頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。** 等 xref 與實機截圖確認後再另開變更；不合的列剔除。

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
