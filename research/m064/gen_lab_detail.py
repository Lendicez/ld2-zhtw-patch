r"""m064 lab：角色詳情視窗字串（稱號／特徵／狀態）原位 Big5 目錄產生器。

這些字串由字型 A／B（charset_patch 改 CHINESEBIG5 後）繪製，必須同步改 Big5，否則亂碼。
輸入只有 offset→繁中（本檔 ZH），原文槽 sha256／長度／合約一律由使用者的 pristine EXE 讀出，
本庫不含原文。輸出格式同 lab-places.zh-TW.json，供 build_lab（rdata_ansi）使用。

  python gen_lab_detail.py --exe pristine\Ld95.exe --out lab-detail.zh-TW.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rdata_ansi as R  # noqa: E402

# 稱號（.rdata，依能力值選出，顯示於詳情名字欄：稱號＋名字）
EPITHET = {
    0x12e800: '鮮豔濁瞳', 0x12e810: '瘋狂美貌', 0x12e81c: '黑銀微笑', 0x12e82c: '鮮烈闇姿', 0x12e838: '水映之月',
    0x12e844: '迷人美男', 0x12e850: '美麗肉體', 0x12e85c: '美裝清人', 0x12e868: '美形的', 0x12e870: '豔麗肌膚',
    0x12e87c: '纖細指尖', 0x12e888: '美麗眼瞳', 0x12e894: '月斬流星', 0x12e8a0: '黑色子彈', 0x12e8ac: '炎嵐閃電',
    0x12e8b8: '神速的', 0x12e8c0: '雷電', 0x12e8c8: '蒼色旋風', 0x12e8d4: '疾風的', 0x12e8dc: '慾望之知',
    0x12e8e8: '邪思考的', 0x12e8f4: '真實探求者', 0x12e904: '智慧守門人', 0x12e910: '賢人', 0x12e918: '求知者',
    0x12e928: '無所不知的', 0x12e938: '活辭典', 0x12e944: '肌肉惡塊', 0x12e950: '黑鋼肌肉', 0x12e95c: '勇敢大力士',
    0x12e96c: '白銀肉體', 0x12e978: '戰慄肌肉', 0x12e984: '怪力的', 0x12e98c: '華麗肌肉', 0x12e998: '筋骨隆隆的',
    0x12e9a4: '湧現邪氣', 0x12e9b4: '黑暗精神', 0x12e9c0: '永久魔力的', 0x12e9cc: '無限魔法力', 0x12e9dc: '氣力充沛的',
    0x12e9e8: '氣之寶庫', 0x12e9f4: '氣力之泉', 0x12ea00: '精神力之源', 0x12ea0c: '倖存的', 0x12ea18: '百傷之男',
    0x12ea24: '不死之男', 0x12ea30: '沉靜巨岩', 0x12ea40: '持久之男', 0x12ea4c: '體力自豪的', 0x12ea58: '忍耐之男',
    0x12ea64: '體力狂人', 0x12ea70: '闇世創造者', 0x12ea80: '邪神', 0x12ea88: '死神之鐮', 0x12ea94: '惡魔化身',
    0x12eaa0: '神之鐵鎚', 0x12eaac: '聖人', 0x12eab4: '神力使用者', 0x12eac4: '神之右腦', 0x12ead0: '求道',
    0x12ead8: '求聖者', 0x12eae4: '邪之使者', 0x12eaf0: '暗黑僧侶', 0x12eafc: '志在成神者', 0x12eb0c: '愛之傳道者',
    0x12eb18: '神聖之光', 0x12eb24: '幸福使者', 0x12eb30: '神罰使徒', 0x12eb3c: '神之使者', 0x12eb48: '聽聞天聲',
    0x12eb54: '神之代行者', 0x12eb60: '慈悲之男', 0x12eb6c: '傳道師', 0x12eb74: '崇拜者', 0x12eb7c: '僧侶的',
    0x12eb84: '黑暗魔', 0x12eb8c: '暗黑魔人', 0x12eb98: '惡魔天才', 0x12eba4: '狂亂頭腦', 0x12ebb0: '操神秘之光',
    0x12ebc0: '閃光法術師', 0x12ebd0: '永恆之術', 0x12ebdc: '崇高賢人', 0x12ebec: '變貌之魔', 0x12ebf8: '瘋狂魔力',
    0x12ec04: '魔性之心', 0x12ec10: '瘋狂賢者', 0x12ec1c: '閃耀指尖', 0x12ec28: '清魔使者', 0x12ec34: '白色魔者',
    0x12ec40: '光之魔法師', 0x12ec50: '魔知的', 0x12ec58: '不可思議之力', 0x12ec68: '操控魔法', 0x12ec74: '魔法師的',
    0x12ec80: '魔技師的', 0x12ec8c: '魔法使用者', 0x12ec9c: '施術者', 0x12eca4: '魔術師的', 0x12ecb0: '暗黑之鷹',
    0x12ecbc: '黑暗隼', 0x12ecc4: '暗黑街支配者', 0x12ecd4: '沉默暗殺者', 0x12ece4: '榮光快手', 0x12ecf0: '大盜賊',
    0x12ecf8: '擁有神之手', 0x12ed08: '兵貴神速的', 0x12ed14: '黑暗指尖', 0x12ed20: '神速之蠅', 0x12ed2c: '黑亮蜘蛛',
    0x12ed38: '惡盜賊', 0x12ed40: '白鯊', 0x12ed48: '銀狼', 0x12ed50: '看透黑暗', 0x12ed60: '義賊的',
    0x12ed68: '快手的', 0x12ed70: '速戰速決的', 0x12ed7c: '旋風的', 0x12ed84: '電光石火的', 0x12ed90: '貓之瞳',
    0x12ed98: '奔走暗夜', 0x12eda4: '竊賊', 0x12edac: '盜賊的', 0x12edb4: '黑騎士', 0x12edbc: '死神保鏢',
    0x12edcc: '暗黑戰神', 0x12edd8: '破壞王', 0x12ede0: '勇者', 0x12ede8: '榮光戰歷', 0x12edf4: '善良不敗鬥士',
    0x12ee04: '光之騎士', 0x12ee10: '邪戰士', 0x12ee18: '黑暗戰士', 0x12ee24: '劍拔弩張的', 0x12ee30: '狼子野心的',
    0x12ee3c: '快刀', 0x12ee44: '一閃光芒', 0x12ee50: '劍神', 0x12ee58: '白之戰士', 0x12ee64: '蒼瞳之虎',
    0x12ee70: '飛龍的', 0x12ee78: '我流的', 0x12ee80: '信戰的', 0x12ee88: '戰鬥輓歌', 0x12ee94: '特攻狂人',
    0x12eea0: '戰鬥的', 0x12eea8: '戰士的', 0x12eeb0: '放蕩無賴', 0x12eebc: '浪跡天涯的', 0x12eec8: '飛龍乘雲',
    0x12eed4: '雷之探險家', 0x12eee0: '風暴冒險者', 0x12eeec: '不滅旅人', 0x12eef8: '冒險狂人', 0x12ef04: '自由人的',
    0x12ef10: '永遠的浪人', 0x12ef20: '浪蕩人', 0x12ef28: '流雲', 0x12ef30: '流浪的', 0x12ef38: '漂泊的',
    0x12ef44: '探險家的', 0x12ef50: '不要命的', 0x12ef5c: '冒險者的', 0x12ef68: '武術達人', 0x12ef78: '魔術達人',
    0x12ef88: '忍術達人', 0x12f2c8: '武術達人', 0x12f2d4: '魔術達人', 0x12f2e0: '忍術達人',
}
# 狀態（.rdata）
STATUS = {
    0x12eff8: '正常', 0x12f000: '越獄', 0x12f008: '逃亡', 0x12f010: '通緝犯', 0x12f018: '護衛', 0x12f020: '救出',
    0x12f028: '綁架', 0x12f030: '死亡',
}
# 特徵（.data，17 bytes 槽）
TRAIT = {
    0x345c0b: '圓圓大眼', 0x345c1c: '銳眼', 0x345c2d: '單眼皮', 0x345c3e: '雙眼皮', 0x345c4f: '獨眼',
    0x345c60: '高鼻樑', 0x345c71: '塌鼻子', 0x345c82: '薄嘴唇', 0x345c93: '厚嘴唇', 0x345ca4: '虎牙',
    0x345cb5: '福耳', 0x345cc6: '美聲', 0x345cd7: '高嗓音', 0x345ce8: '低嗓音', 0x345cf9: '長手指',
    0x345d0a: 'O型腿', 0x345d1b: '內八字', 0x345d2c: '長腿', 0x345d3d: '短腿', 0x345d4e: '細腿',
    0x345d5f: '粗腿', 0x345d70: '黑痣', 0x345d81: '傷疤', 0x345d92: '眼鏡', 0x345da3: '酒窩',
    0x345db4: '潔癖', 0x345dc5: '素食主義', 0x345dd6: '愛做菜', 0x345de7: '愛乾淨', 0x345df8: '美食家',
    0x345e09: '味覺遲鈍', 0x345e1a: '愛喝酒', 0x345e2b: '酒品差', 0x345e3c: '講話快', 0x345e4d: '音痴',
    0x345e5e: '愛炫耀', 0x345e6f: '嚴謹', 0x345e80: '邋遢', 0x345e91: '長髮', 0x345ea2: '捲髮',
    0x345eb3: '硬髮',
}
GROUPS = (('epithet', EPITHET), ('status', STATUS), ('trait', TRAIT))


def build(exe: bytes) -> dict:
    items = []
    for sub, table in GROUPS:
        for off, zh in sorted(table.items()):
            end = exe.index(b'\0', off)
            src = exe[off:end]
            if off and exe[off - 1] != 0:
                raise ValueError(f'{off:#x} not at string start')
            enc = zh.encode('cp950')
            if len(enc) > len(src):
                raise ValueError(f'{off:#x} over capacity {len(enc)}>{len(src)}')
            items.append({
                'category': 'runtime_ansi', 'subcategory': f'detail_{sub}', 'file_offset': off,
                'file_offset_hex': hex(off), 'source_bytes_len': len(src),
                'source_name_sha256': hashlib.sha256(src).hexdigest(),
                'source_name_contract': R.zh_contract(src.decode('cp932')),
                'text_zh_tw': zh, 'text_cp950_bytes_len': len(enc), 'text_cp950_hex': enc.hex(),
                'name_cp950_encodable': True, 'fits_capacity': True,
                'capacity_slack_bytes': len(src) - len(enc), 'review_status': 'claude_lab_candidate',
                'translation_method': 'claude', 'site_binding': 'character detail window (fonts A/B)', 'note': sub})
    return {'schema_version': 1, 'milestone': 'm064-lab-detail', 'source_sha256': hashlib.sha256(exe).hexdigest(),
            'production_can_apply': False, 'release_approved': False, 'rendering_verified': False,
            'preview_only': True, 'draft_owner': 'Claude',
            'note': 'Detail window epithet/status/trait tables; drawn with SHIFTJIS fonts A/B -> pair with charset_patch.py.',
            'item_count': len(items), 'mona_approved_candidate': False, 'site_binding_confirmed': False, 'items': items}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--out', required=True)
    x = ap.parse_args(argv)
    doc = build(Path(x.exe).read_bytes())
    Path(x.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), 'utf-8')
    print(doc['item_count'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
