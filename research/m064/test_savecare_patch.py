"""savecare_patch 小段程式的模擬測試（unicorn；Windows API、MFC 與遊戲函式以 Python 模擬）。"""
import re
import struct
import unittest

import savecare_patch as S

try:
    import unicorn
    from unicorn import x86_const as X
except ImportError:
    unicorn = None

BASE = 0x30000000
MOCK = 0x40000000
STACK = 0x50000000
HEAP = 0x60000000
APP, FRAME, MODS, GAME = HEAP, HEAP + 0x1000, HEAP + 0x2000, HEAP + 0x3000
STRS = HEAP + 0x8000
MDICLIENT, FRAMEHWND = 0x777, 0x100
END = 0x70000000


def lead(b):
    return 0x81 <= b <= 0xfe


class Emu:
    def __init__(self, exe_path=b'C:\\G\\Ld95.exe', profile=None, files=None, enabled=1):
        self.mu = mu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
        self.page, self.sym = S.load_stub(BASE)
        mu.mem_map(BASE, S.GROW); mu.mem_write(BASE, self.page)
        mu.mem_map(0x400000, 0x200000)
        mu.mem_map(MOCK, 0x1000); mu.mem_map(STACK, 0x10000); mu.mem_map(HEAP, 0x10000); mu.mem_map(END, 0x1000)
        mu.mem_write(END, b'\xf4')
        mu.mem_write(MODS + 4, struct.pack('<I', APP))
        mu.mem_write(APP + S.APP_MAINWND, struct.pack('<I', FRAME))
        mu.mem_write(APP + S.APP_GAME, struct.pack('<I', GAME))
        mu.mem_write(FRAME + S.FRAME_MDICLIENT, struct.pack('<I', MDICLIENT))
        self.exe_path, self.enabled = exe_path, enabled
        self.profile = dict(profile or {})
        self.files = dict(files or {})        # 路徑(bytes) → (size, timelow)
        self.calls, self.fn = [], {}
        self.timers, self.msgs, self.saved = {}, [], []
        self.clock = 0x90000000

        def reg(name, addr, nargs, f, this=False):
            self.fn[addr] = (name, nargs, f, this); mu.mem_write(addr, b'\xc3')
        apis = (('GetFileAttributesA', 1, self._gfa), ('CreateFileA', 7, lambda a: 0x1234), ('FindFirstFileA', 2, self._fff),
                ('FindClose', 1, lambda a: 1), ('GetModuleFileNameA', 3, self._gmfn), ('GetModuleHandleA', 1, lambda a: 0x7c800000),
                ('GetProcAddress', 2, self._gpa), ('lstrlenA', 1, lambda a: len(self.cstr(a[0]))),
                ('lstrcpyA', 2, self._lstrcpy), ('wsprintfA', 0, self._wsprintf), ('SetTimer', 4, self._settimer),
                ('KillTimer', 2, self._killtimer), ('IsWindowEnabled', 1, lambda a: self.enabled),
                ('SendMessageA', 4, self._sendmsg), ('GetParent', 1, lambda a: FRAMEHWND if a[0] == MDICLIENT else 0))
        for k, (name, nargs, f) in enumerate(apis):
            addr = MOCK + 0x10 * k
            mu.mem_write(S.IAT[name], struct.pack('<I', addr)); reg(name, addr, nargs, f)
        self.k32 = {}
        for k, name in enumerate(('CopyFileA', 'MoveFileExA', 'CreateDirectoryA', 'IsDBCSLeadByte')):
            addr = MOCK + 0x400 + 0x10 * k
            self.k32[name] = addr
            reg(name, addr, {'CopyFileA': 3, 'MoveFileExA': 3, 'CreateDirectoryA': 2, 'IsDBCSLeadByte': 1}[name],
                {'CopyFileA': self._copy, 'MoveFileExA': self._move, 'CreateDirectoryA': lambda a: 1,
                 'IsDBCSLeadByte': lambda a: int(lead(a[0] & 0xff))}[name])
        reg('afx', S.AFX_MODULE_STATE, 0, lambda a: MODS)
        reg('GetProfileInt', S.GET_PROFILE_INT, 3, self._getint, True)
        reg('WriteProfileInt', S.WRITE_PROFILE_INT, 3, self._writeint, True)
        reg('SaveGame', MOCK + 0x800, 1, self._savegame, True)
        # SaveGame 本體：以 CFile::Open 同樣參數經 hook_cf 開檔，再交給 Python（MOCK+0x800）
        tail = MOCK + 0x800
        body = (bytes.fromhex('8b442404') + b'\x6a\x00' + b'\x68' + struct.pack('<I', 0x80) + b'\x6a\x02\x6a\x00\x6a\x00'
                + b'\x68' + struct.pack('<I', 0x40000000) + b'\x50' + b'\xba' + struct.pack('<I', self.sym['hook_cf']) + b'\xff\xd2')
        body += b'\xe9' + struct.pack('<i', tail - (S.SAVE_GAME + len(body) + 5))
        mu.mem_write(S.SAVE_GAME, body)
        reg('MessageBox', S.MSGBOX, 3, lambda a: 99, True)
        # SetMode 本體：mov eax,[esp+0x10] ; mov [esi+0x108],eax ; pop edi ; pop esi ; pop ebx ; ret 4
        mu.mem_write(S.SETMODE_BODY, bytes.fromhex('8b442410898608010000') + b'\x5f\x5e\x5b\xc2\x04\x00')
        # LoadGame 本體：mov esp,ebp ; pop ebp ; ret 4
        mu.mem_write(S.LOADGAME_BODY, bytes.fromhex('8be55dc20400'))
        mu.hook_add(unicorn.UC_HOOK_CODE, self._hook)

    # ---- 工具 ----
    def cstr(self, p):
        out = b''
        while True:
            c = bytes(self.mu.mem_read(p, 64)); i = c.find(b'\0')
            if i >= 0: return out + c[:i]
            out += c; p += 64

    def wstr(self, p, s):
        self.mu.mem_write(p, s + b'\0')

    def put(self, s):
        p = STRS + 0x400 * len(getattr(self, '_strs', []))
        self._strs = getattr(self, '_strs', []) + [s]; self.wstr(p, s); return p

    def mode(self, v=None):
        if v is not None: self.mu.mem_write(FRAME + S.FRAME_MODE, struct.pack('<i', v))
        return struct.unpack('<i', self.mu.mem_read(FRAME + S.FRAME_MODE, 4))[0]

    def var(self, name):
        return struct.unpack('<I', self.mu.mem_read(BASE + S.DATA_OFF + S.DATA[name][0], 4))[0]

    def setvar(self, name, v):
        self.mu.mem_write(BASE + S.DATA_OFF + S.DATA[name][0], struct.pack('<I', v))

    def call(self, entry, args=(), ecx=0, ret_ok=True):
        sp = STACK + 0x8000
        stack = struct.pack('<I', END) + b''.join(struct.pack('<I', a) for a in args)
        sp -= len(stack); self.mu.mem_write(sp, stack)
        self.mu.reg_write(X.UC_X86_REG_ESP, sp); self.mu.reg_write(X.UC_X86_REG_ECX, ecx)
        start = self.sym[entry] if isinstance(entry, str) else entry
        self.mu.emu_start(start, END, count=200000)
        return self.mu.reg_read(X.UC_X86_REG_EAX), self.mu.reg_read(X.UC_X86_REG_ESP) - sp

    def _hook(self, mu, addr, size, _):
        if addr not in self.fn: return
        name, nargs, f, this = self.fn[addr]
        sp = mu.reg_read(X.UC_X86_REG_ESP)
        args = [struct.unpack('<I', mu.mem_read(sp + 4 + 4 * i, 4))[0] for i in range(8)]
        if this: args = [mu.reg_read(X.UC_X86_REG_ECX)] + args
        r = f(args); self.calls.append(name)
        ret = struct.unpack('<I', mu.mem_read(sp, 4))[0]
        mu.reg_write(X.UC_X86_REG_EAX, (r or 0) & 0xffffffff)
        mu.reg_write(X.UC_X86_REG_ESP, sp + 4 + 4 * nargs); mu.reg_write(X.UC_X86_REG_EIP, ret)
        for r_ in (X.UC_X86_REG_ECX, X.UC_X86_REG_EDX): mu.reg_write(r_, 0xbadbad)

    # ---- 模擬 API ----
    def _gfa(self, a):
        return 0x20 if self.cstr(a[0]) in self.files else 0xffffffff

    def _fff(self, a):
        p = self.cstr(a[0])
        if p not in self.files: return 0xffffffff
        size, t = self.files[p]
        wfd = bytearray(0x140); struct.pack_into('<I', wfd, 0x14, t); struct.pack_into('<I', wfd, 0x20, size)
        self.mu.mem_write(a[1], bytes(wfd)); return 0x5555

    def _gmfn(self, a):
        self.wstr(a[1], self.exe_path); return len(self.exe_path)

    def _gpa(self, a):
        return self.k32.get(self.cstr(a[1]).decode(), 0)

    def _lstrcpy(self, a):
        self.wstr(a[0], self.cstr(a[1])); return a[0]

    def _wsprintf(self, a):
        fmt = self.cstr(a[1]); vals = list(a[2:]); out = b''
        for part in re.split(rb'(%s|%d)', fmt):
            if part == b'%s': out += self.cstr(vals.pop(0))
            elif part == b'%d': out += str(vals.pop(0)).encode()
            else: out += part
        self.wstr(a[0], out); return len(out)

    def _settimer(self, a):
        self.timers[(a[0], a[1])] = a[3]; return a[1]

    def _killtimer(self, a):
        self.timers.pop((a[0], a[1]), None); return 1

    def _sendmsg(self, a):
        self.msgs.append((a[0], a[1], self.cstr(a[3]).decode('cp950'))); return 0

    def _copy(self, a):
        src, dst = self.cstr(a[0]), self.cstr(a[1])
        self.files[dst] = self.files[src]; self.calls.append(('copy', src, dst)); return 1

    def _move(self, a):
        src, dst = self.cstr(a[0]), self.cstr(a[1])
        if src not in self.files: return 0
        self.files[dst] = self.files.pop(src); self.calls.append(('move', src, dst)); return 1

    def _getint(self, a):
        return self.profile.get(self.cstr(a[2]).decode(), a[3])

    def _writeint(self, a):
        self.profile[self.cstr(a[2]).decode()] = a[3]; return 1

    def _savegame(self, a):
        p = self.cstr(a[1]); self.saved.append(p)
        if getattr(self, 'save_fails', False): return 0
        self.clock += 0x1000
        self.files[p] = (3032781, self.clock); return 1


