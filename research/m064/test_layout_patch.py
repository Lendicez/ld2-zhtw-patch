"""layout_patch 小段程式的模擬測試（unicorn；Windows API 與 MFC 函式以 Python 模擬）。"""
import struct
import unittest

import layout_patch as L

try:
    import unicorn
    from unicorn import x86_const as X
except ImportError:
    unicorn = None

BASE = 0x30000000
MOCK = 0x40000000            # 模擬函式入口（每個 0x10）
STACK = 0x50000000


class Emu:
    def __init__(self, ini=None, children=None, client=(0, 0, 984, 584)):
        self.mu = mu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
        self.code, self.sym = L.load_stub(BASE)
        mu.mem_map(BASE, 0x2000); mu.mem_write(BASE, self.code)
        mu.mem_map(0x525000, 0x1000); mu.mem_map(0x4e0000, 0x20000)
        mu.mem_map(MOCK, 0x1000); mu.mem_map(STACK, 0x10000); mu.mem_map(0x60000000, 0x10000)
        self.ini = dict(ini or {}); self.children = children or {}; self.client = client
        self.calls = []
        self.app, self.frame = 0x60000000, 0x60001000
        mu.mem_write(self.app + L.APP_MAINWND, struct.pack('<I', self.frame))
        mu.mem_write(self.frame + L.FRAME_MDICLIENT, struct.pack('<I', 0x777))
        self.mods = 0x60002000                         # AFX_MODULE_STATE
        mu.mem_write(self.mods + 4, struct.pack('<I', self.app))
        self.fn = {}
        def reg(name, addr, nargs, f):
            self.fn[addr] = (name, nargs, f)
            mu.mem_write(addr, b'\xc3')
        k = 0
        for name, nargs, f in (('IsIconic', 1, lambda a: 0), ('IsZoomed', 1, lambda a: 0), ('GetWindowTextA', 3, self._gwt),
                               ('GetWindowRect', 2, self._gwr), ('MapWindowPoints', 4, self._mwp), ('GetClientRect', 2, self._gcr),
                               ('GetWindow', 2, self._gw), ('SendMessageA', 4, self._sm), ('wsprintfA', 0, self._wsp)):
            addr = MOCK + 0x10 * k; k += 1
            mu.mem_write(L.IAT[name], struct.pack('<I', addr)); reg(name, addr, nargs, f)
        for name, va, nargs, f in (('afx', L.AFX_MODULE_STATE, 0, lambda a: self.mods), ('GPI', L.GET_PROFILE_INT, 3, self._gpi),
                                   ('WPI', L.WRITE_PROFILE_INT, 3, self._wpi), ('WPS', L.WRITE_PROFILE_STRING, 3, lambda a: 1)):
            reg(name, va, nargs, f)
        mu.hook_add(unicorn.UC_HOOK_CODE, self._hook)

    def s(self, p):
        b = bytes(self.mu.mem_read(p, 64)); return b[:b.index(b'\0')].decode('cp950')

    def _hook(self, mu, addr, size, _):
        if addr not in self.fn: return
        name, nargs, f = self.fn[addr]
        sp = mu.reg_read(X.UC_X86_REG_ESP)
        args = [struct.unpack('<I', mu.mem_read(sp + 4 + 4 * i, 4))[0] for i in range(max(nargs, 4))]
        r = f(args); self.calls.append(name)
        ret = struct.unpack('<I', mu.mem_read(sp, 4))[0]
        mu.reg_write(X.UC_X86_REG_EAX, (r or 0) & 0xffffffff)
        mu.reg_write(X.UC_X86_REG_ESP, sp + 4 + 4 * nargs); mu.reg_write(X.UC_X86_REG_EIP, ret)
        for r_ in (X.UC_X86_REG_ECX, X.UC_X86_REG_EDX):   # 呼叫約定：ecx/edx 可被破壞
            mu.reg_write(r_, 0xbadbad)

    def _wsp(self, a):
        buf, fmt = a[0], self.s(a[1]); t = self.s(a[2])
        out = (fmt % t).encode('cp950') + b'\0'; self.mu.mem_write(buf, out); return len(out) - 1
    def _gpi(self, a):
        return self.ini.get((self.s(a[0]), self.s(a[1])), a[2])
    def _wpi(self, a):
        v = a[2] - (1 << 32) if a[2] >= 1 << 31 else a[2]
        self.ini[(self.s(a[0]), self.s(a[1]))] = v; return 1
    def _gwt(self, a):
        t = self.children[a[0]][0].encode('cp950') + b'\0'; self.mu.mem_write(a[1], t); return len(t) - 1
    def _gwr(self, a):
        x, y, w, h = self.children[a[0]][1]
        self.mu.mem_write(a[1], struct.pack('<iiii', x + 100, y + 50, x + 100 + w, y + 50 + h)); return 1   # 螢幕座標（client 在 100,50）
    def _mwp(self, a):
        l, t, r, b = struct.unpack('<iiii', self.mu.mem_read(a[2], 16))
        self.mu.mem_write(a[2], struct.pack('<iiii', l - 100, t - 50, r - 100, b - 50)); return 1
    def _gcr(self, a):
        self.mu.mem_write(a[1], struct.pack('<iiii', *self.client)); return 1
    def _gw(self, a):
        keys = sorted(self.children)
        if a[1] == 5: return keys[0] if keys else 0
        i = keys.index(a[0]); return keys[i + 1] if i + 1 < len(keys) else 0
    def _sm(self, a):
        self.sent = a[:4]; return 0x1234

    def run_call(self, entry, stack_words, regs):
        mu = self.mu
        sp = STACK + 0x8000
        ret = MOCK + 0xf00; mu.mem_write(ret, b'\xf4')
        mu.mem_write(sp, struct.pack('<I', ret) + b''.join(struct.pack('<I', w & 0xffffffff) for w in stack_words))
        mu.reg_write(X.UC_X86_REG_ESP, sp)
        for r, v in regs.items(): mu.reg_write(r, v)
        mu.emu_start(self.sym[entry], ret, count=5000)
        return mu.reg_read(X.UC_X86_REG_ESP) - sp


