# m063 draft25：runtime ANSI 提示／模板（候選 catalog）

- 檔案：`research/translations/m063-draft25-runtime-ansi-tips-templates.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `44dce9bea94595e0b291dfc9d33365b4ff70ed84e797a26924d8009c5b944f18`
- 本檔 sha256：`65ce83fd9c066f051757a33bede42def360262e1ef751f59bb677d3bb6372b06`
- 19 列：戰鬥／迷宮／旅店／裝備／訓練提示、委託標籤「委託」、前導空白模板（出獄／逮捕）等
- 前導空白模板列保留原樣空白。
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）：尚未 xref 呼叫點確認，也未在 Win11 實機綁定畫面。
- 頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。** 等 xref 與實機截圖確認後再另開變更；不合的列剔除。

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
