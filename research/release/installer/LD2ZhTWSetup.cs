// 《俠客遊 前途道標》（Lunatic Dawn: Passage of the Book / Ld95.exe）繁體中文化補丁安裝程式。
// 以 Windows 內建 .NET Framework 4 csc.exe 編譯；payload（差分包，見 make_delta.py）以內嵌資源方式附帶。
// 只改寫 payload 列出的檔案；原檔先備份到 <遊戲資料夾>\_zhTW_backup\ 並核對雜湊；可解除安裝還原。
// 不處理 Usr（存檔）、ini 或任何其他檔案。命令列：/status <dir>、/install <dir>、/uninstall <dir>（自動測試用）。
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("俠客遊 前途道標 繁體中文化補丁")]
[assembly: AssemblyProduct("ld2-zhtw-patch")]
[assembly: AssemblyVersion(LD2ZhTW.Ver.Assembly)]

namespace LD2ZhTW
{
    static partial class Ver { }

    class PFile
    {
        public string Path, Kind, SrcSha, DstSha; public long SrcSize, DstSize; public int OpsOff, OpsLen;
        // 舊版本（升級來源）安裝後的雜湊 → 版本號；OldOnly＝舊版改過、本版不再改的檔（升級時還原原檔）
        public Dictionary<string, string> OldDst = new Dictionary<string, string>(); public bool OldOnly;
    }

    class Payload
    {
        public string Version; public List<PFile> Files = new List<PFile>(); public byte[] Ops;
        public IEnumerable<PFile> AllFiles { get { return Files.Concat(OldOnlyFiles); } }
        public List<PFile> OldOnlyFiles = new List<PFile>();

        public static Payload Load()
        {
            byte[] all;
            using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.bin"))
            using (var m = new MemoryStream()) { s.CopyTo(m); all = m.ToArray(); }
            if (Encoding.ASCII.GetString(all, 0, 7) != "LD2ZHTW" || all[7] != 1) throw new Exception("payload 格式錯誤");
            int jl = BitConverter.ToInt32(all, 8);
            string json = Encoding.UTF8.GetString(all, 12, jl);
            var p = new Payload();
            p.Ops = new byte[all.Length - 12 - jl];
            Buffer.BlockCopy(all, 12 + jl, p.Ops, 0, p.Ops.Length);
            var root = (Dictionary<string, object>)new MiniJson(json).Parse();
            p.Version = (string)root["version"];
            foreach (Dictionary<string, object> f in (List<object>)root["files"])
                p.Files.Add(new PFile {
                    Path = (string)f["path"], Kind = f.ContainsKey("kind") ? (string)f["kind"] : "bytes", SrcSha = (string)f["src_sha256"], DstSha = (string)f["dst_sha256"],
                    SrcSize = Convert.ToInt64(f["src_size"]), DstSize = Convert.ToInt64(f["dst_size"]),
                    OpsOff = Convert.ToInt32(f["ops_off"]), OpsLen = Convert.ToInt32(f["ops_len"]) });
            if (root.ContainsKey("previous"))
                foreach (Dictionary<string, object> pv in (List<object>)root["previous"])
                {
                    string ver = (string)pv["version"];
                    foreach (Dictionary<string, object> f in (List<object>)pv["files"])
                    {
                        string path = (string)f["path"], src = (string)f["src_sha256"], dst = (string)f["dst_sha256"];
                        var cur = p.Files.FirstOrDefault(x => x.Path == path) ?? p.OldOnlyFiles.FirstOrDefault(x => x.Path == path);
                        if (cur == null)
                        {
                            cur = new PFile { Path = path, Kind = "restore", SrcSha = src, DstSha = src, OldOnly = true };
                            p.OldOnlyFiles.Add(cur);
                        }
                        if (cur.SrcSha != src) throw new Exception("舊版本資料不一致：" + path);
                        if (dst != cur.DstSha && !cur.OldDst.ContainsKey(dst)) cur.OldDst[dst] = ver;
                    }
                }
            return p;
        }

