# m061 HANDOFF-LOADER-INERT：惰性雙 helper loader 驗收（Win11，一次）

**只驗證「Windows 能載入這個 EXE 並進到標題畫面」。** 不啟用任何翻譯功能。
`production_can_apply=false`、`release_approved=false`，本包不改變這兩個值。

## 這個 EXE 是什麼

- 基底：m045 `Ld95.exe`（sha256 `4a0910…9da7`，7,118,848 B）。
- 加上三個新段：`.ld2t`（TextOutW helper＋清單 helper 程式碼）、`.ld2c`（共用目錄）、`.ld2i`（新匯入表）。
- 匯入描述子 13→15：新增 `GDI32.dll!TextOutW`、`USER32.dll!SendDlgItemMessageW`；既有 IAT 位址全部不變。
- **惰性**：hook 區段（檔案位移 0x6dc7d..0x6dca5）與 8 個清單呼叫點都沒改，遊戲不會執行到新程式碼。EntryPoint 不變。
- 結果：sha256 **`6a43dc4e3d881a207f4b0dae2fcc5f1fca5d079d6fe90139115da84ac3ef1cfe`**（7,286,784 B，SizeOfImage 0x70C000，PE checksum 0x6FCB68）。
- 清單 helper 物件：使用者 Stage A 編出的 `list_insert_w.obj` sha256 `d5349e58…61e0`（Linux 稽核通過）。

## 怎麼產生

Linux 端用 `merge_plan.build_inert`（m045＋m058 物件＋m051 目錄＋m061 清單物件）在記憶體內合成，並和 m045 比對出差異：
標頭 8 小段（共 103 B）＋檔尾附加 167,936 B。打包成 `m061-inert.delta.bin`（sha256 `f26cdbb0…a64a`）與
`m061-inert.delta.json`（每段位移／長度／sha256）。Windows 腳本只會：讀 m045 → 套 delta → 核對每段與整檔 hash → 寫到你指定的副本。
腳本拒絕修改 m045 既有段落（位移 0x1000 以後、原長度以內的區域）。

`m061-inert.delta.bin` 含目錄資料（從遊戲文字衍生），**只在 zip 裡交給使用者，不進 GitHub 倉庫**。

## 檔案

| 檔案 | 用途 |
|---|---|
| `WINDOWS-LOADER-INERT.ps1` | P（建副本＋寫惰性 EXE）、L（啟動一次）、G（收尾）；`-DisposableRoot` 必填 |
| `m061-inert.delta.bin`／`.json` | 差異資料（hash 已釘在腳本內） |
| `USER-STEPS.zh-TW.md` | 使用者操作步驟 |
| `observations.template.md` | 觀察紀錄樣板（P 會複製到 evidence\） |

## 判定

- **通過**：看到標題畫面；L 的結束碼 0 或 1；無 Ld95 錯誤／WER 事件、無新 dump；`module_probe.module_memory_size = 0x70C000`（新段已映射，若有讀到）。
- **失敗**：loader 錯誤框（找不到程序進入點、0xc000007b 等）、崩潰、無回應。只截圖＋跑 G，回傳證據，不重試。

## 之後（另案授權）

通過後才考慮功能版：啟用 TextOutW hook 與 8 個清單呼叫點，在副本上觀察商店／酒館／委託畫面。
