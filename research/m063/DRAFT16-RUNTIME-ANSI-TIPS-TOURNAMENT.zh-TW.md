# m063 draft16：runtime ANSI 委託／旅行提示與競技播報（候選 catalog）

- 檔案：`research/translations/m063-draft16-runtime-ansi-tips-tournament.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `ab2ec542af00e4c1b59f2f6ff263f860c7cc96dc4d6cf9ecc24e53d9c860f075`
- 本檔 sha256：`6a6862b9b41c4a0bea230ee08aecb058e502279503ad0b38d1c1bb14ba49770f`
- 19 列：委託提示7、旅行提示3、競技播報9
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）：尚未 xref 呼叫點確認，也未在 Win11 實機綁定畫面。
- 頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。** 等 xref 與實機截圖確認後再另開變更；不合的列剔除。

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