        public byte[] Build(PFile f, byte[] src)
        {
            if (f.Kind == "bmh") return Bmh.EncodeRaw(ApplyOps(f, Bmh.Decode(src)), src);
            if (f.Kind != "bytes") throw new Exception("不支援的差分類型：" + f.Kind);
            return ApplyOps(f, src);
        }

        byte[] ApplyOps(PFile f, byte[] src)
        {
            var o = new MemoryStream((int)f.DstSize);
            int p = f.OpsOff, end = f.OpsOff + f.OpsLen;
            while (p < end)
            {
                byte k = Ops[p]; uint a = BitConverter.ToUInt32(Ops, p + 1); int b = BitConverter.ToInt32(Ops, p + 5); p += 9;
                if (k == 1) { if (a + (long)b > src.Length) throw new Exception("差分超出原檔範圍"); o.Write(src, (int)a, b); }
                else if (k == 2) { o.Write(Ops, p, b); p += b; }
                else throw new Exception("差分格式錯誤");
            }
            return o.ToArray();
        }
    }

    // 遊戲 .BMH 圖檔（Huffman 區塊）：解碼與「原樣區塊」封裝（同 research/m064/bmh.py）
    static class Bmh
    {
        public static byte[] Decode(byte[] b)
        {
            if (b.Length < 0x18 || b[8] != (byte)'H' || b[9] != (byte)'F') throw new Exception("不是 BMH 檔");
            int outSize = BitConverter.ToInt32(b, 4);
            var o = new MemoryStream(outSize);
            int p = 0x18;
            while (o.Length < outSize)
            {
                uint nbits = BitConverter.ToUInt32(b, p); int count = BitConverter.ToInt32(b, p + 4);
                if (nbits == 0) { o.Write(b, p + 8, count); p += 8 + count; continue; }
                var left = new int[512]; var right = new int[512];
                for (int i = 0; i < 512; i++) { left[i] = 0x7fff; right[i] = 0x7fff; }
                int nodes = 0, sumLen = 0;
                long bitPos = (long)(p + 8 + 256) * 8;
                for (int sym = 0; sym < 256; sym++)
                {
                    int len = b[p + 8 + sym]; sumLen += len; int node = 0;
                    for (int i = 0; i < len; i++)
                    {
                        int bit = (b[bitPos >> 3] >> (7 - (int)(bitPos & 7))) & 1; bitPos++;
                        var arr = bit == 1 ? right : left; int v = arr[node];
                        if (v == 0x7fff)
                        {
                            if (i == len - 1) arr[node] = sym - 256;
                            else { nodes++; if (nodes >= 512) throw new Exception("BMH 樹溢位"); arr[node] = nodes; node = nodes; }
                        }
                        else { if (i == len - 1 || v < 0) throw new Exception("BMH 碼衝突"); node = v; }
                    }
                }
                int hdr = 0x108 + (sumLen + 7) / 8;
                bitPos = (long)(p + hdr) * 8;
                for (int k = 0; k < count; k++)
                {
                    int node = 0;
                    while (true)
                    {
                        int bit = (b[bitPos >> 3] >> (7 - (int)(bitPos & 7))) & 1; bitPos++;
                        node = (bit == 1 ? right : left)[node];
                        if (node < 0) break;
                        if (node == 0x7fff) throw new Exception("BMH 資料錯誤");
                    }
                    o.WriteByte((byte)(node & 0xff));
                }
                p += hdr + (int)((nbits + 7) / 8);
            }
            var r = o.ToArray();
            if (r.Length > outSize) Array.Resize(ref r, outSize);
            return r;
        }

        public static byte[] EncodeRaw(byte[] data, byte[] template)
        {
            var o = new byte[0x18 + 8 + data.Length];
            Buffer.BlockCopy(template, 0, o, 0, 0x18);
            BitConverter.GetBytes(0x18 + 8 + data.Length).CopyTo(o, 0);
            BitConverter.GetBytes(data.Length).CopyTo(o, 4);
            BitConverter.GetBytes(0).CopyTo(o, 0x18);
            BitConverter.GetBytes(data.Length).CopyTo(o, 0x1c);
            Buffer.BlockCopy(data, 0, o, 0x20, data.Length);
            return o;
        }
    }

