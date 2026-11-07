# m061b HANDOFF-COMPILE-M061B：清單 helper v2（Unicode 視窗切換）編譯＋mock（不上遊戲）

最後更新：2026-10-29 04:00（台北）。`production_can_apply=false`。本包**不會**啟動遊戲、**不會**寫入任何遊戲 EXE、**不會**套用補丁。設計見 `research/m061/M061B-DESIGN.zh-TW.md`。

## 為什麼要重新編譯

m061 啟用版 run1 證實：helper 送出的 UTF-16 被 ANSI 清單框轉成 CP950，假名變 `?`。v2 helper（`list_insert_u.cpp`）多了：

- 一個 `.ld2c` 政策字 `LD2_ListMode`（0＝只在 catalog 全命中時走 W；1＝run1 行為；2＝預設，未命中時先把該清單框切成 Unicode 視窗）
- 4 個新的 USER32 匯入（`IsWindowUnicode`、`GetWindowLongW`、`GetClassLongW`、`SetWindowLongW`）＋沿用遊戲既有的 `GetDlgItem` IAT

原始碼與綁定都變了，所以 v1 的 `d5349e58…61e0` 物件不能沿用，必須用同一套 MSVC 14.44 旗標重新產出 Stage A 物件，交回 Linux 稽核並鎖定 hash。

## 內容

| 檔案 | 用途 |
|---|---|
| `WINDOWS-COMPILE.ps1` | Stage A（`cl /c`，不連結）＋ Stage B（mock 連結並執行一次） |
| `native/list_insert_u.cpp` | v2 helper，入口 `@LD2_ListInsertU@24` |
| `native/list_core_u.h` | 可攜決策核心（回報 catalog 未命中數） |
| `native/list_bindings_u.h` | 綁定契約（13 個未定義符號） |
| `native/list_mock_test_u.cpp` | 假 API mock（22 個案例） |

## 使用

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd <解壓目錄>\HANDOFF-COMPILE-M061B
.\WINDOWS-COMPILE.ps1
```

預期：

| 路徑 | 內容 |
|---|---|
| `<LD2_ROOT>\zhTW_lab\runs\m061b\compile-only\list_insert_u.obj` | Stage A 物件（交回 Linux） |
| `...\compile-only\list_insert_u.asm`、`compile-command.json` | 組語列表、旗標與 sha256 |
| `...\mock\list-mock-u.once.exe` | Stage B 診斷 EXE（**不要**上傳） |
| `...\mock\stdout.txt`、`once-result.json` | 執行結果 |

stdout 最後一行必須是 `cases=22 assertions=1116 failed=0 game_or_user32_called=false`，否則腳本會 throw。

## Linux 端後續

```text
python3 -I -B research/m061/audit_list_obj.py --profile u path/to/list_insert_u.obj --json-out runs/m061b/list_insert_u.audit.json
```

稽核鎖定：

- 未定義符號恰好 13 個：v1 的 7 個，加上 `_LD2_ListMode`、`_LD2_GetDlgItem`、`_LD2_IsWindowUnicode`、`_LD2_GetWindowLongW`、`_LD2_GetClassLongW`、`_LD2_SetWindowLongW`
- 資料綁定（EntryCount／Entries／ListMode／cookie）不得被 call
- 唯一公開入口 `@LD2_ListInsertU@24`，所有正常路徑 `ret 16`，ESP 與非揮發暫存器保全
- 禁止 CRT／EH／memcpy／chkstk／DEFAULTLIB、FS 段、間接 jmp

通過後才把 sha256 寫進 `merge_plan.LIST_U_OBJECT_SHA256`，再合成新的啟用版 delta。那是下一份 handoff，**不在本包**。

## 已知可能的編譯差異

Linux 用 clang 預演時，最佳化器會把回退呼叫改成尾呼叫（`jmp eax`），稽核會拒絕。預演用 `-fno-optimize-sibling-calls` 避開。MSVC v1 物件沒有這個情形。如果 v2 物件出現 `indirect jump`，回報給 Linux 端調整原始碼，不要自行改旗標。

## 明確不做

- 不開遊戲、不寫 `Ld95.exe`、不做 loader 驗收、不改清單呼叫點、不設 `production_can_apply`
