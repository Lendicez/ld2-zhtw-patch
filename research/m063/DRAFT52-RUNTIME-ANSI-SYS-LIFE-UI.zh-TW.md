# m063 draft52：執行期 ANSI 系統／人生 UI 候選目錄

- 目錄 JSON：`research/translations/m063-draft52-runtime-ansi-sys-life-ui.zh-TW.json`
- 來源 public_copy sha256：`707e86e9ec8442e343b98b46d0181f1dc5aef00b59cc89ccbd66322a656b0ff8`
- 提交檔 sha256：`3b89823e595e365b26cca8b2464436263e7d80e5c084d812cbee55528d4821a1`

## 內容（19 列）
月／年格式（`%2s`／`%4s`）、銷毀世界／磁碟不足／影片／強制結束／繼續冒險／引退／壽終／人生紀錄 UI、退隊道謝／同性結婚確認／告白、無可用魔法道具（兩個近似日文變體）、行星破壞裝置警告、打倒大魔王。純 ANSI，不含 UTF-16。

## 檢查
- 已驗證無假名；月／年列保留 `%2s`、`%4s`。
- review_status = `mona_approved_candidate_pending_site`
- stripped_fields：source_name_ja、source_name_cp932_hex（項目內無 ja／cp932 資料）

## 註記
- 無宿泊補包：宿泊天數句已在 draft10 `0x168dd4`（未配線）。

## 為何是候選
site_binding 未確認：mona_approved_candidate true；site_binding_confirmed false。**未配線**（不進 apply／profile）。

## 旗標
production_can_apply／release_approved／rendering_verified 皆為 false。
