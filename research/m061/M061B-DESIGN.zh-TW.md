# m061b 設計：清單框改成 Unicode 視窗（Linux 端設計＋靜態測試）

最後更新：2026-10-29 04:30（台北）。MSVC 物件 `e8144466…4d51` 已稽核鎖定，啟用版交接 `HANDOFF-LOADER-ENABLED-M061B` 已備妥（見 RESULT）。`production_can_apply=false`、`release_approved=false`。本文件只描述 Linux 端已完成的設計、原始碼與靜態測試。**尚未**產生任何要給使用者套用的遊戲 EXE 或 delta。

## 1. 問題（m061 啟用版 run1）

- helper 正確把 CP932 名稱解成 UTF-16，經 `SendDlgItemMessageW` 送出。
- 但 8 個優先清單點所在的對話框清單框都是 **ANSI 視窗**。Windows 把 W 訊息轉回 ANSI（zh-TW 系統的 CP950）再交給清單框，CP950 沒有假名，所以假名變 `?`，漢字留下。
- 證據：11 個 `?` 對上「コンディションパウダー」的假名數；委託清單的漢字（退治、救出、宅配…）正確。

## 2. 決策：一個政策字，預設模式 2

`.ld2c` 目錄區在 `[OriginalDlgItem]` 之後多放一個 32 位元字 `LD2_ListMode`，由合成器寫入（唯讀區段），helper 每次呼叫時讀取：

| 模式 | 行為 | 風險 | 用途 |
|---|---|---|---|
| 0 | 只有「每個非 ASCII 欄位都是 catalog 唯一命中」才走 W；否則整串交回原 ANSI 路徑（等同 m045） | 最低：未命中的字串完全不變 | 保底／正式版候選 |
| 1 | run1 行為：能解碼就走 W | 已驗證穩定，但假名變 `?` | 對照組 |
| **2（預設）** | 同 1，但遇到 catalog 未命中，且目標是清單框（LB_*）時，先把**該控制項**切成 Unicode 視窗 | 中：會改一個系統控制項的 A/W 屬性 | 想要假名正常顯示 |
| >2 | 一律走原路徑 | 無 | 緊急停用 |

只在**未命中**時才切換：全命中字串（正體中文）經 CP950 本來就不會掉字，不需要動視窗。組合框（CB_INSERTSTRING）不切換，只走模式 1 行為。

### 模式 2 流程（`native-u/list_insert_u.cpp`）

```text
守門（同 v1：wnd 非空、m_pCtrlSite==0、所有綁定非空）＋ mode<=2
units = LD2_ListPrepare(..., &misses)        // misses = 未命中且含非 ASCII 的欄位數
units<=0                → 原 ANSI 路徑（m045）
misses>0 且 mode==0     → 原 ANSI 路徑
misses>0 且 mode==2 且 msg!=CB_INSERTSTRING:
    h = GetDlgItem(m_hWnd, id)
    若 h 且 !IsWindowUnicode(h):
        p = GetWindowLongW(h, GWL_WNDPROC)
        c = GetClassLongW(h, GCL_WNDPROC)
        若 p!=0 且 p==c:  SetWindowLongW(h, GWL_WNDPROC, p)   // 同一個程序，只換 W 註冊
SendDlgItemMessageW(m_hWnd, id, msg, wp, owned)               // 不論切換成功與否
```

- 切換失敗（被子類化、`p!=c`、`p==0`、找不到控制項、系統不接受）時，結果與 run1 完全相同（漢字可讀、假名 `?`），不會比 run1 更差。
- 因此不需要「切換後再檢查」：兩個結果都走 W，差別只看畫面上假名是否正常。
- 每個對話框實例第一次未命中時切換一次；之後 `IsWindowUnicode` 為真，只多兩個呼叫。

## 3. 匯入

