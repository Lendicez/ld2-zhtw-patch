# m063 draft44：runtime ANSI 銀行／迷宮（候選 catalog）

- 檔案：`research/translations/m063-draft44-runtime-ansi-bank-dungeon.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `383829bb0ada77363c1437f7cdafcf8045b6b012b5356ee40a603bf8045e7b77`
- 本檔 sha256：`9f6f7ea3d4a35076d77415e988b1933e17143965acae5f46acde26ab37a9f809`（2026-11-05 修 `0x166e28`；原 `4588b761…ed83`）
- 19 列（擴掃）：銀行／同伴／確認 UI、迷宮建議（%s）、情報屋迷宮定位（%A–%E）、懸賞／越獄、故事獎勵、走私態度（純 ANSI，無 UTF-16）
- 已驗證 JSON 無假名；`%s`／`%d`／`%A`–`%E` 保留於 `text_zh_tw`。
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列保留 `site_binding`（unconfirmed）；頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。**

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。

## 2026-11-05 修稿（Claude）
- `0x166e28`：譯文多出原文沒有的 `%E`（m064 `rdata_ansi.py` 合約檢查擋下）。原文替換符為 `%A %A %B %B %C %D`（%C 地點、%D 迷宮名），改為「…現在好像在「%C」名叫「%D」的迷宮裡探索。要再等一會兒嗎？」；CP950 94 bytes ≤ 153。
