# m063 draft41：runtime ANSI 信任／契合／武鬥落敗（候選 catalog）

- 檔案：`research/translations/m063-draft41-runtime-ansi-affinity-tourney.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `cc1a765b53f9677e3a93ab05fb51a0f61c31fc5ad541d6b9c703eb219b1017da`
- 本檔 sha256：`dc572e2f1c0e496b1d554b90393f9dcb713a5026f163d3ca269eb0042a46e689`
- 19 列：信任4、契合8、金錢／居家、武鬥落敗3（純 ANSI）
- 已驗證 JSON 無假名（含 note／base_doc）。
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）；頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。**

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
