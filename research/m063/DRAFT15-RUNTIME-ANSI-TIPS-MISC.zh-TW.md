# m063 draft15：runtime ANSI 提示／雜項字串（候選 catalog）

- 檔案：`research/translations/m063-draft15-runtime-ansi-tips-misc.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `bff48dee68a748d3165ab847a57479ff9aa55873cd56d79bf0b1303850b3c402`
- 本檔 sha256：`75737023c3ba3d86f126f5cd1322e046a0de4a2e24bc5233204b0a59c8b400e2`
- 19 列：競技6、王室販售、妖精傳聞、彩票開獎、委託／通緝／戰鬥提示、道具求購／典故
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）：尚未 xref 呼叫點確認，也未在 Win11 實機綁定畫面。
- 頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。** 等 xref 與實機截圖確認後再另開變更；不合的列剔除。

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
