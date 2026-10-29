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

- `audit_list_obj.py`：未定義符號恰好 7 個（5 個 helper 綁定＋2 個 security-cookie）；拒絕 memcpy／memset／chkstk／EH／CRT／DEFAULTLIB；入口 `@LD2_ListInsert@24`（fastcall 修飾）正常路徑 `ret 16`；內部 `__cdecl` 函式遞迴稽核。**真正的 MSVC 物件已鎖定 `d5349e58…61e0` 並通過稽核**（見 `RESULT.zh-TW.md`）。
- `coff_obj.py`：通用 i386 COFF 重定位器；對 m058 物件與 m060 `relocate_reviewed` **逐位元組相同**。
- `merge_plan.py`：可接受第二個 helper（list），與 TextOutW 共用 `.ld2c`；雙 helper 惰性合併另加 `SendDlgItemMessageW` 與尾端 `OriginalDlgItem=0x4ea671` 字。單 helper 輸出 hash 仍與先前一致（原版 `08b9ec9e…41a1`、m045 `40fa133b…143c`）。雙 helper＋真實 list 物件：原版 `7468ddbe…dc07`、m045 `6a43dc4e…1cfe`。

## 6. 仍需 Windows（使用者執行 HANDOFF-COMPILE；其餘尚未授權）

1. ~~執行 `HANDOFF-COMPILE/WINDOWS-COMPILE.ps1`（Stage A＋B）~~ 已完成（2026-10-29，Stage B exit 0）。
2. ~~交回物件 → 稽核 → pin sha256~~ 已完成：`d5349e58…61e0`。
3. ~~惰性合併 loader 驗收（可丟棄副本寫出 EXE 一次）~~ **通過**（2026-10-29 03:07 台北；見 `RESULT.zh-TW.md`、`loader-inert-run1/`）。
4. 啟用版（8 個清單點＋TextOutW hook）：2026-10-29 03:34 台北在 Win11 執行一次。穩定性通過（結束碼 1、0 事件、選單結束），但還沒跑 G 收尾。清單漢字可讀，假名變 `?`（ANSI 清單的 CP950 轉換），見 §10。

## 7. 下一個可自動進行的 Linux 步驟

啟用版已在 Win11 跑過一次（§9、§10）。m061b 的設計與靜態測試已完成（§11），下一步是 `HANDOFF-COMPILE-M061B`。並行可做 m062（versions.json 依 profile 讀取；`release_approved` 仍 false）——本輪未展開。

## 8. HANDOFF-LOADER-INERT（2026-10-29 備妥；同日 Win11 執行一次：**通過**）

- 目的：只驗證 Windows 能載入雙 helper 惰性合併 EXE（m045 基底，輸出 `6a43dc4e…1cfe`，7,286,784 B，SizeOfImage 0x70C000）並到達標題畫面。hook 區段與 8 個清單點**未修改**。
- `WINDOWS-LOADER-INERT.ps1`：`-DisposableRoot` 必填且必須是新路徑；只讀原安裝、只寫副本。步驟 `-CheckOnly` → P → `-Launch`（一次）→ `-Finalize`。
- 差異：m045 → 輸出只差 8 段標頭（103 B）＋檔尾附加 167,936 B；`m061-inert.delta.json`（本倉庫）列出每段位移／長度／sha256。
  `m061-inert.delta.bin`（sha256 `f26cdbb0…a64a`）含目錄資料，**只放在交付 zip，不進倉庫**；lab 端 `make_loader_delta.py` 可重現並比對。
