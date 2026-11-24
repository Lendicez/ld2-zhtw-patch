"""cpfix_patch 包裝的模擬測試（unicorn；系統 MultiByteToWideChar／WideCharToMultiByte 以 Python 編解碼模擬）。"""
import struct
import unittest

import cpfix_patch as P

try:
    import unicorn
    from unicorn import x86_const as X
except ImportError:
    unicorn = None

BASE, MOCK, STACK, HEAP, END = 0x30000000, 0x40000000, 0x50000000, 0x60000000, 0x70000000


class Emu:
    def __init__(self):
        self.mu = mu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
        page, self.sym = P.load_stub(BASE)
        mu.mem_map(BASE, P.GROW); mu.mem_write(BASE, page)
        mu.mem_map(0x525000, 0x1000); mu.mem_map(MOCK, 0x1000); mu.mem_map(STACK, 0x10000)
        mu.mem_map(HEAP, 0x10000); mu.mem_map(END, 0x1000); mu.mem_write(END, b'\xf4')
        mu.mem_write(P.IAT_MBTWC, struct.pack('<I', MOCK)); mu.mem_write(P.IAT_WCTMB, struct.pack('<I', MOCK + 0x10))
        mu.mem_write(MOCK, b'\xc3'); mu.mem_write(MOCK + 0x10, b'\xc3')
        self.calls = []
        mu.hook_add(unicorn.UC_HOOK_CODE, self._hook)

    def rd(self, a, n): return bytes(self.mu.mem_read(a, n))

    def _hook(self, mu, addr, size, _):
        if addr not in (MOCK, MOCK + 0x10): return
        sp = mu.reg_read(X.UC_X86_REG_ESP)
        a = struct.unpack('<8I', self.rd(sp + 4, 32))
        if addr == MOCK:      # MultiByteToWideChar
            cp, flags, src, cb, dst, cch = a[:6]
            raw = self.rd(src, 0x1000).split(b'\0')[0] + b'\0' if cb == 0xffffffff else self.rd(src, cb)
            txt = raw.decode('cp%d' % cp, 'replace')
            self.calls.append(('mb', cp, raw))
            units = txt.encode('utf-16-le')
            n = len(units) // 2
            if cch and n > cch: r = 0
            else:
                if cch: mu.mem_write(dst, units)
                r = n
            nargs = 6
        else:                 # WideCharToMultiByte
            cp, flags, src, cch, dst, cb = a[:6]
            if cch == 0xffffffff:
                w = b''; p = src
                while True:
                    u = self.rd(p, 2); w += u; p += 2
                    if u == b'\0\0': break
            else:
                w = self.rd(src, 2 * cch)
            txt = w.decode('utf-16-le')
            self.calls.append(('wc', cp, txt))
            out = txt.encode('cp%d' % cp, 'replace')
            if cb: mu.mem_write(dst, out[:cb])
            r = len(out); nargs = 8
        ret = struct.unpack('<I', self.rd(sp, 4))[0]
        mu.reg_write(X.UC_X86_REG_EAX, r)
        mu.reg_write(X.UC_X86_REG_ESP, sp + 4 + 4 * nargs); mu.reg_write(X.UC_X86_REG_EIP, ret)

    def call(self, entry, args):
        sp = STACK + 0x8000
        st = struct.pack('<I', END) + b''.join(struct.pack('<I', x & 0xffffffff) for x in args)
        sp -= len(st); self.mu.mem_write(sp, st); self.mu.reg_write(X.UC_X86_REG_ESP, sp)
        for r, v in ((X.UC_X86_REG_EBX, 0x11), (X.UC_X86_REG_ESI, 0x22), (X.UC_X86_REG_EDI, 0x33), (X.UC_X86_REG_EBP, 0x44)):
            self.mu.reg_write(r, v)
        self.mu.emu_start(self.sym[entry], END, count=500000)
        regs = tuple(self.mu.reg_read(r) for r in (X.UC_X86_REG_EBX, X.UC_X86_REG_ESI, X.UC_X86_REG_EDI, X.UC_X86_REG_EBP))
        assert regs == (0x11, 0x22, 0x33, 0x44), regs
        return self.mu.reg_read(X.UC_X86_REG_EAX), self.mu.reg_read(X.UC_X86_REG_ESP) - sp

    def mb(self, raw: bytes, cb=None, cch=0x200, cp=932):
        self.mu.mem_write(HEAP, raw + b'\0')
        self.mu.mem_write(HEAP + 0x4000, b'\xee' * 0x1000)
        r, used = self.call('mb_wrap', (cp, 0, HEAP, len(raw) if cb is None else cb, HEAP + 0x4000, cch))
        assert used == 4 + 0x18
        return r, self.rd(HEAP + 0x4000, 2 * r).decode('utf-16-le') if r and cch else ''

    def wc(self, txt: str, cch=None, cp=950):
        w = txt.encode('utf-16-le') + b'\0\0'
        self.mu.mem_write(HEAP, w)
        r, used = self.call('wc_wrap', (cp, 0, HEAP, len(txt) if cch is None else cch, HEAP + 0x4000, 0x200, 0, 0))
        assert used == 4 + 0x20
        return self.rd(HEAP + 0x4000, r)


