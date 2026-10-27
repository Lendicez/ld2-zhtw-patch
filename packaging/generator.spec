# Only source modules plus four reviewed UTF-8 JSON files are bundled.
import os
from pathlib import Path

root = Path(SPECPATH).parent
mode = os.environ.get('LD2_BUNDLE_MODE', 'onefile')
if mode not in ('onedir', 'onefile'):
    raise ValueError('Unsupported bundle mode')
datas = [(str(root / 'patches' / name), 'ld2patch/data') for name in
         ('m020-recipe.json', 'ui-m020.zh-TW.json', 'versions.json', 'steam-product.json')]
a = Analysis([str(root / 'tools/generator_entry.py')], pathex=[str(root / 'src')],
             binaries=[], datas=datas, hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['unittest'], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
options = dict(name='ld2-patch-generator', debug=False, bootloader_ignore_signals=False,
               strip=False, upx=False, console=True, uac_admin=False, uac_uiaccess=False,
               manifest=str(root / 'packaging/as-invoker.manifest'))
if mode == 'onefile':
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **options)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **options)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ld2-patch-generator')
