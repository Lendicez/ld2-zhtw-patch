# m063 draft14：runtime ANSI 彩票／競技／委託等字串（候選 catalog）

- 檔案：`research/translations/m063-draft14-runtime-ansi-lottery-quest.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `9dcf4849e107eba71e8be2a7a12f33e5b3a45acbf6586b5ad27d5024997156f5`
- 本檔 sha256：`75a390c247b5b2992eacaebff93827e0e25d2c398771fbb7417d97bc5f811fba`
- 19 列：彩票5、競技10、通緝、委託請託／提示、道具典故
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）：尚未 xref 呼叫點確認，也未在 Win11 實機綁定畫面。
- 頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。** 等 xref 與實機截圖確認後再另開變更；不合的列剔除。

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
