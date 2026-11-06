"""One serial owner for independent work mapping and persistent attention."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import tempfile
import termios
import time

from motor_bridge_base import CodexRolloutAdapter, serial_candidates
from attention_state import AttentionAdapter
from root_catalog import RootCatalog
from runtime_feed import DesktopRuntimeFeed
from state_reducer import RolloutSnapshot, RuntimeSnapshot, reduce_state, SPEED_RANK
from workbuddy_adapter import WorkBuddyAdapter


def select_outputs(known_rollouts, snapshot, pending, now):
    """Fresh desktop runtime determines work; async cards independently light.

    A missing/stale desktop feed fails quiet and cannot revive a blocked task
    from an old task_started record. The pending cache itself is not cleared.
    """
    runtimes=[]
    for tid, entry in snapshot.get('threads', {}).items():
        if entry.get('parent_thread_id') is not None or entry.get('host_id') != 'local':
            continue
        observed=entry.get('observed_at', 0)
        status=entry.get('runtime_status')
        if entry.get('archived'):
            status={'type':'idle'}
        elif not entry.get('owner_found'):
            observed=entry.get('owner_checked_at', 0)
            status={'type':'idle'}
        elif isinstance(status,dict) and status.get('type') in ('notLoaded','systemError'):
            # Neither state indicates ongoing execution. This does not resolve
            # a question card; explicit answer/cancellation/closure does that.
            status={'type':'idle'}
        runtimes.append(RuntimeSnapshot.from_status(tid,status,observed,is_root=tid in known_rollouts))
    heartbeat=snapshot.get('last_message_at')
    healthy=(snapshot.get('connected') and isinstance(heartbeat,(int,float))
             and -2 <= now-heartbeat < 6)
    if not healthy:
        # No IPC health: do not misrepresent the computer as still working.
        return reduce_state([],[],[],now=now,fallback_policy='stop'), False
    state=reduce_state(known_rollouts.values(),runtimes,pending,now=now,
                       runtime_ttl=6,fallback_policy='stop')
    return state, True


def log(message):
    print(time.strftime('%Y-%m-%d %H:%M:%S'), message, flush=True)


class Flower:
    def __init__(self, port='auto'):
        self.port=port; self.fd=None; self.path=None
        self.last_probe=-100; self.last_send=-100; self.last_state=None
        self.buffer=b''
        self.last_device_line=None
        self.capabilities=[]

    def close(self):
        if self.fd is not None:
            try: fcntl.ioctl(self.fd,termios.TIOCNXCL)
            except OSError: pass
            try: os.close(self.fd)
            except OSError: pass
        self.fd=None; self.path=None; self.last_state=None; self.buffer=b''
        self.capabilities=[]

    def connect(self):
        if self.fd is not None:
            return True
        now=time.monotonic()
        if now-self.last_probe<2:
            return False
        self.last_probe=now
        for path in serial_candidates() if self.port=='auto' else [self.port]:
            fd=None
            try:
                subprocess.run(['stty','-f',path,'115200','raw','-echo'],check=True,capture_output=True,timeout=2)
                fd=os.open(path,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
                fcntl.ioctl(fd,termios.TIOCEXCL)
                os.write(fd,b'DEVICE INFO\nPING\n')
                data=b''; deadline=time.monotonic()+1.2
                while time.monotonic()<deadline:
                    if select.select([fd],[],[],.1)[0]:
                        chunk=os.read(fd,4096)
                        if not chunk: raise OSError('Serial EOF')
                        data+=chunk
                        if b'FLOWER_COMBINED_V1 PWM=OK ' in data:
                            self.fd=fd; self.path=path; self.last_send=-100
                            self.last_state=None
                            self.capabilities=['motor','attention']
                            log('Connected integrated flower: '+path)
                            return True
                if b'PONG' in data:
                    self.fd=fd; self.path=path; self.capabilities=['motor']
                    self.last_state=None; self.last_send=-100
                    log('Connected legacy motor-only flower: '+path)
                    return True
            except (OSError,subprocess.SubprocessError):
                pass
            if fd is not None:
                try: fcntl.ioctl(fd,termios.TIOCNXCL)
                except OSError: pass
                os.close(fd)
        return False

    def drain(self):
        # Nonblocking and bounded: no serial response should stall heartbeats.
        for _ in range(4):
            if not select.select([self.fd],[],[],0)[0]: break
            chunk=os.read(self.fd,4096)
            if not chunk: raise OSError('Serial EOF')
            self.buffer+=chunk
            lines=self.buffer.split(b'\n');self.buffer=lines.pop()[-4096:]
            for line in lines:
                value=line.decode(errors='replace').strip()
                if value and value != self.last_device_line:
                    log('DEVICE: '+value)
                    self.last_device_line=value

    def send(self, motor, light):
        if motor not in ('STOP','RUN LOW','RUN MEDIUM','RUN HIGH','RUN XHIGH','RUN ULTRA'):
            raise ValueError('Invalid motor state')
        if not self.connect(): return False
        try:
            if self.capabilities == ['motor']:
                # Report an incompatible board to setup without attempting light
                # commands or starting motion on an unverified protocol.
                if time.monotonic()-self.last_send>=1.5:
                    os.write(self.fd,b'STOP\n');self.last_send=time.monotonic()
                self.drain()
                return False
            now=time.monotonic(); state=(motor,bool(light))
            if state!=self.last_state or now-self.last_send>=1.5:
                data=(motor+'\nATTENTION '+('ON' if light else 'OFF')+'\n').encode()
                written=os.write(self.fd,data)
                if written!=len(data): raise OSError('Short serial write')
                if state!=self.last_state:
                    log(f'SENT {motor}; LIGHT={"ON" if light else "OFF"}')
                self.last_send=now; self.last_state=state
            self.drain()
            return True
        except OSError as exc:
            log(f'Disconnected {self.path}: {exc}')
            self.close()
            return False

    def stop(self):
        if self.fd is not None:
            try: os.write(self.fd,b'STOP\nATTENTION OFF\n')
            except OSError: pass
        self.close()


class CodexSource:
    def __init__(self, root, cache):
        self.root=Path(root)
        self.motor=CodexRolloutAdapter(root)
        self.attention=AttentionAdapter(root,state_path=cache)
        self.catalog=RootCatalog(root)
        self.feed=DesktopRuntimeFeed(refresh_seconds=2)
        self.known={}

    def poll(self, now):
        self.motor.poll(); self.attention.poll(); self.catalog.poll()
        for tid in self.catalog.ids:
            self.known.setdefault(tid,RolloutSnapshot(tid,False,None,0))
        for entry in self.motor.files.values():
            s=entry.state
            self.known[s.session_id]=RolloutSnapshot(s.session_id,s.active,s.effort,entry.mtime,s.started_at)
        self.feed.set_targets(self.known)
        snapshot=self.feed.snapshot()
        for tid,entry in snapshot.get('threads',{}).items():
            if entry.get('archived') and any(k[0]==tid for k in self.attention.pending):
                self.attention.close_chat(tid,now)
        selected,healthy=select_outputs(self.known,snapshot,self.attention.pending,now)
        readiness,detail,error=codex_readiness(self.root,snapshot,healthy,bool(self.known))
        return {'healthy':bool(healthy and readiness=='ready'),'error':error,
                'readiness':readiness,'detail':detail,
                'motor':selected.motor_command,'light':selected.light,
                'working_threads':list(selected.working_threads),
                'waiting_threads':list(selected.waiting_threads),
                'pending_questions':selected.pending_question_count}

    def close(self):
        self.motor.close(); self.attention.close(); self.feed.close()


def codex_readiness(root, snapshot, healthy, has_chats):
    """Separate normal first-use/offline states from broken source access."""
    error=snapshot.get('error')
    offline={'not_started','FileNotFoundError','ConnectionRefusedError','EOFError',
             'ConnectionResetError','ConnectionAbortedError','BrokenPipeError'}
    if error and error not in offline:
        return 'error',None,error
    try:
        root.stat()
    except FileNotFoundError:
        return 'not_initialized','打开并登录 Codex，开始一次任务后会自动联动。',None
    if not root.is_dir():
        return 'error',None,'Codex task path is not a directory'
    if healthy:
        return 'ready',None,None
    if error in offline:
        return 'not_running','打开 Codex 后会自动联动，无需重新安装。',None
    if snapshot.get('connected') and not has_chats:
        return 'not_initialized','在 Codex 开始一次任务后会自动联动。',None
    return 'error',None,error or 'Codex live task connection is not responding'


class RecoveringSource:
    """Isolate source startup failures as well as later disconnections."""
    def __init__(self, factory):
        self.factory=factory; self.instance=None; self.retry_at=0; self.error=None

    def poll(self, now):
        if self.instance is None and now>=self.retry_at:
            try:
                self.instance=self.factory();self.error=None
            except (OSError,ValueError,KeyError,TypeError) as exc:
                self.error='Source initialization failed: '+type(exc).__name__
                self.retry_at=now+5
        if self.instance is None:
            return {'healthy':False,'error':self.error,'readiness':'error','motor':'STOP','light':False,
                    'working_threads':[],'waiting_threads':[],'pending_questions':0}
        return self.instance.poll(now)

    def close(self):
        if self.instance is not None:self.instance.close()


def combine_sources(sources):
    # One source failing must never suppress another healthy source.
    healthy=[s for s in sources.values() if s.get('healthy')]
    commands=[s['motor'] for s in healthy if s['motor'].startswith('RUN ')]
    motor=max(commands,key=lambda c:SPEED_RANK[c.split()[1]]) if commands else 'STOP'
    return motor,any(s['light'] for s in healthy)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sessions-root',type=Path,default=Path.home()/'.codex/sessions')
    parser.add_argument('--workbuddy-root',type=Path,default=Path.home()/'.workbuddy')
    parser.add_argument('--source',choices=('codex','workbuddy','both'),default='workbuddy')
    parser.add_argument('--port',default='auto')
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--launch-id',default='')
    parser.add_argument('--attention-cache',type=Path,default=Path(__file__).with_name('attention-cache.json'))
    parser.add_argument('--status-file',type=Path,default=Path(__file__).with_name('status.json'))
    args=parser.parse_args()
    lock=None
    if not args.once:
        lock=(Path(tempfile.gettempdir())/f'codex-motor-bridge-{os.getuid()}.lock').open('a+')
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    running=True
    def stop(*_):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
    sources={}
    if args.source in ('codex','both'):
        sources['codex']=RecoveringSource(lambda:CodexSource(args.sessions_root,None if args.once else args.attention_cache))
    if args.source in ('workbuddy','both'):
        sources['workbuddy']=RecoveringSource(lambda:WorkBuddyAdapter(args.workbuddy_root))
    flower=Flower(args.port);previous=None;last_status=0
    once_deadline=time.monotonic()+5
    try:
        while running:
            now=time.time()
            snapshots={}
            for name,source in sources.items():
                try:
                    snapshots[name]=source.poll(now)
                except (OSError,ValueError,KeyError,TypeError) as exc:
                    snapshots[name]={'healthy':False,'error':type(exc).__name__,'readiness':'error',
                                     'motor':'STOP','light':False,'working_threads':[],
                                     'waiting_threads':[],'pending_questions':0}
            command,light=combine_sources(snapshots)
            state=json.dumps(snapshots,sort_keys=True)
            if state!=previous:
                log(f'SOURCES {state}; motor={command}; light={light}')
                previous=state
            if args.once:
                if time.monotonic()>=once_deadline:
                    print(json.dumps({'motor':command,'light':light,'sources':snapshots}));return
            else:
                flower.send(command,light)
                if now-last_status>=1:
                    status={'updated_at':now,'launch_id':args.launch_id,'source':args.source,
                            'sources':snapshots,'motor':command,'light':light,
                            'device_connected':flower.fd is not None,
                            'device_port':flower.path,'device_capabilities':flower.capabilities,
                            'last_device_line':flower.last_device_line}
                    tmp=args.status_file.with_suffix('.tmp')
                    tmp.write_text(json.dumps(status,indent=2)+'\n');tmp.replace(args.status_file)
                    last_status=now
            time.sleep(.3)
    finally:
        flower.stop()
        for source in sources.values():source.close()
        if lock:lock.close()
        log('Read-only status check ended' if args.once else 'Integrated bridge stopped; STOP and light OFF requested')

if __name__=='__main__':main()
