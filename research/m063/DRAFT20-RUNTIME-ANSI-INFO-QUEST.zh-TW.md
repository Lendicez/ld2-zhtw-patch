# m063 draft20：runtime ANSI 情報屋／委託（候選 catalog）

- 檔案：`research/translations/m063-draft20-runtime-ansi-info-quest.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `f202c6e83f3db8d5c9c8d36fcc938f1ea17aa987e0655de7599e021065dd1b05`
- 本檔 sha256：`113f38546e74950928636618a9d4fd10df6bc629c0fad74215cf7ce32c6c633e`
- 19 列：情報屋7、勇者／委託請託、迷宮提示、獲得%s、故鄉
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）：尚未 xref 呼叫點確認，也未在 Win11 實機綁定畫面。
- 頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。** 等 xref 與實機截圖確認後再另開變更；不合的列剔除。

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