@unittest.skipIf(unicorn is None, 'unicorn not installed')
class TestBackup(unittest.TestCase):
    def test_rotate_and_copy(self):
        name = b'C:\\G\\USR\\LUNAS003.LDP'
        bk = lambda k: b'C:\\G\\USR\\_backup\\LUNAS003-%d.LDP' % k
        e = Emu(files={name: (10, 1), bk(1): (9, 0), bk(2): (8, 0), bk(5): (5, 0)})
        r, used = e.call('hook_cf', (e.put(name), 0x40000000, 0, 0, 2, 0x80, 0))
        self.assertEqual(r, 0x1234)                    # 原樣呼叫 CreateFileA
        self.assertEqual(used, 4 + 4 * 7)              # stdcall 7 個參數
        moves = [c[1:] for c in e.calls if isinstance(c, tuple) and c[0] == 'move']
        self.assertEqual(moves, [(bk(1), bk(2)), (bk(2), bk(3))][::-1] if False else [(bk(2), bk(3)), (bk(1), bk(2))])
        self.assertEqual(e.files[bk(1)], (10, 1))
        self.assertEqual(e.files[bk(2)], (9, 0))
        self.assertEqual(e.files[bk(3)], (8, 0))
        self.assertIn(('copy', name, bk(1)), e.calls)

    def test_skip_cases(self):
        name = b'C:\\G\\USR\\LUNAS003.LDP'
        for args in ((name, 0x80000000, 2), (name, 0x40000000, 3), (b'C:\\G\\USR\\X.LDE', 0x40000000, 2), (b'C:\\G\\USR\\NEW.LDP', 0x40000000, 2)):
            e = Emu(files={name: (1, 1), b'C:\\G\\USR\\X.LDE': (1, 1)})
            r, _ = e.call('hook_cf', (e.put(args[0]), args[1], 0, 0, args[2], 0x80, 0))
            self.assertEqual(r, 0x1234)
            self.assertFalse([c for c in e.calls if isinstance(c, tuple)], args)

    def test_lowercase_and_dbcs_dir(self):
        name = '遊戲\\許\\usr\\lunas001.ldp'.encode('cp950')     # 「許」第二位元組是 0x5c
        e = Emu(files={name: (7, 7)})
        e.call('hook_cf', (e.put(name), 0xc0000000, 0, 0, 2, 0x80, 0))
        self.assertIn(('copy', name, '遊戲\\許\\usr\\_backup\\lunas001-1.LDP'.encode('cp950')), e.calls)


