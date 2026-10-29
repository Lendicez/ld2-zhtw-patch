# m062 Mina 草稿 draft3 → draft4 審查（Mina 翻譯，Mona 審查與發布）

> **目前來源：draft4**（lab sha256 `a3e964ca05dd32997fbee2415aaf9be414342ce9c66ca71353c68b6bed5cf71f`）。本目錄公開檔已由 draft4 重新產生，檔名沿用 `m062-draft3-*` 以保持連續；詳見文末「draft4」一節。以下 draft3／draft3u 段落保留為歷史紀錄，數字以 draft4 一節為準。

最後更新：2026-10-29 12:00（台北）。狀態：**研究草稿**。`production_can_apply=false`、`release_approved=false`、`rendering_verified=false`、`preview_only=true`。
本目錄沒有 EXE、obj、delta、存檔、截圖或任何日文原文。draft3 取代 draft2（draft2 未公開）。

## 來源與分工
- 翻譯：Mina（lab 本地產生器，來源為 pristine Ld95.exe，sha256 `6c817a09…40d5d2`）。
- 審查、清理、commit：Mona。
- lab 完整草稿（含日文欄位）sha256 `d0e162f3e31c75552536d6d80849b45ccc720e1cdc7a256f2ed9539836ecde25`，記在 draft3-review.summary.json。
- **draft3u**（draft3＋使用者定稿 3 名、7 列，`review_status=user_decided`、`curated_v3`）：lab sha256 `83e69d7fa97ee9c1f2ac942c3377115f7d4a5f0288b1d3302a9f64e8d511c593`。公開檔已由 draft3u 重新產生，每個 JSON 的 `lab_full_draft_sha256` 現為 draft3u。使用者定稿：アラ→阿拉（4 列）、マダ→馬達（1 列）、ヒーム→希姆（2 列）。完整草稿、`review.tsv`、產生器與男名逐組對照（含日文）只留在 lab。

## 公開檔案
| 檔案 | 筆數 |
|---|---|
| `m062-draft3-consumables-tools.zh-TW.json` | 127（consumable 55、tool 72） |
| `m062-draft3-weapons.zh-TW.json` | 161 |
| `m062-draft3-armor.zh-TW.json` | 128（含飾品） |
| `m062-draft3-adventurers-{western,arabic,chinese,japanese}.zh-TW.json` | 各 350（男名前段 100、後段 100、女名 150） |
| `draft3-review.summary.json` | Mona 獨立驗證結果（只有數量與 hash） |
| `male_join_static.draft3.summary.json` | Mina 對完整 draft3 跑 `male_join_static.py`（只有數量與中文；歷史） |
| `male_join_static.draft4.summary.json` | Mona 對完整 draft4（draft4；Mona hold 已於 draft4-sara 解除）重跑 `male_join_static.py` |
| `male_join_static.lab_preview.summary.json`、`male_join_all40000.lab_preview.summary.json` | lab_preview 子集的男名拼接稽核 |
| `static_verify_v3.lab_preview_draft3.summary.json` | 用 lab_preview 子集重建 v3 映像（記憶體內）並跑完整靜態驗證 |

- 道具依類別拆 3 檔、冒險者依地區拆 4 檔，因為 `audit_upload` 規定每檔 < 400000 bytes。每列一筆 JSON 物件，metadata 沿用 m051。
- 清理：刪除 `source_name_ja`、`source_name_cp932_hex`。
- Mona 修改 2 處（不影響 hash／contract）：
  - extended 63 說明中以片假名（U+30C8）寫的字形名稱，改為漢字「卜字形」（公開檔不收假名）。
  - 2 筆男名後段的 `draft3_review_note` 含日文，改寫成不含日文的同義說明。

