# m063 draft37：runtime ANSI 移動／陣營（候選 catalog）

- 檔案：`research/translations/m063-draft37-runtime-ansi-travel-faction.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `f24e4003f20c05dc4abc11f32ab6e8fac2e11f0bebe4fa640162ca8e26903aec`
- 本檔 sha256：`a5ea86dee8e3cd51019fa44723d86e93631d67bdde7357bf50bdd3e813dbf29e`
- 19 列：移動金錢警告、武鬥會結束、混沌／秩序傳聞、遺物、故事、商店／傳聞、信任
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`
- 地名沿用暫定：倫西亞／伊爾塔爾／龍江／日紫（本批無新地名）

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）；頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。**

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
