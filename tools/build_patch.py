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
    parser.add_argument('--profile',choices=['m020','m037','m038','m041'],default='m020')
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--metadata-out',type=Path,required=True)
    args=parser.parse_args()
    try:
        folder=ROOT/'patches' if args.profile=='m020' else ROOT/'patches'/args.profile
        recipe_name='m020-recipe.json' if args.profile=='m020' else 'recipe.json'
        catalog_name='ui-m020.zh-TW.json' if args.profile=='m020' else 'catalog.json'
        recipe=strict_json((folder/recipe_name).read_bytes())
        if recipe['catalog']!=catalog_name:raise ValueError('Unrecognized bundled catalog')
        metadata=build_to_paths(args.input,args.out,args.metadata_out,
                                (folder/catalog_name).read_bytes(),
                                strict_json((folder/'versions.json').read_bytes()),recipe)
    except (ValueError,OSError,KeyError) as exc:
        print(json.dumps({'status':'refused_or_failed','reason':str(exc),'installed':False}),file=sys.stderr)
        return 1
    print(json.dumps({'status':'built_only','output_sha256':metadata['output_sha256'],
                      'output_bytes':metadata['output_bytes'],'text_locations':metadata['text_locations'],
                      'production_can_apply':False,'executed':False}))
    return 0


if __name__=='__main__':raise SystemExit(main())
