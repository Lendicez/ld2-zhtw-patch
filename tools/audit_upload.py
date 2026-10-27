"""Exact-file allowlist + conservative text/secret/asset scan. No network."""
from pathlib import Path
import hashlib,json,re,sys,subprocess
ROOT=Path(__file__).resolve().parents[1]
allowed=set(json.loads((ROOT/'UPLOAD_ALLOWLIST.json').read_text(encoding='utf-8'))['files'])
patterns={
 'private_key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
 'github_token':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{25,})\b'),
 'aws_key':re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
 'credential_assignment':re.compile(r'(?i)(?:password|access_token|api_key|client_secret)\s*[:=]\s*["\x27][^"\x27\s]{8,}["\x27]'),
 'embedded_binary':re.compile(r'(?<![A-Za-z0-9])[A-Za-z0-9+/]{300,}={0,2}'),
 'large_hex':re.compile(r'\b[0-9a-fA-F]{256,}\b'),
 'private_machine_path':re.compile(r'(?i)[A-Z]:[\\/](?:Users|GameDev)[\\/]'),
}
findings=[];manifest=[];actual=set()
for p in ROOT.rglob('*'):
 rel=p.relative_to(ROOT).as_posix()
 if '.git' in p.relative_to(ROOT).parts:continue
 if p.is_symlink():findings.append({'path':rel,'rule':'symlink'});continue
 if not p.is_file():continue
 actual.add(rel)
 if rel not in allowed:findings.append({'path':rel,'rule':'not_allowlisted'});continue
 data=p.read_bytes()
 if len(data)>400000 or b'\0' in data or data[:2]==b'MZ':findings.append({'path':rel,'rule':'size_or_binary'})
 try:text=data.decode('utf-8')
 except UnicodeError:findings.append({'path':rel,'rule':'not_utf8'});continue
 # Scanner's regex declarations are audited source, not discovered credentials.
 if rel!='tools/audit_upload.py':
  for rule,pattern in patterns.items():
   for m in pattern.finditer(text):findings.append({'path':rel,'rule':rule,'line':text.count('\n',0,m.start())+1})
 manifest.append({'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
for rel in sorted(allowed-actual):findings.append({'path':rel,'rule':'missing_allowlisted_file'})
tracked=subprocess.run(['git','-C',str(ROOT),'ls-files','-z'],capture_output=True,check=True).stdout.decode().split('\0')
tracked=set(filter(None,tracked))
if tracked!=allowed:findings.append({'rule':'git_index_path_set_mismatch','missing':sorted(allowed-tracked),'extra':sorted(tracked-allowed)})
for rel in sorted(tracked):
 data=subprocess.run(['git','-C',str(ROOT),'show',':'+rel],capture_output=True,check=True).stdout
 if data!=(ROOT/rel).read_bytes():findings.append({'path':rel,'rule':'index_worktree_bytes_differ'})
print(json.dumps({'files':sorted(manifest,key=lambda x:x['path']),'total_files':len(manifest),'total_bytes':sum(x['bytes'] for x in manifest),'findings':findings,'network_used':False,'limits':'Heuristic scan plus reviewed whitelist; not a guarantee of all possible secrets. Scanner source excluded from its own regex pass; no secrets printed.'},ensure_ascii=False,indent=2))
sys.exit(bool(findings))
