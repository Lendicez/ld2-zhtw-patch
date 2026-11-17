import unittest
import kbcapture_patch as K

try:
    import unicorn
    from unicorn import x86_const as X
except ImportError:
    unicorn = None

TA, GC, RC = 0x5253c4, 0x525590, 0x5255ec
STUB = 0x500000


@unittest.skipIf(unicorn is None, 'unicorn 未安裝')
class T(unittest.TestCase):
    def run_stub(self, msg, vk, captured):
        """回傳（是否呼叫 ReleaseCapture、最後跳到的位址、esp 是否保持）。"""
        mu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
        mu.mem_map(0x500000, 0x1000); mu.mem_map(0x525000, 0x1000); mu.mem_map(0x600000, 0x10000); mu.mem_map(0x700000, 0x1000)
        mu.mem_write(STUB, K.stub(TA, GC, RC))
        # 匯入表：GetCapture→0x700000，ReleaseCapture→0x700010，TranslateAcceleratorA→0x700020
        for iat, fn in ((GC, 0x700000), (RC, 0x700010), (TA, 0x700020)):
            mu.mem_write(iat, fn.to_bytes(4, 'little'))
        mu.mem_write(0x700000, b'\xb8' + (0x1234 if captured else 0).to_bytes(4, 'little') + b'\xc3')   # mov eax,x ; ret
        mu.mem_write(0x700010, b'\xc7\x05\x00\x08\x70\x00\x01\x00\x00\x00\xc3')                        # mov [0x700800],1 ; ret
        mu.mem_write(0x700020, b'\xf4')
        lp = 0x608000
        mu.mem_write(lp, (0x99).to_bytes(4, 'little') + msg.to_bytes(4, 'little') + vk.to_bytes(4, 'little'))
        sp = 0x60f000
        mu.mem_write(sp, b''.join(x.to_bytes(4, 'little') for x in (0xdeadbeef, 0x11, 0x22, lp)))
        mu.reg_write(X.UC_X86_REG_ESP, sp)
        mu.emu_start(STUB, 0x700020, count=200)
        released = int.from_bytes(mu.mem_read(0x700800, 4), 'little') == 1
        return released, mu.reg_read(X.UC_X86_REG_EIP), mu.reg_read(X.UC_X86_REG_ESP) == sp

    def test_cases(self):
        for vk in (0x25, 0x26, 0x27, 0x28, 0x61, 0x65, 0x69):
            self.assertEqual(self.run_stub(0x100, vk, True), (True, 0x700020, True), hex(vk))
            self.assertEqual(self.run_stub(0x100, vk, False), (False, 0x700020, True), hex(vk))
        for vk in (0x24, 0x29, 0x60, 0x6a, 0x4e, 0x0d):
            self.assertEqual(self.run_stub(0x100, vk, True), (False, 0x700020, True), hex(vk))
        for msg in (0x101, 0x104, 0x102):
            self.assertEqual(self.run_stub(msg, 0x26, True), (False, 0x700020, True), hex(msg))


if __name__ == '__main__':
    unittest.main()
