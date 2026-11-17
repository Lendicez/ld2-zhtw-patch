import unittest
import walk_patch as W

try:
    import capstone
except ImportError:
    capstone = None


class T(unittest.TestCase):
    def test_same_length(self):
        self.assertEqual(len(W.OLD), len(W.NEW))

    @unittest.skipIf(capstone is None, 'capstone 未安裝')
    def test_disasm(self):
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        ins = [(i.address, i.mnemonic, i.op_str) for i in md.disasm(W.NEW, W.VA)]
        text = '\n'.join(f'{m} {o}' for _, m, o in ins)
        self.assertIn('cmp dword ptr [ecx + 0x101a0], 0', text)
        self.assertIn('and dword ptr [ecx + 0xf160], 0', text)
        jne = next(a for a, m, o in ins if m == 'jne')
        jbe = next(a for a, m, o in ins if m == 'jbe')
        ret = next(a for a, m, o in ins if m == 'ret')
        self.assertEqual(int(next(o for a, m, o in ins if m == 'jne'), 16), ret)
        self.assertEqual(int(next(o for a, m, o in ins if m == 'jbe'), 16), ret)
        self.assertLess(ret + 3, W.VA + 48 + 1)

    @unittest.skipIf(capstone is None, 'capstone 未安裝')
    def test_semantics_emulated(self):
        try:
            import unicorn
            from unicorn import x86_const as X
        except ImportError:
            self.skipTest('unicorn 未安裝')
        for dirv, f160_after in ((0, 0), (1, 1), (4, 1), (5, 0), (8, 0), (0xd, 0), (0xe, 0)):
            mu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
            mu.mem_map(0x400000, 0x100000); mu.mem_map(0x10000000, 0x20000); mu.mem_map(0x20000000, 0x10000)
            mu.mem_write(W.VA, W.NEW)
            obj = 0x10000000
            mu.mem_write(obj + 0xf154, (3).to_bytes(4, 'little')); mu.mem_write(obj + 0xf160, (1).to_bytes(4, 'little'))
            sp = 0x20008000
            mu.mem_write(sp, (0x400000).to_bytes(4, 'little') + dirv.to_bytes(4, 'little'))   # 返回位址、參數
            mu.reg_write(X.UC_X86_REG_ESP, sp); mu.reg_write(X.UC_X86_REG_ECX, obj)
            mu.mem_write(0x400000, b'\xf4')
            mu.emu_start(W.VA, 0x400000, count=50)
            g = lambda d: int.from_bytes(mu.mem_read(obj + d, 4), 'little')
            self.assertEqual(g(0xf154), dirv); self.assertEqual(g(0xf158), 3); self.assertEqual(g(0xf160), f160_after, dirv)
            self.assertEqual(mu.reg_read(X.UC_X86_REG_ESP), sp + 8)
        # 忙碌（+0x101a0≠0）時不改任何欄位
        mu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
        mu.mem_map(0x400000, 0x100000); mu.mem_map(0x10000000, 0x20000); mu.mem_map(0x20000000, 0x10000)
        mu.mem_write(W.VA, W.NEW); obj = 0x10000000
        mu.mem_write(obj + 0x101a0, (1).to_bytes(4, 'little')); mu.mem_write(obj + 0xf160, (1).to_bytes(4, 'little'))
        sp = 0x20008000; mu.mem_write(sp, (0x400000).to_bytes(4, 'little') + (5).to_bytes(4, 'little'))
        mu.reg_write(X.UC_X86_REG_ESP, sp); mu.reg_write(X.UC_X86_REG_ECX, obj); mu.mem_write(0x400000, b'\xf4')
        mu.emu_start(W.VA, 0x400000, count=50)
        self.assertEqual(int.from_bytes(mu.mem_read(obj + 0xf154, 4), 'little'), 0)
        self.assertEqual(int.from_bytes(mu.mem_read(obj + 0xf160, 4), 'little'), 1)


if __name__ == '__main__':
    unittest.main()
