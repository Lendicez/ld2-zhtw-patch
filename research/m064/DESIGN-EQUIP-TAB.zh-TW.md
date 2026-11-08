# m064 設計：屬性表分頁標題（角色名）繁中化

> 2026-11-05。lab 設計，尚未實作。`production_can_apply=false`。

## 現象
裝備視窗（32812）等屬性表的分頁標籤是角色名，畫面為亂碼（如「濯毆楳晴」）。分頁經 `PropertySheetA` 以 ANSI 顯示；
名字是 CP932 原文，沒有經過 m063 v4 的人名查表。

## 來源（pristine Ld95.exe 反組譯）
遊戲自己設定每頁標題，6 個屬性表用同一段樣式（MFC `CPropertyPage::m_psp` 由 `0x4ef7f3` 取得）：

```
call 0x4ef7f3          ; eax = &page->m_psp
mov  [eax+0x14], edi   ; psp.pszTitle = edi（角色名，CP932）
call 0x4ef7f3
or   dword [eax+4], 8  ; psp.dwFlags |= PSP_USETITLE
```

| 位置（`or [eax+4],8`） | 推測用途 |
|---|---|
| `0x46c81e` | 裝備（與裝備下拉 0x46c46c 同函式群） |
| `0x4705fe` | 物品／交換類 |
| `0x47c2fe` | item-page |
| `0x481dfe` | item-page-b |
| `0x49674e` | 其他人物屬性表 |
| `0x4b703e` | 其他人物屬性表 |

另有 MFC 函式庫本身 `0x4f0d73`（`m_strCaption` → pszTitle），遊戲這 6 處不經過它。

## 改法（最小）
每處把 `call 0x4ef7f3; mov [eax+0x14], edi`（5＋3＝8 bytes）換成 `call stub_title; nop×3`。
`stub_title`（放 `.ld2t` 剩餘空間，約 0x4c0 bytes；暫存放 `.ld2i` 可寫區）：

```
stub_title:
    call 0x4ef7f3                 ; 原呼叫，eax = &psp
    push eax                      ; 保存 psp
    ; n = strlen(edi)（上限 64）
    ; units = LD2N_FindCopy(edi, n, wbuf)          ; v4 人名查表（stdcall，回傳 UTF-16 長度；0 = 查無）
    ; if units == 0: title = edi（原文；不變）
    ; else: k = WideCharToMultiByte(950, 0, wbuf, units, abuf[slot], 64, NULL, NULL); abuf[slot][k] = 0; title = abuf[slot]
    pop  eax
    mov  [eax+0x14], title        ; 與原指令相同效果
    ret
```

- `abuf` 需在 `PropertySheetA` 呼叫前保持有效 → 用 8 格輪替靜態緩衝（每格 65 bytes），一個屬性表最多 8 位隊員。
- 保存／還原 ecx、edx、esi、edi、ebx（只動 eax 為原語意）；stub 內呼叫皆 stdcall。
- `LD2N_FindCopy` 位址：由 `.ld2t` 的 NameTextOut 物件符號表（m063b pin 物件 + merge plan 位置）取得；或在啟用版 EXE 以其函式序言比對找出。
- `WideCharToMultiByte`：若 KERNEL32 匯入表沒有，改用 v4 helper 已綁定的 API 指標（helper 已用 MultiByteToWideChar），或在 `.ld2i` 補一個 IAT 槽（需調整匯入表 → 成本高，優先找既有指標）。
- Big5 顯示：分頁用對話框字型，系統 ACP 950 → `PropertySheetA` 的 ANSI 標題以 950 轉 Unicode，Big5 正確。

## 驗證
1. 合成測試：Python 模型驗 stub 位元組（或在 Linux 以 unicorn／自寫最小 x86 模擬執行 stub＋假 FindCopy）。
2. lab：`char_windows` 裝備視窗 dump 的 SysTabControl32 項目文字（TCM_GETITEM）＝繁中角色名；回歸全套。
3. 失敗即退回原文（units==0 路徑），不影響其他視窗。

## 風險
- 6 處若有一處的暫存器用法不同（edi 非名字）→ 逐處反組譯核對前後 0x20 bytes 一致才改。
- `.ld2t` 剩餘空間與對齊；stub 不可跨越區段尾。
- Kris 類同 bytes 人名／道具：FindCopy 走 NAME_ONLY 人名旗標，不會取到道具名。
