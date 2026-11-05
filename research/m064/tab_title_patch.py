r"""m064 lab：屬性表分頁標題（角色名）經 v4 人名查表轉繁中（設計：DESIGN-EQUIP-TAB.zh-TW.md）。

6 個屬性表以相同樣式設定頁標題：
    call 0x4ef7f3 ; mov ecx,esi (8b ce) ; mov [eax+0x14],edi (89 78 14) ; call 0x4ef7f3 ; or dword [eax+4],8
把中間 5 bytes（8b ce 89 78 14）換成 `call stub`。stub：
    mov ecx,esi ; pushad
    n = lstrlenA(edi)；1..64 才查
    units = LD2N_FindCopy(edi, n, WBUF)            ; v4 人名旗標（stdcall @12）
    k = WideCharToMultiByte(950, 0, WBUF, units, ABUF[slot], 71, 0, 0)；ABUF[slot][k] = 0
    title = 成功 ? ABUF[slot] : edi（原文）
    [psp+0x14] = title ; popad ; ret
8 格輪替緩衝（每格 72 B）放 `.ld2i` 可寫區尾端。只寫 lab 複本；production_can_apply=false。

輸入必須是 m063d v4 啟用版系列（`.ld2t` sha256 固定）。
  python tab_title_patch.py --exe in.exe --out out.exe
"""
import argparse, hashlib, json, struct, sys
from pathlib import Path

BASE = 0x400000
LD2T_SHA = 'f3501d3f2ce64c6a0110dde818ee115218a64f36b67cbc8a066c51c41464db6f'
LD2T_USED = 0x2b40
FINDCOPY = 0xae5a20
FINDCOPY_PROLOGUE = bytes.fromhex('558bec83ec1053568b75085785f60f84')
SITES_OR = (0x46c81e, 0x4705fe, 0x47c2fe, 0x481dfe, 0x49674e, 0x4b703e)   # `or dword [eax+4],8`
PSP_GETTER = 0x4ef7f3
STUB = 0xae5b40                       # .ld2t 剩餘空間（16 對齊）
WBUF, SLOT, ABUF = 0xb25400, 0xb25610, 0xb25620
SLOTS, SLOT_BYTES = 8, 72
WTMP, WTMP2, AFULL = 0xb25880, 0xb25980, 0xb25a80   # 半形→全形正規化暫存
CP950, CP932 = 950, 932
LCID_JA, LCMAP_FULLWIDTH = 0x411, 0x00800000


def sections(exe):
    pe = struct.unpack_from('<I', exe, 0x3c)[0]
    n = struct.unpack_from('<H', exe, pe + 6)[0]
    so = struct.unpack_from('<H', exe, pe + 20)[0]
    out = {}
    for i in range(n):
        h = pe + 24 + so + 40 * i
        name, vsz, va, rsz, raw = struct.unpack_from('<8sIIII', exe, h)
        out[name.rstrip(b'\0').decode('latin1')] = dict(hdr=h, vsz=vsz, va=va, rsz=rsz, raw=raw)
    return out, pe


def va2off(secs, va):
    rva = va - BASE
    for s in secs.values():
        if s['va'] <= rva < s['va'] + max(s['vsz'], s['rsz']):
            return s['raw'] + rva - s['va']
    raise ValueError(f'va {va:#x} not in any section')


def iat_slot(exe, secs, pe, dll, func):
    imp = struct.unpack_from('<I', exe, pe + 24 + 104)[0]
    o = va2off(secs, BASE + imp)

    def cstr(rva):
        p = va2off(secs, BASE + rva)
        return exe[p:exe.index(b'\0', p)].decode('latin1')
    while True:
        oft, _, _, name, ft = struct.unpack_from('<IIIII', exe, o)
        if not name:
            break
        if cstr(name).lower() == dll.lower():
            t = va2off(secs, BASE + (oft or ft)); k = 0
            while True:
                v = struct.unpack_from('<I', exe, t + 4 * k)[0]
                if not v:
                    break
                if not v & 0x80000000 and cstr(v + 2) == func:
                    return BASE + ft + 4 * k
                k += 1
        o += 20
    raise ValueError(f'import {dll}!{func} not found')


