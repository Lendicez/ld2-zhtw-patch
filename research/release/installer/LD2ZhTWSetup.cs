// 《俠客遊 前途道標》（Lunatic Dawn: Passage of the Book / Ld95.exe）繁體中文化補丁安裝程式。
// 以 Windows 內建 .NET Framework 4 csc.exe 編譯；payload（差分包，見 make_delta.py）以內嵌資源方式附帶。
// 只改寫 payload 列出的檔案；原檔先備份到 <遊戲資料夾>\_zhTW_backup\ 並核對雜湊；可解除安裝還原。
// 不處理 Usr（存檔）、ini 或任何其他檔案。命令列：/status <dir>、/install <dir> [/noadmin]、/uninstall <dir>、
// /setmode <dir> admin|noadmin（自動測試用）。
// 「免系統管理員權限啟動」：只把 Ld95.exe manifest 的 requireAdministrator 等長改為 asInvoker（位置由 make_release 依資源結構算出並核對）。
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
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
        // 免系統管理員模式（manifest asInvoker）的本版雜湊；null＝此檔沒有該模式
        public string AltDst; public HashSet<string> OldAlt = new HashSet<string>();
    }

    class Payload
    {
        public string Version; public List<PFile> Files = new List<PFile>(); public byte[] Ops;
        public IEnumerable<PFile> AllFiles { get { return Files.Concat(OldOnlyFiles); } }
        public List<PFile> OldOnlyFiles = new List<PFile>();
        // 免系統管理員模式：Ld95.exe manifest 內 level="requireAdministrator" 的位置與替換字串
        public PFile ModeFile; public int ManOff = -1; public byte[] ManAdmin, ManInvoker;

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
            LoadVariants(p);
            return p;
        }

        static void LoadVariants(Payload p)
        {
            var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("variants.json");
            if (s == null) return;
            string json; using (var r = new StreamReader(s, Encoding.UTF8)) json = r.ReadToEnd();
            var v = (Dictionary<string, object>)new MiniJson(json).Parse();
            var f = p.Files.FirstOrDefault(x => x.Path == (string)v["path"]);
            if (f == null) throw new Exception("variants 資料不一致");
            p.ModeFile = f; f.AltDst = (string)v["noadmin_dst_sha256"];
            p.ManOff = Convert.ToInt32(v["offset"]);
            p.ManAdmin = Encoding.ASCII.GetBytes((string)v["admin"]); p.ManInvoker = Encoding.ASCII.GetBytes((string)v["invoker"]);
            if (p.ManAdmin.Length != p.ManInvoker.Length) throw new Exception("variants 長度不符");
            if (v.ContainsKey("old_noadmin"))
                foreach (var kv in (Dictionary<string, object>)v["old_noadmin"])
                {
                    if (!f.OldDst.ContainsKey(kv.Key)) f.OldDst[kv.Key] = (string)kv.Value;
                    f.OldAlt.Add(kv.Key);
                }
        }

        /// <summary>把已安裝（標準模式）的 EXE 內容換成指定模式；核對替換位置的原字串與結果雜湊。</summary>
        public byte[] WithMode(byte[] dst, bool noAdmin)
        {
            byte[] from = noAdmin ? ManAdmin : ManInvoker, to = noAdmin ? ManInvoker : ManAdmin;
            if (ManOff < 0 || ManOff + from.Length > dst.Length) throw new Exception("此版本不支援切換啟動權限");
            for (int i = 0; i < from.Length; i++) if (dst[ManOff + i] != from[i]) throw new Exception("manifest 內容與預期不符，已停止");
            var o = (byte[])dst.Clone(); Buffer.BlockCopy(to, 0, o, ManOff, to.Length);
            if (Engine.Sha(o) != (noAdmin ? ModeFile.AltDst : ModeFile.DstSha)) throw new Exception("切換後雜湊不符，已停止");
            return o;
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
            if (h == f.DstSha || (f.AltDst != null && h == f.AltDst)) return f.OldOnly ? FState.Original : FState.Patched;
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

        /// <summary>Ld95.exe 目前的啟動權限模式："admin"、"noadmin"，未安裝本版則 null。</summary>
        public string Mode()
        {
            var f = P.ModeFile; if (f == null) return null;
            string p = Full(f); if (!File.Exists(p)) return null;
            string h = Sha(File.ReadAllBytes(p));
            return h == f.DstSha ? "admin" : (f.AltDst != null && h == f.AltDst) ? "noadmin" : null;
        }

        public void SetMode(bool noAdmin)
        {
            if (GameRunning()) throw new Exception("遊戲正在執行，請先關閉 Ld95.exe。");
            var f = P.ModeFile; if (f == null) throw new Exception("此版本不支援切換啟動權限");
            string cur = Mode(); if (cur == null) throw new Exception("尚未安裝本版補丁，無法切換啟動權限");
            if (cur == (noAdmin ? "noadmin" : "admin")) { Log("啟動權限已是" + (noAdmin ? "免系統管理員" : "系統管理員") + "模式。"); return; }
            string t = Full(f), tmp = t + ".zhtw-new";
            byte[] o = P.WithMode(File.ReadAllBytes(t), noAdmin);
            File.WriteAllBytes(tmp, o);
            if (Sha(File.ReadAllBytes(tmp)) != (noAdmin ? f.AltDst : f.DstSha)) { File.Delete(tmp); throw new Exception("寫入驗證失敗：" + f.Path); }
            File.Copy(tmp, t, true); File.Delete(tmp);
            Log(noAdmin ? "已改為免系統管理員權限啟動（不再出現 UAC 提示）。" : "已改回以系統管理員權限啟動（原版設定）。");
        }

        /// <summary>目前程序是否以提升權限（系統管理員）執行。</summary>
        public static bool Elevated()
        {
            try { return new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator); }
            catch { return false; }
        }

        /// <summary>一般權限能否保存遊戲資料：遊戲資料夾、Usr、ld95.ini、既有存檔。可以則回傳 null，否則回傳原因。
        /// 必須在未提升的程序中呼叫才有意義。只建立／刪除自己的測試檔，不改既有檔案內容。</summary>
        public string SaveWriteProblem()
        {
            if (!CanWrite(Dir)) return "遊戲資料夾無法寫入";
            string usr = System.IO.Path.Combine(Dir, "Usr");
            if (Directory.Exists(usr))
            {
                if (!CanWrite(usr)) return "存檔資料夾 Usr 無法寫入";
                foreach (var fp in Directory.GetFiles(usr))
                {
                    if ((File.GetAttributes(fp) & FileAttributes.ReadOnly) != 0) return "存檔為唯讀：" + System.IO.Path.GetFileName(fp);
                    try { using (new FileStream(fp, FileMode.Open, FileAccess.ReadWrite, FileShare.ReadWrite)) { } }
                    catch { return "存檔無法寫入：" + System.IO.Path.GetFileName(fp); }
                }
            }
            string ini = System.IO.Path.Combine(Dir, "ld95.ini");
            if (File.Exists(ini))
            {
                if ((File.GetAttributes(ini) & FileAttributes.ReadOnly) != 0) return "ld95.ini 為唯讀";
                try { using (new FileStream(ini, FileMode.Open, FileAccess.ReadWrite, FileShare.ReadWrite)) { } }
                catch { return "ld95.ini 無法寫入"; }
            }
            return null;
        }

        public static bool GameRunning()
        {
            return Process.GetProcessesByName("Ld95").Length > 0;
        }

        public void Install() { Install(null); }

        /// <summary>noAdmin：true＝免系統管理員模式、false＝原版（系統管理員）模式、null＝維持目前模式（未安裝時為原版模式）。</summary>
        public void Install(bool? noAdmin)
        {
            string modeBefore = Mode();
            if (modeBefore == null && P.ModeFile != null && File.Exists(Full(P.ModeFile)) &&
                P.ModeFile.OldAlt.Contains(Sha(File.ReadAllBytes(Full(P.ModeFile))))) modeBefore = "noadmin";   // 舊版的免系統管理員模式
            bool wantNoAdmin = noAdmin ?? (modeBefore == "noadmin");
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
            if (todo.Count == 0)
            {
                Log("已是本版補丁，不需安裝。");
                if (P.ModeFile != null && wantNoAdmin != (Mode() == "noadmin")) SetMode(wantNoAdmin);
                return;
            }
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
            if (P.ModeFile != null && wantNoAdmin) SetMode(true);
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
        readonly Label stateLbl = new Label(), modeHint = new Label();
        readonly Button installBtn = new Button(), uninstallBtn = new Button(), browseBtn = new Button(), manualBtn = new Button(), closeBtn = new Button(), backupBtn = new Button(), mediaBtn = new Button();
        readonly CheckBox noAdminChk = new CheckBox(), autoSaveChk = new CheckBox();
        bool allowNoAdmin, curAutoSave = true; string curMode, installedText;

        public MainForm(Payload p, string initialDir)
        {
            P = p;
            Text = "俠客遊 前途道標 繁體中文化補丁 " + p.Version;
            Font = new Font("Microsoft JhengHei UI", 9.5f);
            ClientSize = new Size(640, 564); FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            var intro = new Label { Left = 16, Top = 12, Width = 608, Height = 52,
                Text = "本程式會把《俠客遊 前途道標》（Lunatic Dawn: Passage of the Book，Steam 版 Ld95.exe 1.0.3.16）改為繁體中文。\r\n" +
                       "原檔會先備份在遊戲資料夾的 _zhTW_backup，隨時可用本程式「解除安裝」還原。存檔（Usr）不會被修改。" };
            var dl = new Label { Left = 16, Top = 72, Width = 120, Text = "遊戲資料夾：" };
            dirBox.SetBounds(16, 94, 500, 26);
            browseBtn.SetBounds(524, 92, 100, 30); browseBtn.Text = "瀏覽…";
            stateLbl.SetBounds(16, 128, 608, 40);
            noAdminChk.SetBounds(16, 170, 608, 24); noAdminChk.Text = "免系統管理員權限啟動（遊戲啟動時不再跳出 UAC 提示）";
            modeHint.SetBounds(34, 194, 590, 40); modeHint.ForeColor = SystemColors.GrayText;
            autoSaveChk.SetBounds(16, 238, 440, 24); autoSaveChk.Text = "自動存檔（回到城鎮時與進入迷宮前，存到第 015 格）";
            backupBtn.SetBounds(464, 234, 160, 30); backupBtn.Text = "開啟存檔備份資料夾";
            installBtn.SetBounds(16, 272, 140, 34); installBtn.Text = "安裝";
            uninstallBtn.SetBounds(166, 272, 140, 34); uninstallBtn.Text = "解除安裝";
            manualBtn.SetBounds(464, 272, 160, 34); manualBtn.Text = "開啟繁中說明書";
            mediaBtn.SetBounds(316, 272, 140, 34); mediaBtn.Text = "媒體診斷";
            logBox.SetBounds(16, 316, 608, 188); logBox.Multiline = true; logBox.ReadOnly = true; logBox.ScrollBars = ScrollBars.Vertical;
            closeBtn.SetBounds(504, 516, 120, 34); closeBtn.Text = "關閉"; closeBtn.Click += (s, e) => Close(); CancelButton = closeBtn;
            Controls.Add(closeBtn);
            Controls.AddRange(new Control[] { intro, dl, dirBox, browseBtn, stateLbl, noAdminChk, modeHint, autoSaveChk, backupBtn, installBtn, uninstallBtn, mediaBtn, manualBtn, logBox });
            mediaBtn.Click += (s, e) =>
            {
                string g = dirBox.Text.Trim();
                if (!File.Exists(Path.Combine(g, "Ld95.exe"))) { Log("請先選擇遊戲資料夾。"); return; }
                Log("── 媒體診斷（以遊戲相同的 32 位元播放方式測試；會播放幾秒音樂、音效與片頭動畫） ──");
                Cursor = Cursors.WaitCursor; mediaBtn.Enabled = false;
                try { foreach (var line in MediaDiag.Run(g, true)) Log(line); }
                catch (Exception ex) { Log("診斷中斷：" + ex.Message); }
                finally { Cursor = Cursors.Default; mediaBtn.Enabled = true; }
            };
            noAdminChk.CheckedChanged += (s, e) => UpdateApply();
            autoSaveChk.CheckedChanged += (s, e) => UpdateApply();
            backupBtn.Click += (s, e) =>
            {
                string b = Path.Combine(dirBox.Text.Trim(), "USR", "_backup");
                if (!Directory.Exists(b)) { Log("還沒有存檔備份（第一次覆蓋存檔時才會建立 USR\\_backup）。"); return; }
                try { Process.Start(new ProcessStartInfo(b) { UseShellExecute = true }); } catch (Exception ex) { Log("無法開啟資料夾：" + ex.Message); }
            };
            manualBtn.Click += (s, e) =>
            {
                string m = Path.Combine(dirBox.Text.Trim(), "index.html");
                try { Process.Start(new ProcessStartInfo(m) { UseShellExecute = true }); } catch (Exception ex) { Log("無法開啟說明書：" + ex.Message); }
            };
            browseBtn.Click += (s, e) =>
            {
                using (var fb = new FolderBrowserDialog { Description = "請選擇含有 Ld95.exe 的遊戲資料夾" })
                    if (fb.ShowDialog(this) == DialogResult.OK) { dirBox.Text = fb.SelectedPath; Refresh2(); }
            };
            dirBox.Leave += (s, e) => Refresh2();
            installBtn.Click += (s, e) => Run(true);
            uninstallBtn.Click += (s, e) => Run(false);
            uint acp = Native.GetACP();
            if (acp == 65001)
                Log("注意：此電腦開啟了「Beta：使用 Unicode UTF-8 提供全球語言支援」（代碼頁 65001）。本遊戲與補丁在此設定下文字會亂碼，" +
                    "請到「控制台 → 地區 → 系統管理 → 變更系統地區設定」取消勾選該項，並把「目前系統地區設定」設為「中文（繁體，台灣）」後重新開機。");
            else if (acp != 950)
                Log("注意：此電腦的「非 Unicode 程式語言」不是繁體中文（代碼頁 " + acp + "）。補丁需在繁體中文（950）環境下才能正確顯示；" +
                    "請到「控制台 → 地區 → 系統管理 → 變更系統地區設定」設為「中文（繁體，台灣）」後重新開機。");
            string sys86 = Environment.GetFolderPath(Environment.SpecialFolder.SystemX86);
            if (!string.IsNullOrEmpty(sys86) && (!File.Exists(Path.Combine(sys86, "wmadmod.dll")) || !File.Exists(Path.Combine(sys86, "wmvcore.dll"))))
                Log("注意：此電腦缺少 Windows Media 元件（常見於 Windows N／KN 版），遊戲的背景音樂可能無法播放。" +
                    "請到「設定 → 系統 → 選用功能」新增「媒體功能套件」（Media Feature Pack）。可按「媒體診斷」實際測試。");
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

        const string Tips =
            "── 第一次遊玩的建議 ──\r\n" +
            "‧迷宮中移動太快：讀取存檔後，選單「設定 → 遊戲設定」可調慢遊戲速度。\r\n" +
            "‧戰鬥來不及下指令：「設定 → 戰鬥設定」把［輸入時間］調到最慢，戰鬥就會一直等你下指令（其他設定會在一定時間後自動決定）。\r\n" +
            "‧視窗太多重疊：選單「視窗 → 並排顯示／重疊排列」。\r\n" +
            "‧完整的繁中說明：按右上「開啟繁中說明書」（或開啟遊戲資料夾的 index.html）。存檔只能在城鎮中進行。\r\n" +
            "‧存檔保護：覆蓋存檔前，舊檔會自動備份到 USR\\_backup（每格留 5 份，-1 最新；要還原時複製回 USR 並改回原檔名）。\r\n" +
            "‧自動存檔：回到城鎮時與進入迷宮前自動存到第 015 格；若第 015 格是您自己存的，不會覆蓋（狀態列會提示）。\r\n" +
            "‧沒有聲音或片頭動畫無法播放：按「媒體診斷」，會以遊戲相同的方式測背景音樂、音效與片頭動畫並顯示原因。";

        /// <summary>依目前狀態設定「免系統管理員權限啟動」選項。必須在 stateLbl 更新後呼叫。</summary>
        void RefreshMode(Engine e)
        {
            bool hasMode = P.ModeFile != null; noAdminChk.Visible = modeHint.Visible = hasMode;
            if (!hasMode) return;
            curMode = e.Mode();
            bool elevated = Engine.Elevated();
            string problem = elevated ? null : e.SaveWriteProblem();
            allowNoAdmin = !elevated && problem == null;
            noAdminChk.Enabled = allowNoAdmin || curMode == "noadmin";
            noAdminChk.Checked = curMode != null ? curMode == "noadmin" : allowNoAdmin;
            if (elevated)
                modeHint.Text = "本程式正以系統管理員身分執行，無法確認一般權限能否存檔。如要使用此選項，請直接開啟本程式（不要選「以系統管理員身分執行」）。";
            else if (problem != null)
                modeHint.Text = "一般權限無法保存遊戲資料（" + problem + "），維持原版的系統管理員模式。" +
                                "可在 Steam「設定 → 儲存空間」對該遊戲庫使用「修復資料夾」後再試。";
            else
                modeHint.Text = "已確認目前帳號以一般權限就能寫入存檔與設定。之後若搬移遊戲或換帳號後無法存檔，再執行本程式取消此選項即可。";
            manualBtn.Enabled = File.Exists(Path.Combine(dirBox.Text.Trim(), "index.html"));
        }

        void UpdateApply()
        {
            if (installedText == null) return;   // 只在「已安裝本版」時把安裝鈕當成「套用」
            bool differs = (noAdminChk.Enabled && noAdminChk.Checked != (curMode == "noadmin")) ||
                           (autoSaveChk.Enabled && autoSaveChk.Checked != curAutoSave);
            installBtn.Text = differs ? "套用" : "安裝"; installBtn.Enabled = differs;
        }

        void Refresh2()
        {
            installBtn.Enabled = uninstallBtn.Enabled = false;
            string d = dirBox.Text.Trim();
            if (d.Length == 0 || !File.Exists(Path.Combine(d, "Ld95.exe")))
            { stateLbl.Text = "狀態：此資料夾沒有 Ld95.exe。"; noAdminChk.Enabled = autoSaveChk.Enabled = backupBtn.Enabled = mediaBtn.Enabled = false; manualBtn.Enabled = false; modeHint.Text = ""; installedText = null; return; }
            curAutoSave = AutoSave.Get(d); autoSaveChk.Checked = curAutoSave; autoSaveChk.Enabled = backupBtn.Enabled = mediaBtn.Enabled = true;
            var e = new Engine(P, d, null); var s = e.Summary(); int n = s.Values.Sum();
            installBtn.Text = "安裝"; pendingUpgrade = null; installedText = null;
            if (P.Files.All(f => e.State(f) == FState.Patched) &&
                P.OldOnlyFiles.All(f => { var st = e.State(f); return st == FState.Original || st == FState.Missing; }))
            { stateLbl.Text = installedText = "狀態：已安裝本版繁中補丁（" + P.Version + "）。"; uninstallBtn.Enabled = true; }
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
            RefreshMode(e); UpdateApply();
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
            Cursor = Cursors.WaitCursor; bool done = false;
            try
            {
                var e = new Engine(P, d, Log);
                if (install)
                {
                    bool firstInstall = curMode == null;
                    e.Install(noAdminChk.Visible && noAdminChk.Enabled ? noAdminChk.Checked : (bool?)null);
                    if (autoSaveChk.Checked != curAutoSave) { AutoSave.Set(d, autoSaveChk.Checked); Log(autoSaveChk.Checked ? "已開啟自動存檔。" : "已關閉自動存檔。"); }
                    if (firstInstall) Log(Tips);
                    Log("── 已完成，可按右下角「關閉」結束本程式。 ──");
                }
                else { e.Uninstall(); Log("── 已完成，可按右下角「關閉」結束本程式。 ──"); }
                done = true;
            }
            catch (Exception ex) { Log("失敗：" + ex.Message); MessageBox.Show(this, ex.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error); }
            finally
            {
                Cursor = Cursors.Default; Refresh2();
                if (done) { closeBtn.Font = new Font(closeBtn.Font, FontStyle.Bold); AcceptButton = closeBtn; closeBtn.Focus(); }
            }
        }
    }

    static class Native
    {
        [DllImport("kernel32.dll")] public static extern uint GetACP();
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] public static extern uint GetPrivateProfileInt(string sec, string key, int def, string file);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] public static extern bool WritePrivateProfileString(string sec, string key, string val, string file);
    }

    /// <summary>
    /// 媒體診斷：以遊戲同樣的方式（32 位元行程）分別測背景音樂（music\*.wma，DirectShow）、音效（DirectSound／RES\*.WAV）、
    /// 片頭動畫（avi\OPENING.avi，MCI avivideo）。只讀遊戲檔，不改系統設定。audible=false 時靜音、不顯示影片視窗（自動測試用）。
    /// </summary>
    static class MediaDiag
    {
        [ComImport, Guid("56a868a9-0ad4-11ce-b03a-0020af0ba770"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IGraphBuilder
        {
            [PreserveSig] int AddFilter(IntPtr f, [MarshalAs(UnmanagedType.LPWStr)] string n);
            [PreserveSig] int RemoveFilter(IntPtr f);
            [PreserveSig] int EnumFilters(out IntPtr e);
            [PreserveSig] int FindFilterByName([MarshalAs(UnmanagedType.LPWStr)] string n, out IntPtr f);
            [PreserveSig] int ConnectDirect(IntPtr a, IntPtr b, IntPtr mt);
            [PreserveSig] int Reconnect(IntPtr p);
            [PreserveSig] int Disconnect(IntPtr p);
            [PreserveSig] int SetDefaultSyncSource();
            [PreserveSig] int Connect(IntPtr a, IntPtr b);
            [PreserveSig] int Render(IntPtr p);
            [PreserveSig] int RenderFile([MarshalAs(UnmanagedType.LPWStr)] string file, [MarshalAs(UnmanagedType.LPWStr)] string playlist);
        }
        [ComImport, Guid("56a868b1-0ad4-11ce-b03a-0020af0ba770"), InterfaceType(ComInterfaceType.InterfaceIsDual)]
        interface IMediaControl
        {
            [PreserveSig] int Run();
            [PreserveSig] int Pause();
            [PreserveSig] int Stop();
            [PreserveSig] int GetState(int timeout, out int state);
        }
        [ComImport, Guid("56a868b6-0ad4-11ce-b03a-0020af0ba770"), InterfaceType(ComInterfaceType.InterfaceIsDual)]
        interface IMediaEvent
        {
            [PreserveSig] int GetEventHandle(out IntPtr h);
            [PreserveSig] int GetEvent(out int code, out IntPtr p1, out IntPtr p2, int timeout);
            [PreserveSig] int WaitForCompletion(int timeout, out int code);
        }
        [ComImport, Guid("56a868b3-0ad4-11ce-b03a-0020af0ba770"), InterfaceType(ComInterfaceType.InterfaceIsDual)]
        interface IBasicAudio
        {
            [PreserveSig] int put_Volume(int v);
            [PreserveSig] int get_Volume(out int v);
        }
        [ComImport, Guid("36b73880-c2c8-11cf-8b46-00805f6cef60"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IMediaSeeking
        {
            [PreserveSig] int GetCapabilities(out int c);
            [PreserveSig] int CheckCapabilities(ref int c);
            [PreserveSig] int IsFormatSupported(ref Guid f);
            [PreserveSig] int QueryPreferredFormat(out Guid f);
            [PreserveSig] int GetTimeFormat(out Guid f);
            [PreserveSig] int IsUsingTimeFormat(ref Guid f);
            [PreserveSig] int SetTimeFormat(ref Guid f);
            [PreserveSig] int GetDuration(out long d);
            [PreserveSig] int GetStopPosition(out long s);
            [PreserveSig] int GetCurrentPosition(out long c);
            [PreserveSig] int ConvertTimeFormat(out long t, ref Guid tf, long s, ref Guid sf);
            [PreserveSig] int SetPositions(ref long cur, int curFlags, ref long stop, int stopFlags);
        }
        [DllImport("winmm.dll", CharSet = CharSet.Unicode, EntryPoint = "mciSendStringW")] static extern int mciSendString(string cmd, StringBuilder ret, int len, IntPtr cb);
        [DllImport("winmm.dll", CharSet = CharSet.Unicode, EntryPoint = "mciGetErrorStringW")] static extern bool mciGetErrorString(int err, StringBuilder buf, int len);
        [DllImport("winmm.dll", CharSet = CharSet.Unicode, EntryPoint = "PlaySoundW")] static extern bool PlaySound(string f, IntPtr mod, uint flags);
        [DllImport("dsound.dll")] static extern int DirectSoundCreate(IntPtr guid, out IntPtr ds, IntPtr outer);

        const string NHint = "。可能原因：Windows N／KN 版缺少媒體元件（到「設定 → 系統 → 選用功能」新增「媒體功能套件」），或遊戲檔損毀（Steam「驗證遊戲檔案完整性」）";

        public static List<string> Run(string game, bool audible)
        {
            var o = new List<string>();
            o.Add("執行環境：" + OsText() + "；測試行程 " + (IntPtr.Size == 4 ? "32 位元（與遊戲相同）" : "64 位元"));
            o.Add(Bgm(game, audible));
            o.Add(Se(game, audible));
            o.Add(Video(game, audible));
            return o;
        }

        static string OsText()
        {
            try
            {
                using (var k = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion"))
                {
                    int build; int.TryParse(k.GetValue("CurrentBuild") as string, out build);
                    string ed = k.GetValue("EditionID") as string ?? "?", dv = k.GetValue("DisplayVersion") as string ?? "";
                    return "Windows " + (build >= 22000 ? "11" : "10") + (dv.Length > 0 ? " " + dv : "") + "（組建 " + build + "，" + ed + "）";
                }
            }
            catch { return "Windows " + Environment.OSVersion.Version; }
        }

        static string Bgm(string game, bool audible)
        {
            string f = Path.Combine(game, @"music\01.wma");
            if (!File.Exists(f)) return "背景音樂：找不到 music\\01.wma（遊戲檔不完整？可用 Steam「驗證遊戲檔案完整性」）";
            object g = null;
            try
            {
                g = Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("e436ebb3-524f-11ce-9f53-0020af0ba770")));
                int hr = ((IGraphBuilder)g).RenderFile(f, null);
                if (hr < 0) return "背景音樂：異常，無法解碼 WMA（0x" + hr.ToString("X8") + "）" + NHint;
                if (!audible) ((IBasicAudio)g).put_Volume(-10000);
                var mc = (IMediaControl)g; var ms = (IMediaSeeking)g; var me = (IMediaEvent)g;
                long dur; ms.GetDuration(out dur);
                mc.Run(); System.Threading.Thread.Sleep(audible ? 3000 : 1500);
                long pos; ms.GetCurrentPosition(out pos);
                if (pos <= 0) { mc.Stop(); return "背景音樂：異常，已載入但沒有開始播放（音訊裝置或解碼器問題）" + NHint; }
                // 曲末：跳到結尾前 2 秒，確認能正常播完
                long cur = Math.Max(0, dur - 20000000L), stop = 0;
                ms.SetPositions(ref cur, 1, ref stop, 0);
                int code; int r = me.WaitForCompletion(8000, out code);
                mc.Stop();
                string end = (r >= 0 && code == 1) ? "曲末正常" : "曲末未在預期時間結束（code=" + code + "，0x" + r.ToString("X8") + "）";
                return "背景音樂（WMA，DirectShow）：正常，可播放（長度 " + (dur / 10000000) + " 秒，" + end + "）";
            }
            catch (Exception ex) { return "背景音樂：異常，" + ex.Message + NHint; }
            finally { if (g != null) Marshal.ReleaseComObject(g); }
        }

        static string Se(string game, bool audible)
        {
            IntPtr ds;
            int hr = DirectSoundCreate(IntPtr.Zero, out ds, IntPtr.Zero);
            if (hr < 0) return "音效（DirectSound）：異常，無法開啟音訊裝置（0x" + hr.ToString("X8") + "）。請確認有可用的播放裝置。";
            Marshal.Release(ds);
            string w = Path.Combine(game, @"RES\ATTACK0.WAV");
            if (!File.Exists(w)) return "音效：找不到 RES\\ATTACK0.WAV（遊戲檔不完整？）";
            if (audible && !PlaySound(w, IntPtr.Zero, 0x20000 /*SND_FILENAME*/ | 0x2 /*SND_NODEFAULT*/))
                return "音效（DirectSound）：裝置可用，但播放測試音效失敗。";
            return "音效（DirectSound）：正常，音訊裝置可用" + (audible ? "（已播放 RES\\ATTACK0.WAV）" : "");
        }

        static string Video(string game, bool audible)
        {
            string f = Path.Combine(game, @"avi\OPENING.avi");
            if (!File.Exists(f)) return "片頭動畫：找不到 avi\\OPENING.avi（遊戲檔不完整？）";
            var sb = new StringBuilder(256);
            int e = mciSendString("open \"" + f + "\" type avivideo alias ld2diag", null, 0, IntPtr.Zero);
            if (e != 0) { mciGetErrorString(e, sb, sb.Capacity); return "片頭動畫（AVI，MCI）：異常，無法開啟：" + sb + "（可用 Steam「驗證遊戲檔案完整性」）"; }
            try
            {
                if (!audible) { mciSendString("window ld2diag state hide", null, 0, IntPtr.Zero); mciSendString("setaudio ld2diag off", null, 0, IntPtr.Zero); }
                e = mciSendString("play ld2diag", null, 0, IntPtr.Zero);
                if (e != 0) { mciGetErrorString(e, sb, sb.Capacity); return "片頭動畫（AVI，MCI）：異常，無法播放：" + sb; }
                System.Threading.Thread.Sleep(audible ? 5000 : 1500);
                mciSendString("status ld2diag position", sb, sb.Capacity, IntPtr.Zero);
                long p; long.TryParse(sb.ToString(), out p);
                return p > 0 ? "片頭動畫（AVI，MCI）：正常，可播放" : "片頭動畫（AVI，MCI）：異常，沒有開始播放（Cinepak 解碼器？）";
            }
            finally { mciSendString("close ld2diag", null, 0, IntPtr.Zero); }
        }
    }

    /// <summary>自動存檔開關：遊戲資料夾 ld95.ini [zhTW] AutoSave（沒有時視為開；遊戲本身以同一個鍵判斷）。</summary>
    static class AutoSave
    {
        static string Ini(string dir) { return Path.Combine(dir, "ld95.ini"); }
        public static bool Get(string dir) { return Native.GetPrivateProfileInt("zhTW", "AutoSave", 1, Ini(dir)) != 0; }
        public static void Set(string dir, bool on)
        {
            if (!Native.WritePrivateProfileString("zhTW", "AutoSave", on ? "1" : "0", Ini(dir))) throw new Exception("無法寫入 ld95.ini");
        }
    }

    static class Program
    {
        [STAThread]
        static int Main(string[] args)
        {
            if (args.Length >= 2 && args[0] == "/mediatest")
            {
                try { foreach (var line in MediaDiag.Run(args[1], args.Contains("/audible"))) Console.Out.WriteLine(line); return 0; }
                catch (Exception ex) { Console.Out.WriteLine("ERROR " + ex.Message); return 1; }
            }
            Payload p;
            try { p = Payload.Load(); }
            catch (Exception ex) { MessageBox.Show("安裝資料損毀：" + ex.Message); return 3; }
            if (args.Length >= 2 && (args[0] == "/status" || args[0] == "/install" || args[0] == "/uninstall" || args[0] == "/setmode"))
            {
                var log = new StringBuilder();
                try
                {
                    var e = new Engine(p, args[1], s => log.AppendLine(s));
                    if (args[0] == "/install") e.Install(args.Contains("/noadmin") ? true : args.Contains("/admin") ? false : (bool?)null);
                    if (args[0] == "/install" && args.Contains("/autosave:off")) AutoSave.Set(args[1], false);
                    if (args[0] == "/install" && args.Contains("/autosave:on")) AutoSave.Set(args[1], true);
                    if (args[0] == "/setmode")
                    {
                        if (args.Length < 3 || (args[2] != "admin" && args[2] != "noadmin")) throw new Exception("用法：/setmode <dir> admin|noadmin");
                        e.SetMode(args[2] == "noadmin");
                    }
                    if (args[0] == "/status")
                    {
                        string prob = e.SaveWriteProblem();
                        log.AppendLine("elevated=" + Engine.Elevated() + " save_write=" + (prob == null ? "ok" : prob) + " acp=" + Native.GetACP());
                    }
                    if (args[0] == "/uninstall") e.Uninstall();
                    var s2 = e.Summary();
                    log.AppendLine("version=" + p.Version + " original=" + s2[FState.Original] + " patched=" + s2[FState.Patched] +
                                   " older=" + s2[FState.Older] +
                                   " unknown=" + s2[FState.Unknown] + " missing=" + s2[FState.Missing] +
                                   " mode=" + (e.Mode() ?? "-") + " autosave=" + (AutoSave.Get(args[1]) ? 1 : 0));
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
