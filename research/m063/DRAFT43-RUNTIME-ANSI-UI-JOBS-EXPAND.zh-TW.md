# m063 draft43：runtime ANSI 擴掃 UI／委託（候選 catalog）

- 檔案：`research/translations/m063-draft43-runtime-ansi-ui-jobs-expand.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `16d7d5b983ea2aec3c5122559d8579051923acc28e9329349cc41701704c90f5`
- 本檔 sha256：`eb0e53826cde0f9c60d90bd02592b33ffcdbd32c129d6ee05a79eec612d718cc`
- 19 列（擴掃 0x12xxxx）：道具／MP／裝備／復活 UI、迷宮定位模板（%A–%D）、城鎮事件、走私／越獄／復仇委託態度、戰鬥提示（純 ANSI，無 UTF-16）
- 已驗證 JSON 無假名；`%s`／`%d`／`%A`–`%D` 保留於 `text_zh_tw`。
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）；頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。**

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
