# m062：catalog 容量、男名兩段查表、item_sidecar 分批（研究用）

`production_can_apply=false`、`release_approved=false`。這一輪只做 Linux 上的工作：沒有產生 EXE 或 delta，沒有跑遊戲，也沒有在 Win11 編譯。

## 1. 結論
- **264 列的上限有兩層。** 第一層在 Python（`encode_entries` 和 `reviewed_catalog` 的 `len==24`）。第二層在已經釘住 hash 的兩個 MSVC object 裡：
  - m058 NamePair：`name_pair.cpp` 的 `LD2_FindEntry` 寫著 `LD2_EntryCount>264 → return 0`。
  - m061b ListInsertU：`list_core_u.h` 的 `ld2_list_find` 寫著 `count > 264 → return 0`。
  - 所以只放寬 Python 是不行的。只要 catalog 超過 264 列，兩個 helper 每一次都會查表失敗，連 m051 的 24 項也會整組退回原文。
  - 要超過 264 列，**一定要重新編譯 helper**（之後需要一次 Win11 編譯）。這一輪先把 Linux 這邊能做的都做完。
- 新增 `catalog_v3.py`，裡面有兩種 encoder，共用同一套「已驗證列」模型：
  - `encode_v1`：和 m060 的 `encode_entries` 逐 byte 相同，維持 264 列上限，餵給目前釘住的 object。m051 的 golden hash 不變：264 列、156,288 B、sha256 `108b067c…9612`（有測試）。
  - `encode_v3`：排序過的緊湊表，最多 8192 列、pool 1 MiB，給之後重編的 helper 用。
- 實際資料（m051 加上 Mina 草稿）：去重後共 2343 列。
  - 若用 v1 的 592 B 列格式，要 1,387,056 B。
  - 用 v3 只要 87,628 B。
- `native-v3/catalog_core_v3.h` 是可攜的 C 查表核心，不用 CRT，也沒有 heap 和 global。
  - Linux 上 gcc 測過，結果和 Python 參考模型一致：合成資料 3308 個 case 全對，Mina 草稿約 1 萬個 case 全對。
  - 也做了 `-m32 -ffreestanding` 編譯檢查，沒有任何外部呼叫。

## 2. v3 格式（little-endian）
| 區段 | 內容 |
|---|---|
| header 32 B | `'LD2C'`、u16 version=3、u16 header=32、u32 count、u32 row=16、u32 rows_off=32、u32 pool_off、u32 pool_bytes、u32 flags=1（已排序） |
| row 16 B | u16 ansi_len、u16 wide_units、i16 id（-1 代表不限）、u8 kind、u8 0、u32 ansi_off、u32 wide_off |
| pool | ANSI 以 NUL 結尾；UTF-16 以 2 byte 對齊，用 0000 結尾；相同字串共用 |

- 排序鍵是 `(kind, ansi_len, ansi bytes, id)`，查詢用二分搜尋。
- kind 有四種：
  - 1 `full_id`：道具，用 stored_id 當鍵，帶 11 種 +N 後綴。
  - 2 `full_any`：女名，整串比對。
  - 3 `prefix`／4 `suffix`：男名的前段／後段。**這兩種只用來做兩段拼接，絕不拿來比對整串。**
- 查詢規則（`Lookup` 和 C 核心一致；只要有疑問就回 0，也就是走原本的 ANSI 路徑）：
  1. 先查 `full_id`。給了 id 就先用 id 過濾。如果命中多列而且譯名不同，回 0。如果同一組 bytes 只存在於其他 id 底下，也回 0，不會繼續往下查。
  2. 查 `full_any`。
  3. 前兩步只要有找到 key（即使因為歧義回 0），都不會再做拼接。
  4. 兩段拼接：在每一個 CP932 字元邊界 k 切開，看 `prefix[s[:k]]` 和 `suffix[s[k:]]` 是否都存在。所有切法得到的譯名必須完全相同，否則回 0。遇到被截斷的 lead byte 也回 0。

## 3. 男名兩段查表（0x44e7xx）和女名完全比對
以下是靜態反組譯結果，對象是 pristine `Ld95.exe` 的 0x44e737–0x44e896。
- **男名**：
  - 前段 `CString(0x745ec8 + 8*(r*200+i))`，後段 `CString(0x7461e8 + 8*(r*200+j))`，都經過 `0x412010`。
  - `operator+` 在 `0x438f70`，把兩段**直接串接、沒有分隔字元**，再由 `0x405b50` 指派給成員。
  - i 和 j 是各地區的循環計數器，各自 `mod 100`。前段計數器在 `obj+0x47c+r*16`，後段在 `obj+0x480+r*16`。
- **女名**：`0x7477c8 + 13*(r*150+k)`，經 `0x405990` 指派，計數器 `mod 150`。
- 結果是存檔與記憶體裡保存的都是**串接後的原始日文 bytes**，沒有片段 ID。

