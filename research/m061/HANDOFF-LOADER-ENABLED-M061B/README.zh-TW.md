# m061b HANDOFF-LOADER-ENABLED-M061B：清單 Unicode 版驗收（Win11，可丟棄副本，一次）

**尚未在 Win11 執行。** `production_can_apply=false`、`release_approved=false`，本包不改變這兩個值。

## 和 m061 啟用版 run1 的差別

run1（`57103342…ce5b`）在 Win11 穩定執行（結束碼 1、無崩潰），但清單裡的假名都變成 `?`：清單框是 ANSI 視窗，W 訊息被 Windows 轉回 CP950。m061b 只換掉清單 helper：

| 項目 | run1 | m061b |
|---|---|---|
| 清單 helper | `@LD2_ListInsert@24`（`d5349e58…61e0`） | `@LD2_ListInsertU@24`（MSVC 物件 **`e8144466…4d51`**，4,038 B） |
| 新匯入 | TextOutW、SendDlgItemMessageW | 再加 IsWindowUnicode、GetWindowLongW、GetClassLongW、SetWindowLongW（USER32） |
| `.ld2c` | … [OriginalDlgItem] | … [OriginalDlgItem] **[ListMode]**（VA 0xb0a28c） |
| TextOutW hook 區段／8 個清單點位置 | 同 | 同（清單點新目標 0xae3850） |

清單模式（詳見 `M061B-DESIGN.zh-TW.md`）：

- **模式 2（預設）**：遇到 catalog 沒命中的名稱時，若清單框沒被子類化（`GetWindowLongW == GetClassLongW`），就用 `SetWindowLongW` 把同一個系統清單程序重新以 W 註冊，讓清單框變成 Unicode 視窗，假名才不會掉。切不過去時效果與 run1 相同。
- **模式 0（保底，加 `-Mode0`）**：只有每個非 ASCII 欄位都命中 catalog 時才走 W；其他情況整串交回原本 ANSI 路徑，等同 m045。

| | 模式 2（預設） | 模式 0（`-Mode0`） |
|---|---|---|
| 惰性合併 sha256 | `6f9a8903…e1aa` | `287472cc…6c99` |
| **啟用版 sha256** | **`3a1b75b35aca01a8b3e0e475ea8fd7454ebe2367f03165ebab18a7054825ed31`** | `49b623950708612c16b8b2a9f234ce499094104514820c84b7fb5c3d44d0d876` |
| PE CheckSum | 0x6F8780 | 0x6F877E |
| delta bin sha256 | `5853948c…91cd` | `4bbfc190…1331` |

兩者大小都是 7,286,784 B，SizeOfImage 0x70C000，只差模式字（4 B）與 CheckSum。

## Linux 端已做

1. **物件稽核**（`audit_list_obj.py --profile u --expect-sha256 e8144466…`）：通過。
   - 未定義符號剛好 13 個（v1 的 7 個＋ListMode＋5 個 USER32 綁定），沒有 CRT／heap／EH／chkstk。
   - 唯一公開符號 `@LD2_ListInsertU@24`；正常路徑皆 `ret 16`，654 個 CFG 狀態，ESP 與非揮發暫存器保全。
   - 每個外部呼叫的 callee 清理量都對（W API stdcall、OriginalDlgItem ret 16、cookie 檢查 fastcall）。
2. **Win11 mock**（使用者回傳）：`cases=22 assertions=1116 failed=0`，沒碰遊戲、沒呼叫真的 USER32。
3. **記憶體內合併＋啟用**（`build_enabled_u_lab.py`，模式 0／1／2 都跑）：
   - hook stub 反組譯與 run1 相同（`67f30b3e…`）；沒有任何分支落進 hook 區段內部。
   - 8 個清單點舊目標都是 0x4ea671，新目標都是 0xae3850。
   - helper 內所有間接呼叫只經過 8 個審查過的槽：MultiByteToWideChar 0x52537c、GetDlgItem 0x525498、OriginalDlgItem 0xb0a288、SendDlgItemMessageW／IsWindowUnicode／GetWindowLongW／GetClassLongW／SetWindowLongW 0xb0b1e8..0xb0b1f8。唯一一個 `call eax` 的值來自 OriginalDlgItem 槽（=0x4ea671）。
   - 沒有新增 SetWindowLongA、CallWindowProc*、SetWindowsHookEx*、VirtualProtect、LoadLibrary*、GetProcAddress、SetClassLong*。
   - pefile：checksum 正確、7 個段、15 個匯入描述子、EntryPoint 不變；相對惰性版只差 65 bytes。
4. **PowerShell 重建**：在 Linux 用 pwsh 跑腳本裡的 `Assert-Delta`／`Build-Enabled`，模式 2 與模式 0 都得到上表的 sha256。
5. 測試：`test_m061b.py` 13／13（新增真實物件稽核）、`test_m061.py` 19／19、`test_merge_lab.py` 6／6。

## Win11 要回答的問題

1. 清單假名是否正常顯示（`p==c` 是否成立、切換是否生效）。
2. 切換後清單操作（選取、買賣、排序）是否正常，有沒有錯誤框或崩潰。
3. 若模式 2 有任何異常：只跑 G 收尾，回報；之後再用 `-Mode0` 跑一個新的副本。

## 判定

- **通過**：能讀檔；每個清單和說明視窗都能打開且不崩潰；結束碼 0 或 1，沒有 Ld95 錯誤／WER 事件，沒有新 dump；原安裝沒變動。
- **顯示另外記錄**：假名是否正常（不再是 `?`）、命中 catalog 的名稱是否為繁中。
- **失敗**：錯誤框、崩潰、無回應、清單空白、選取後行為錯誤。只截圖並執行 G，不重試。

## 檔案

| 檔案 | 用途 |
|---|---|
| `WINDOWS-LOADER-ENABLED-M061B.ps1` | `-DisposableRoot` 必填。P（建副本）→ L（啟動一次）→ G（收尾）；`-Mode0` 換保底版 |
| `m061b-enabled-mode2.delta.*`／`mode0.delta.*` | m045 到啟用版的差異。bin 含 catalog 與 helper 位元組，只放在 zip 裡，不進倉庫 |
| `enabled_static_verify.summary.json` | Linux 靜態驗證摘要（只有 hash、位址、我們自己的 stub 反組譯） |
| `USER-STEPS.zh-TW.md` | 給使用者的完整指令 |
| `observations.template.md` | 必填的觀察紀錄 |
