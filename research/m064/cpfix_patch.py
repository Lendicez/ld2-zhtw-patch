r"""轉換收尾（1.0.7）：所有補丁小段程式的 MultiByteToWideChar／WideCharToMultiByte 呼叫改經兩個包裝。

擁有者回報（2026-11-25）：
1. 人名出現「?」（「女戰士的?奈」、委託人「吉岡 直?」）：日文漢字經 CP932 → UTF-16 → CP950 時，
   Big5 沒有的字（新字體「恵」「沢」「斉」、國字「榊」「峠」等）被 WideCharToMultiByte 換成「?」。
2. 「使用魔法」目標清單亂碼：名字本來就是 Big5（玩家自取的名字、已音譯後存檔的名字），
   m063 的整串查表清單 hook（0xae4b20／0xae4d40）把它當 CP932 解碼（Big5 位元組被拆成半形片假名）→「?p????」。

修法（附加在 .ld2i 尾，0x1000 程式＋對照表、0x2000 資料）：
- WC 包裝：CodePage = 950 時，先把 UTF-16 來源複製到暫存區並逐字查 `cp950_variants.json`
  （CP932 有、Big5 沒有的字 → Big5 可表示的對應字：恵→惠、沢→澤、斉→齊、榊→神…；二分搜尋），再呼叫系統函式。
- MB 包裝：CodePage = 932 時，先依 CP932 規則掃一遍；出現 CP932 不會有的位元組（0x80、0xA0–0xDF 或 0xF0–0xF9 當首位元組、
  0xFD–0xFF）就視為「Big5 夾 CP932」的混合字串，逐段解碼（與 savelist／MIXW 同規則）：0x81–0x9F 開頭的 CP932 段
  （續接 0x81–0x9F／0xE0–0xEA 首位元組）以 932、其餘（Big5 一字 2 位元組、ASCII）以 950。純 CP932 字串照舊。
- 只改 .ld2t／.ld2i（補丁自己的程式）中 `call [IAT]` 的呼叫點；遊戲原本的程式碼不動。

小段程式以 keystone 組譯；倉庫內存 `cpfix_stub.json`（BASE0 的位元組與絕對位址重定位表）。`python cpfix_patch.py --regen`。
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'src'))

IAT_MBTWC, IAT_WCTMB = 0x52537c, 0x525378
MAXW = 0x800            # 包裝處理的最大長度（UTF-16 單元／位元組）；超過就原樣交給系統
CODE_MAX = 0x1000
DATA_OFF, GROW = 0x1000, 0x3000
PATCH_SECTIONS = ('.ld2t', '.ld2i')
VARIANTS_JSON = HERE / 'cp950_variants.json'
STUB_JSON = HERE / 'cpfix_stub.json'
BASE0, BASE1 = 0x10000000, 0x20000000

ASM = r"""
; ===== MB 包裝：MultiByteToWideChar(cp, flags, src, cb, dst, cch)，stdcall ret 0x18 =====
mb_wrap:
    cmp dword ptr [esp+4], 932
    jne mb_real
    pushad
    mov esi, [esp+0x2c]
    test esi, esi
    jz mb_pass
    mov ecx, [esp+0x30]
    cmp ecx, -1
    jne mb_len
    mov edi, esi
mb_sl:
    cmp byte ptr [edi], 0
    je mb_sle
    inc edi
    jmp mb_sl
mb_sle:
    mov ecx, edi
    sub ecx, esi
mb_len:
    test ecx, ecx
    jle mb_pass
    cmp ecx, {MAXW}
    ja mb_pass
    lea edx, [esi+ecx]
    mov edi, esi
md_loop:
    cmp edi, edx
    jae mb_pass
    movzx eax, byte ptr [edi]
    cmp al, 0x80
    jb md_1
    je md_mix
    cmp al, 0x9f
    jbe md_2
    cmp al, 0xe0
    jb md_mix
    cmp al, 0xef
    jbe md_2
    cmp al, 0xfa
    jb md_mix
    cmp al, 0xfc
    jbe md_2
    jmp md_mix
md_1:
    inc edi
    jmp md_loop
md_2:
    add edi, 2
    jmp md_loop
md_mix:
    xor ebx, ebx
    mov edi, esi
sg_loop:
    cmp edi, edx
    jae sg_done
    movzx eax, byte ptr [edi]
    cmp al, 0x81
    jb sg_other
    cmp al, 0x9f
    ja sg_other
    mov ebp, edi
c9:
    cmp ebp, edx
    jae c9e
    movzx eax, byte ptr [ebp]
    cmp al, 0x81
    jb c9e
    cmp al, 0x9f
    jbe c9n
    cmp al, 0xe0
    jb c9e
    cmp al, 0xea
    ja c9e