| API | 來源 | IAT | 呼叫慣例 |
|---|---|---|---|
| `GetDlgItem` | 遊戲既有 USER32 | 0x525498（合成器逐一核對名稱） | stdcall，ret 8 |
| `MultiByteToWideChar` | 遊戲既有 KERNEL32 | 0x52537c（核對名稱） | stdcall，ret 24 |
| `SendDlgItemMessageW` | 新增（v1 已有） | `.ld2i` | stdcall，ret 20 |
| `IsWindowUnicode` | **新增** | `.ld2i` | stdcall，ret 4 |
| `GetWindowLongW` | **新增** | `.ld2i` | stdcall，ret 8 |
| `GetClassLongW` | **新增** | `.ld2i` | stdcall，ret 8 |
| `SetWindowLongW` | **新增** | `.ld2i` | stdcall，ret 12 |

- 遊戲只匯入 `GetWindowLongA`／`SetWindowLongA`／`GetClassLongA`，W 版都沒有，所以要新增。`import_builder.extend` 會拒絕重複匯入。
- `import_builder.REVIEWED_APIS` 只加這 4 個。測試確認沒有 `SetWindowLongA`、`SetClassLong*`、`CallWindowProc*`、`SetWindowsHookEx*`、`VirtualProtect`、`LoadLibrary*`、`GetProcAddress`。
- 32 位元程序，`GetWindowLongW`／`SetWindowLongW` 等同 `*Ptr` 版本。

## 4. MFC 與子類化風險

| 來源 | 對清單框的影響 | 處理 |
|---|---|---|
| MFC CBT hook（`AfxOldWndProc`） | 只子類化非子視窗；清單框是子視窗 | 不影響 |
| `DDX_Control`／`SubclassDlgItem` | 會把程序換成 ANSI 的 `AfxWndProc` | `p!=c`，不切換，維持 run1 行為 |
| CTL3D／`Enable3dControls` | 靜態掃描沒有 | — |
| OLE 控制項站台（`m_pCtrlSite`） | 原 wrapper 走另一條路 | 守門：非 0 就走原路徑（同 v1） |
| IME、協助工具、其他注入 DLL | 可能子類化 | 同樣由 `p==c` 擋下 |

- 切換只是用 W API 重新設定**同一個**系統清單框程序，不在清單框裡跑任何新程式碼。
- 遊戲自己的 ANSI 訊息（沒改寫的 `LB_ADDSTRING` 等）送到已切換的視窗時，Windows 用 CP_ACP 做 A→W，和原本 ANSI 清單框內部的轉換相同，預期沒有行為差異。
- `GetWindowLongW` 對 ANSI 系統控制項回傳的值是否等於 `GetClassLongW`，取決於 Windows 內部實作，Linux 無法驗證。不相等時守門會拒絕切換，效果就是 run1。這是 Win11 驗收要回答的第一個問題。

## 5. 讀回（readback）

- 靜態掃描：推 `LB_GETTEXT` 的 wrapper 呼叫只在 0x46144b（對話框 172，控制項 0x42f）與 0x47fd12、0x4806c0、0x499665、0x499ef0（存檔對話框 152／153）。都不是 8 個優先對話框，這些清單不會被切換。
- 優先對話框的 `readback_on_same_control` 全為 false。
- 已切換的清單框若被 ANSI 讀回，Windows 會 W→A（CP950）。假名變 `?` 和 run1 存進去的內容一樣，不會更差。
- 0x4514d3 的 `LB_FINDSTRINGEXACT` 位元組樣式其實呼叫遊戲函式 0x43f870，判定不是訊息呼叫。CB 系列命中在 MFC 內部（0x4f624e、0x500191、0x4de7d1）。列為殘餘風險。

## 6. 殘餘風險

1. Win11 上 `p==c` 是否成立、切換是否生效：只能實機觀察（假名是否正常）。
2. `%-12s`／`%-16s` 補空白的委託人名稱不會命中 catalog，所以算未命中：模式 2 會觸發切換，模式 0 則整串走 ANSI（與 m045 相同）。
3. 0x4514d3 的樣式（見 §5）。
4. 實際 MSVC 物件的指令形狀：clang 預演曾產生尾呼叫 `jmp eax`，稽核拒絕間接 jmp。MSVC 物件必須另行通過稽核。