## Mona 獨立驗證（對 pristine EXE 重算，lab）
- 道具 416 筆：record（216 B）、名字、stored_id、說明 offset 與說明 sha256、說明數字、name／description contract 全部吻合（0 失敗）。與 m051 的 24 個 slot 不重疊。
- `catalog_v3.verified_rows`（m051＋完整 draft3u）：6127 列，v3 sha256 `763ae097…c091`，和 Mina 回報一致。
- `sidecar_plan.split_items` 14 批（13×30＋26）全部通過 `build_item_sidecar`；`validate_adventurers` 1400 筆通過。
- 同一組來源 bytes 只對應一個譯名（含 m051）：0 件衝突。`name_cp950_encodable` 與實際一致；非 CP950 名字 8 筆（7 個日系漢字）。

## 狀態判定（本批不標 human_reviewed／approved）
`merge_plan_v3.review_gate` 只接受 `human_reviewed`／`approved`（reviewed）或再加 `mina_draft`（lab_preview），而且是整份 catalog 檢查、不會默默略過。完整 draft3 帶有 `mina_draft2`／`mina_draft3`／`machine_needs_review`／`mina_draft2_label_desc_mismatch`，**原樣會被閘門拒絕**。

Mona 的 lab_preview 政策（只在 lab，產生 lab 專用子集 sha256 `fc2ae802…8425`，含日文欄位、不公開；舊 draft3 子集 `d68bfcd7…60bf5` 作廢）：
| 處理 | 列數 |
|---|---:|
| 收進 lab_preview（`mina_draft`／`mina_draft2`／`mina_draft3`／`user_decided` 一律改標 `mina_draft`，原值保留在 `mina_review_status`） | 1787（道具 392、冒險者 1395） |
| 排除：`machine_needs_review`（4 種來源：アフ／ダオ／ファイ／バード） | 5 |
| 排除：`mina_draft2_label_desc_mismatch`（primary 272–295，名字是怪物攻擊標籤、說明卻是裝備說明） | 24 |

- reviewed 政策維持只有 m051 的 24 項。沒有任何列升為 `human_reviewed`（user_decided 7 列也只進 lab_preview）：curated／curated_v2／curated_v3 是 Mina 的人工校對，但還沒經過使用者或遊戲內確認。
- lab_preview 子集 + m051：5859 列、v3 243,124 B，sha256 `5ec21918…f511`，`release_eligible=false`。
- 用這份 blob 重建 m045 + v3 helper 映像（模式 2／0，只在記憶體）並跑完 `build_v3_lab` 全部靜態驗證：通過。模式 2 enabled `5da5910e…1558`、模式 0 enabled `6f3df00f…bfe8`。沒有寫出 EXE。

## 男名拼接（lab_preview 子集，40,000 組全部列舉）
| 結果 | 組數 |
|---|---:|
| 兩段都收錄、顯示正確拼接 | 39,501 |
| 兩段都收錄、因跨地區假切分退回原文（阿爾頓×2、迪翁、法拉恩、法特恩） | 5 |
| 含被排除片段、退回原文（遊戲顯示日文） | 491 |
| 含被排除片段、另一種切法剛好得到 draft3 同一譯名 | 1 |
| 含被排除片段、被道具 exact row 搶走顯示「戟斧」（arabic 69+31、69+95） | 2 |

## 剩下的阻礙
1. **Kris 短劍（extended 28）**：bytes 與女名「克莉絲」相同，同一 bytes 只能有一個譯名，目前不收。建議：人名顯示點（清單 helper，id=-1）不比對 `full_id`；改好後再收「克力士劍」。
2. **男名 7 組**：5 組跨地區假切分 → v3 的 prefix/suffix 列加上 region，只接同地區片段；2 組被「戟斧」搶走 → 同第 1 點（id=-1 不比對 `full_id`）。都要改 helper（需 Win11 重編），翻譯端無法解。
3. **5 列（4 種來源）仍是機器音譯**：阿夫、達奧、法伊、巴德（戟斧衝突）。阿拉／馬達／希姆已由使用者定稿（draft3u，7 列）。
4. **24 筆標籤／說明不一致**：要在遊戲中確認這些名字是否會出現在道具畫面。
5. **非 CP950 的 7 個字**（咲宍惣杢梶榊笹，8 筆）：v3 一律輸出 UTF-16，理論上可顯示，待實機確認。
6. 所有新譯名與說明都還沒在遊戲內確認渲染。

