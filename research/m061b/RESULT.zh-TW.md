# m061b 結果：清單框 Unicode 切換（模式 2）啟用版驗收

日期：2026-10-29（Asia/Taipei）。`production_can_apply=false`、`release_approved=false` 不變。
設計見 `../m061/M061B-DESIGN.zh-TW.md`；編譯與合成見 `../m061/RESULT.zh-TW.md`（m061b 各節）。

## 總結：**通過**（清單假名顯示＋穩定性）

模式 2 啟用版在 Win11 可丟棄副本操作約 7.5 分鐘：商店、酒館、旅館委託、委託一覽、道具說明視窗的**清單假名正常顯示**（不再是 `?`），沒有崩潰、錯誤框或事件，原安裝未變動。
已知殘留：**委託資訊（詳情）視窗**的非清單欄位仍有 `?`／缺字，這不在 m061b 的 8 個清單點範圍內（見下）。

## 執行（Win11，HANDOFF-LOADER-ENABLED-M061B，一次）

時間：2026-10-29 10:54:51（P）→ 10:55:06–11:02:39（L）→ 11:03:12（Finalize），台北時間；Windows NT 10.0.26200。
證據原件 zip sha256 `87d379f47d702f058daf1ab8fd0c81bdf5750de7634656aeacbb74703490cbd5`（2,993,178 B），解開後只留在實驗室 `evidence-run1/`。倉庫只放去識別化摘要 `loader-enabled-run1/`（路徑改為 `<LD2_ROOT>`，不含截圖、EXE、存檔內容或存檔 hash、完整檔案清單）。

| 判定項 | 結果 | 依據 |
|---|---|---|
| 啟用版 EXE | `3a1b75b35aca01a8b3e0e475ea8fd7454ebe2367f03165ebab18a7054825ed31`，7,286,784 B，與 Linux 合成值相符；`game\Ld95.exe` 即此版 | `launch-L.json`、`hashes-after.json` |
| 基底／delta | m045 `4a0910…9da7` → 惰性 `6f9a8903…e1aa` → 啟用；delta `5853948c…91cd` | `hashes-before.summary.json` |
| helper 物件 | `e8144466755d223a18f5d8f586510f64822c5cc1d793c708f171e964f6064d51`（MSVC 鎖定版） | 同上 |
| 模式／啟用狀態 | `list_mode=2`、`list_sites_patched=true`、`textoutw_hook_enabled=true`；hook stub `67f30b3e…ca9e` | 同上 |
| 讀檔 | 第 2 格（3 個存檔從 m060 可丟棄副本複製）；沒有存檔 | `observations.filled.md` |
| 結束 | 結束碼 1（`soft-warn-exit1`，從選單結束），453.3 秒 | `launch-L.json` |
| 事件／WER／dump | 0／0／0（`launch-L-events.txt` 只有 BOM＋換行） | `launch-L.json` |
| 錯誤框／崩潰／卡住 | 無／無／無；上下選取清單無異常（選錯、錯行、價格不符皆無） | `observations.filled.md` |
| 原安裝 | **未變動**：`Ld95.exe` `6c817a09…d5d2` 修改時間相同，`source_exe_same_as_before=true`，1029 檔清單 `source_manifest_changes=[]` | `hashes-after.json` |
| 流程 | `steps_done=[P,L]`、`finalized=true`、`stopped=null`（Finalize 已跑，m061 run1 缺的 G 這次補上了） | `state.json` |
| module_probe | `ok=false`，Win32 錯誤 5（存取被拒）。最佳努力項，不在通過條件內 | `launch-L.json` |

## 畫面判讀（截圖只在實驗室）

對照 m061 run1（模式 1：漢字可讀、假名全部 `?`）：

| 畫面（dialog） | m061 run1 | **m061b 模式 2** |
|---|---|---|
| 商店・購買（137） | 「コンディションパウダー」→ 11 個 `?` | **片假名道具名正常**（使用者指為最明顯：`L-shop-buy.jpg`） |
| 商店・出售（138） | `???` | 使用者標「部分繁中、部分日文」，未見 `?` 回報 |
| 酒館（143） | 冒險者名全部 `?` | **片假名冒險者名正常** |
| 旅館・委託（140） | 漢字可讀、假名 `?` | 漢字＋假名都正常 |
| 委託一覽（169） | 委託人部分 `???` | 委託人名正常（含「イブラムッド」） |
| 道具說明視窗名稱行 | 日文正常 | 清單與詳情的假名都正常 |
| 委託資訊（156／388） | 大量缺字 | **仍有 `?`／缺字**（使用者標「亂碼／空白」） |
| 商店・強化（139） | 未到達 | 未到達 |

- 「部分繁中、部分日文」符合預期：catalog（24 個基本名稱，武器／防具／藥水等）命中的顯示繁中，未命中的顯示日文原文。模式 2 解決的是「未命中時的日文」能完整顯示，**不會讓它變成繁中**。
- 模式 2 切換確實生效的推論：若 `SetWindowLongW` 沒切成功，行為會和 run1 一樣（假名 `?`）。這次假名正常 ⇒ 這些清單框已經是 Unicode 視窗，且 MFC 沒有子類化它們（`GetWindowLongW==GetClassLongW` 條件成立）。
- 固定 UI（選單、對話框標籤）仍是 m045 繁中，沒有退步。

### 已知殘留：委託資訊視窗的 `?`

委託詳情裡出問題的是靜態欄位與說明文字框，字串推測走 SetDlgItemText 或自行繪字等**清單以外**的路徑（與 m061 run1 判讀相同），不經過 `CWnd::SendDlgItemMessage`（0x4ea671）的 8 個清單點。這是 m061b 範圍外的既知限制，不算退步。需要另開里程碑追蹤該 dialog 的文字設定路徑。

## 結論

- 模式 2：**通過**。清單假名問題已在實機解決，穩定性與 run1 相同（0 事件／0 dump），原安裝未變動。
- 模式 0（保底）`49b62395…d876` 不需要另外驗收（模式 2 沒有異常）；保留作為正式版候選的低風險選項。
- 仍未完成（不影響本判定）：
  1. 委託資訊視窗非清單欄位（另案）。
  2. 商店・強化（139）未到達；catalog 命中畫面（武器店／防具店）的繁中尚未特別截圖確認。
  3. 清單繁中化需要擴充 catalog（Mina 消耗品／冒險者名譯稿審核、放寬 `reviewed_catalog` 24 筆限制），規劃在 m062 v3 catalog＋重編 helper。
  4. `module_probe` 錯誤 5：可接受為 n/a，或之後在提權 PowerShell 執行。

`production_can_apply=false`、`release_approved=false` 不變。