c9n:
    add ebp, 2
    jmp c9
c9e:
    cmp ebp, edx
    jbe c9ok
    mov ebp, edx
c9ok:
    mov eax, 932
    jmp sg_dec
sg_other:
    mov ebp, edi
o9:
    cmp ebp, edx
    jae o9e
    movzx eax, byte ptr [ebp]
    cmp al, 0x81
    jb o9s
    cmp al, 0x9f
    jbe o9e
    cmp al, 0xa1
    jb o9s
    cmp al, 0xf9
    ja o9s
    lea eax, [ebp+1]
    cmp eax, edx
    jae o9s
    add ebp, 2
    jmp o9
o9s:
    inc ebp
    jmp o9
o9e:
    cmp ebp, edx
    jbe o9ok
    mov ebp, edx
o9ok:
    mov eax, 950
sg_dec:
    mov ecx, {MAXW}
    sub ecx, ebx
    jle mb_pass
    push ecx
    lea ecx, [ebx*2+{MWBUF}]
    push ecx
    mov ecx, ebp
    sub ecx, edi
    push ecx
    push edi
    push 0
    push eax
    call dword ptr [{IAT_MBTWC}]
    add ebx, eax
    mov edi, ebp
    jmp sg_loop
sg_done:
    cmp dword ptr [esp+0x30], -1
    jne sg_nn
    cmp ebx, {MAXW}
    jae mb_pass
    mov word ptr [ebx*2+{MWBUF}], 0
    inc ebx
sg_nn:
    mov ecx, [esp+0x38]
    test ecx, ecx
    jz sg_ret
    cmp ebx, ecx
    ja sg_small
    mov edi, [esp+0x34]
    mov esi, {MWBUF}
    mov ecx, ebx
    rep movsw
sg_ret:
    mov [esp+0x1c], ebx
    popad
    ret 0x18
sg_small:
    mov dword ptr [esp+0x1c], 0
    popad
    ret 0x18
mb_pass:
    popad
mb_real:
    jmp dword ptr [{IAT_MBTWC}]

; ===== WC 包裝：WideCharToMultiByte(cp, flags, wsrc, cch, dst, cb, def, used)，stdcall ret 0x20 =====
wc_wrap:
    cmp dword ptr [esp+4], 950
    jne wc_real
    pushad
    mov esi, [esp+0x2c]
    test esi, esi
    jz wc_pass
    mov ecx, [esp+0x30]
    cmp ecx, -1
    jne wc_len
    mov edi, esi
wc_sl:
    cmp word ptr [edi], 0
    je wc_sle
    add edi, 2
    jmp wc_sl
wc_sle:
    mov ecx, edi
    sub ecx, esi
    shr ecx, 1
    inc ecx
wc_len:
    test ecx, ecx
    jle wc_pass
    cmp ecx, {MAXW}
    ja wc_pass
    mov edi, {WBUF}
wc_loop:
    movzx eax, word ptr [esi]
    cmp eax, {LOWEST}
    jb wc_put
    xor ebx, ebx
    mov edx, {NTAB}
bs:
    cmp ebx, edx
    jae wc_put
    lea ebp, [ebx+edx]
    shr ebp, 1
    cmp ax, word ptr [ebp*4+{TAB}]
    je bs_hit
    jb bs_lo
    lea ebx, [ebp+1]
    jmp bs
bs_lo:
    mov edx, ebp
    jmp bs
bs_hit:
    movzx eax, word ptr [ebp*4+{TAB}+2]
wc_put:
    mov [edi], ax
    add esi, 2
    add edi, 2
    dec ecx
    jnz wc_loop
    mov dword ptr [esp+0x2c], {WBUF}
wc_pass:
    popad
wc_real:
    jmp dword ptr [{IAT_WCTMB}]