@unittest.skipIf(unicorn is None, 'unicorn 未安裝')
class T(unittest.TestCase):
    def mcs(self, e, title, x, y, cx, cy):
        p = 0x60003000; t = 0x60003100
        e.mu.mem_write(t, title.encode('cp950') + b'\0')
        e.mu.mem_write(p, struct.pack('<IIIiiii', 0, t if title else 0, 0, x, y, cx, cy))
        return p

    def create(self, e, p):
        e.mu.mem_write(STACK + 0x100, b'')
        d = e.run_call('hook_create', [0x220, 0, p], {X.UC_X86_REG_ESI: e.frame, X.UC_X86_REG_EBX: L.IAT['SendMessageA'] and e.fn and [k for k, v in e.fn.items() if v[0] == 'SendMessageA'][0],
                                                     X.UC_X86_REG_EDI: 0x11, X.UC_X86_REG_EBP: 0x22})
        x, y, cx, cy = struct.unpack('<iiii', e.mu.mem_read(p + 0xc, 16))
        return (x, y, cx, cy), d

    def test_create_clamp_no_memory(self):
        e = Emu(client=(0, 0, 984, 584))
        (x, y, cx, cy), d = self.create(e, self.mcs(e, '資訊', 897, 265, 290, 137))
        self.assertEqual((x, y), (984 - 290, 265))
        self.assertEqual(e.sent, [0x777, 0x220, 0, 0x60003000])     # 原樣送出 WM_MDICREATE
        self.assertEqual(d, 4 + 12)                                    # 堆疊平衡（回到呼叫點時 3 參數已由 SendMessage 清掉）
        self.assertEqual(e.mu.reg_read(X.UC_X86_REG_EDI), 0x11); self.assertEqual(e.mu.reg_read(X.UC_X86_REG_EBP), 0x22)
        e = Emu(client=(0, 0, 984, 584))
        (x, y, _, _), _ = self.create(e, self.mcs(e, '地圖', 7, 548, 290, 337))
        self.assertEqual((x, y), (7, 584 - 337))
        e = Emu(client=(0, 0, 200, 100))                               # 子視窗比工作區大 → 靠左上
        (x, y, _, _), _ = self.create(e, self.mcs(e, '場景視窗', 2, 40, 634, 369))
        self.assertEqual((x, y), (0, 0))

    def test_create_restore(self):
        e = Emu(ini={('ChildWindows', '資訊.x'): 300, ('ChildWindows', '資訊.y'): 20}, client=(0, 0, 1584, 884))
        (x, y, _, _), _ = self.create(e, self.mcs(e, '資訊', 897, 265, 290, 137))
        self.assertEqual((x, y), (300, 20))
        e = Emu(ini={('ChildWindows', '資訊.x'): 1500}, client=(0, 0, 1584, 884))   # 只有 x → 不套用（兩軸都要有）
        (x, y, _, _), _ = self.create(e, self.mcs(e, '資訊', 897, 265, 290, 137))
        self.assertEqual((x, y), (897, 265))
        e = Emu(ini={('ChildWindows', '資訊.x'): 1500, ('ChildWindows', '資訊.y'): 900}, client=(0, 0, 1584, 884))  # 記下的位置超出 → 限制
        (x, y, _, _), _ = self.create(e, self.mcs(e, '資訊', 897, 265, 290, 137))
        self.assertEqual((x, y), (1584 - 290, 884 - 137))
        e = Emu(client=(0, 0, 1584, 884))                              # 沒有標題 → 只限制
        (x, y, _, _), _ = self.create(e, self.mcs(e, '', 10, 10, 100, 100))
        self.assertEqual((x, y), (10, 10))
        self.assertNotIn('GPI', e.calls)

    def test_destroy_saves(self):
        e = Emu(children={0x501: ('資訊', (320, 40, 290, 137))})
        d = e.run_call('hook_destroy', [0x777, 0x221, 0x501, 0], {X.UC_X86_REG_ESI: 0x33})
        self.assertEqual(e.ini[('ChildWindows', '資訊.x')], 320); self.assertEqual(e.ini[('ChildWindows', '資訊.y')], 40)
        self.assertEqual(e.sent, [0x777, 0x221, 0x501, 0]); self.assertEqual(d, 4 + 16)
        self.assertEqual(e.mu.reg_read(X.UC_X86_REG_ESI), 0x33)

    def test_exit_saves_all(self):
        e = Emu(children={0x501: ('資訊', (320, 40, 290, 137)), 0x502: ('地圖', (-5, 600, 290, 337)), 0x503: ('達吉爾塔爾', (400, 300, 200, 150))})
        d = e.run_call('hook_exit', [1, 2, 3], {X.UC_X86_REG_ECX: e.app})
        self.assertEqual(e.ini[('ChildWindows', '地圖.x')], -5); self.assertEqual(e.ini[('ChildWindows', '地圖.y')], 600)
        self.assertEqual(e.ini[('ChildWindows', '達吉爾塔爾.y')], 300)
        self.assertIn('WPS', e.calls); self.assertEqual(d, 4 + 12)

    def test_show(self):
        def run(ncmd, saved, flags):
            e = Emu()
            sp = STACK + 0x8000; ret = MOCK + 0xf00; e.mu.mem_write(ret, b'\xf4')
            frame = struct.pack('<I', ret) + b'\0' * 0x1c + struct.pack('<III', 0x2c, flags, saved)   # 呼叫端 esp+0x1c=wp
            e.mu.mem_write(sp, frame); e.mu.reg_write(X.UC_X86_REG_ESP, sp); e.mu.reg_write(X.UC_X86_REG_EAX, ncmd)
            e.mu.emu_start(e.sym['hook_show'], ret, count=100)
            return struct.unpack('<I', e.mu.mem_read(sp + 4 + 0x24, 4))[0]
        self.assertEqual(run(1, 3, 2), 3)      # 一般啟動、上次最大化 → 最大化
        self.assertEqual(run(10, 3, 2), 3)     # SW_SHOWDEFAULT 也沿用（原版會變一般視窗）
        self.assertEqual(run(10, 1, 0), 1)
        self.assertEqual(run(7, 3, 2), 7)      # 要求最小化啟動 → 照辦
        self.assertEqual(run(1, 2, 2), 3)      # 上次存的是最小化（原本最大化）→ 最大化
        self.assertEqual(run(1, 2, 0), 1)      # 上次存的是最小化 → 一般


if __name__ == '__main__':
    unittest.main()
