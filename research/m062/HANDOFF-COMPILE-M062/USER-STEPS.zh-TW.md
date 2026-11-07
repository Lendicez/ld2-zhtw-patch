# m062 v3 編譯包：使用者步驟（Win11，約 5–10 分鐘，不開遊戲）

這一包**只編譯、只跑假測試**：

- 不會開遊戲
- 不會碰遊戲檔或存檔
- 可以和 m061b 驗收包分開做，先後都不影響彼此

下面每一段都可以整段複製、貼進 PowerShell，再按 Enter。

## 0. 準備

1. 把 `m062-v3-compile-handoff.zip` 解壓到 C 槽的 `\GameDev\LD2\zhTW_lab\research\m062\` 資料夾。
   - 資料夾不存在就自己建一個。
   - 解壓後應該會出現 C 槽的 `\GameDev\LD2\zhTW_lab\research\m062\HANDOFF-COMPILE-M062\`。
2. 開 PowerShell：按「開始」，輸入 `PowerShell`，按 Enter。

> 指令裡的 `$env:SystemDrive` 會自動變成 `C:`，照貼即可。

## 1. 進入資料夾、解除封鎖

整段貼上。這段會做兩件事：

- 切換到交接包資料夾。
- 解除 Windows 對下載檔案的封鎖，否則腳本會被擋。

```powershell
cd "$env:SystemDrive\GameDev\LD2\zhTW_lab\research\m062\HANDOFF-COMPILE-M062"
Get-ChildItem -Recurse | Unblock-File
```

## 2. 編譯並跑 mock

整段貼上。這段只在這一次允許執行本機腳本，不會改變系統設定。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-COMPILE-M062.ps1
```

成功時會依序看到：

- `Stage A OK name_pair_v3.obj sha256=…` 和 `Stage A OK list_insert_v3.obj sha256=…`
- `exit=0 last line: cases=29 assertions=1164 failed=0 game_or_user32_called=false`
- `exit=0 last line: {"cases":38,…"failed":0,…"game_or_gdi_called":false}`
- `Return zip: …\Desktop\m062-v3-compile-return.zip`
- 最後是綠字 `HANDOFF-COMPILE-M062 finished OK`

若出現黃字 `note: name mock assertion count differs…`，不算失敗，照常回傳即可。

## 3. 回傳

把**桌面上的 `m062-v3-compile-return.zip`** 傳回來。

- 裡面只有兩個 `.obj`、兩個 `.asm`、`compile-command.json`、`once-result.json`，以及 stdout、stderr 文字檔。
- 沒有 EXE，也沒有遊戲檔。

## 出錯時

- **出現紅字**（例如 `Stage A cl failed`、`mock … did not …`）：
  - 用滑鼠選取整個 PowerShell 視窗的文字，按 Enter 複製，貼給 Mona。
  - 若桌面已經有 `m062-v3-compile-return.zip`，也一起傳回。
  - **不要重試，也不要改任何檔案。**
- **出現 `Set $env:LD2_ZHTW_LAB …`**：代表實驗室不在預設位置。先貼下面這行（把 `E:` 換成實際的磁碟代號），再重做第 2 步：

```powershell
$env:LD2_ZHTW_LAB = Join-Path "E:" "GameDev\LD2\zhTW_lab"
```