@unittest.skipIf(unicorn is None, 'unicorn not installed')
class TestAutoSave(unittest.TestCase):
    AUTO = b'C:\\G\\USR\\LUNAS015.LDP'

    def setmode(self, e, m):
        e.call('sm_wrap', (m,), ecx=FRAME)
        self.assertEqual(e.mode(), m)

    def fire(self, e):
        (hwnd, tid), proc = next(iter(e.timers.items()))
        e.call(proc, (hwnd, 0x113, tid, 0))

    def test_return_from_dungeon_schedules_and_saves(self):
        e = Emu(); e.mode(3)
        self.setmode(e, 4); self.assertEqual(e.timers, {})
        self.setmode(e, 3)
        self.assertEqual(list(e.timers), [(FRAMEHWND, S.TIMER_ID)])
        self.assertEqual(e.timers[(FRAMEHWND, S.TIMER_ID)], e.sym.get('timer_proc', e.timers[(FRAMEHWND, S.TIMER_ID)]))
        e.enabled = 0; self.fire(e); self.assertEqual(e.saved, [])          # 有對話框時等
        e.enabled = 1; self.fire(e)
        self.assertEqual(e.saved, [self.AUTO]); self.assertEqual(e.timers, {})
        self.assertEqual(e.profile['AutoSaveSize'], 3032781)
        self.assertEqual(e.profile['AutoSaveTime'], e.files[self.AUTO][1] & 0x7fffffff)
        self.assertIn('已自動存檔', e.msgs[-1][2])
        # 第二次：015 是自己上次存的 → 再存，舊的進備份
        self.setmode(e, 6); self.setmode(e, 0); self.setmode(e, 3); self.fire(e)
        self.assertEqual(len(e.saved), 2)
        self.assertIn(b'C:\\G\\USR\\_backup\\LUNAS015-1.LDP', e.files)

    def test_travel_and_no_trigger_cases(self):
        e = Emu(); e.mode(3)
        for m in (0, 6, 10, 6, 9, 0, 3):
            self.setmode(e, m)
        self.assertEqual(len(e.timers), 1)
        e2 = Emu(); e2.mode(3)
        for m in (5, 3):                      # 城鎮戰鬥
            self.setmode(e2, m)
        self.assertEqual(e2.timers, {})
        e3 = Emu(); e3.mode(0)
        for m in (2, 3):                      # 新遊戲
            self.setmode(e3, m)
        self.assertEqual(e3.timers, {})
        e4 = Emu(); e4.mode(0)
        self.setmode(e4, 3)                   # 讀檔
        self.assertEqual(e4.timers, {})

    def test_loadgame_cancels(self):
        e = Emu(); e.mode(3)
        self.setmode(e, 4); self.setmode(e, 3)
        self.assertEqual(len(e.timers), 1)
        e.call('lg_wrap', (e.put(b'x'),), ecx=GAME)
        self.assertEqual(e.timers, {}); self.assertEqual(e.var('V_AWAY'), 0)
        e2 = Emu(); e2.mode(3); self.setmode(e2, 4)
        self.assertEqual(e2.var('V_AWAY'), 1)
        e2.call('lg_wrap', (e2.put(b'x'),), ecx=GAME)
        self.assertEqual(e2.var('V_AWAY'), 0)

    def test_player_slot_not_overwritten(self):
        e = Emu(files={self.AUTO: (3032781, 0x1234)}, profile={'AutoSaveSize': 3032781, 'AutoSaveTime': 0x999}); e.mode(3)
        e.call('hook_predungeon'); self.assertEqual(e.saved, [])
        self.assertIn('您自己的存檔', e.msgs[-1][2])
        e = Emu(files={self.AUTO: (3032781, 0x80001234)}, profile={'AutoSaveSize': 3032781, 'AutoSaveTime': 0x1234}); e.mode(3)
        e.call('hook_predungeon'); self.assertEqual(e.saved, [self.AUTO])

    def test_disabled_or_not_town(self):
        e = Emu(profile={'AutoSave': 0}); e.mode(3); e.call('hook_predungeon'); self.assertEqual(e.saved, [])
        e = Emu(); e.mode(4); e.call('hook_predungeon'); self.assertEqual(e.saved, [])
        e = Emu(exe_path='D:\\遊戲\\許\\Ld95.exe'.encode('cp950')); e.mode(3); e.call('hook_predungeon')
        self.assertEqual(e.saved, ['D:\\遊戲\\許\\USR\\LUNAS015.LDP'.encode('cp950')])

    def test_predungeon_preserves_registers_and_tail_calls_afx(self):
        e = Emu(); e.mode(3)
        e.mu.reg_write(X.UC_X86_REG_EBX, 0x11); e.mu.reg_write(X.UC_X86_REG_ESI, 0x22); e.mu.reg_write(X.UC_X86_REG_EDI, 0x33)
        r, used = e.call('hook_predungeon')
        self.assertEqual(r, MODS); self.assertEqual(used, 4)
        self.assertEqual((e.mu.reg_read(X.UC_X86_REG_EBX), e.mu.reg_read(X.UC_X86_REG_ESI), e.mu.reg_read(X.UC_X86_REG_EDI)), (0x11, 0x22, 0x33))

    def test_save_failure(self):
        e = Emu(); e.mode(3); e.save_fails = True
        e.call('hook_predungeon')
        self.assertIn('失敗', e.msgs[-1][2]); self.assertNotIn('AutoSaveSize', e.profile)

    def test_hook_msg(self):
        e = Emu()
        r, used = e.call('hook_msg', (1, 2, 3), ecx=FRAME)
        self.assertEqual(r, 99); self.assertIn('MessageBox', e.calls)
        e = Emu(); e.setvar('V_BUSY', 1)
        r, used = e.call('hook_msg', (1, 2, 3), ecx=FRAME)
        self.assertEqual((r, used), (1, 16)); self.assertNotIn('MessageBox', e.calls)


if __name__ == '__main__':
    unittest.main()
