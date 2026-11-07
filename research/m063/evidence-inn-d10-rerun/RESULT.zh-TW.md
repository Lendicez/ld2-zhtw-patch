# 旅館住宿天數框（draft10 `0x168dd4`）重跑＋讀檔框焦點修正 — inn-d10 證據

> 來源：Win11 本機 harness（`zhTW_lab\ld2-autotest`），2026-11-05 Asia/Taipei，由 Claude 接手執行。僅文字；截圖留在本機 `runs\<run-id>\screens\`，EXE／存檔不入庫。`production_can_apply=false`，所有旗標維持 false。

## 綠燈 run
| run-id | steps | 結果 |
|---|---|---|
| `innfix-20261105-003` | `load_inn_tavern_quest.json` | **69/69 通過**，43 秒，`force_killed=false` |
| `inn-d10-20261105-007` | `site_inn_days_d10.json` | **42/42 通過**，36 秒 |

Ld95.exe SHA-256：`240ab04d7f81f185820865549c72b12a0c73475bb1f8dd073146731dab3f4121`（與 innfix-20261105-001 相同）。

## 住宿天數框觀測
- 路徑：讀檔 LUNAS001 → 32840 移動至水鏡都市 → 32831 旅館 → 住宿分頁 → Edit 1047 輸入 `0`、`999`。
- 兩次皆跳出標題「確認」的驗證框；Static 文字（GetWindowTextA，CP932）＝ draft10 `0x168dd4` 模板代入 `%d=1`、`%d=30` 的日文原句。
- **畫面仍為日文**：此進點確實使用 `0x168dd4`，但 candidate 譯文尚未配線（NOT WIRED）。屬「未配線」，不是漏翻。
- 結論：進點對應關係與既有判斷一致；`site_binding_confirmed` 依規則**不改**（需配線後畫面出現繁中才可改）。

## 先前 inn-d10-005／006 失敗的判定
- 失敗點皆在 step 7「未出現讀檔對話框」；步驟檔與 innfix 讀檔段逐步相同。
- 判定為環境因素：當時前景常為 Steam，選單點擊落在 Steam 視窗。

## Harness 修正
- 新增 `foreground_info()`、`minimize_focus_thieves()`：前景為 `steam.exe`／`steamwebhelper.exe` 時將其可見頂層視窗最小化。
- `open_load_dialog` 每輪先檢查前景；非遊戲行程則重新 `focus_attach`；失敗時於 state 記錄 `foreground_at_fail`（程式名），利於日後判讀。
- 本機備份：`ld2_autotest.py.bak-steamfocus-20261105`。

## 下一步
- 探測會跳出「張數」數量框的商店（卡片／卷軸類），以確認或否定 draft46 `0x158f60`。
- 配線（wiring）設計：以 draft10 `0x168dd4` 作為第一個 lab 配線驗證點。