三種做法比較：
| 做法 | 優點 | 問題 | 判斷 |
|---|---|---|---|
| A. 顯示時兩段查表（v3 的 prefix/suffix） | 存檔 bytes 不變，生成邏輯不用動 | 要重新編 helper | **採用** |
| B. 在 0x44e7xx 串接點把片段換成中文 ANSI | 不用改 helper | 存檔會寫入 CP950 bytes，用 CP932 讀會變亂碼，違反「原始 bytes 回寫」策略；另有 7 個字不在 CP950 | 否決 |
| C. 串接時另外記錄 (r,i,j) | 可以精確查回片段 | 物件沒有空位可存，要改物件大小和存檔格式 | 否決 |

### Mina 草稿的靜態稽核
`male_join_static.py` 只輸出數量，不含日文。結果寫在 `male_join_static.summary.json`。
- 4 個地區各 100×100 種組合，共 40,000 種，不同的完整字串有 32,129 種。
  - 39,966 種可以正確拼接。
  - 有 8 種的 bytes 剛好和某個女名相同，女名的整串比對會先命中，顯示女名的譯名，例如「馬魯」會顯示成「瑪兒」、「夏汗」會顯示成「莎涵」。
  - 有 26 種因為切法不同會得到不同譯名，會退回原文。例如同一串 bytes 可以切成「迪奧+爾」或「迪+奧爾」。
  - 最長的拼接結果是 7 個 UTF-16 單位，原始 bytes 都在 64 以內。
- 給 Mina 的建議：summary 裡的 `review` 列出了這 34 種組合（地區、前段 index、後段 index、譯名），請統一片段的譯名。例如讓同音的女名和男名用同一個譯名，或讓尾音片段不管怎麼切都得到相同結果。這屬於翻譯端的修正，不用改程式。

## 4. item_sidecar 分批與 adventurer
- `item_sidecar.build_item_sidecar` 只在 lab 的 m051 工作樹裡（尚未 commit），GitHub 上沒有。這一輪**不改它**。
- 新增 `sidecar_plan.py`：
  - `split_items(limit<=30)`：依 (table, slot) 排序後，固定切成每批最多 30 筆。Mina 的 72 筆道具切成 30／30／12，三批都**原封不動**通過 `build_item_sidecar`（lab 實測）。超過 30 的上限會被拒絕。
  - `validate_adventurers`：檢查 adventurer 列。
    - 表格、地區、index 範圍（男名 100、女名 150）都要合法，不能重複。
    - 列上不能帶 slot、stored_id 或 record hash。
    - `exact_match_usable` 必須和表格一致：女名 true，男名 false。
    - 譯名要是 NFC、不能有控制字元、最多 12 個 UTF-16 單位，`name_cp950_encodable` 必須和實際狀況相符。
    - 同一組來源 bytes 只能對應一個譯名。
    - Mina 草稿的 1400 筆全部通過。
  - `public_copy`：公開前把 `source_name_ja` 和 `source_name_cp932_hex` 刪掉。
- `catalog_v3.verified_rows` 會對照釘住 hash 的 EXE，驗證 adventurer 的 file_offset 和名字 sha。1400 筆全部相符。

## 5. 剩下的阻礙
1. **helper 要重新編譯（需要 Win11，一次就好）。** NamePair 和 ListInsert 都要改成 include `catalog_core_v3.h`。NamePair 傳入 stored_id，不做拼接；ListInsert 和男名顯示點傳 id=-1，允許拼接。編好後要再做一次 COFF 稽核、hash 釘選，並且在 `merge_plan` 裡加 v3 綁定（`_LD2_Catalog` 和 `_LD2_CatalogBytes` 取代 Entries 和Count）。
2. **冒險者名字在哪裡顯示，還沒追蹤到。** 已知的 NamePair 顯示點都帶有道具 ID 的上下文；人名可能走別的 TextOut、DrawText 或 list。下一步要在 Linux 上靜態找出 `CString(obj+名字成員)` 被繪製的呼叫點。在 mode 2 底下，list 裡的人名目前會從 CP932 解碼成 Unicode，所以應該顯示日文，而不是 ???。
3. 515 筆音譯草稿、新增 72 項的遊戲內顯示、7 個 CP950 以外的字都要人工校對。v3 一律輸出 UTF-16，所以這 7 個字理論上能顯示，但還沒驗證。
4. 約 350 項道具還沒翻譯。v3 的容量足夠，約 350×11 列，總數仍在 8192 列以內。

## 6. 重跑方式（Linux）
```bash
python3 -m unittest research/m062/test_m062.py   # 合成測試；沒有授權輸入的部分會 skip
LD2_TEST_EXE=<pristine Ld95.exe> LD2_M051_CATALOG=<m051-items.zh-TW.json> \
  python3 -m unittest research/m062/test_m062.py   # 加上 m051 golden
```
