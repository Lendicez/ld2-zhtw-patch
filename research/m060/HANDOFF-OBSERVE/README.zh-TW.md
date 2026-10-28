# m060 可丟棄副本單次觀察：Win11 交接包

使用者已於 **2026-10-28 批准一次**。這只是觀察，**不是**安裝；`production_can_apply=false`、`release_approved=false` 不變。權威計畫：`..\OBSERVATION-PLAN.zh-TW.md`。逐步清單：[USER-STEPS.zh-TW.md](USER-STEPS.zh-TW.md)。

## 前提
- 電腦上已有 `<LD2_ROOT>\`（含 `LunaticDawnPotB\` 遊戲資料夾、`zhTW_lab\`、`ld2-zhtw-patch-m051\`）。
- 遊戲沒在執行；本輪不讓 Steam「驗證完整性」或更新。
- 不關 Defender、不加排除、不改 ACL／地區設定。被封鎖就停止並截圖。

## 解壓位置
把 zip 解壓到 `<LD2_ROOT>\zhTW_lab\research\m060\`（會產生 `HANDOFF-OBSERVE\` 資料夾）。

## 腳本做什麼
`WINDOWS-ONCE.ps1` 只會寫入 `<LD2_ROOT>\zhTW_lab\game-acceptance\m060\`（已存在就拒絕）：
- `game\`：用 `robocopy /E /XD Usr LUNAS /XJ` 從遊戲資料夾**只讀複製**，私人存檔不複製，另建空的 `Usr\`。
- `exe-store\`：原版與 m045 EXE；切換版本時複製到 `game\Ld95.exe`（檔名不變）。
- `evidence\`：`hashes-before.json`、`launch-B/C/F.json`、`hashes-after.json`、`screens\`、`observations.md`。

會檢查：來源 `Ld95.exe` 在複製前後都是 `6c817a09…d5d2`；m045 是 `4a091024…9da7`（7,118,848 bytes）。腳本會在 `zhTW_lab\runs\m045\build-first\` 等位置找 m045；**找不到就停止**，並印出離線生成指令（`tools\build_patch.py --profile m045`），生成好再重跑。

遊戲來源不是 `<LD2_ROOT>\LunaticDawnPotB` 的話，加上 `-SourceDir "<路徑>"`。來源只讀；用 Steam 安裝目錄也一樣，絕不寫入。

## 執行（每個指令只跑一次）
```powershell
cd <LD2_ROOT>\zhTW_lab\research\m060\HANDOFF-OBSERVE
Unblock-File .\WINDOWS-ONCE.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -CheckOnly   # 只檢查，不寫
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1              # A
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -LaunchStep B
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -LaunchStep C  # C+D+E 一次
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -LaunchStep F
powershell -NoProfile -ExecutionPolicy Bypass -File .\WINDOWS-ONCE.ps1 -Finalize     # G
```
`-ExecutionPolicy Bypass` 只套用到這一個 PowerShell 程序，不改系統設定。遊戲只在帶 `-LaunchStep` 時才會啟動，腳本會等你關掉遊戲後記錄結束碼。

## 回傳證據
把 `game-acceptance\m060\evidence\` 裡的**全部內容**複製到 **`<LD2_ROOT>\zhTW_lab\runs\m060-observe\`**，壓成 `m060-observe-evidence.zip` 回傳。
**不要**放入：任何 EXE、遊戲素材（RES／music／avi）、私人存檔、crash dump 本體。
