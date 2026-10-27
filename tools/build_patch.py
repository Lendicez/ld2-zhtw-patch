"""Offline only: licensed input -> new EXE and asset-free metadata; never run it."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.patch_engine import build_to_paths,strict_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--metadata-out',type=Path,required=True)
    args=parser.parse_args()
    try:
        recipe=strict_json((ROOT/'patches/m020-recipe.json').read_bytes())
        # The recipe's path is validated in build_patch; no arbitrary catalog CLI.
        if recipe['catalog']!='ui-m020.zh-TW.json':raise ValueError('Unrecognized bundled catalog')
        metadata=build_to_paths(args.input,args.out,args.metadata_out,
                                (ROOT/'patches/ui-m020.zh-TW.json').read_bytes(),
                                strict_json((ROOT/'patches/versions.json').read_bytes()),recipe)
    except (ValueError,OSError,KeyError) as exc:
        print(json.dumps({'status':'refused_or_failed','reason':str(exc),'installed':False}),file=sys.stderr)
        return 1
    print(json.dumps({'status':'built_only','output_sha256':metadata['output_sha256'],
                      'output_bytes':metadata['output_bytes'],'text_locations':metadata['text_locations'],
                      'production_can_apply':False,'executed':False}))
    return 0


if __name__=='__main__':raise SystemExit(main())
