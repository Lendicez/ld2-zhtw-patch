# m063 draft21：runtime ANSI 委託／彩票（候選 catalog）

- 檔案：`research/translations/m063-draft21-runtime-ansi-quest-lottery.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `18c63c1c08c26e9a515e033fb2cea7a980322ff708ca50027b127a5d468abdd1`
- 本檔 sha256：`5f953b325c0bd3ba676578f704dc57163e368182dd571dc9b7646489c5a56eb1`
- 19 列：越獄委託3、彩票、地圖道具提示、證件、日期格式、小姐%s（7B 容量）、故事等
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）：尚未 xref 呼叫點確認，也未在 Win11 實機綁定畫面。
- 頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。** 等 xref 與實機截圖確認後再另開變更；不合的列剔除。

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
