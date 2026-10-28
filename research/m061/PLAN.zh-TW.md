# m061：對話框清單 Unicode 顯示＋helper 合併鏈（Linux 靜態階段）

最後更新：2026-10-29。`production_can_apply=false`、`release_approved=false` 不變。本輪沒有執行遊戲、沒有 native／loader 執行，也沒有寫出任何 EXE。

> 命名註記：ROADMAP §3 原把「planner 依 profile 讀 versions 記錄」暫稱 m061。由於 run2 結果把「清單動態字串」列為最優先，本里程碑改用 m061；versions.json 任務順延為 **m062**，內容不變。

## 0. 起點（run2 結論）

m045 在 Win11 上的靜態 UI 已正確顯示繁中。但商店、酒館、委託等**對話框清單**裡的道具、冒險者、委託名稱會顯示 `?` 或亂碼，例如「捲識」。位元組驗證顯示，這是 Shift-JIS 資料被當成 CP950 解讀造成的。

## 1. 新發現：清單字串的實際路徑（原版靜態分析）

- 遊戲在清單裡加字串時，全部經過 MFC `CWnd::SendDlgItemMessage` 包裝函式（VA `0x4ea671`）。它的一般 HWND 分支在 `0x4ea689` 呼叫 `USER32!SendDlgItemMessageA`。換句話說，這裡**沒有 TextOutA**，因此 m056/m058 的 TextOutW helper 只涵蓋道具說明視窗，蓋不到清單。
- 盤點 `list_sites.json`，經 vtable→建構子→資源 ID 對到對話框：
  - 字串插入：`LB_INSERTSTRING` 71 處、`LB_ADDSTRING` 33 處、`CB_INSERTSTRING` 5 處。
  - 讀回：`LB_GETTEXT` 5 處。
  - 另有 5 處包裝呼叫的訊息不是立即值（未解析）。
- 對應到對話框後，所有相關清單框都不是 owner-draw。
- `LB_ADDSTRING` 從未寫進設了 `LBS_SORT` 的清單；商店清單雖有 `LBS_SORT`，用的卻是不排序的 `LB_INSERTSTRING`。因此換成 Unicode 不會改變索引順序。
- 有讀回的控制項如下，第一階段一律排除，維持原 ANSI 路徑：
  - 存讀檔對話框 152／153 的 1025、1026；
  - 分配道具對話框 172 的 1071。
- `MultiByteToWideChar` 已在原 IAT（`0x52537c`）；`LoadStringA` 沒有匯入，因此清單字串不是來自 m045 翻過的字串表。
- 第一階段候選共 83 處，其中優先 8 處：

  | VA | 訊息 | 控制項 | 對話框 | 角色 |
  |---|---|---|---|---|
  | `0x4aaf19`、`0x4ab0fe` | LB_INSERTSTRING | 1000 | 137 | 商店・購買 |
  | `0x4b4df1` | LB_INSERTSTRING | 1000 | 138 | 商店・出售 |
  | `0x4b46e4` | LB_INSERTSTRING | 1000 | 139 | 商店・強化 |
  | `0x4b3477` | LB_INSERTSTRING | 1000 | 140 | 旅館・委託 |
  | `0x4b2d1f` | LB_INSERTSTRING | 1000 | 143 | 酒館 |
  | `0x492431` | LB_INSERTSTRING | 1073 | 169 | 委託一覽 |
  | `0x4b1153` | LB_INSERTSTRING | 1021 | 156 | 委託資訊 |

  每一處都是 5-byte `call rel32` 指向包裝函式，前 16 bytes 加上 call 的視窗 hash 已固定在 manifest 中。

## 2. 設計：`LD2_ListInsert`（逐點替換，不動全域包裝）