    enum FState { Original, Patched, Older, Unknown, Missing }

    class Engine
    {
        public readonly Payload P; public readonly string Dir; public readonly Action<string> Log;
        public Engine(Payload p, string dir, Action<string> log) { P = p; Dir = dir; Log = log ?? (s => { }); }

        public static string Sha(byte[] b) { using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(b)).Replace("-", "").ToLowerInvariant(); }
        string Full(PFile f) { return System.IO.Path.Combine(Dir, f.Path.Replace('/', '\\')); }
        string BackupDir { get { return System.IO.Path.Combine(Dir, "_zhTW_backup"); } }
        string BackupOf(PFile f) { return System.IO.Path.Combine(BackupDir, "original", f.Path.Replace('/', '\\')); }

        public FState State(PFile f)
        {
            string p = Full(f);
            if (!File.Exists(p)) return FState.Missing;
            string h = Sha(File.ReadAllBytes(p));
            if (h == f.DstSha) return f.OldOnly ? FState.Original : FState.Patched;
            if (h == f.SrcSha) return FState.Original;
            return f.OldDst.ContainsKey(h) ? FState.Older : FState.Unknown;
        }

        public Dictionary<FState, int> Summary()
        {
            var d = new Dictionary<FState, int>();
            foreach (FState s in Enum.GetValues(typeof(FState))) d[s] = 0;
            foreach (var f in P.AllFiles) { var st = State(f); if (!(f.OldOnly && st == FState.Missing)) d[st]++; }
            return d;
        }

        /// <summary>目前安裝的舊版本號（以檔案雜湊判斷；可能不只一個）。</summary>
        public List<string> OlderVersions()
        {
            var v = new List<string>();
            foreach (var f in P.AllFiles)
            {
                string p = Full(f);
                if (!File.Exists(p)) continue;
                string ver;
                if (f.OldDst.TryGetValue(Sha(File.ReadAllBytes(p)), out ver) && !v.Contains(ver)) v.Add(ver);
            }
            return v;
        }

        byte[] OriginalOf(PFile f)
        {
            string b = BackupOf(f);
            if (!File.Exists(b)) throw new Exception("找不到舊版安裝時留下的原檔備份，無法更新：" + f.Path + "（可先用 Steam「驗證遊戲檔案完整性」還原原版再安裝）");
            byte[] src = File.ReadAllBytes(b);
            if (Sha(src) != f.SrcSha) throw new Exception("原檔備份內容不符，已停止：" + b);
            return src;
        }

        public static bool GameRunning()
        {
            return Process.GetProcessesByName("Ld95").Length > 0;
        }

