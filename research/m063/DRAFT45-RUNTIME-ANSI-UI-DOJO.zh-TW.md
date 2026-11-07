# m063 draft45：runtime ANSI UI／道場（候選 catalog）

- 檔案：`research/translations/m063-draft45-runtime-ansi-ui-dojo.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `6863cb6cbe5b852a062409aed7c7dab9632f49514e48f6ba4ffc1b8d9c1227c8`
- 本檔 sha256：`4145afbcd1ba847da056408bc72c3ae43754eb7d6daccb56df297a1a1bc40b11`
- 19 列：道具／住家／店／鍛造上限 UI、加入同伴（%s）、道場挑戰／達人對白、長老智慧、同伴倒下戰吼、走私態度（純 ANSI，無 UTF-16）
- 已驗證 JSON 無假名；`%s` 保留於 `text_zh_tw`。
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）；頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。**

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
