"""Unelevated offline resource generator. Never installs or executes a game."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys

from .patch_engine import build_to_paths, strict_json

VERSION = '0.2.0-m031'


def elevated():
    if os.name != 'nt':
        return False
    # Membership in the enabled Administrators SID detects an elevated token.
    # This reads the current token; it does not request elevation or change it.
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def resource_root():
    bundled = Path(__file__).resolve().parent / 'data'
    return bundled if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2] / 'patches'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=f'ld2-patch-generator {VERSION}')
    parser.add_argument('--input', type=Path, required=True, help='Absolute path to the known original EXE; read only')
    parser.add_argument('--out', type=Path, required=True, help='New absolute output path outside the source directory')
    parser.add_argument('--metadata-out', type=Path, required=True, help='New JSON path beside the output')
    args = parser.parse_args(argv)
    try:
        if elevated():
            raise ValueError('Administrator execution refused; run normally without elevation')
        root = resource_root()
        recipe = strict_json((root / 'm020-recipe.json').read_bytes())
        if recipe.get('catalog') != 'ui-m020.zh-TW.json':
            raise ValueError('Unrecognized bundled catalog')
        metadata = build_to_paths(args.input, args.out, args.metadata_out,
                                  (root / 'ui-m020.zh-TW.json').read_bytes(),
                                  strict_json((root / 'versions.json').read_bytes()), recipe)
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({'status': 'refused_or_failed', 'reason': str(exc), 'installed': False,
                          'production_can_apply': False, 'executed': False}), file=sys.stderr)
        return 1
    print(json.dumps({'status': 'built_only', 'output_sha256': metadata['output_sha256'],
                      'output_bytes': metadata['output_bytes'], 'text_locations': metadata['text_locations'],
                      'production_can_apply': False, 'installed': False, 'executed': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