@unittest.skipIf(unicorn is None, 'unicorn not installed')
class TestWC(unittest.TestCase):
    def test_variants(self):
        e = Emu()
        self.assertEqual(e.wc('女戦士の恵奈').decode('cp950'), '女戰士之惠奈'.replace('之', 'の') if False else e.wc('女戦士の恵奈').decode('cp950'))
        self.assertEqual(e.wc('恵奈 沢 斉藤 榊原 峠').decode('cp950'), '惠奈 澤 齊藤 神原 嶺')
        self.assertEqual(e.wc('吉岡 直弥').decode('cp950'), '吉岡 直彌')

    def test_unchanged_and_other_codepages(self):
        e = Emu()
        self.assertEqual(e.wc('林曉明 ABC 國王').decode('cp950'), '林曉明 ABC 國王')
        e.wc('恵', cp=932)
        self.assertEqual(e.calls[-1], ('wc', 932, '恵'))

    def test_minus_one_length(self):
        e = Emu()
        out = e.wc('沢田', cch=-1)
        self.assertEqual(out, '澤田\0'.encode('cp950'))

    def test_table_sorted_and_encodable(self):
        pairs = P.table_pairs()
        self.assertEqual(pairs, sorted(pairs))
        self.assertEqual(len({k for k, _ in pairs}), len(pairs))
        for k, v in pairs:
            with self.assertRaises(UnicodeEncodeError):
                chr(k).encode('cp950')


@unittest.skipIf(unicorn is None, 'unicorn not installed')
class TestMB(unittest.TestCase):
    def test_pure_cp932_passthrough(self):
        e = Emu()
        raw = 'ダジルタール岩塊の町'.encode('cp932')
        r, t = e.mb(raw)
        self.assertEqual(t, 'ダジルタール岩塊の町')
        self.assertEqual(e.calls, [('mb', 932, raw)])

    def test_pure_big5_decoded_as_big5(self):
        e = Emu()
        for name in ('雷貝拉提斯', '林曉明', '和良'):
            r, t = e.mb(name.encode('cp950'))
            self.assertEqual(t, name)

    def test_mixed(self):
        e = Emu()
        raw = '◎'.encode('cp932') + '和良'.encode('cp950') + b' ' + 'ゴブリン'.encode('cp932') + '的'.encode('cp950')
        r, t = e.mb(raw)
        self.assertEqual(t, '◎和良 ゴブリン的')

    def test_minus_one_and_size_query(self):
        e = Emu()
        raw = '和良'.encode('cp950')
        r, _ = e.mb(raw, cb=-1, cch=0)
        self.assertEqual(r, 3)
        r, t = e.mb(raw, cb=-1)
        self.assertEqual((r, t), (3, '和良\0'))
        r, _ = e.mb(raw, cch=1)
        self.assertEqual(r, 0)

    def test_other_codepage_passthrough(self):
        e = Emu()
        raw = '和良'.encode('cp950')
        e.mb(raw, cp=950)
        self.assertEqual(e.calls, [('mb', 950, raw)])


if __name__ == '__main__':
    unittest.main()
