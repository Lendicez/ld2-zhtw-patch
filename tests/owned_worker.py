"""Only terminate the exact child this test object just created, never a PID lookup.

Retained Popen process handle + PID + creation time + image + WMI command line +
private-pipe nonce/argv handshake are checked immediately before TerminateProcess.
No termination fallback, process-name search, privilege or security-setting change.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib,json,ntpath,os,queue,subprocess,sys,threading
from pathlib import Path
from ld2patch.windows_fixture import NativeFailure,FixtureRefusal
from ld2patch.windows_capture import encode

BLOCKED=None
EVIDENCE=[]
class WorkerUnavailable(Exception):pass


class ProcessAPI:
    def __init__(self):
        self.k=C.WinDLL('kernel32',use_last_error=True)
        def bind(name,args,result):
            f=getattr(self.k,name);f.argtypes=args;f.restype=result;return f
        self.pid=bind('GetProcessId',[W.HANDLE],W.DWORD)
        self.times=bind('GetProcessTimes',[W.HANDLE,*([C.POINTER(W.FILETIME)]*4)],W.BOOL)
        self.image=bind('QueryFullProcessImageNameW',[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)],W.BOOL)
        self.terminate=bind('TerminateProcess',[W.HANDLE,W.UINT],W.BOOL)
    def identity(self,handle):
        times=[W.FILETIME() for _ in range(4)]
        if not self.times(handle,*[C.byref(t) for t in times]):raise NativeFailure('GetProcessTimes',C.get_last_error())
        pid=self.pid(handle)
        if not pid:raise NativeFailure('GetProcessId',C.get_last_error())
        buf=C.create_unicode_buffer(1024);size=W.DWORD(len(buf))
        if not self.image(handle,0,buf,C.byref(size)):raise NativeFailure('QueryFullProcessImageNameW',C.get_last_error())
        return {'pid':pid,'created':(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime,
                'image':buf.value}


def validate_identity(initial,current,expected_pid,expected_image,command,expected_command,handshake,expected_argv,nonce):
    if (not all(isinstance(x,dict) for x in (initial,current,command,handshake)) or
        initial!=current or current.get('pid')!=expected_pid or
        ntpath.normcase(current.get('image',''))!=ntpath.normcase(expected_image) or
        command.get('ProcessId')!=expected_pid or command.get('CommandLine')!=expected_command or
        ntpath.normcase(command.get('ExecutablePath') or '')!=ntpath.normcase(expected_image) or
        handshake.get('pid')!=expected_pid or handshake.get('argv')!=expected_argv or
        handshake.get('nonce')!=nonce or ntpath.basename(expected_image).lower()!='python.exe'):
        raise FixtureRefusal('owned worker identity/command mismatch; no termination')


class OwnedWorker:
    def __init__(self,parent,registration,mode,pause=None):
        global BLOCKED
        if BLOCKED:raise WorkerUnavailable(BLOCKED)
        self.script=Path(__file__).resolve().parents[1]/'tools/capture_worker.py'
        self.script_hash=hashlib.sha256(self.script.read_bytes()).hexdigest()
        self.nonce=registration['nonce'];self.pause=pause
        self.args=[sys.executable,'-I','-B',str(self.script),'--parent',str(parent),
                   '--mode',mode,'--nonce',self.nonce]
        if pause:self.args+=['--pause',pause]
        self.p=subprocess.Popen(self.args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        self.api=ProcessAPI()
        # CPython Windows Popen owns this process handle from CreateProcess.
        # Keep it; never reopen a process by a possibly reused PID.
        self.handle=int(self.p._handle)
        try:self.initial=self.api.identity(self.handle)
        except NativeFailure:
            self.p.stdin.close()  # No registration supplied; child aborts on EOF.
            self.p.wait(timeout=10)
            raise
        self.lines=queue.Queue()
        def read_lines():
            while True:
                line=self.p.stdout.readline(16385)
                self.lines.put(line)
                if not line:break
        threading.Thread(target=read_lines,daemon=True).start()
        self.p.stdin.write(encode(registration).decode('utf-8'));self.p.stdin.close()
        self.hello=self.take()
        self.expected_argv=self.args[3:]
        self.record={'mode':mode,'phase':pause,'initial':self.initial,'argv':self.args,
                     'script_sha256':self.script_hash,'terminated':False}
        EVIDENCE.append(self.record)
    def close(self):
        if self.p.poll() is None:
            # A paused fixture cooperatively aborts at its own deadline.
            self.p.wait(timeout=25)
        self.p.stdout.close()
    def take(self):
        line=self.lines.get(timeout=25)
        if not line or len(line)>16384:raise FixtureRefusal('worker output absent/oversized')
        try:return json.loads(line)
        except ValueError as e:raise FixtureRefusal('worker output is not structured evidence') from e
    def finish(self):
        if self.hello.get('event')=='error':result=self.hello
        else:
            if self.hello.get('event')!='ready':raise FixtureRefusal('worker not ready')
            result=self.take()
        code=self.p.wait(timeout=10);self.record.update(exit_code=code,result=result)
        return code,result
    def stop_unavailable(self,reason):
        global BLOCKED
        BLOCKED=reason;self.record['blocked']=reason
        # Worker itself has a 20-second pause deadline and aborts thereafter.
        # No alternate termination action is attempted.
        try:self.record['cooperative_exit']=self.p.wait(timeout=25)
        except subprocess.TimeoutExpired:self.record['still_running']=True
        raise WorkerUnavailable(reason)
    def kill_at_pause(self):
        if self.hello.get('event')!='ready':raise FixtureRefusal(str(self.hello))
        paused=self.take()
        if paused!={'event':'paused','phase':self.pause,'pid':self.p.pid,'nonce':self.nonce}:
            raise FixtureRefusal('wrong pause identity; no termination')
        if self.p.poll() is not None:raise FixtureRefusal('worker already exited; no termination')
        # Read only this newly owned PID, never enumerate unrelated processes.
        ps=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        query=("$ErrorActionPreference='Stop'; "
            "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
            f"Get-CimInstance Win32_Process -Filter 'ProcessId = {self.p.pid}' | "
            "Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress")
        helper=subprocess.Popen([str(ps),'-NoProfile','-NonInteractive','-Command',query],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        try:out,err=helper.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            self.stop_unavailable('owned-PID command query timeout; no termination retry')
        if helper.returncode:
            self.stop_unavailable('owned-PID command query failed: '+err.decode('utf-8',errors='replace')[:400])
        try:command=json.loads(out.decode('utf-8-sig'))
        except ValueError:self.stop_unavailable('owned-PID command query unavailable')
        try:current=self.api.identity(self.handle)
        except NativeFailure as e:self.stop_unavailable(str(e))
        validate_identity(self.initial,current,self.p.pid,sys.executable,command,
            subprocess.list2cmdline(self.args),self.hello,self.expected_argv,self.nonce)
        if hashlib.sha256(self.script.read_bytes()).hexdigest()!=self.script_hash:
            raise FixtureRefusal('worker source changed; no termination')
        self.record.update(preterminate=current,os_command=command,identity_verified=True)
        if not self.api.terminate(self.handle,0xE034):
            self.stop_unavailable(f'TerminateProcess WinError {C.get_last_error()}; no retry')
        self.record['terminated']=True
        code=self.p.wait(timeout=10)
        self.record['exit_code']=code
        if code!=0xE034:raise FixtureRefusal('unexpected terminated exit code')
        return self.record
