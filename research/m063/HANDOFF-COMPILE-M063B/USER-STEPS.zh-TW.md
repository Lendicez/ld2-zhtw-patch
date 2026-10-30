# m063b v4 編譯包：使用者步驟（Win11，約 5–10 分鐘，不開遊戲）

這一包**只編譯、只跑假測試**：

- 不會開遊戲
- 不會碰遊戲檔或存檔
- 做法和 m062 那包幾乎一樣，只是這次一次編三個檔案

下面每一段灰底框都可以整段複製、貼進 PowerShell，再按 Enter。每段上面有一句說明它在做什麼。

## 0. 準備

1. 把 `m063b-v4-compile-handoff.zip` 解壓到 C 槽的 `\GameDev\LD2\zhTW_lab\research\m063\` 資料夾。
   - 資料夾不存在也沒關係，下面第 1 步會自動建好；也可以先做第 1 步再解壓。
   - 解壓後應該會出現 C 槽的 `\GameDev\LD2\zhTW_lab\research\m063\HANDOFF-COMPILE-M063B\`，裡面有 `WINDOWS-COMPILE-M063B.ps1` 和 `native` 資料夾。
2. 開 PowerShell：按「開始」，輸入 `PowerShell`，按 Enter。

> 指令裡的 `$env:SystemDrive` 會自動變成 `C:`，照貼即可。

## 1.（可選）用指令解壓

如果 zip 在「下載」資料夾，可以直接貼這段代替手動解壓。

- 第一行：建立目標資料夾（已存在也不會出錯）。
- 第二行：把下載資料夾裡的 zip 解壓到那裡（`-Force` 代表覆蓋舊檔）。

```powershell
New-Item -ItemType Directory -Force -Path "$env:SystemDrive\GameDev\LD2\zhTW_lab\research\m063" | Out-Null
Expand-Archive -Path "$env:USERPROFILE\Downloads\m063b-v4-compile-handoff.zip" -DestinationPath "$env:SystemDrive\GameDev\LD2\zhTW_lab\research\m063" -Force
```

## 2. 進入資料夾、解除封鎖

整段貼上。這段會做兩件事：

- 第一行：切換到交接包資料夾。
- 第二行：解除 Windows 對下載檔案的封鎖，否則腳本會被擋。

```powershell
cd "$env:SystemDrive\GameDev\LD2\zhTW_lab\research\m063\HANDOFF-COMPILE-M063B"
Get-ChildItem -Recurse | Unblock-File
```

## 3. 編譯並跑 mock

整段貼上。這行只在這一次允許執行這個腳本，不會改變系統設定。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-COMPILE-M063B.ps1
```

成功時會依序看到：

- `Stage A OK name_pair_v4.obj sha256=…`、`Stage A OK list_insert_v4.obj sha256=…`、`Stage A OK name_textout_v4.obj sha256=…`
- `exit=0 last line: cases=54 assertions=2301 failed=0 game_or_user32_called=false`
- `exit=0 last line: {"cases":36,…"failed":0,…"game_or_gdi_called":false}`
- `exit=0 last line: {"cases":45,…"failed":0,…"game_or_gdi_called":false}`
- `Return zip: …\Desktop\m063b-v4-compile-return.zip`
- 最後是綠字 `HANDOFF-COMPILE-M063B finished OK`

若出現黃字 `note: … assertion count differs…`，不算失敗，照常回傳即可。

## 4. 回傳

把**桌面上的 `m063b-v4-compile-return.zip`** 傳回來。

- 裡面只有三個 `.obj`、三個 `.asm`、`compile-command.json`、`once-result.json`，以及三組 stdout、stderr 文字檔。
- 沒有 EXE，也沒有遊戲檔。

想先確認 zip 裡有什麼，可以貼這行（只列出檔名，不會改任何東西）：

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem; [IO.Compression.ZipFile]::OpenRead("$([Environment]::GetFolderPath('Desktop'))\m063b-v4-compile-return.zip").Entries | Select-Object FullName, Length
```

## 出錯時

- **出現紅字**（例如 `Stage A cl failed`、`mock … did not …`）：
  - 用滑鼠選取整個 PowerShell 視窗的文字，按 Enter 複製，貼回來。
  - 若桌面已經有 `m063b-v4-compile-return.zip`，也一起傳回。
  - **不要重試，也不要改任何檔案。**
- **出現 `Set $env:LD2_ZHTW_LAB …`**：代表實驗室不在預設位置。先貼下面這行（把 `E:` 換成實際的磁碟代號），再重做第 3 步：

```powershell
$env:LD2_ZHTW_LAB = Join-Path "E:" "GameDev\LD2\zhTW_lab"
```

- **出現「無法辨識 Expand-Archive 的路徑」**：代表 zip 不在「下載」資料夾，改用滑鼠手動解壓（第 0 步）即可。