## Win11 建議
靜態面已準備好做一次 **lab_preview 拋棄式副本觀察**（模式 2 優先，模式 0 備用）：酒館清單已在 m061b 的改寫點內，所以能看到冒險者名與道具清單的繁中顯示。但內容全部仍是草稿，依 RESULT「Win11 交接」條件 (b)，要先取得使用者同意才打包，本輪不準備交接包。

## draft4（目前來源，2026-10-29）
- Mina draft4-names：draft3u＋7 列改為 `review_status=mina_draft4`、`translation_method=curated_v4_web`（網路對照）。`machine_needs_review` 歸零。
  - ダオ 達奧→**達烏**（Dawud 達烏德）；アフ 阿夫、ファイ 法伊（拼接強制，改「費」會多 1 個衝突）、バード 巴德 保留；男名 サラ 莎拉→薩拉（2 列）。使用者定稿 阿拉／馬達／希姆 未動。
- **サラ 使用者定稿（2026-10-29）**：同一組來源 bytes 的 3 列（男 western/95、arabic/37，女 western/94）一律「**薩拉**」，`review_status: user_decided`；Mona hold 解除，`validate_adventurers` 通過。來源＝Mina draft4-sara（sha256 `33f63c04…0f8e`），公開檔已剝 ja／hex，與其 1816 列譯名逐列一致。
- 公開清理同前（剝 `source_name_ja`、`source_name_cp932_hex`）；另把 4 種 `draft4_review_note` 內的日文改寫為不含日文的同義說明。
- Mona 獨立驗證：道具 416 筆對 EXE 0 失敗；`validate_adventurers` 1400 通過；14 批 sidecar 通過；同 bytes 多譯名 0；非 CP950 8 筆。`verified_rows`（m051＋完整 draft4/hold）6127 列，v3 `c380f8dd…053c`。
- **lab_preview**（lab 專用子集 sha256 `0a63ccff…9ead`，取代 draft3u 子集 `fc2ae802…8425`）：收 `mina_draft`／`mina_draft2`／`mina_draft3`／`mina_draft4`／`user_decided` → 1792 列（道具 392、冒險者 **1400**）；只排除 24 筆 label/desc mismatch，machine 排除 0。＋m051：5863 列、v3 243,240 B，sha256 `6a7a119d…de75c`，`release_eligible=false`。
- `build_v3_lab` 靜態驗證（模式 2／0，記憶體內，不寫 EXE）通過：模式 2 enabled `ea1e5b41…993d`、模式 0 enabled `c4babb27…7885`。
- 男名 40,000 組（lab_preview）：正確 39,993；跨地區假切分退回原文 5（阿爾頓×2、迪翁、法拉恩、法特恩）；被道具「戟斧」搶走 2（arabic 69+31、69+95）；不再有含被排除片段的組合。`male_join_static`：join_ok 39,985、conflicting 0。

### draft4 後剩下的阻礙
1. ~~サラ 男女同 bytes~~：已定稿「薩拉」（2026-10-29）。
2. **Kris 短劍（extended 28）**：與女名同 bytes，未收；需 helper 在人名點（id=-1）不比對 `full_id`。
3. **男名 7 組**：5 組跨地區假切分（prefix/suffix 需帶 region）、2 組 哈爾巴德→戟斧（同第 2 點）。需改 helper＋Win11 重編，翻譯端無法解。
4. **24 筆 label/desc mismatch**（primary 272–295）仍排除。
5. **非 CP950 7 字（8 筆）**待實機確認；所有新譯名均未經遊戲內確認，沒有任何列升為 human_reviewed。

### Win11 建議（draft4）
不變：靜態上可做 lab_preview 拋棄式觀察（模式 2），現在冒險者 1400 名全收、不會再看到日文退回（除 5 組假切分）；但仍屬草稿，需使用者同意才打包，本輪不打包。