- **安裝方式**：只把上表各點的 `E8 rel32` 改指向新 helper，長度一樣是 5 bytes，原包裝函式與其餘呼叫點完全不動。`site_plan.py` 會驗證視窗 hash 並在記憶體中算出 (offset, old, new)，但不套用。
- **ABI**：使用 `__fastcall`，並放一個不用的 EDX 參數，效果等同原 thiscall（ECX=CWnd*、4 個 stack DWORD、`ret 0x10`）。
- **行為**（`native/list_core.h` 為可攜核心；`native/list_insert_w.cpp` 為 MSVC x86 入口）：
  1. 遇到下列任一情況就把原參數原封交回原包裝：訊息不是 ADD/INSERT 類、`m_pCtrlSite≠0`、指標小於 0x10000、超過 256 bytes 沒有 NUL、有 Tab 以外的控制字元、全部是 ASCII。
  2. 字串依 Tab 分段，每段先查共用 catalog（沿用 m056 的 592-byte 列格式，只比對完整 bytes，忽略 ID；若同一組 bytes 對到不同譯文，視為歧義，不翻譯）。
  3. catalog 沒有命中時，用 `MultiByteToWideChar(932, MB_ERR_INVALID_CHARS)` 嚴格解碼。解碼失敗就走原路徑。
  4. 用 `SendDlgItemMessageW` 送出 helper 自己堆疊上的 UTF-16 緩衝區（257 units）。清單框會同步複製字串；送出後清零緩衝區。不配置 heap，也不使用全域狀態。
- **效果預期（尚未實機驗證）**：沒有譯文的字串至少顯示為正確日文，不再是 `?`；有 catalog 的道具名顯示為繁中。原存檔與 record bytes 都不變（方案 1：只在顯示層投影）。
- **新匯入**：只需要 `USER32!SendDlgItemMessageW`。原 USER32 descriptor 不動，另外追加一個 descriptor。

## 3. 合併鏈（本輪已實作，純記憶體）

| 模組 | 內容 |
|---|---|
| `source_profile.py` | 證明 m045 輸出（`4a0910…9da7`）與原版只差在 `.rsrc` 和 12 個白名單 header bytes（SizeOfInitializedData、SizeOfImage、CheckSum、資源目錄大小、`.rsrc` VirtualSize／SizeOfRawData）；`.text`／`.rdata`／`.data` 完全相同（hash 已固定）。因此原版審過的 VA 在 m045 上同樣有效。新區段起點是 m045 的 SizeOfImage `0x6e3000`（原版為 `0x6dc000`；原 m060 布局 `0x6dc000` 會和 m045 的 `.rsrc` 重疊）。 |
| `import_builder.py` | 把 m057/m060 的 `add_textoutw` 一般化為「已審 API 清單」（TextOutW、SendDlgItemMessageW）。在原版、TextOutW 的條件下，輸出與 m060 片段**逐位元組相同**（`16be0bf6…724d`）。 |
| `pe_serializer.py` | 有界的 PE32 區段附加器：只接受固定基址（已 strip relocations）、無 overlay、header slack 為 0、Section RVA 必須等於規劃位置、區段屬性只允許 RX／R／RW，只能改 import 目錄。會重算 SizeOfImage、SizeOfCode／InitData 與 CheckSum（演算法對原版 `0x6c4492` 與 m045 `0x6d0c03` 皆正確重現），並讀回驗證舊區段與 header 白名單。 |
| `merge_plan.py`（實驗室限定，依賴 m060） | 「惰性合併」：helper code（`.ld2t`）、catalog（`.ld2c`）、import（`.ld2i`）附加到原版或 m045，import 目錄改指向新表。**hook 片段 `0x6dc7d–0x6dca5` 不改**，遊戲執行時不會進到 helper。結果只算 hash，不寫檔。 |

惰性合併結果（記憶體中，未寫檔）：

| 輸入 | code RVA | catalog RVA | import RVA | TextOutW IAT | 輸出 sha256 |
|---|---|---|---|---|---|
| 原版 | `0x6dc000` | `0x6dd000` | `0x704000` | `0xb0414c` | `08b9ec9e…41a1` |
| m045 | `0x6e3000` | `0x6e4000` | `0x70b000` | `0xb0b14c` | `40fa133b…143c` |

