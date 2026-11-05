# m063 draft46：runtime ANSI 商店／戰鬥（候選 catalog）

- 檔案：`research/translations/m063-draft46-runtime-ansi-shop-combat.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `f46ad7e618a6cfb1723f82e0b2cf12e86a164909271528a3ae07f81dca2a9dcd`
- 本檔 sha256：`e8ae7b3d0cb71d9bb110b763ff76defd013226d960e008d2e763538d3c687c27`
- 19 列：商店可購張數（%d/%d）、名字／戰鬥 stub（%s）、購屋／增建、道場成名、戰鬥攻擊／魔法線、越獄態度（純 ANSI，無 UTF-16）
- 已驗證 JSON 無假名；`%s`／`%d` 保留於 `text_zh_tw`。
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）；頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。**

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。

## 2026-11-05 site-bind 註記（Rona harness）
- `0x158f60` 枚數行：一般道具店不跳數量框；疑為卡片／卷軸店；仍 unconfirmed。見 `evidence-draft40-47-sitebind/RESULT.zh-TW.md`。
