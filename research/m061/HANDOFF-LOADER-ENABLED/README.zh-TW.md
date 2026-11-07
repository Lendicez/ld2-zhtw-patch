# m061 HANDOFF-LOADER-ENABLED：啟用版功能驗收（Win11，可丟棄副本，一次）

**尚未在 Win11 執行。** `production_can_apply=false`、`release_approved=false`，本包不改變這兩個值。

## 和惰性版的差別

惰性版（`6a43dc4e…1cfe`）已於 2026-10-29 在 Win11 通過：進到標題畫面，結束碼 1（從選單結束），沒有任何事件、WER 或 dump。
啟用版用同一個 m045 基底和同樣三個新段，只多改下面三處：

1. **TextOutW hook**：把檔案位移 0x6dc7d..0x6dca5 這 40 bytes 換成下面的 stub，負責道具說明視窗的名稱那一行：
   ```
   push dword [esp+0x18]   ; stored_id = [F+0x18]
   push esi                ; byte_count
   push dword [esp+0x1c]   ; ansi = [F+0x14]（名稱 CString）
   push ebp                ; CDC*
   call 0xae3170           ; _LD2_NamePair@16（stdcall，ret 0x10）
   jmp  0x46dca5           ; 回到原續接點
   int3 ×20
   ```
   原本是兩次 thiscall 的 ANSI 繪字，每次 4 個參數、ret 0x10。換成 stub 後，ESP 在續接點同樣等於 F，非揮發暫存器也不變。helper 遇到不認得的 vtable 或 catalog 沒有命中時，會改走原本兩次 ANSI 呼叫。
2. **8 個清單點**：把 `call 0x4ea671`（CWnd::SendDlgItemMessage）改成 `call 0xae3790`（`@LD2_ListInsert@24`）。長度同樣是 5 bytes，而且 fastcall 加上不用的 EDX，效果和原本的 thiscall（ret 0x10）一樣。涵蓋商店的購買（兩處）、出售、強化，旅館委託，酒館，委託一覽，委託資訊。
3. PE CheckSum 重算為 `0x700B22`。

除此之外沒有任何位元組改動（相對惰性版共 66 bytes 不同）。輸出 sha256 是 **`57103342f130da2ab51bf70e94d4dfb6c63245c3b375154bb4fbe27906b7ce5b`**，大小 7,286,784 B，SizeOfImage 0x70C000。

## Linux 靜態驗證（`enabled_static_verify.summary.json`）

- 用 capstone 反組譯 stub，確認順序和 call／jmp 目標都正確。
- 掃描整個 `.text` 的 rel32 call／jmp／jcc、原函式 347 條指令的短跳，以及全檔的絕對 DWORD，沒有任何目標落在 hook 區段內部（0 筆）。
- 8 個清單點：視窗 hash 符合，舊目標都是 0x4ea671，新目標都是 0xae3790。
- pefile 檢查：checksum 正確、7 個段、15 個匯入描述子、EntryPoint 沒變。
- OriginalDlgItem 槽的值是 0x4ea671，ExpectedTextOutA 的值是 0x4e13d7。
- 腳本**只允許**改寫既有段裡這 9 個位置（hook 區段 40 B，加上 8 個 rel32，每個 4 B）。其他任何位置都會被拒絕，這點已在 Linux 用竄改測試確認。

## 載入檢查（修正惰性版的 `module_probe`）

惰性版用 `MainModule` 讀模組大小，結果讀到 null。這次改成以只讀權限（`PROCESS_QUERY_LIMITED_INFORMATION|PROCESS_VM_READ`）直接用 ReadProcessMemory 讀 0x400000，確認三件事：

- SizeOfImage 等於 0x70C000；
- `TextOutW`／`SendDlgItemMessageW` 的 IAT 已綁定，值不再是檔案裡的 hint RVA；
- 記憶體裡 9 個改寫點和 delta 的 hash 一致。

如果讀取失敗，會記下 Win32 錯誤碼（5 代表存取被拒，可能是遊戲以系統管理員身分或在相容性模式下執行）。這項檢查不影響判定。

## 存檔

副本不會拿原安裝的 `Usr\`。腳本預設從 m060 的可丟棄副本 `<LD2_ROOT>\zhTW_lab\game-acceptance\m060\game\Usr\` 複製 `LUNAS*.LDP`，並記錄每個檔的 sha256；也可以用 `-SeedUsrFrom` 指定其他資料夾。指向原安裝會被拒絕。

## 判定

- **通過**：
  - 能讀檔；
  - 每個清單和說明視窗都能打開，而且不會崩潰；
  - 結束碼 0 或 1，沒有 Ld95 錯誤／WER 事件，也沒有新的 dump；
  - 原安裝沒有變動。
- **顯示結果另外記錄，不算崩潰判定**：清單裡的道具、冒險者、委託名稱是繁中（catalog 命中）或正確日文（沒命中，不再出現 `?`）；說明視窗的名稱是繁中。
- **失敗**：錯誤框、崩潰、無回應、清單空白，或程式在某個清單畫面直接結束。這時只截圖並執行 G，不要重試。

## 檔案

| 檔案 | 用途 |
|---|---|
| `WINDOWS-LOADER-ENABLED.ps1` | `-DisposableRoot` 必填。步驟：P（建副本、寫啟用版、複製 m060 存檔）→ L（啟動一次）→ G（收尾） |
| `m061-enabled.delta.bin`／`.json` | m045 到啟用版的差異。bin 含 catalog 資料，只放在 zip 裡，不進倉庫 |
| `USER-STEPS.zh-TW.md` | 操作清單 |
| `observations.template.md` | 必填的觀察紀錄 |
