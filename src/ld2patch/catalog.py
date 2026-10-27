"""Apply reviewed text/font edits in memory to a licensed, hash-locked input."""
from .pe_resources import PE,Builder,sha,parse_dialog,encode_dialog,string_block,encode_string_block
from . import menu
from .contracts import validate,verify_source,contract
def validate_catalog(cat):
    if cat.get('schema_version')!=1 or cat.get('coverage_established') is not False: raise ValueError('Catalog version/coverage')
    seen=set()
    for e in cat['entries']:
        if e['source_key'] in seen: raise ValueError('Duplicate source context')
        seen.add(e['source_key'])
        if e['kind'] not in ('menu','dialog_title','dialog_control','string'): raise ValueError('Unknown edit kind')
        if e['current_version_game_seen'] is not False: raise ValueError('Unverified runtime claim')
        validate(e['translation'],e['contract'])
    return len(seen)
def build_bytes(source,cat):
    validate_catalog(cat)
    if sha(source)!=cat['source_sha256']: raise ValueError('Unsupported source version')
    pe=PE(source); objects={}; raw={tuple(r['path']):pe.payload(r) for r in pe.resources}
    def get(kind,rid,lang):
        key=(kind,rid,lang)
        if key not in objects:objects[key]=({4:menu.parse,5:parse_dialog,6:string_block}[kind])(raw[key])
        return objects[key]
    for e in cat['entries']:
        kind=e['kind'];typ=4 if kind=='menu' else 6 if kind=='string' else 5
        o=get(typ,e['resource'],e['language'])
        if kind=='menu':
            nodes=o['items']
            for depth,index in enumerate(e['locator']):
                field=nodes[index]
                if depth+1<len(e['locator']):nodes=field['children']
            if e.get('command_id') is not None and field.get('id')!=e['command_id']:raise ValueError('Command ID mismatch')
            old=field['text'];key='text'
        elif kind=='string':
            if e['resource']!=e['string_id']//16+1 or e['index']!=e['string_id']%16:raise ValueError('String ID mismatch')
            field=o;key=e['index'];old=field[key]
        else:
            field=o['title'] if kind=='dialog_title' else o['items'][e['item_index']]['title'];key='text';old=field[key]
            if kind=='dialog_control':
                header=bytes.fromhex(o['items'][e['item_index']]['header']);cid=int.from_bytes(header[-4:] if o['extended'] else header[-2:],'little')
                # Legacy review normalizes the static -1 sentinel to UINT32_MAX.
                if cid==65535:cid=0xffffffff
                expected=e['control_id'];expected=0xffffffff if expected==65535 else expected
                if cid!=expected:raise ValueError('Control ID mismatch')
        verify_source(old,e['source_utf16_sha256'])
        if contract(old)!=e['source_contract']:raise ValueError('Source contract mismatch')
        validate(e['translation'],e['contract']);field[key]=e['translation']
    for e in cat['dialog_fonts']:
        o=get(5,e['resource'],e['language']);verify_source(o['font']['text'],e['source_font_utf16_sha256']);o['font']['text']=e['font']
    builder=Builder(source,cat['source_sha256'])
    for r in pe.resources:
        key=tuple(r['path'])
        if key in objects:builder.resource(r['path'],{4:menu.encode,5:encode_dialog,6:encode_string_block}[key[0]](objects[key]))
    result=builder.finish()
    if sha(result)!=cat['historical_m020_sha256']:raise ValueError('Output differs from reviewed m020')
    return result
