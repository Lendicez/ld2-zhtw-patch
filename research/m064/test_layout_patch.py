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
MOCK = 0x40000000
STACK = 0x50000000
CLIENT = 0x777


class Emu:
    def __init__(self, client=(0, 0, 944, 632), parent=CLIENT, wrect=(10, 20, 300, 157), mainwnd=True):
        self.mu = mu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
        self.code, self.sym = L.load_stub(BASE)
        mu.mem_map(BASE, 0x2000); mu.mem_write(BASE, self.code)
        mu.mem_map(0x525000, 0x1000); mu.mem_map(0x4e0000, 0x20000)
        mu.mem_map(MOCK, 0x1000); mu.mem_map(STACK, 0x10000); mu.mem_map(0x60000000, 0x10000)
        self.client, self.parent, self.wrect = client, parent, wrect
        app, frame, mods = 0x60000000, 0x60001000, 0x60002000
        mu.mem_write(app + L.APP_MAINWND, struct.pack('<I', frame if mainwnd else 0))
        mu.mem_write(frame + L.FRAME_MDICLIENT, struct.pack('<I', CLIENT))
        mu.mem_write(mods + 4, struct.pack('<I', app))
        self.fn, self.calls = {}, []
        def reg(name, addr, nargs, f):
            self.fn[addr] = (name, nargs, f); mu.mem_write(addr, b'\xc3')
        self.kids = {}; self.moves = []; self.iconic = set()
        for k, (name, nargs, f) in enumerate((('GetParent', 1, self._gp), ('GetClientRect', 2, self._gcr),
                                              ('GetWindowRect', 2, self._gwr), ('SetWindowPos', 7, self._swp),
                                              ('InvalidateRect', 3, lambda a: 1), ('IsIconic', 1, lambda a: int(a[0] in self.iconic)),
                                              ('IsZoomed', 1, lambda a: 0), ('GetWindow', 2, self._gw), ('MapWindowPoints', 4, self._mwp))):
            addr = MOCK + 0x10 * k
            mu.mem_write(L.IAT[name], struct.pack('<I', addr)); reg(name, addr, nargs, f)
        reg('afx', L.AFX_MODULE_STATE, 0, lambda a: mods)
        mu.hook_add(unicorn.UC_HOOK_CODE, self._hook)

    def _hook(self, mu, addr, size, _):
        if addr not in self.fn: return
        name, nargs, f = self.fn[addr]
        sp = mu.reg_read(X.UC_X86_REG_ESP)
        args = [struct.unpack('<I', mu.mem_read(sp + 4 + 4 * i, 4))[0] for i in range(max(nargs, 7))]
        r = f(args); self.calls.append(name)
        ret = struct.unpack('<I', mu.mem_read(sp, 4))[0]
        mu.reg_write(X.UC_X86_REG_EAX, (r or 0) & 0xffffffff)
        mu.reg_write(X.UC_X86_REG_ESP, sp + 4 + 4 * nargs); mu.reg_write(X.UC_X86_REG_EIP, ret)
        for r_ in (X.UC_X86_REG_ECX, X.UC_X86_REG_EDX): mu.reg_write(r_, 0xbadbad)

    def _gp(self, a):
        return 0x100 if a[0] == CLIENT else self.parent
    def _gw(self, a):
        ks = sorted(self.kids)
        if a[1] == 5: return ks[0] if ks else 0
        i = ks.index(a[0]); return ks[i + 1] if i + 1 < len(ks) else 0
    def _mwp(self, a):
        l, t, r, b = struct.unpack('<iiii', self.mu.mem_read(a[2], 16))
        self.mu.mem_write(a[2], struct.pack('<iiii', l - 100, t - 50, r - 100, b - 50)); return 1
    def _gcr(self, a):
        self.mu.mem_write(a[1], struct.pack('<iiii', *self.client)); return 1
    def _gwr(self, a):
        if a[0] in self.kids:
            x, y, w, h = self.kids[a[0]]
            self.mu.mem_write(a[1], struct.pack('<iiii', x + 100, y + 50, x + 100 + w, y + 50 + h)); return 1
        self.mu.mem_write(a[1], struct.pack('<iiii', *self.wrect)); return 1
    def _swp(self, a):
        self.swp = [v - (1 << 32) if v >= 1 << 31 else v for v in a[:7]]; self.moves.append(self.swp); return 1

    def swp_call(self, x, y, cx, cy, flags):
        mu = self.mu; sp = STACK + 0x8000; ret = MOCK + 0xf00; mu.mem_write(ret, b'\xf4')
        mu.mem_write(sp, struct.pack('<I', ret) + struct.pack('<IIiiiiI', 0x501, 0, x, y, cx, cy, flags))
        mu.reg_write(X.UC_X86_REG_ESP, sp)
        for r, v in ((X.UC_X86_REG_EBX, 0x11), (X.UC_X86_REG_ESI, 0x22), (X.UC_X86_REG_EDI, 0x33), (X.UC_X86_REG_EBP, 0x44)):
            mu.reg_write(r, v)
        mu.emu_start(self.sym['hook_swp'], ret, count=5000)
        self.assertregs = [mu.reg_read(r) for r in (X.UC_X86_REG_EBX, X.UC_X86_REG_ESI, X.UC_X86_REG_EDI, X.UC_X86_REG_EBP)]
        return self.swp, mu.reg_read(X.UC_X86_REG_ESP) - sp


