# m063 draft53：執行期 ANSI 地點／國王／預言候選目錄

- 目錄 JSON：`research/translations/m063-draft53-runtime-ansi-place-king-prophecy.zh-TW.json`
- 來源 public_copy sha256：`b5cfe64de4ef80a31300c9abd3457fc912338080cef09921ed2292b91608e193`
- 提交檔 sha256：`273d9dc554a2a734da4d6c3b751437078cbb487a8f553f6267b18a98bad6464a`

## 內容（19 列）
地點標籤（情報屋／訓練所／道具店／武器店／競技場／武鬥會／移動中／鎮外）、國王資格／繼承／使者、劇情道具註記、復活前綴、護衛謝禮、預言（`%s` ×4）。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；四列預言保留 `%s`。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex（項目內無 ja／cp932 資料）

## 註記
- 無宿泊補包：宿泊天數句已在 draft10 `0x168dd4`（未配線）。

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
