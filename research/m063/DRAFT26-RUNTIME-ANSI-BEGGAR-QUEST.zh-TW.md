# m063 draft26：runtime ANSI 乞丐劇情／委託（候選 catalog）

- 檔案：`research/translations/m063-draft26-runtime-ansi-beggar-quest.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `a6042a6c23bb749518fc4ba1721097e49249dd139ad91265680c402fc6cb361f`
- 本檔 sha256：`ebbdf1afc1d297a0696a90173d3b1f29e23e6aa14c40dac86697d12667375221`
- 19 列：乞丐劇情、傳說、委託提示／模板（含 DOA）、勇者標籤等
- 前導空白模板列保留原樣空白；`DOA` 保留原文字面。
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）：尚未 xref 呼叫點確認，也未在 Win11 實機綁定畫面。
- 頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。** 等 xref 與實機截圖確認後再另開變更；不合的列剔除。

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
