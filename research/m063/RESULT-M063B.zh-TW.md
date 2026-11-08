# m063b 結果：Win11 MSVC 編譯三個 v4 helper（compile-only）＋ Linux 稽核與 pin

日期：2026-10-31（台北）。分支 `research/m062-catalog-capacity`（PR #26，Draft，不合併）。
`production_can_apply=false`、`release_approved=false`、`game_touched=false`。沒有 loader 套用、沒有寫出 EXE。

## 執行經過（Win11，使用者經 Rona 同意，`HANDOFF-COMPILE-M063B/`）
| 輪次 | 結果 | 修正 |
|---|---|---|
| 1 | Stage A `name_textout_v4.h` C4819（CP950 下註解「戟斧」）→ `/WX` 失敗 | Stage A 加 `/utf-8`（`7206c2c`） |
| 2 | Stage A 三個 OK；Stage B textout mock C4996 `strcpy` | mock 改寫＋`_CRT_SECURE_NO_WARNINGS`（`06279e7`） |
| 3 | Stage B C4005 巨集重複定義（命令列已定義） | 拿掉檔內 `#define`（`901a438`） |
| 4 | **全部通過**，回傳 `m063b-v4-compile-return.zip`（sha256 `c1534129…9727`） | — |

修正只動交接包的旗標與 mock；三個 helper 的 `.cpp/.h` 核心邏輯沒有改。

## Stage A：compile-only（`cl /c /W4 /WX /utf-8 /O2 /Oi /Oy- /GS /Gy /Zl /EHs`，SDK 10.0.26100.0，不連結）
| 物件 | 位元組 | sha256 | 公開入口 |
|---|---|---|---|
| `name_pair_v4.obj` | 7006 | `bf33cfc674f28fd6f8bb069d76176f45d1309a8ab3198f068fc31c3ed87792e6` | `_LD2_NamePair@16` |
| `list_insert_v4.obj` | 9629 | `cb74d585c9936f41debc831c863e1eb91dd652770ba4911660e16dd4e3c72b35` | `@LD2_ListInsertV4@24`、`@LD2_ListInsertNameV4@24` |
| `name_textout_v4.obj` | 6631 | `76d0adb7cecc82e54c1e0543a2d5f8b932f3b2d9f82a255ac6941390385cc0f6` | `@LD2_NameTextOut@24` |

## Stage B：mock 連結＋執行一次（Stage A 物件，不碰遊戲）
| mock | cases | assertions | failed | 其他 |
|---|---|---|---|---|
| list-mock-v4 | 54 | 2301 | 0 | `game_or_user32_called=false` |
| textout-mock-v4 | 36 | 13431 | 0 | `catalog_version=4`、`game_or_gdi_called=false`（Linux zig 為 12398；MSVC 端斷言數不同屬預期，失敗數為 0） |
| name-mock-v4 | 45 | 25959 | 0 | `catalog_version=4`、`game_or_gdi_called=false`、旗標 0 |

三個 exit code 皆 0。mock EXE 不在回傳包、也不進 repo。

## Linux 稽核（`rehearse_v4_objs.py --list-obj/--textout-obj/--name-obj`）：通過
- `list_insert_v4`：兩入口都走完整 CFG，各 19 個正常返回、1485 個 CFG 狀態、`ret 16`、無 cookie noreturn 尾巴、ESP 與非揮發暫存器在正常路徑保留；undefined 13 個與 v3 清單相同；內部呼叫只有 `LD2C4_*`／`ld2c4_*`／`ld2_make_unicode`。
- `name_textout_v4`：`audit_name_textout` 完整 CFG 通過；公開 3、undefined 6 與 m063a 相同。
- `name_pair_v4`：`audit_name_pair_v3` 完整 CFG 通過（與 m062 v3 物件同一套規則）；公開 6、undefined 6。
- 三個物件的 undefined／public 集合也與 `merge_plan_v4.SHAPES` 完全相符。
- 完整輸出：`compile-v4-run1/audit.json`。

## Lab 記憶體內建置（lab 鏡像，m051 264 列 catalog；不寫檔）
`merge_plan_v4.build_inert_v4`（不給 rehearsal pin，用鎖定的 MSVC pin）→ `rehearsal=false`、`handoff_eligible=true`；
`.ld2t` `0xae3000–0xae5b40`、code sha256 `0520c1b4…954c`、blob `d8214a95…1de2`；
`enable_plan_v4.apply_enabled_v4` → pair5 25、tail8 1、清單 18（item 7／name 11），`file_written=false`、`production_can_apply=false`。
`test_native_v4.LabBuildV4.test_build_msvc_pinned` 在設定 `LD2_M063B_RETURN` 指向本機物件時重跑此流程（物件不在時 skip）。

## Pin
`rehearse_v4_objs.py`、`merge_plan_v4.py` 的 `NAME/LIST/TEXTOUT_V4_OBJECT_SHA256` 由 `None` 改為上表三值；`test_native_v4.py` 同步斷言。`enable_plan_v4.py` 沒有物件 pin（只吃 inert 影像），不需改。

## 物件存放
`.obj`／`.asm` 是二進位／大檔，依 `UPLOAD_ALLOWLIST.json` 與 `tools/audit_upload.py` 規則**不進 repo**（比照 m062 `compile-v3-run1/`）。repo 只收 `compile-v4-run1/` 的 `audit.json`、`compile-command.json`、`once-result.json`、`stdout.txt`；物件留在 Linux 工作機本地。

## 下一步（仍不套用到正式版）
- `production_can_apply` 仍為 false；沒有 loader 套用、沒有產出可執行檔。
- 若要往前：把 v4 inert＋enabled 影像打包成 Win11 lab 驗收交接（類似 m062 之後的啟用驗收），**需使用者另外同意**後才做；實機觀察項見 `STATUS.zh-TW.md`。
