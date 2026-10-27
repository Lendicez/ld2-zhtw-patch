"""Build the reviewed m040 geometry candidate into a new directory; never execute it."""
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ld2patch.deadline_layout import build_layout
from ld2patch.patch_engine import _safe_path,strict_json
from ld2patch.pe_resources import MAX_FILE,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path)
    p.add_argument('--out-dir',required=True,type=Path)
    a=p.parse_args()
    source=_safe_path(a.source,True);out=_safe_path(a.out_dir,False)
    if out.exists() or out.is_relative_to(source.parent):
        raise ValueError('Fresh output directory outside original required')
    _safe_path(out.parent,True)
    with source.open('rb') as f:
        before=os.fstat(f.fileno())
        if before.st_nlink!=1 or before.st_size>MAX_FILE:raise ValueError('Source size/link')
        data=f.read(MAX_FILE+1)
        d=ROOT/'patches/m038'
        built=build_layout(data,(d/'catalog.json').read_bytes(),
                           strict_json((d/'versions.json').read_bytes()),
                           strict_json((d/'recipe.json').read_bytes()))
        f.seek(0)
        if f.read(MAX_FILE+1)!=data or source.stat().st_ino!=before.st_ino:
            raise ValueError('Source changed during build')
        out.mkdir() # Exclusive creation; failure does not overwrite anything.
        for name,payload in [('Ld95.exe',built.output),('build.json',(json.dumps(built.metadata,sort_keys=True,indent=2)+'\n').encode())]:
            target=_safe_path(out/name,False)
            with target.open('xb') as w:w.write(payload);w.flush();os.fsync(w.fileno())
            if target.read_bytes()!=payload:raise ValueError('Artifact verification failed')
        f.seek(0)
        if f.read(MAX_FILE+1)!=data or source.read_bytes()!=data:raise ValueError('Original changed')
    print(json.dumps(built.metadata))

if __name__=='__main__':main()