@unittest.skipIf(unicorn is None, 'unicorn 未安裝')
class T(unittest.TestCase):
    def test_clamp_nosize(self):
        e = Emu(wrect=(1000, 300, 1290, 437))                 # 資訊 290×137
        (h, after, x, y, cx, cy, fl), d = e.swp_call(895, 225, 0, 0, 0x295)
        self.assertEqual((x, y), (944 - 290, 225)); self.assertEqual((cx, cy, fl), (0, 0, 0x295))
        self.assertEqual(d, 4 + 28); self.assertEqual(e.assertregs, [0x11, 0x22, 0x33, 0x44])
        e = Emu(wrect=(0, 0, 290, 337))                       # 地圖 290×337
        (_, _, x, y, _, _, _), _ = e.swp_call(5, 508, 0, 0, 0x295)
        self.assertEqual((x, y), (5, 632 - 337))

    def test_clamp_with_size(self):
        e = Emu()
        (_, _, x, y, cx, cy, _), _ = e.swp_call(900, 700, 200, 100, 0x14)
        self.assertEqual((x, y, cx, cy), (744, 532, 200, 100)); self.assertNotIn('GetWindowRect', e.calls)
        e = Emu(client=(0, 0, 100, 80))                       # 比工作區大 → 靠左上
        (_, _, x, y, _, _, _), _ = e.swp_call(50, 50, 634, 369, 0x14)
        self.assertEqual((x, y), (0, 0))
        e = Emu()
        (_, _, x, y, _, _, _), _ = e.swp_call(-30, -5, 200, 100, 0x14)
        self.assertEqual((x, y), (0, 0))

    def test_untouched(self):
        e = Emu(parent=0x999)                                  # 不是 MDI 工作區的子視窗
        (_, _, x, y, _, _, _), _ = e.swp_call(5000, 5000, 10, 10, 0x14)
        self.assertEqual((x, y), (5000, 5000)); self.assertNotIn('GetClientRect', e.calls)
        e = Emu()                                              # SWP_NOMOVE
        (_, _, x, y, _, _, _), _ = e.swp_call(5000, 5000, 10, 10, 0x16)
        self.assertEqual((x, y), (5000, 5000)); self.assertNotIn('GetParent', e.calls)
        e = Emu(mainwnd=False)                                 # 主視窗尚未建立
        (_, _, x, y, _, _, _), _ = e.swp_call(5000, 5000, 10, 10, 0x14)
        self.assertEqual((x, y), (5000, 5000))

    def test_size(self):
        e = Emu(client=(0, 0, 800, 500))
        e.kids = {0x501: (895, 225, 290, 137), 0x502: (5, 508, 290, 337), 0x503: (0, 0, 634, 369), 0x504: (-20, 600, 100, 50)}
        e.iconic = {0x504 + 1}
        mu = e.mu; sp = STACK + 0x8000; ret = MOCK + 0xf00; mu.mem_write(ret, b'\xf4')
        mu.mem_write(sp, struct.pack('<IIII', ret, CLIENT, 0, 1)); mu.reg_write(X.UC_X86_REG_ESP, sp)
        mu.emu_start(e.sym['hook_size'], ret, count=20000)
        mv = {m[0]: (m[2], m[3], m[6]) for m in e.moves}
        self.assertEqual(mv[0x501], (800 - 290, 225, 0x15)); self.assertEqual(mv[0x502], (5, 500 - 337, 0x15))
        self.assertNotIn(0x503, mv)                         # 已在範圍內 → 不動
        self.assertEqual(mv[0x504], (0, 450, 0x15))
        self.assertEqual(mu.reg_read(X.UC_X86_REG_ESP) - sp, 4 + 12)
        e = Emu(client=(0, 0, 800, 500)); e.kids = {0x501: (895, 225, 290, 137)}; e.iconic = {0x100}   # 主視窗最小化
        mu = e.mu; mu.mem_write(ret, b'\xf4'); mu.mem_write(sp, struct.pack('<IIII', ret, CLIENT, 0, 1)); mu.reg_write(X.UC_X86_REG_ESP, sp)
        mu.emu_start(e.sym['hook_size'], ret, count=20000)
        self.assertEqual(e.moves, [])

    def test_show(self):
        def run(ncmd, saved, flags):
            e = Emu()
            sp = STACK + 0x8000; ret = MOCK + 0xf00; e.mu.mem_write(ret, b'\xf4')
            e.mu.mem_write(sp, struct.pack('<I', ret) + b'\0' * 0x1c + struct.pack('<III', 0x2c, flags, saved))
            e.mu.reg_write(X.UC_X86_REG_ESP, sp); e.mu.reg_write(X.UC_X86_REG_EAX, ncmd)
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