- Linux 驗證：`pwsh -CheckOnly`（用 lab 的原版與 m045）記憶體內合併 sha256 = `6a43dc4e…1cfe`、未寫檔；竄改 delta 1 bit → 停止（exit 2）。P／L／G 需 Windows（robocopy、事件記錄、32 位元模組探測）。
- 證據：`evidence\` 壓成 `m061-loader-inert-evidence.zip`（不含 EXE／存檔／dump）。
- `production_can_apply=false`、`release_approved=false` 不變。
- 結果（2026-10-29 03:06:57–03:07:29 台北）：到達標題畫面；結束碼 1（soft-warn，選單結束）；事件／WER／dump 皆 0；原安裝未變動。`module_probe` 讀不到 MainModule（最佳努力項，不影響判定，下一版修正）。

## 9. HANDOFF-LOADER-ENABLED（2026-10-29 Linux 備妥；同日 Win11 執行一次：穩定性通過，顯示部分達成）

- 輸出 `57103342f130da2ab51bf70e94d4dfb6c63245c3b375154bb4fbe27906b7ce5b`（7,286,784 B，CheckSum 0x700B22）。做法是在惰性版上再改：
  - hook 區段 0x6dc7d..0x6dca5 的 40 B 換成 stub（sha `67f30b3e…ca9e`），呼叫 `_LD2_NamePair@16`（0xae3170）後跳回 0x46dca5；
  - 8 個清單點的 rel32 從 0x4ea671 改成 0xae3790（`@LD2_ListInsert@24`）；
  - 重算 checksum。

  相對惰性版共 66 B 不同。
- `enable_plan.py`（可進倉庫）只允許改 hook 區段、8 個清單點和 checksum，其餘位置一律拒絕。測試在 `test_m061.py` 的 `EnablePlanTests`。
- 靜態驗證摘要在 `enabled_static_verify.summary.json`（capstone＋pefile）：
  - 沒有分支或絕對位址指進 hook 區段內部；
  - stub 前後 ESP 相同；
  - 8 個清單點的舊目標和新目標都核對過；
  - checksum 正確。
- delta：m045 → 啟用版。共 8 段標頭、9 段既有段改寫（40 B＋8×4 B），加上檔尾附加 167,936 B。`m061-enabled.delta.json` 放在本倉庫；`.bin`（`92d89d4d…2f`）只放在交付 zip，不進倉庫。
- ps1 的變更：
  - `-SeedUsrFrom`：從 m060 可丟棄副本只複製 `LUNAS*.LDP`，指向原安裝會被拒絕；
  - `module_probe` 改用 ReadProcessMemory，檢查 SizeOfImage、IAT 綁定和 9 個改寫點的記憶體 hash；
  - 觀察紀錄改為必填（各清單顯示結果、錯誤框、是否從選單結束）。
- Linux 驗證：從 zip 解出後跑 `pwsh -CheckOnly`，記憶體內合併 sha 正確，沒有寫檔。把 delta 改成允許清單以外的位置時，腳本會拒絕。P／L／G 需要 Windows。
- 已知限制：
  - 只涵蓋 8 個優先清單點；
  - 字型和字形顯示還沒驗證；
  - helper 的例外和 unwind 行為還沒在實機證明；
  - catalog 沒命中時會顯示日文原文；
  - 沒有存檔可複製時，需要開新遊戲才能進商店。
- `production_can_apply=false`、`release_approved=false` 不變。

## 10. 啟用版觀察結果與 m061b 方向（2026-10-29）

- 結果見 `RESULT.zh-TW.md`；證據摘要在 `loader-enabled-run1/`。
- 已確認 helper 有在執行：SJIS 名稱被解成 UTF-16。但因為清單是 ANSI 視窗，`SendDlgItemMessageW` 送進去的字串會被系統轉成 CP950，漢字能保留，假名變 `?`。catalog 命中的繁中理論上不受影響，但這次截圖剛好沒有 catalog 內的道具。
- m061b（Linux，設計和靜態稽核，不改任何發布旗標）：
  1. 研究讓單一清單控制項變成 Unicode 的最小作法：在 helper 內 `GetDlgItem`，`!IsWindowUnicode` 時用 `SetWindowLongW(GWL_WNDPROC)` 換成同一個 proc。要確認三件事：這 8 個點沒有在同一控制項做 A 版讀回（`readback_on_same_control=false`），MFC 沒有 subclass 這些控制項，以及需要新增 USER32 匯入。
  2. 也可以只在 catalog 命中時才走 W 路徑，沒命中就一律走原路徑。這樣顯示和 m045 一樣，風險最小，但日文假名仍是亂碼。
  3. 待補：G 收尾、module_probe 錯誤 5 的處理（在提權的 PowerShell 執行，或接受為 n/a），以及 catalog 命中畫面（武器店或防具店）。

## 11. m061b：清單框 Unicode 切換（2026-10-29 Linux 設計＋靜態測試完成；需新的 Win11 編譯）

- 設計全文見 `M061B-DESIGN.zh-TW.md`。採用 §10 第 1 案，並把第 2 案做成同一個 helper 的模式 0：
  - `.ld2c` 多一個政策字 `LD2_ListMode`，預設 2。
  - 模式 2：遇到 catalog 未命中，且目標是清單框時，用 `GetDlgItem`→`IsWindowUnicode`→`GetWindowLongW`／`GetClassLongW`（必須相等）→`SetWindowLongW`（同一個 proc）把該控制項切成 Unicode。
  - 切不成功時就是 run1 行為。
  - 模式 0：只在全命中時走 W（保底）。
  - 模式 1：run1 行為。
- 新增 USER32 匯入 `IsWindowUnicode`、`GetWindowLongW`、`GetClassLongW`、`SetWindowLongW`。`GetDlgItem` 沿用 0x525498，`MultiByteToWideChar` 沿用 0x52537c，合成器都會核對名稱。
- 原始碼在 `native-u/`，v1 的 `native/` 與已鎖定的 `d5349e58…61e0` 物件不變。稽核用 `audit_list_obj.py --profile u`，profile v1 的行為不變。
- 靜態測試：`test_m061b.py` 12 項全部通過，內容包括：
  - i386 mock 實際執行（22 個案例）；
  - clang 預演物件通過 profile u 稽核；
  - 記憶體內的惰性合併與啟用。
- 尚未產生給使用者的遊戲 EXE 或 delta。下一步是 `HANDOFF-COMPILE-M061B`（只編譯＋mock）。交回 MSVC 物件、稽核並鎖定之後，才合成模式 2 和模式 0 的啟用版 delta。
- `production_can_apply=false`、`release_approved=false` 不變。

## 12. m061b 啟用版（2026-10-29 04:30 台北 Linux 備妥；同日 10:55–11:03 Win11 執行一次：**通過**）

- MSVC 物件 `e8144466…4d51` 已稽核並鎖定（`LIST_U_OBJECT_SHA256`）。
- 模式 2 啟用版 `3a1b75b3…ed31`；保底模式 0 `49b62395…d876`。同一包用 `-Mode0` 切換。
- 交接：`HANDOFF-LOADER-ENABLED-M061B/USER-STEPS.zh-TW.md`（完整可貼上的 PowerShell 指令）。副本路徑 `<LD2_ROOT>\zhTW_lab\game-acceptance\m061b-loader-enabled`。
- 判定與 run1 相同；另外記錄假名是否正常。
- **結果（2026-10-29 Win11，模式 2）：通過。** 商店、酒館、旅館委託、委託一覽、道具說明的清單假名正常顯示；453.3 秒、結束碼 1（選單結束）、事件／WER／dump 0；原安裝未變動；Finalize 已跑。詳見 `../m061b/RESULT.zh-TW.md`，去識別化摘要 `../m061b/loader-enabled-run1/`。
- 殘留：委託資訊（詳情）視窗的非清單欄位仍有 `?`，不在 8 個清單點範圍，另案處理。模式 0 保底不需另外驗收。
- 下一步：m062 v3 catalog＋重編 helper（Win11 編譯包待執行），讓 catalog 擴充後的清單名稱顯示繁中。