原版 profile 重定位後的 code hash 為 `c08f8b08…0ed9cb5`，與 m060 完全一致（交叉驗證）。以 pefile 獨立解析 m045 合併結果：7 個區段、CheckSum 正確、14 個 import descriptor（最後一個為 GDI32!TextOutW）、資源樹仍可解析。

## 4. 測試（Linux，2026-10-29）

| 測試 | 結果 |
|---|---|
| `python -I -B test_m061.py` | 12 tests OK：serializer 合成正例與 9 個拒絕案例、目錄規則、竄改偵測、manifest 合約（純 ASCII、無遊戲文字）、原版＋m045 授權測試、竄改 `.text`／header 遭拒、host C 核心 |
| `native/host_test.c`（gcc＋iconv CP932） | 16 checks、0 failed：ASCII 不轉、catalog 命中、Tab 分段、歧義改走解碼、非法 CP932、控制字元、256／257 bytes 邊界、catalog 數量防護、列大小 592 |
| `python -I -B test_merge_lab.py` | 3 tests OK（原版重現 m060、m045 布局／hash、錯誤 object 被拒） |
| m060 `test_memory_plan.py` 回歸 | 28 tests OK |

紀錄存於 `zhTW_lab/runs/m061/`。

## 5. HANDOFF-COMPILE（本輪已備妥，待 Win11 執行）

包：交回使用者的 `m061-handoff-compile.zip`（附 `.sha256`；本倉庫只收 HANDOFF-COMPILE 原始檔，不收 zip）。

| Stage | 內容 | 產物 |
|---|---|---|
| A | `cl /c /W4 /WX /O2 /Oi /Oy- /GS /Gy /Zl /EHs list_insert_w.cpp`（不連結） | `runs/m061/compile-only/list_insert_w.obj` |
| B | 編譯 `list_mock_test.cpp`，與 A 連結並執行一次（假 API，不開遊戲） | `runs/m061/mock/once-result.json` |

Linux 端已就緒：

- `audit_list_obj.py`：未定義符號恰好 7 個（5 個 helper 綁定＋2 個 security-cookie）；拒絕 memcpy／memset／chkstk／EH／CRT／DEFAULTLIB；入口 `_LD2_ListInsert@24` 正常路徑 `ret 16`。以 synthetic COFF stand-in 跑過（sha `4ecaf65a…8493`）；**真正的 MSVC 物件 hash 待 Stage A 後鎖定**。
- `coff_obj.py`：通用 i386 COFF 重定位器；對 m058 物件與 m060 `relocate_reviewed` **逐位元組相同**。
- `merge_plan.py`：可接受第二個 helper（list），與 TextOutW 共用 `.ld2c`；雙 helper 惰性合併另加 `SendDlgItemMessageW` 與尾端 `OriginalDlgItem=0x4ea671` 字。單 helper 輸出 hash 仍與先前一致（原版 `08b9ec9e…41a1`、m045 `40fa133b…143c`）。雙 helper＋synthetic list：m045 `38119770…de2c`。

## 6. 仍需 Windows（使用者執行 HANDOFF-COMPILE；其餘尚未授權）

1. 執行 `HANDOFF-COMPILE/WINDOWS-COMPILE.ps1`（Stage A＋B）。不上遊戲。
2. 把 `list_insert_w.obj`＋`compile-command.json` 交回 Linux → 跑 `audit_list_obj.py` → pin sha256。
3. **之後另案授權**：惰性合併 loader 驗收（可丟棄副本寫出 EXE 一次）。
4. 再之後：啟用 8 個清單點＋TextOutW hook 的功能版，Win11 觀察商店／酒館／委託。

## 7. 下一個可自動進行的 Linux 步驟

等 Stage A 物件交回後：跑稽核、把 list object sha256 寫進 `merge_plan` pin、更新 dual-merge 金樣。並行可做 m062（versions.json 依 profile 讀取；`release_approved` 仍 false）——本輪未展開。
