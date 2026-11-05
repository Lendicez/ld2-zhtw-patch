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

# 稱號 A（女性／複合職業，0x12dde0–0x12e7f4）
EPITHET_A = {
    0x12dde0: '神之傀儡魔女', 0x12ddf0: '聖魔之知', 0x12ddfc: '詠唱魔法尼僧', 0x12de0c: '盜賊女僧侶', 0x12de1c: '隱忍女盜賊',
    0x12de2c: '虔誠女盜賊', 0x12de3c: '為神而盜', 0x12de4c: '竊盜魔女', 0x12de58: '魔隼', 0x12de60: '神秘之影', 0x12de6c: '施魔術女盜賊',
    0x12de7c: '神聖女騎士', 0x12de8c: '神龍', 0x12de94: '慈悲雌虎', 0x12dea4: '聽聞神聲鬥士', 0x12deb4: '戰鬥女術士', 0x12dec4: '魔法戰姬',
    0x12ded0: '博學鬥騎', 0x12dedc: '鬥神術士', 0x12deec: '闇瞳女劍士', 0x12defc: '英勇之隼', 0x12df08: '銳喙黑鷲', 0x12df14: '銀光鬥將',
    0x12df20: '黑暗笑顏', 0x12df2c: '撩人闇少女', 0x12df3c: '黑暗麗人', 0x12df48: '魔性美貌', 0x12df54: '秀麗美貌', 0x12df60: '寶石之淚',
    0x12df6c: '天使微笑', 0x12df7c: '絕世美女', 0x12df88: '麗人', 0x12df90: '永遠少女', 0x12df9c: '甜美旋律', 0x12dfa8: '疾風黑刃',
    0x12dfb8: '閃光之牙', 0x12dfc4: '光之旋律', 0x12dfd0: '神之閃光', 0x12dfdc: '敏捷少女', 0x12dfe8: '秀麗之風', 0x12dff4: '緋色龍捲',
    0x12e000: '風之女神', 0x12e00c: '魔之探求者', 0x12e018: '灰色頭腦', 0x12e024: '白色腦袋', 0x12e030: '神聖知識', 0x12e03c: '真實之女',
    0x12e048: '知之少女', 0x12e054: '智慧寶庫', 0x12e060: '學者型的', 0x12e06c: '捏碎之臂', 0x12e078: '擁有惡鬼之力', 0x12e088: '為世之腕力',
    0x12e098: '神之肌肉', 0x12e0a4: '力之女', 0x12e0ac: '美麗肌肉', 0x12e0b8: '怪力少女', 0x12e0c4: '鐵之豪腕', 0x12e0d0: '魔淫氣',
    0x12e0d8: '暗黑魔力塊', 0x12e0e8: '無盡聖魔力', 0x12e0f8: '不絕聖氣', 0x12e104: '氣力之姬', 0x12e110: '強大精神', 0x12e11c: '氣之渦',
    0x12e124: '絕大魔法力', 0x12e134: '黑暗體力', 0x12e140: '惡魔肉牆', 0x12e14c: '正義之盾', 0x12e158: '弱者守護人', 0x12e164: '不死之女',
    0x12e170: '無窮體力', 0x12e17c: '隱忍少女', 0x12e18c: '惡魔傳道女', 0x12e19c: '惡魔新娘', 0x12e1a8: '暗黑闇女神', 0x12e1b8: '魔性尼姬',
    0x12e1c4: '女神微笑', 0x12e1d4: '神秘光輝', 0x12e1e0: '神聖少女', 0x12e1ec: '神之左腦', 0x12e1f8: '暗黑女神', 0x12e204: '惡神僕從',
    0x12e210: '暗黑女僧侶', 0x12e220: '憤怒女神', 0x12e22c: '傳遞愛者', 0x12e238: '神聖之瞳', 0x12e244: '天使戀人', 0x12e250: '賜予幸福者',
    0x12e260: '背負光環', 0x12e26c: '全心奉神者', 0x12e27c: '擁有女神心', 0x12e28c: '知曉神意者', 0x12e29c: '慈愛少女', 0x12e2a8: '虔誠的',
    0x12e2b4: '尼僧', 0x12e2bc: '暗黑魔女', 0x12e2c8: '黑暗隱形衣', 0x12e2d8: '繼承邪惡之力', 0x12e2ec: '操狂喜之魔', 0x12e2fc: '指尖銀光',
    0x12e30c: '神聖魔女', 0x12e318: '操女神之光', 0x12e328: '榮光賢者', 0x12e334: '狂亂女神', 0x12e340: '黑暗魔女', 0x12e34c: '墮惡魔姬',
    0x12e35c: '魔性少女', 0x12e368: '精素魔操姬', 0x12e378: '純淨魔法', 0x12e388: '白色魔法少女', 0x12e398: '光之魔法', 0x12e3a4: '魔姬',
    0x12e3ac: '術少女', 0x12e3b4: '奇異的', 0x12e3c0: '無形波動', 0x12e3d0: '魔法師', 0x12e3dc: '魔女', 0x12e3e4: '女魔術師',
    0x12e3f0: '惡魔盜者', 0x12e3fc: '黑色爪刃', 0x12e408: '暗黑街之姬', 0x12e414: '闇中舞龍', 0x12e420: '真實盜賊', 0x12e42c: '正義之指',
    0x12e438: '洞察之瞳', 0x12e444: '女神之手', 0x12e450: '斬闇指尖', 0x12e460: '永遠流浪者', 0x12e470: '蜘蛛女', 0x12e478: '惡盜賊之女',
    0x12e484: '赤色鯊牙', 0x12e490: '白銀女狼', 0x12e49c: '疾馳暗夜', 0x12e4ac: '女義賊', 0x12e4b4: '四臂', 0x12e4c0: '敏捷指尖',
    0x12e4cc: '雷光石火的', 0x12e4d8: '急流', 0x12e4e4: '闇中生存之女', 0x12e4f4: '貓娘之瞳', 0x12e500: '女盜賊的', 0x12e50c: '死神之妻',
    0x12e518: '緋色闇騎士', 0x12e528: '暗黑鬥女神', 0x12e538: '破壞女神', 0x12e544: '榮光女戰士', 0x12e554: '光之女騎士', 0x12e560: '心眼的',
    0x12e568: '不畏死的', 0x12e574: '鬥影少女', 0x12e580: '邪道戰女', 0x12e590: '黑暗女戰士', 0x12e59c: '凝視戰鬥者', 0x12e5ac: '劍女神',
    0x12e5b4: '赤色光芒', 0x12e5c0: '白色女戰士', 0x12e5cc: '女劍士', 0x12e5d4: '戰之少女', 0x12e5e0: '紅虎', 0x12e5e8: '鬥爭的',
    0x12e5f0: '打頭陣的', 0x12e5fc: '為戰而生', 0x12e60c: '女戰士的', 0x12e618: '空中飛舞綿絮', 0x12e628: '漂泊落葉', 0x12e634: '流雲',
    0x12e640: '順從慾望', 0x12e64c: '流浪者', 0x12e658: '行者', 0x12e660: '黃昏的', 0x12e668: '永遠旅人', 0x12e674: '穿越時空',
    0x12e680: '自由少女', 0x12e690: '不要命的', 0x12e69c: '流水', 0x12e6a8: '清潔的', 0x12e6b0: '愛冒險的', 0x12e6bc: '雙手操魔',
    0x12e6cc: '操魔法僧侶', 0x12e6dc: '神聖魔法師', 0x12e6ec: '神仕魔術師', 0x12e6fc: '過道僧侶', 0x12e708: '竊盜僧侶', 0x12e714: '慈愛竊賊',
    0x12e720: '慈悲盜賊', 0x12e730: '盜賊賢者', 0x12e73c: '博學盜賊', 0x12e74c: '魔技竊賊', 0x12e758: '施魔法盜賊', 0x12e768: '崇拜之刃',
    0x12e774: '戰鬥傳道師', 0x12e780: '神風戰士', 0x12e78c: '受祝福戰士', 0x12e79c: '博學豪腕', 0x12e7ac: '戰鬥魔法師', 0x12e7bc: '粗暴術師',
    0x12e7cc: '魔法戰士的', 0x12e7d8: '鬥狼', 0x12e7e0: '疾風戰士', 0x12e7ec: '風之刃', 0x12e7f4: '盜賊戰士的',
}
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
# 性別（.rdata；0x173340 女、0x173344 男，程式直接引用）
GENDER = {0x173340: '女', 0x173344: '男'}
# 特徵（.data，17 bytes 槽）
TRAIT = {
    0x345c0b: '圓圓大眼', 0x345c1c: '銳眼', 0x345c2d: '單眼皮', 0x345c3e: '雙眼皮', 0x345c4f: '獨眼',
    0x345c60: '高鼻樑', 0x345c71: '塌鼻子', 0x345c82: '薄嘴唇', 0x345c93: '厚嘴唇', 0x345ca4: '虎牙',
    0x345cb5: '福耳', 0x345cc6: '美聲', 0x345cd7: '高嗓音', 0x345ce8: '低嗓音', 0x345cf9: '長手指',
    0x345d0a: 'O型腿', 0x345d1b: '內八字', 0x345d2c: '長腿', 0x345d3d: '短腿', 0x345d4e: '細腿',
    0x345d5f: '粗腿', 0x345d70: '黑痣', 0x345d81: '傷疤', 0x345d92: '眼鏡', 0x345da3: '酒窩',
    0x345db4: '潔癖', 0x345dc5: '素食主義', 0x345dd6: '愛做菜', 0x345de7: '愛乾淨', 0x345df8: '美食家',
    0x345e09: '味覺遲鈍', 0x345e1a: '愛喝酒', 0x345e2b: '酒瘋', 0x345e3c: '快嘴', 0x345e4d: '音痴',
    0x345e5e: '浮誇', 0x345e6f: '嚴謹', 0x345e80: '邋遢', 0x345e91: '長髮', 0x345ea2: '捲髮',
    0x345eb3: '硬髮',
}
EPITHET = {**EPITHET_A, **EPITHET}
EPITHET_TABLE = (0x349700, 0x34a2c0)  # .data {char* name; u32 flags} ×376
GROUPS = (('epithet', EPITHET), ('status', STATUS), ('gender', GENDER), ('trait', TRAIT))


def build(exe: bytes) -> dict:
    items = []
    for k in range(*EPITHET_TABLE, 8):
        o = int.from_bytes(exe[k:k + 4], 'little') - 0x400000
        if o not in EPITHET:
            raise ValueError(f'epithet table entry {k:#x} -> {o:#x} untranslated')
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
