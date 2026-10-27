"""Apply reviewed text/font edits in memory to a licensed, hash-locked input."""
from .pe_resources import PE,Builder,sha,parse_dialog,encode_dialog,string_block,encode_string_block
from . import menu
from .contracts import validate,verify_source,contract
def validate_catalog(cat):
    import re
    def number(value,maximum):
        if type(value) is not int or not 0<=value<=maximum:raise ValueError('Catalog integer range/type')
    def hash_value(value):
        if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):raise ValueError('Catalog hash')
    if not isinstance(cat,dict) or set(cat)!={'schema_version','source_sha256','historical_m020_sha256','encoding_scope','coverage_established','entries','dialog_fonts'}:
        raise ValueError('Catalog fields')
    if type(cat['schema_version']) is not int or cat['schema_version']!=1 or cat['coverage_established'] is not False:
        raise ValueError('Catalog version/coverage')
    hash_value(cat['source_sha256']);hash_value(cat['historical_m020_sha256'])
    if not isinstance(cat['entries'],list) or not 1<=len(cat['entries'])<=10000 or not isinstance(cat['dialog_fonts'],list) or len(cat['dialog_fonts'])>512:
        raise ValueError('Catalog entry/font budget')
    seen=set();targets=set()
    common={'source_key','kind','resource','language','source_utf16_sha256','translation','source_contract','contract','status','current_version_game_seen','prior_observation_scope'}
    extra={'menu':{'locator','command_id'},'string':{'index','string_id'},'dialog_title':set(),'dialog_control':{'item_index','control_id'}}
    for e in cat['entries']:
        if not isinstance(e,dict) or e.get('kind') not in extra or set(e)!=(common|extra[e['kind']]):raise ValueError('Catalog entry fields/kind')
        if not isinstance(e['source_key'],str) or not e['source_key'] or len(e['source_key'])>200 or e['source_key'] in seen:raise ValueError('Duplicate/invalid source context')
        seen.add(e['source_key']);number(e['resource'],65535);number(e['language'],65535)
        hash_value(e['source_utf16_sha256'])
        if e['current_version_game_seen'] is not False:raise ValueError('Unverified runtime claim')
        target=(e['kind'],e['resource'],e['language'])
        if e['kind']=='menu':
            if not isinstance(e['locator'],list) or not 1<=len(e['locator'])<=16:raise ValueError('Menu locator budget')
            for i in e['locator']:number(i,999)
            if e['command_id'] is not None:number(e['command_id'],65535)
            target+=tuple(e['locator'])
        elif e['kind']=='string':
            number(e['index'],15);number(e['string_id'],65535)
            if e['resource']!=e['string_id']//16+1 or e['index']!=e['string_id']%16:raise ValueError('String ID mismatch')
            target+=(e['index'],)
        elif e['kind']=='dialog_control':
            number(e['item_index'],4095);number(e['control_id'],0xffffffff);target+=(e['item_index'],)
        if target in targets:raise ValueError('Duplicate physical text target')
        targets.add(target)
        if not isinstance(e['source_contract'],dict) or not isinstance(e['contract'],dict):raise ValueError('Catalog contract type')
        validate(e['translation'],e['contract'])
    fonts=set()
    for e in cat['dialog_fonts']:
        if not isinstance(e,dict) or set(e)!={'resource','language','font','source_font_utf16_sha256'}:raise ValueError('Font fields')
        number(e['resource'],65535);number(e['language'],65535);hash_value(e['source_font_utf16_sha256'])
        key=(e['resource'],e['language'])
        if key in fonts:raise ValueError('Duplicate font target')
        fonts.add(key)
        validate(e['font'],contract(e['font']),max_utf16_units=32)
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
