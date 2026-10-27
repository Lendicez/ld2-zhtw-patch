"""Bounded offline VDF parsing; this module does not search disk or read registry."""
import re
TOKEN=re.compile(r'\s+|//[^\r\n]*|"(?:\\.|[^"\\])*"|[{}]')
def parse(text):
    if len(text)>2*1024*1024:raise ValueError('VDF size budget')
    tokens=[];p=0
    while p<len(text):
        m=TOKEN.match(text,p)
        if not m:raise ValueError('Unexpected VDF syntax')
        p=m.end();t=m.group()
        if t.isspace() or t.startswith('//'):continue
        if t.startswith('"'):
            t=t[1:-1]
            t=re.sub(r'\\([\\"])',r'\1',t)
            tokens.append(('s',t))
        else:tokens.append((t,t))
    i=0
    def block(depth,closed):
        nonlocal i
        if depth>12:raise ValueError('VDF depth budget')
        out={}
        while i<len(tokens):
            typ,key=tokens[i];i+=1
            if typ=='}':
                if not closed:raise ValueError('Unexpected close')
                return out
            if typ!='s' or i>=len(tokens) or key in out:raise ValueError('Key/duplicate')
            typ,value=tokens[i];i+=1
            if typ=='{':value=block(depth+1,True)
            elif typ!='s':raise ValueError('Value')
            out[key]=value
        if closed:raise ValueError('Unclosed block')
        return out
    return block(0,False)
def libraries(document):
    root=document.get('libraryfolders',document.get('LibraryFolders'))
    if not isinstance(root,dict):raise ValueError('Missing libraryfolders')
    result=[]
    for key,value in root.items():
        if not key.isdecimal():continue
        path=value.get('path') if isinstance(value,dict) else value
        if not isinstance(path,str) or not path:raise ValueError('Library path')
        if path not in result:result.append(path)
    return result
def app_manifest(document):
    app=document.get('AppState')
    if not isinstance(app,dict):raise ValueError('Missing AppState')
    appid=app.get('appid');folder=app.get('installdir')
    if not isinstance(appid,str) or not appid.isdecimal() or int(appid)<=0:raise ValueError('AppID')
    if not isinstance(folder,str) or not folder or folder in ('.','..') or any(c in folder for c in '\\/:\0'):raise ValueError('Unsafe install directory')
    return {'appid':appid,'installdir':folder}
