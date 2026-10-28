# m061 HANDOFF-COMPILE：清單 shim 編譯＋mock（不上遊戲）

最後更新：2026-10-29。`production_can_apply=false`。本包**不會**啟動遊戲、**不會**寫入任何遊戲 EXE、**不會**套用正式補丁。

## 目的

在 Win11 上完成兩件 Linux 無法做的事：

1. **Stage A（compile-only）**：用與 m058 相同的旗標編譯 `list_insert_w.cpp`，產出 `list_insert_w.obj`（不連結）。
2. **Stage B（mock）**：編譯 `list_mock_test.cpp`，與 Stage A 物件連結成控制台 EXE，執行一次。假 API 記錄每一次呼叫；不載入 USER32／GDI 真身，不開遊戲。

完成後把 Stage A 的 `.obj`（與 `compile-command.json`）交回 Linux，跑 `audit_list_obj.py` 鎖定 hash 與 ABI。

## 前置

- 本機已有 m059／m058 用過的 MSVC 工具鏈：`<LD2_ROOT>\zhTW_lab\toolchains\msvc2022\...`
- Windows 10/11 SDK（um\x86、ucrt\x86、rc.exe）；腳本會找 `10.0.26100.0` 或較新版本
- 可選：設定環境變數 `LD2_ZHTW_LAB` 指向實驗室根目錄；否則腳本會從本包相對路徑尋找 `toolchains\msvc2022`；找不到就要求設定 `LD2_ZHTW_LAB`

## 使用

1. 解壓本 zip 到任意工作目錄（建議不要解到遊戲目錄裡）。
2. PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd <解壓目錄>\HANDOFF-COMPILE
.\WINDOWS-COMPILE.ps1
```

3. 預期產物：

| 路徑 | 內容 |
|---|---|
| `<LD2_ROOT>\zhTW_lab\runs\m061\compile-only\list_insert_w.obj` | Stage A 物件（交回 Linux） |
| `...\compile-only\list_insert_w.asm` | 組語列表 |
| `...\compile-only\compile-command.json` | 旗標與 sha256 |
| `...\mock\list-mock.once.exe` | Stage B 診斷 EXE（**不要**上傳到 Git） |
| `...\mock\stdout.txt` / `once-result.json` | 執行結果 |

4. stdout 應類似：`cases=10 assertions=… failed=0 game_or_user32_called=false`，結束碼 0。

5. 把 `list_insert_w.obj` + `compile-command.json`（可加 asm）打成 zip 交回 Mona／Linux。**不要**交 mock EXE、截圖、存檔或遊戲二進位。

## Linux 端後續（自動）

```text
python3 -I -B research/m061/audit_list_obj.py path/to/list_insert_w.obj --json-out runs/m061/list_insert_w.audit.json
```

稽核會鎖定：

- 未定義符號恰好 7 個：`_LD2_EntryCount`、`_LD2_Entries`、`_LD2_OriginalDlgItem`、`_LD2_SendDlgItemMessageW`、`_LD2_MultiByteToWideChar`、`___security_cookie`、`@__security_check_cookie@4`
- 拒絕任何 memcpy／memset／chkstk／EH／CRT 符號與 DEFAULTLIB
- 公開入口只有 `_LD2_ListInsert@24`，正常路徑 `ret 16`，ESP／非揮發暫存器保全

通過後把物件 sha256 寫進 `merge_plan.py` 的 pin，取代目前的 synthetic stand-in。

## 明確不做

- 不開遊戲、不寫入 `Ld95.exe`、不做 loader 驗收、不改清單 call site、不設 `production_can_apply`
- loader／可丟棄副本驗收是下一份（需另授權）的 HANDOFF，不在本包