class Asm:
    def __init__(self, origin):
        self.org, self.b, self.labels, self.fix8, self.fix32 = origin, bytearray(), {}, [], []

    def emit(self, *parts):
        for p in parts:
            self.b += p if isinstance(p, (bytes, bytearray)) else bytes(p)

    def imm32(self, v): return struct.pack('<I', v & 0xffffffff)
    def here(self): return self.org + len(self.b)
    def label(self, name): self.labels[name] = self.here()

    def jcc8(self, op, name):
        self.emit([op, 0]); self.fix8.append((len(self.b) - 1, name))

    def jcc32(self, op, name):
        self.emit([0x0F, op, 0, 0, 0, 0]); self.fix32.append((len(self.b) - 4, name))

    def call_rel(self, target):
        self.emit([0xE8], struct.pack('<i', target - (self.here() + 5)))

    def call_ind(self, slot): self.emit([0xFF, 0x15], self.imm32(slot))

    def finish(self):
        for pos, name in self.fix8:
            rel = self.labels[name] - (self.org + pos + 1)
            if not -128 <= rel <= 127:
                raise ValueError('rel8 out of range')
            self.b[pos] = rel & 0xff
        for pos, name in self.fix32:
            struct.pack_into('<i', self.b, pos, self.labels[name] - (self.org + pos + 4))
        return bytes(self.b)


DBG = 0xb25600   # --debug：+0 name ptr，+0x14 呼叫次數，+0x18 strlen，+0x1c FindCopy units


def build_stub(lstrlen_slot, wctmb_slot, mbtwc_slot, lcmap_slot, origin=STUB, findcopy=FINDCOPY,
               wbuf=WBUF, slot=SLOT, abuf=ABUF, debug=False):
    """v2：查表前先把名字正規化成全形（屬性表標題用半形片假名，如「ﾀﾞｼﾞﾙﾀｰﾙ」）。"""
    a = Asm(origin)
    JZ, JA = 0x84, 0x87
    a.emit([0x8B, 0xCE])                         # mov ecx,esi (原指令)
    a.emit([0x60])                               # pushad
    if debug:
        a.emit([0xFF, 0x05], a.imm32(DBG + 0x14))   # inc dword [DBG+0x14]
        a.emit([0x89, 0x3D], a.imm32(DBG))          # mov [DBG],edi
    a.emit([0x89, 0xFE])                         # mov esi,edi
    a.emit([0x56]); a.call_ind(lstrlen_slot)     # n = lstrlenA(esi)
    if debug:
        a.emit([0xA3], a.imm32(DBG + 0x18))
    a.emit([0x85, 0xC0]); a.jcc32(JZ, 'fb')
    a.emit([0x83, 0xF8, 0x40]); a.jcc32(JA, 'fb')
    # w = MultiByteToWideChar(932, 0, esi, n, WTMP, 128)
    a.emit([0x68], a.imm32(128), [0x68], a.imm32(WTMP), [0x50, 0x56, 0x6A, 0x00], [0x68], a.imm32(CP932))
    a.call_ind(mbtwc_slot)
    a.emit([0x85, 0xC0]); a.jcc32(JZ, 'fb')
    # w2 = LCMapStringW(0x411, LCMAP_FULLWIDTH, WTMP, w, WTMP2, 128)
    a.emit([0x68], a.imm32(128), [0x68], a.imm32(WTMP2), [0x50], [0x68], a.imm32(WTMP),
           [0x68], a.imm32(LCMAP_FULLWIDTH), [0x68], a.imm32(LCID_JA))
    a.call_ind(lcmap_slot)
    a.emit([0x85, 0xC0]); a.jcc32(JZ, 'fb')
    # m = WideCharToMultiByte(932, 0, WTMP2, w2, AFULL, 72, 0, 0)
    a.emit([0x6A, 0x00, 0x6A, 0x00, 0x6A, SLOT_BYTES], [0x68], a.imm32(AFULL), [0x50], [0x68], a.imm32(WTMP2),
           [0x6A, 0x00], [0x68], a.imm32(CP932))
    a.call_ind(wctmb_slot)
    a.emit([0x85, 0xC0]); a.jcc32(JZ, 'fb')
    a.emit([0x83, 0xF8, 0x40]); a.jcc32(JA, 'fb')
    a.emit([0xC6, 0x80], a.imm32(AFULL), [0x00])  # mov byte [eax+AFULL],0
    # units = LD2N_FindCopy(AFULL, m, WBUF)
    a.emit([0x68], a.imm32(wbuf), [0x50], [0x68], a.imm32(AFULL))
    a.call_rel(findcopy)
    if debug:
        a.emit([0xA3], a.imm32(DBG + 0x1c))
    a.emit([0x85, 0xC0]); a.jcc32(JZ, 'fb')
    a.emit([0x8B, 0x1D], a.imm32(slot))          # mov ebx,[SLOT]
    a.emit([0x43, 0x83, 0xE3, SLOTS - 1])        # inc ebx; and ebx,7
    a.emit([0x89, 0x1D], a.imm32(slot))          # mov [SLOT],ebx
    a.emit([0x6B, 0xDB, SLOT_BYTES])             # imul ebx,ebx,72
    a.emit([0x81, 0xC3], a.imm32(abuf))          # add ebx,ABUF
    a.emit([0x6A, 0x00, 0x6A, 0x00, 0x6A, SLOT_BYTES - 1, 0x53, 0x50])   # 0,0,71,ebx,units
    a.emit([0x68], a.imm32(wbuf), [0x6A, 0x00], [0x68], a.imm32(CP950))  # WBUF,0,950
    a.call_ind(wctmb_slot)
    a.emit([0x85, 0xC0]); a.jcc32(JZ, 'fb')
    a.emit([0xC6, 0x04, 0x03, 0x00])             # mov byte [ebx+eax],0
    a.emit([0x89, 0xDF])                         # mov edi,ebx
    a.jcc8(0xEB, 'done')
    a.label('fb'); a.emit([0x89, 0xF7])          # mov edi,esi
    a.label('done')
    a.emit([0x8B, 0x44, 0x24, 0x1C])             # mov eax,[esp+0x1c]（pushad 存的 eax＝psp）
    a.emit([0x89, 0x78, 0x14])                   # mov [eax+0x14],edi
    a.emit([0x61, 0xC3])                         # popad; ret
    return a.finish()


