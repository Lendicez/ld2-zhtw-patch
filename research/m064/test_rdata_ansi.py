"""m064 rdata_ansi 單元測試：只用合成 bytes，不含遊戲資料。"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rdata_ansi as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _slot(src: bytes, off: int, exe: bytearray) -> dict:
    exe[off:off + len(src)] = src
    exe[off + len(src)] = 0
    return {'file_offset': off, 'source_bytes_len': len(src), 'source_name_sha256': hashlib.sha256(src).hexdigest()}


def _item(base: dict, zh: str, contract: dict | None = None) -> dict:
    enc = zh.encode('cp950')
    return {**base, 'category': 'runtime_ansi', 'subcategory': 'synthetic', 'text_zh_tw': zh,
            'text_cp950_hex': enc.hex(),
            'source_name_contract': contract or R.zh_contract(zh), '_catalog': 'synthetic.json'}


class ContractTests(unittest.TestCase):
    def test_game_placeholders_merge_with_printf_in_order(self):
        c = R.zh_contract('%A的%d個「%B」\t%s')
        self.assertEqual(c['printf'], ['%A', '%d', '%B', '%s'])
        self.assertEqual(c['controls'], ['TAB'])
        self.assertEqual(c['other_percent'], 0)

    def test_extra_placeholder_is_mismatch(self):
        src = R.zh_contract('%A持有%B')
        self.assertNotEqual(R.zh_contract('%A持有%B於%E'), src)

    def test_shortcuts_int_and_list_normalize(self):
        a = R._norm_contract({'shortcuts': 0})
        b = R._norm_contract({'shortcuts': []})
        self.assertEqual(a, b)

    def test_real_catalog_contracts(self):
        """入庫 m063 catalog：合約不一致的列必須正好是已知的 0x166e28（多一個 %E）。"""
        pats = [str(ROOT / 'research' / 'translations' / 'm063-draft*.json')]
        try:
            items = R.load_items(pats)
        except FileNotFoundError:
            self.skipTest('no m063 catalogs')
        bad = [it['file_offset_hex'] for it in items
               if R._norm_contract(R.zh_contract(it['text_zh_tw'])) != R._norm_contract(it['source_name_contract'])]
        self.assertEqual(bad, ['0x166e28'])


class PlanApplyTests(unittest.TestCase):
    def setUp(self):
        self.exe = bytearray(b'\xAA' * 4096)
        # 合成 CP932 片假名區 bytes（非遊戲資料）
        self.s1 = _slot(bytes.fromhex('8341834283438345834683478348') + b'%d', 0x100, self.exe)
        self.s2 = _slot(bytes.fromhex('8349834a834b834c'), 0x200, self.exe)

    def test_apply_writes_cp950_and_nul_pad(self):
        items = [_item(self.s1, '可%d'), _item(self.s2, '確定')]
        p = R.plan(bytes(self.exe), items)
        self.assertEqual((p['ok'], p['skipped']), (2, 0))
        out = R.apply(bytes(self.exe), p)
        n1 = self.s1['source_bytes_len']
        self.assertEqual(out[0x100:0x100 + n1], '可%d'.encode('cp950') + b'\0' * (n1 - 4))
        self.assertEqual(out[0x100 + n1], 0)
        changed = [i for i in range(len(out)) if out[i] != self.exe[i]]
        self.assertTrue(all(0x100 <= i < 0x100 + n1 or 0x200 <= i < 0x208 for i in changed))

    def test_slot_sha_mismatch_skips(self):
        it = _item(self.s1, '可%d')
        it['source_name_sha256'] = '0' * 64
        p = R.plan(bytes(self.exe), [it])
        self.assertEqual(p['rows'][0]['reason'], 'source_slot_sha_mismatch')

    def test_over_capacity_skips(self):
        p = R.plan(bytes(self.exe), [_item(self.s2, '確定確定確定')])
        self.assertEqual(p['rows'][0]['reason'], 'over_capacity')

    def test_not_nul_terminated_skips(self):
        self.exe[0x208] = 0x41
        p = R.plan(bytes(self.exe), [_item(self.s2, '確定')])
        self.assertEqual(p['rows'][0]['reason'], 'slot_not_nul_terminated')

    def test_contract_mismatch_skips(self):
        it = _item(self.s1, '可%d', contract=R.zh_contract('可%d%d'))
        p = R.plan(bytes(self.exe), [it])
        self.assertEqual(p['rows'][0]['reason'], 'contract_mismatch')

    def test_not_cp950_skips(self):
        it = _item(self.s2, '確定')
        it['text_zh_tw'] = '確\U0001F600'  # emoji 不在 CP950
        p = R.plan(bytes(self.exe), [it])
        self.assertEqual(p['rows'][0]['reason'], 'not_cp950_encodable')

    def test_hex_mismatch_skips(self):
        it = _item(self.s2, '確定')
        it['text_cp950_hex'] = 'a4a4a4e5'
        p = R.plan(bytes(self.exe), [it])
        self.assertEqual(p['rows'][0]['reason'], 'cp950_hex_mismatch')

    def test_only_filter(self):
        items = [_item(self.s1, '可%d'), _item(self.s2, '確定')]
        p = R.plan(bytes(self.exe), items, only={0x200})
        self.assertEqual([r['offset'] for r in p['rows']], [0x200])

    def test_cli_refuses_overwrite_and_flags_false(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            exe = d / 'x.exe'
            exe.write_bytes(bytes(self.exe))
            cat = d / 'c.json'
            items = [{k: v for k, v in _item(self.s2, '確定').items() if not k.startswith('_')}]
            cat.write_text(json.dumps({'production_can_apply': False, 'release_approved': False, 'items': items}), 'utf-8')
            self.assertEqual(R.main(['apply', '--exe', str(exe), '--out', str(exe), '--catalog', str(cat)]), 2)
            out = d / 'o' / 'x.exe'
            man = d / 'm.json'
            self.assertEqual(R.main(['apply', '--exe', str(exe), '--out', str(out), '--catalog', str(cat), '--manifest', str(man)]), 0)
            m = json.loads(man.read_text('utf-8'))
            self.assertEqual((m['rows_applied'], m['production_can_apply'], m['lab_only']), (1, False, True))
            self.assertEqual(exe.read_bytes(), bytes(self.exe))  # 輸入未被改
            bad = d / 'bad.json'
            bad.write_text(json.dumps({'production_can_apply': True, 'release_approved': False, 'items': items}), 'utf-8')
            with self.assertRaises(ValueError):
                R.load_items([str(bad)])


if __name__ == '__main__':
    unittest.main()
