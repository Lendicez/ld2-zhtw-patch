# Only source modules, runtime and reviewed profile JSON files are bundled.
import os
from pathlib import Path

root = Path(SPECPATH).parent
mode = os.environ.get('LD2_BUNDLE_MODE', 'onefile')
if mode not in ('onedir', 'onefile'):
    raise ValueError('Unsupported bundle mode')
datas = [(str(root / 'patches' / name), 'ld2patch/data') for name in
         ('m020-recipe.json', 'ui-m020.zh-TW.json', 'versions.json', 'steam-product.json')]
for profile in ('m037', 'm038', 'm041', 'm042', 'm045'):
    datas.extend((str(root / 'patches' / profile / name), 'ld2patch/data/' + profile)
                 for name in ('recipe.json', 'catalog.json', 'versions.json'))
trial_policy = os.environ.get('LD2_TRIAL_POLICY')
if trial_policy:
    datas.append((trial_policy, 'ld2patch/data'))
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