def patch(exe: bytes, debug=False):
    secs, pe = sections(exe)
    t, i = secs['.ld2t'], secs['.ld2i']
    if hashlib.sha256(exe[t['raw']:t['raw'] + LD2T_USED]).hexdigest() != LD2T_SHA:
        raise ValueError('.ld2t is not the pinned m063d v4 helper image')
    fc = va2off(secs, FINDCOPY)
    if exe[fc:fc + len(FINDCOPY_PROLOGUE)] != FINDCOPY_PROLOGUE:
        raise ValueError('LD2N_FindCopy prologue mismatch')
    lstrlen = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'lstrlenA')
    wctmb = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'WideCharToMultiByte')
    mbtwc = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'MultiByteToWideChar')
    lcmap = iat_slot(exe, secs, pe, 'KERNEL32.dll', 'LCMapStringW')
    stub = build_stub(lstrlen, wctmb, mbtwc, lcmap, debug=debug)
    so = va2off(secs, STUB)
    end_rva = STUB - BASE + len(stub)
    if end_rva > t['va'] + t['rsz'] or any(exe[so:so + len(stub)]):
        raise ValueError('.ld2t cave not free')
    buf_end = AFULL + SLOT_BYTES
    if buf_end - BASE > i['va'] + i['rsz'] or any(exe[va2off(secs, WBUF):va2off(secs, buf_end)]):
        raise ValueError('.ld2i buffer area not free')
    if not WBUF < WBUF + 0x202 <= SLOT < ABUF + SLOTS * SLOT_BYTES <= WTMP < WTMP + 0x100 <= WTMP2 < WTMP2 + 0x100 <= AFULL:
        raise AssertionError('buffer layout overlap')
    out = bytearray(exe)
    out[so:so + len(stub)] = stub
    sites = []
    for orv in SITES_OR:
        call1, mid, call2 = orv - 15, orv - 10, orv - 5
        o = va2off(secs, mid)
        ok = (exe[va2off(secs, call1)] == 0xE8 and exe[va2off(secs, call2)] == 0xE8
              and exe[o:o + 5] == bytes.fromhex('8bce897814')
              and exe[va2off(secs, orv):va2off(secs, orv) + 4] == bytes.fromhex('83480408'))
        for c in (call1, call2):
            co = va2off(secs, c)
            ok = ok and c + 5 + struct.unpack_from('<i', exe, co + 1)[0] == PSP_GETTER
        if not ok:
            raise ValueError(f'site {orv:#x}: unexpected bytes')
        out[o] = 0xE8
        struct.pack_into('<i', out, o + 1, STUB - (mid + 5))
        sites.append(hex(mid))
    struct.pack_into('<I', out, t['hdr'] + 8, max(t['vsz'], end_rva - t['va']))
    struct.pack_into('<I', out, i['hdr'] + 8, max(i['vsz'], buf_end - BASE - i['va']))
    return bytes(out), {'stub_va': hex(STUB), 'stub_len': len(stub), 'sites': sites,
                        'lstrlenA_iat': hex(lstrlen), 'WideCharToMultiByte_iat': hex(wctmb),
                        'stub_hex': stub.hex()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--debug', action='store_true', help='在 .ld2i 0xb25600 記錄呼叫次數／名字指標／長度／FindCopy 結果')
    x = ap.parse_args(argv)
    if Path(x.exe).resolve() == Path(x.out).resolve():
        print('拒絕覆寫輸入 EXE', file=sys.stderr); return 2
    exe = Path(x.exe).read_bytes()
    out, info = patch(exe, x.debug)
    Path(x.out).write_bytes(out)
    info.update(input_sha256=hashlib.sha256(exe).hexdigest(), output_sha256=hashlib.sha256(out).hexdigest(),
                lab_only=True, production_can_apply=False)
    print(json.dumps(info, ensure_ascii=False)); return 0


if __name__ == '__main__':
    sys.exit(main())