        public void Install()
        {
            if (GameRunning()) throw new Exception("遊戲正在執行，請先關閉 Ld95.exe。");
            // 1) 全部預檢：原檔或已安裝，不允許未知版本
            var todo = new List<KeyValuePair<PFile, byte[]>>();
            foreach (var f in P.AllFiles)
            {
                var st = State(f);
                if (st == FState.Patched || (f.OldOnly && (st == FState.Original || st == FState.Missing))) continue;
                if (st != FState.Original && st != FState.Older)
                    throw new Exception("檔案不是支援的原版或舊版補丁，已停止（未做任何變更）：" + f.Path + "（" + st + "）");
                // 舊版補丁 → 由備份的原檔重建（升級）；原版 → 直接重建
                byte[] src = st == FState.Older ? OriginalOf(f) : File.ReadAllBytes(Full(f));
                byte[] dst = f.OldOnly ? src : P.Build(f, src);
                if (Sha(dst) != f.DstSha) throw new Exception("重建結果雜湊不符：" + f.Path);
                todo.Add(new KeyValuePair<PFile, byte[]>(f, dst));
            }
            if (todo.Count == 0) { Log("已是本版補丁，不需安裝。"); return; }
            // 2) 備份原檔（已有同內容備份則沿用；不同內容不覆寫；升級的檔案備份已在上一步驗證）
            foreach (var kv in todo)
            {
                if (State(kv.Key) == FState.Older) continue;
                string b = BackupOf(kv.Key);
                Directory.CreateDirectory(System.IO.Path.GetDirectoryName(b));
                if (File.Exists(b))
                {
                    if (Sha(File.ReadAllBytes(b)) != kv.Key.SrcSha) throw new Exception("既有備份內容不符，已停止：" + b);
                }
                else
                {
                    File.Copy(Full(kv.Key), b + ".tmp", true);
                    if (Sha(File.ReadAllBytes(b + ".tmp")) != kv.Key.SrcSha) throw new Exception("備份驗證失敗：" + b);
                    File.Move(b + ".tmp", b);
                }
            }
            File.WriteAllText(System.IO.Path.Combine(BackupDir, "README.txt"),
                "俠客遊 前途道標 繁中補丁的原檔備份（解除安裝時使用）。請勿刪除，除非已解除安裝或改用 Steam「驗證檔案完整性」還原。\r\n" +
                "補丁版本：" + P.Version + "\r\n", new UTF8Encoding(true));
            // 3) 逐檔寫入（暫存檔 → 取代），失敗則以備份回滾已寫入者
            var done = new List<PFile>();
            try
            {
                foreach (var kv in todo)
                {
                    string t = Full(kv.Key), tmp = t + ".zhtw-new";
                    File.WriteAllBytes(tmp, kv.Value);
                    if (Sha(File.ReadAllBytes(tmp)) != kv.Key.DstSha) throw new Exception("寫入驗證失敗：" + kv.Key.Path);
                    File.Copy(tmp, t, true); File.Delete(tmp);
                    done.Add(kv.Key);
                    Log("已更新 " + kv.Key.Path);
                }
            }
            catch
            {
                foreach (var f in done) { try { File.Copy(BackupOf(f), Full(f), true); } catch { } }
                foreach (var kv in todo) { try { File.Delete(Full(kv.Key) + ".zhtw-new"); } catch { } }
                throw;
            }
            File.WriteAllText(System.IO.Path.Combine(BackupDir, "installed.txt"), P.Version + "\r\n", new UTF8Encoding(false));
            Log("安裝完成：" + todo.Count + " 個檔案（版本 " + P.Version + "）。");
        }

        public void Uninstall()
        {
            if (GameRunning()) throw new Exception("遊戲正在執行，請先關閉 Ld95.exe。");
            var todo = new List<PFile>();
            foreach (var f in P.AllFiles)
            {
                var st = State(f);
                if (st == FState.Original || (f.OldOnly && st == FState.Missing)) continue;
                if (st != FState.Patched && st != FState.Older) throw new Exception("檔案不是本補丁安裝的版本，已停止（未做任何變更）：" + f.Path);
                string b = BackupOf(f);
                if (!File.Exists(b) || Sha(File.ReadAllBytes(b)) != f.SrcSha) throw new Exception("找不到正確的原檔備份：" + f.Path);
                todo.Add(f);
            }
            foreach (var f in todo)
            {
                string t = Full(f), tmp = t + ".zhtw-old";
                File.Copy(BackupOf(f), tmp, true);
                if (Sha(File.ReadAllBytes(tmp)) != f.SrcSha) throw new Exception("還原驗證失敗：" + f.Path);
                File.Copy(tmp, t, true); File.Delete(tmp);
                Log("已還原 " + f.Path);
            }
            try { File.Delete(System.IO.Path.Combine(BackupDir, "installed.txt")); } catch { }
            Log("解除安裝完成：" + todo.Count + " 個檔案已還原為原版。（備份資料夾保留，可自行刪除 _zhTW_backup）");
        }