"""


def table_pairs():
    t = json.loads(VARIANTS_JSON.read_text('utf-8'))
    pairs = sorted((ord(k), ord(v)) for k, v in t.items() if len(k) == 1 and len(v) == 1 and ord(k) < 0x10000)
    for k, v in pairs:
        chr(v).encode('cp950')
    return pairs


def _layout(base: int, code_len: int):
    pairs = table_pairs()
    tab = base + ((code_len + 3) & ~3)
    return pairs, tab


def _asm_text(base: int, tab: int, n: int, lowest: int) -> str:
    m = dict(MAXW=hex(MAXW), MWBUF=hex(base + DATA_OFF), WBUF=hex(base + DATA_OFF + 2 * MAXW),
             IAT_MBTWC=hex(IAT_MBTWC), IAT_WCTMB=hex(IAT_WCTMB), TAB=hex(tab), NTAB=str(n), LOWEST=hex(lowest))
    src = ASM.format(**m)
    return '\n'.join(l.split(';')[0].rstrip() for l in src.splitlines())


def regen():
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    pairs = table_pairs(); n = len(pairs); lowest = pairs[0][0]

    def build(base):
        # 兩遍：先以暫定表位址量長度，再定位（長度不變）
        c0 = bytes(ks.asm(_asm_text(base, base + 0x800, n, lowest), base)[0])
        tab = base + ((len(c0) + 3) & ~3)
        c1 = bytes(ks.asm(_asm_text(base, tab, n, lowest), base)[0])
        assert len(c1) == len(c0)
        return c1, tab
    a, ta = build(BASE0)
    b, tb = build(BASE1)
    assert len(a) == len(b) and ta - BASE0 == tb - BASE1
    tab_off = ta - BASE0
    assert tab_off + 4 * n <= CODE_MAX, (tab_off, n)
    delta, relocs, i = BASE1 - BASE0, [], 0
    while i < len(a):
        if a[i] != b[i]:
            for k in range(4):
                p = i - k
                if p >= 0 and (struct.unpack_from('<I', b, p)[0] - struct.unpack_from('<I', a, p)[0]) & 0xffffffff == delta:
                    relocs.append(p); i = p + 4; break
            else:
                raise ValueError(f'非絕對位址差異 @ {i}')
            continue
        i += 1
    syms = {}
    for name in ('mb_wrap', 'wc_wrap'):
        enc, _ = ks.asm(_asm_text(BASE0, ta, n, lowest) + f'\n__probe: mov eax, {name}\n', BASE0)
        syms[name] = struct.unpack_from('<I', bytes(enc), len(enc) - 4)[0] - BASE0
    doc = {'base0': BASE0, 'hex': a.hex(), 'relocs': relocs, 'symbols': syms, 'table_off': tab_off, 'n': n}
    STUB_JSON.write_text(json.dumps(doc, indent=1) + '\n', 'utf-8')
    return doc


def load_stub(base: int):
    doc = json.loads(STUB_JSON.read_text('utf-8'))
    code = bytearray(bytes.fromhex(doc['hex']))
    for p in doc['relocs']:
        v = struct.unpack_from('<I', code, p)[0]
        struct.pack_into('<I', code, p, (v - doc['base0'] + base) & 0xffffffff)
    pairs = table_pairs()
    if len(pairs) != doc['n']:
        raise ValueError('cp950_variants.json 與 cpfix_stub.json 不一致，請 --regen')
    page = bytearray(GROW)
    page[:len(code)] = code
    t = doc['table_off']
    for k, (s, d) in enumerate(pairs):
        struct.pack_into('<HH', page, t + 4 * k, s, d)
    return bytes(page), {k: base + v for k, v in doc['symbols'].items()}


def patch(exe: bytes):
    from ld2patch.pe_resources import PE
    pe = PE(exe)
    last = max(pe.sections, key=lambda s: s['rp'])
    if last['name'] != '.ld2i' or len(exe) != last['rp'] + last['rs']:
        raise ValueError('.ld2i is not the file tail')
    stub_va = pe.base + last['va'] + last['rs']
    page, sym = load_stub(stub_va)
    out = bytearray(exe)
    sites = {'mb': [], 'wc': []}
    for s in pe.sections:
        if s['name'] not in PATCH_SECTIONS:
            continue
        for kind, slot, entry in (('mb', IAT_MBTWC, 'mb_wrap'), ('wc', IAT_WCTMB, 'wc_wrap')):
            pat = b'\xff\x15' + struct.pack('<I', slot)
            j = exe.find(pat, s['rp'], s['rp'] + s['rs'])
            while j >= 0:
                va = pe.base + s['va'] + (j - s['rp'])
                out[j:j + 6] = b'\xe8' + struct.pack('<i', sym[entry] - (va + 5)) + b'\x90'
                sites[kind].append(hex(va))
                j = exe.find(pat, j + 6, s['rp'] + s['rs'])
    if not sites['mb'] or not sites['wc']:
        raise ValueError('找不到補丁程式中的轉換呼叫點')
    out += page
    hdr = last['header']
    struct.pack_into('<I', out, hdr + 8, last['rs'] + GROW)
    struct.pack_into('<I', out, hdr + 16, last['rs'] + GROW)
    salign = struct.unpack_from('<I', out, pe.opt + 32)[0]
    struct.pack_into('<I', out, pe.opt + 56, (last['va'] + last['rs'] + GROW + salign - 1) // salign * salign)
    return bytes(out), {'stub_va': hex(stub_va), 'sites': sites, 'variants': len(table_pairs())}


if __name__ == '__main__':
    if '--regen' in sys.argv:
        d = regen(); print(len(d['hex']) // 2, 'bytes', len(d['relocs']), 'relocs', d['symbols'], 'table', d['table_off'], d['n'])