## 7. 回退

- 政策字在 `.ld2c`。模式 0／1／2 的合成結果只差那 4 個位元組（測試已驗證三種值都寫得進去）。
- Win11 驗收順序：先跑模式 2。若崩潰、清單異常或卡住，就改用模式 0 的 delta（只換該字）。再不行就回到 run1 或 m045。

## 8. 檔案

| 檔案 | 說明 |
|---|---|
| `native-u/list_core_u.h` | v2 決策核心：`LD2_ListPrepare(..., int* misses)` |
| `native-u/list_bindings_u.h` | 13 個綁定（v1 的 7 個＋`ListMode`＋5 個 USER32） |
| `native-u/list_insert_u.cpp` | v2 入口 `@LD2_ListInsertU@24` |
| `native-u/host_test_u.c` | Linux iconv 主機測試（25／24 項） |
| `native-u/list_mock_test_u.cpp` | 假 API mock，22 個案例（Win11 MSVC 與 Linux i386 都能跑） |
| `audit_list_obj.py` | 新增 `--profile u`（13 個未定義符號、W API 的 callee 清理量、資料綁定不得被 call）。v1 稽核不變 |
| `import_builder.py` | `REVIEWED_APIS` 加 4 個 USER32 W API |
| `synthetic_list_obj.py` | `build('u')` 產生 profile u 的替身 COFF |
| `rehearse_list_obj.py` | 用 clang（`pip install ziglang`）預演物件並以 profile u 稽核；**不可鎖定、不可合併** |
| `test_m061b.py` | 12 個測試（見 §9） |
| `HANDOFF-COMPILE-M061B/` | Win11 編譯包（只編譯＋mock，不開遊戲） |
| 實驗室限定 `merge_plan.py` | `list_profile='u'`、`list_mode`、GetDlgItem／MultiByteToWideChar 的 IAT 名稱核對（不進倉庫，同 v1 慣例） |

## 9. 靜態測試（Linux，2026-10-29）

- `test_m061b.py`：12／12 通過。在實驗室，授權 EXE 的合併／啟用測試也有執行。
  - 審查過的 API 集合完全一致，也沒有危險的 API。
  - profile u 的替身物件通過稽核與重定位（13 個 fixup）；v1 替身的 hash 不變。
  - profile 不能交叉使用；呼叫資料綁定會被拒絕。
  - 主機核心測試：未命中計數正確，包括補空白名稱和拒絕時歸零。
  - i386 mock 用 clang 在 Linux 實際執行 `LD2_ListInsertU`（fastcall 入口、stdcall 假 API）：22 個案例、1116 個斷言，0 失敗。
  - clang 預演物件通過 profile u 稽核：1 個正常回傳、858 個 CFG 狀態，ESP／非揮發暫存器保全。
  - 在記憶體中以 m045 合成惰性版（profile u）：綁定、6 個新匯入（含 v1 的 TextOutW／SendDlgItemMessageW）、模式字 0／1／2 都正確。模式 3、-1、布林、字串都被拒絕；用 v1 的 API 集合也被拒絕。
  - 在記憶體中啟用（hook＋8 清單點）：8 點都指向 v2 入口，helper 內的間接呼叫都只經過審查過的 IAT 槽。不寫任何檔案。
- 既有 `test_m061.py`（19）與 `test_merge_lab.py`（6）照常通過。

## 10. 下一步

1. 使用者在 Win11 執行 `HANDOFF-COMPILE-M061B`（只編譯＋mock，不開遊戲），交回 `list_insert_u.obj`。
2. Linux：`audit_list_obj.py --profile u` 稽核並鎖定 `LIST_U_OBJECT_SHA256`，再合成模式 2（加一份模式 0 備用）的啟用版 delta 與 loader handoff。
3. Win11 可丟棄副本：觀察商店、酒館、委託清單的假名是否正常顯示。
- 另外：m061 啟用版 run1 的 `-Finalize` 還沒跑。它不擋 Linux 工作，但交回下一包證據前請補跑。
