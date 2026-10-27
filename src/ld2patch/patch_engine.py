"""Version-bound offline resource build. Never installs or executes its output."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat

from .catalog import build_bytes, validate_catalog
from .pe_resources import PE, MAX_FILE, align, checksum, need, sha, u16, u32, zfield
from .planner import _versions


def strict_json(data, limit=1024*1024):
    if not isinstance(data,bytes) or len(data)>limit:raise ValueError('JSON input budget/type')
    def pairs(values):
        result={}
        for key,value in values:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    try:
        return json.loads(data.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (UnicodeError,RecursionError) as exc:
        raise ValueError('Invalid/bounded JSON required') from exc


def file_versions(pe):
    versions=[]
    for r in pe.resources:
        if r['path'][0]!=16:continue
        raw=pe.payload(r)
        if u16(raw,0)!=len(raw) or u16(raw,2)!=52 or u16(raw,4)!=0:raise ValueError('Unsupported version root')
        key,p=zfield(raw,6);p=align(p);need(raw,p,52)
        if key.get('text')!='VS_VERSION_INFO' or u32(raw,p)!=0xfeef04bd or u32(raw,p+4)!=0x10000:
            raise ValueError('Invalid fixed file version')
        def text(at):
            ms,ls=u32(raw,at),u32(raw,at+4)
            return f'{ms>>16}.{ms&65535}.{ls>>16}.{ls&65535}'
        versions.append((text(p+8),text(p+16)))
    if not versions or len(set(versions))!=1:raise ValueError('Missing/ambiguous file version')
    return versions[0]


def resource_paths(cat):
    result=set()
    for e in cat['entries']:
        result.add((4 if e['kind']=='menu' else 6 if e['kind']=='string' else 5,e['resource'],e['language']))
    result.update((5,e['resource'],e['language']) for e in cat['dialog_fonts'])
    return result


def verify_resource_only(source, output, allowed_paths):
    """Prove unchanged original bytes except enumerated PE fields/entry pointers."""
    old,new=PE(source),PE(output)
    if len(output)<len(source) or len(old.sections)!=len(new.sections):raise ValueError('Unexpected output layout')
    before={tuple(r['path']):r for r in old.resources};after={tuple(r['path']):r for r in new.resources}
    if before.keys()!=after.keys():raise ValueError('Resource identity set changed')
    changed=[]
    for key,r in before.items():
        n=after[key]
        if old.payload(r)!=new.payload(n):
            if key not in allowed_paths or key[0] not in (4,5,6):raise ValueError('Unapproved resource changed')
            if n['offset']<len(source):raise ValueError('Changed resource was not appended')
            changed.append(key)
    s=old.sections[-1]
    fields=[(old.opt+8,4,'SizeOfInitializedData'),(old.opt+56,4,'SizeOfImage'),
            (old.opt+64,4,'CheckSum'),(old.opt+116,4,'ResourceDirectorySize'),
            (s['header']+8,4,'ResourceVirtualSize'),(s['header']+16,4,'ResourceRawSize')]
    ranges=[(p,p+n) for p,n,_ in fields]+[(before[k]['entry'],before[k]['entry']+8) for k in changed]
    ranges.sort();cursor=0
    for start,end in ranges:
        if start<cursor or end>len(source):raise ValueError('Overlapping allowed change ranges')
        if source[cursor:start]!=output[cursor:start]:raise ValueError('Bytes changed outside resource/header allowlist')
        cursor=end
    if source[cursor:]!=output[cursor:len(source)]:raise ValueError('Original tail changed outside allowlist')
    cursor=len(source)
    for start,end in sorted((after[k]['offset'],after[k]['offset']+after[k]['size']) for k in changed):
        if start<cursor or any(output[cursor:start]):raise ValueError('Unexpected appended bytes/overlap')
        cursor=end
    if any(output[cursor:]):raise ValueError('Unexpected output padding')
    checked=bytearray(output);checksum(checked,new.opt)
    if checked!=output:raise ValueError('Output checksum mismatch')
    sections=[]
    for a,b in zip(old.sections[:-1],new.sections[:-1]):
        if a!=b or source[a['rp']:a['rp']+a['rs']]!=output[b['rp']:b['rp']+b['rs']]:raise ValueError('Code/data section changed')
        sections.append({'name':a['name'],'bytes':a['rs'],'sha256':sha(source[a['rp']:a['rp']+a['rs']]),'unchanged':True})
    return {'non_resource_sections':sections,'resource_count':len(before),
            'changed_resource_paths':[list(k) for k in sorted(changed)],
            'allowed_header_fields':[name for _,_,name in fields],
            'original_prefix_verified_outside_allowlist':True,'appended_resource_and_zero_padding_only':True}


@dataclass(frozen=True)
class PatchBuild:
    output: bytes
    metadata: dict


def build_patch(source: bytes, catalog_bytes: bytes, versions: dict, recipe: dict) -> PatchBuild:
    if not isinstance(source,bytes) or not 256<=len(source)<=MAX_FILE:raise ValueError('Source bytes/size')
    fields={'schema_version','id','engine','version_id','catalog','catalog_sha256','text_locations','font_locations'}
    if not isinstance(recipe,dict) or set(recipe)!=fields or type(recipe['schema_version']) is not int or recipe['schema_version']!=1 or recipe['engine']!='resource_append_v1':
        raise ValueError('Unsupported recipe')
    if not isinstance(recipe['id'],str) or not re.fullmatch('[a-z0-9-]{1,64}',recipe['id']):raise ValueError('Recipe ID')
    if not isinstance(recipe['catalog'],str) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.json',recipe['catalog']):raise ValueError('Recipe catalog name')
    if not isinstance(versions,dict):raise ValueError('Versions object required')
    version=next((v for v in _versions(versions) if v['id']==recipe['version_id']),None)
    if version is None or version.get('catalog')!=recipe['catalog']:raise ValueError('Recipe/version mismatch')
    if sha(source)!=version['source_sha256'] or len(source)!=version['source_size']:raise ValueError('Unsupported original hash/size')
    if sha(catalog_bytes)!=recipe['catalog_sha256']:raise ValueError('Catalog recipe hash mismatch')
    cat=strict_json(catalog_bytes);validate_catalog(cat)
    if (cat['source_sha256']!=version['source_sha256'] or cat['historical_m020_sha256']!=version['historical_m020_sha256']
            or type(recipe['text_locations']) is not int or recipe['text_locations']!=len(cat['entries'])
            or type(recipe['font_locations']) is not int or recipe['font_locations']!=len(cat['dialog_fonts'])):
        raise ValueError('Catalog/version/count mismatch')
    pe=PE(source);file_version,product_version=file_versions(pe)
    if file_version!=version['file_version'] or product_version!=version.get('product_version'):raise ValueError('PE version mismatch')
    try:output=build_bytes(source,cat)
    except (KeyError,IndexError) as exc:raise ValueError('Catalog resource/locator mismatch') from exc
    if sha(output)!=version['historical_m020_sha256'] or len(output)!=version['historical_m020_size']:raise ValueError('Reviewed output mismatch')
    proof=verify_resource_only(source,output,resource_paths(cat))
    metadata={'metadata_schema':1,'recipe_id':recipe['id'],'engine':recipe['engine'],'version_id':version['id'],
              'source_sha256':sha(source),'source_bytes':len(source),'output_sha256':sha(output),'output_bytes':len(output),
              'catalog_sha256':sha(catalog_bytes),'file_version':file_version,'product_version':product_version,
              'text_locations':len(cat['entries']),'font_locations':len(cat['dialog_fonts']),
              'coverage_established':False,'production_can_apply':False,'runtime_tested':False,'proof':proof}
    return PatchBuild(output,metadata)


def metadata_bytes(metadata):
    return (json.dumps(metadata,ensure_ascii=True,sort_keys=True,indent=2)+'\n').encode('utf-8')


def _safe_path(path, must_exist):
    path=Path(path)
    if not path.is_absolute() or '..' in path.parts:raise ValueError('Explicit absolute path required')
    if os.name=='nt':
        from .discovery import windows_path
        windows_path(str(path))
    for current in [path,*path.parents]:
        try:s=current.lstat()
        except FileNotFoundError:continue
        if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&0x400:raise ValueError('Symlink/reparse path refused')
    return path.resolve(strict=must_exist)


def _bounded_file(path, limit):
    with path.open('rb') as f:data=f.read(limit+1)
    if len(data)>limit:raise ValueError('File grew beyond read budget')
    return data


def build_to_paths(input_path, output_path, metadata_path, catalog_bytes, versions, recipe):
    """Explicit new files only, outside the input directory; no game directory writes.

    This is a build-artifact writer, not the transaction/installer backend. Failed
    writes may leave partial artifacts; they are never installed or overwritten.
    """
    source_path=_safe_path(input_path,True)
    output_path=_safe_path(output_path,False);metadata_path=_safe_path(metadata_path,False)
    if output_path==metadata_path or output_path.parent!=metadata_path.parent:
        raise ValueError('Output and metadata must be distinct siblings')
    _safe_path(output_path.parent,True)
    if output_path.parent.is_relative_to(source_path.parent):raise ValueError('Output inside original input directory refused')
    if output_path.exists() or metadata_path.exists():raise ValueError('Existing output refused')
    with source_path.open('rb') as handle:
        before=os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_FILE:raise ValueError('Source size/type')
        if before.st_nlink!=1:raise ValueError('Hardlinked source refused')
        source=handle.read(MAX_FILE+1)
        built=build_patch(source,catalog_bytes,versions,recipe)
        handle.seek(0);same=handle.read(MAX_FILE+1);after=os.fstat(handle.fileno())
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or same!=source:
            raise ValueError('Source changed during build')
        # Recheck the path as well as the open handle before publishing artifacts.
        if source_path.stat().st_ino!=before.st_ino or _bounded_file(source_path,MAX_FILE)!=source:raise ValueError('Source path changed during build')
        for path,data in ((output_path,built.output),(metadata_path,metadata_bytes(built.metadata))):
            _safe_path(path,False)
            with path.open('xb') as f:
                f.write(data);f.flush();os.fsync(f.fileno())
            if _bounded_file(path,len(data))!=data:raise ValueError('Build artifact verification failed')
        if _bounded_file(source_path,MAX_FILE)!=source:raise ValueError('Source changed while writing artifacts')
    return built.metadata
