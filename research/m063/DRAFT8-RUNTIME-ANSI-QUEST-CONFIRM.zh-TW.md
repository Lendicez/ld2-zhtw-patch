# m063 draft8：runtime ANSI 委託／確認字串（候選 catalog）

- 檔案：`research/translations/m063-draft8-runtime-ansi-quest-confirm.zh-TW.json`
- 來源：Mina public_copy（已剝 ja／cp932_hex），sha256 `4d161d0eb31b4e22dad8419c0a25bd72181631252f783d2d98fddb91c3cb6fbc`
- 本檔 sha256：`bdd9b906bd510fceccd89807b70e21b261c5bdf04d6e7d5028e45157175b4b80`
- 19 列：`quest_status` 15 ＋ `confirm` 4（渡す／中止／支払／ありがとう）
- Mona 已審譯文：`review_status = mona_approved_candidate_pending_site`

## 為何只是候選
- 每列 `site_binding = unconfirmed_candidate_adjacent_rdata`：位址僅為訓練塊／委託結果鄰近 .rdata，尚未做 xref 呼叫點確認，也未在 Win11 實機綁定畫面。
- 頂層 `mona_approved_candidate: true`、`site_binding_confirmed: false`。
- **未接入任何 apply／profile 程式碼。** 等 xref 與 Rona 實機截圖確認後再另開變更；不合的列剔除。

## 旗標
`production_can_apply: false`、`release_approved: false`、`rendering_verified: false`。
