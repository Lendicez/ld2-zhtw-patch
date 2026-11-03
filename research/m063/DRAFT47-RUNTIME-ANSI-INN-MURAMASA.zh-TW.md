# m063 draft47：runtime ANSI 旅館／村雨（候選 catalog）

- 檔案：`research/translations/m063-draft47-runtime-ansi-inn-muramasa.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `a09bd645157fa47071ea99fbae9bcd9085fe0e8e4af720855b67e26f9cdbe5e8`
- 本檔 sha256：`6dd85317195cba9f4ff9b58ceb65354b1668ce8f229619531e7b07db9380b6c3`
- 19 列：休養天數（%d/%d）、金幣掉落（%d）、精靈擋城、戰鬥金縛／毒、村雨刀身階段、親情守護、強盜勒索、通緝／逮捕職業態度（純 ANSI，無 UTF-16）
- 已驗證 JSON 無假名；`%d` 保留於 `text_zh_tw`。
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）；頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。**

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