        public static bool CanWrite(string dir)
        {
            try { string p = System.IO.Path.Combine(dir, ".zhtw-write-test"); File.WriteAllText(p, "x"); File.Delete(p); return true; }
            catch { return false; }
        }
    }

    static class Steam
    {
        public static List<string> Candidates()
        {
            var res = new List<string>();
            var roots = new List<string>();
            foreach (var hive in new[] { Registry.CurrentUser, Registry.LocalMachine })
                foreach (var key in new[] { @"Software\Valve\Steam", @"Software\WOW6432Node\Valve\Steam" })
                    try
                    {
                        using (var k = hive.OpenSubKey(key))
                        {
                            if (k == null) continue;
                            foreach (var n in new[] { "SteamPath", "InstallPath" })
                            { var v = k.GetValue(n) as string; if (!string.IsNullOrEmpty(v)) roots.Add(v.Replace('/', '\\')); }
                        }
                    }
                    catch { }
            var libs = new List<string>();
            foreach (var r in roots.Distinct(StringComparer.OrdinalIgnoreCase))
            {
                libs.Add(r);
                try
                {
                    string vdf = Path.Combine(r, @"steamapps\libraryfolders.vdf");
                    if (File.Exists(vdf))
                        foreach (var line in File.ReadAllLines(vdf))
                        {
                            var t = line.Trim();
                            if (!t.StartsWith("\"path\"", StringComparison.OrdinalIgnoreCase)) continue;
                            var parts = t.Split('"');
                            if (parts.Length >= 4) libs.Add(parts[3].Replace(@"\\", @"\"));
                        }
                }
                catch { }
            }
            foreach (var l in libs.Distinct(StringComparer.OrdinalIgnoreCase))
            {
                try
                {
                    string common = Path.Combine(l, @"steamapps\common");
                    if (!Directory.Exists(common)) continue;
                    foreach (var d in Directory.GetDirectories(common))
                        if (File.Exists(Path.Combine(d, "Ld95.exe"))) res.Add(d);
                }
                catch { }
            }
            return res.Distinct(StringComparer.OrdinalIgnoreCase).ToList();
        }
    }

    class MainForm : Form
    {
        readonly Payload P;
        readonly TextBox dirBox = new TextBox(), logBox = new TextBox();
        readonly Label stateLbl = new Label();
        readonly Button installBtn = new Button(), uninstallBtn = new Button(), browseBtn = new Button();

        public MainForm(Payload p, string initialDir)
        {
            P = p;
            Text = "俠客遊 前途道標 繁體中文化補丁 " + p.Version;
            Font = new Font("Microsoft JhengHei UI", 9.5f);
            ClientSize = new Size(640, 420); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            var intro = new Label { Left = 16, Top = 12, Width = 608, Height = 52,
                Text = "本程式會把《俠客遊 前途道標》（Lunatic Dawn: Passage of the Book，Steam 版 Ld95.exe 1.0.3.16）改為繁體中文。\r\n" +
                       "原檔會先備份在遊戲資料夾的 _zhTW_backup，隨時可用本程式「解除安裝」還原。存檔（Usr）不會被修改。" };
            var dl = new Label { Left = 16, Top = 72, Width = 120, Text = "遊戲資料夾：" };
            dirBox.SetBounds(16, 94, 500, 26);
            browseBtn.SetBounds(524, 92, 100, 30); browseBtn.Text = "瀏覽…";
            stateLbl.SetBounds(16, 128, 608, 40);
            installBtn.SetBounds(16, 172, 140, 34); installBtn.Text = "安裝";
            uninstallBtn.SetBounds(166, 172, 140, 34); uninstallBtn.Text = "解除安裝";
            logBox.SetBounds(16, 216, 608, 188); logBox.Multiline = true; logBox.ReadOnly = true; logBox.ScrollBars = ScrollBars.Vertical;
            Controls.AddRange(new Control[] { intro, dl, dirBox, browseBtn, stateLbl, installBtn, uninstallBtn, logBox });
            browseBtn.Click += (s, e) =>
            {
                using (var fb = new FolderBrowserDialog { Description = "請選擇含有 Ld95.exe 的遊戲資料夾" })
                    if (fb.ShowDialog(this) == DialogResult.OK) { dirBox.Text = fb.SelectedPath; Refresh2(); }
            };
            dirBox.Leave += (s, e) => Refresh2();
            installBtn.Click += (s, e) => Run(true);
            uninstallBtn.Click += (s, e) => Run(false);
            if (Native.GetACP() != 950)
                Log("注意：此電腦的「非 Unicode 程式語言」不是繁體中文（代碼頁 " + Native.GetACP() + "）。補丁需在繁體中文（950）環境下才能正確顯示。");
            if (!string.IsNullOrEmpty(initialDir)) dirBox.Text = initialDir;
            else
            {
                var c = Steam.Candidates();
                if (c.Count == 1) { dirBox.Text = c[0]; Log("已在 Steam 資料庫找到遊戲：" + c[0]); }
                else if (c.Count > 1) Log("找到多個可能的遊戲資料夾，請確認：\r\n  " + string.Join("\r\n  ", c));
                else Log("未自動找到遊戲，請按「瀏覽…」選擇含有 Ld95.exe 的資料夾。");
                if (c.Count > 1) dirBox.Text = c[0];
            }
            Refresh2();
        }

        string pendingUpgrade;
        void Log(string s) { logBox.AppendText(s + "\r\n"); }

        void Refresh2()
        {
            installBtn.Enabled = uninstallBtn.Enabled = false;
            string d = dirBox.Text.Trim();
            if (d.Length == 0 || !File.Exists(Path.Combine(d, "Ld95.exe"))) { stateLbl.Text = "狀態：此資料夾沒有 Ld95.exe。"; return; }
            var e = new Engine(P, d, null); var s = e.Summary(); int n = s.Values.Sum();
            installBtn.Text = "安裝"; pendingUpgrade = null;
            if (P.Files.All(f => e.State(f) == FState.Patched) &&
                P.OldOnlyFiles.All(f => { var st = e.State(f); return st == FState.Original || st == FState.Missing; }))
            { stateLbl.Text = "狀態：已安裝本版繁中補丁（" + P.Version + "）。"; uninstallBtn.Enabled = true; }
            else if (s[FState.Original] == n) { stateLbl.Text = "狀態：原版（可安裝）。"; installBtn.Enabled = true; }
            else if (s[FState.Older] > 0 && s[FState.Unknown] + s[FState.Missing] == 0)
            {
                pendingUpgrade = string.Join("、", e.OlderVersions());
                stateLbl.Text = "狀態：已安裝舊版繁中補丁（" + pendingUpgrade + "），可直接更新為 " + P.Version + "。";
                installBtn.Text = "更新"; installBtn.Enabled = uninstallBtn.Enabled = true;
            }
            else if (s[FState.Unknown] + s[FState.Missing] == 0) { stateLbl.Text = "狀態：部分檔案已安裝（可再按安裝完成，或解除安裝）。"; installBtn.Enabled = uninstallBtn.Enabled = true; }
            else
            {
                var bad = P.Files.Where(f => { var st = e.State(f); return st == FState.Unknown || st == FState.Missing; }).Select(f => f.Path).Take(5);
                stateLbl.Text = "狀態：有不支援的檔案版本（可能是其他版本、其他補丁或 Steam 更新），不會進行修改：" + string.Join(", ", bad);
            }
        }

        void Run(bool install)
        {
            string d = dirBox.Text.Trim();
            if (!Engine.CanWrite(d))
            {
                if (MessageBox.Show(this, "此資料夾需要系統管理員權限才能寫入。要以系統管理員身分重新開啟本程式嗎？", Text,
                        MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
                {
                    try
                    {
                        Process.Start(new ProcessStartInfo(Application.ExecutablePath, "\"/dir=" + d + "\"") { UseShellExecute = true, Verb = "runas" });
                        Close();
                    }
                    catch (Exception ex) { Log("未取得權限：" + ex.Message); }
                }
                return;
            }
            if (Engine.GameRunning()) { MessageBox.Show(this, "請先關閉遊戲（Ld95.exe）再操作。", Text); return; }
            if (install && pendingUpgrade != null &&
                MessageBox.Show(this, "偵測到已安裝繁中補丁 " + pendingUpgrade + "。\r\n要直接更新為 " + P.Version + " 嗎？\r\n（存檔不受影響；原檔備份沿用，之後仍可解除安裝還原原版）",
                    Text, MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
            Cursor = Cursors.WaitCursor;
            try { var e = new Engine(P, d, Log); if (install) e.Install(); else e.Uninstall(); }
            catch (Exception ex) { Log("失敗：" + ex.Message); MessageBox.Show(this, ex.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error); }
            finally { Cursor = Cursors.Default; Refresh2(); }
        }
    }

    static class Native { [DllImport("kernel32.dll")] public static extern uint GetACP(); }

    static class Program
    {
        [STAThread]
        static int Main(string[] args)
        {
            Payload p;
            try { p = Payload.Load(); }
            catch (Exception ex) { MessageBox.Show("安裝資料損毀：" + ex.Message); return 3; }
            if (args.Length >= 2 && (args[0] == "/status" || args[0] == "/install" || args[0] == "/uninstall"))
            {
                var log = new StringBuilder();
                try
                {
                    var e = new Engine(p, args[1], s => log.AppendLine(s));
                    if (args[0] == "/install") e.Install();
                    if (args[0] == "/uninstall") e.Uninstall();
                    var s2 = e.Summary();
                    log.AppendLine("version=" + p.Version + " original=" + s2[FState.Original] + " patched=" + s2[FState.Patched] +
                                   " older=" + s2[FState.Older] +
                                   " unknown=" + s2[FState.Unknown] + " missing=" + s2[FState.Missing]);
                    Console.Out.Write(log.ToString()); return 0;
                }
                catch (Exception ex) { Console.Out.Write(log.ToString() + "ERROR " + ex.Message + "\n"); return 1; }
            }
            string dir = null;
            foreach (var a in args) if (a.StartsWith("/dir=")) dir = a.Substring(5);
            Application.EnableVisualStyles();
            Application.Run(new MainForm(p, dir));
            return 0;
        }
    }

    // 最小 JSON 解析（只供 payload 內嵌 metadata）
    class MiniJson
    {
        readonly string s; int i;
        public MiniJson(string s) { this.s = s; }
        public object Parse() { Ws(); var v = Val(); return v; }
        void Ws() { while (i < s.Length && char.IsWhiteSpace(s[i])) i++; }
        object Val()
        {
            Ws(); char c = s[i];
            if (c == '{') { i++; var d = new Dictionary<string, object>(); Ws(); if (s[i] == '}') { i++; return d; }
                while (true) { Ws(); var k = Str(); Ws(); i++; d[k] = Val(); Ws(); if (s[i++] == '}') return d; } }
            if (c == '[') { i++; var l = new List<object>(); Ws(); if (s[i] == ']') { i++; return l; }
                while (true) { l.Add(Val()); Ws(); if (s[i++] == ']') return l; } }
            if (c == '"') return Str();
            if (s.Substring(i).StartsWith("true")) { i += 4; return true; }
            if (s.Substring(i).StartsWith("false")) { i += 5; return false; }
            if (s.Substring(i).StartsWith("null")) { i += 4; return null; }
            int st = i; while (i < s.Length && "+-0123456789.eE".IndexOf(s[i]) >= 0) i++;
            return long.Parse(s.Substring(st, i - st));
        }
        string Str()
        {
            var b = new StringBuilder(); i++;
            while (s[i] != '"')
            {
                if (s[i] == '\\')
                {
                    i++; char e = s[i];
                    if (e == 'u') { b.Append((char)Convert.ToInt32(s.Substring(i + 1, 4), 16)); i += 4; }
                    else b.Append(e == 'n' ? '\n' : e == 't' ? '\t' : e == 'r' ? '\r' : e == 'b' ? '\b' : e == 'f' ? '\f' : e);
                }
                else b.Append(s[i]);
                i++;
            }
            i++; return b.ToString();
        }
    }
}
