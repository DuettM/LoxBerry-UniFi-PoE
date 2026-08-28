#!/usr/bin/env python3
import argparse, json, os, socket, struct, time, random, signal, sys, fcntl, importlib.util, hmac

RUN=True
def stop(*_):
    global RUN; RUN=False
signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)

def enc_len(n):
    out=b''
    while True:
        d=n%128; n//=128
        if n:d|=128
        out+=bytes([d])
        if not n:return out

def mstr(v):
    b=str(v).encode('utf-8'); return struct.pack('!H',len(b))+b

def recv_exact(sock,n):
    b=b''
    while len(b)<n:
        x=sock.recv(n-len(b))
        if not x: raise ConnectionError('MQTT Verbindung geschlossen')
        b+=x
    return b

def recv_packet(sock):
    first=recv_exact(sock,1)[0]; mul=1; rem=0
    for _ in range(4):
        d=recv_exact(sock,1)[0]; rem+=(d&127)*mul
        if not d&128:break
        mul*=128
    return first,recv_exact(sock,rem) if rem else b''

class Client:
    def __init__(self,cfg): self.c=cfg; self.s=None; self.pid=1
    def connect(self):
        host=self.c.get('host','127.0.0.1'); port=int(self.c.get('port',1883)); cid='lb-unifipoe-rx-%04x'%random.randint(0,65535)
        flags=2; payload=mstr(cid)
        if self.c.get('username'):
            flags|=0x80; payload+=mstr(self.c['username'])
            if self.c.get('password') is not None: flags|=0x40; payload+=mstr(self.c.get('password',''))
        vh=mstr('MQTT')+bytes([4,flags])+struct.pack('!H',30)
        self.s=socket.create_connection((host,port),timeout=10); self.s.settimeout(5); self.s.sendall(bytes([0x10])+enc_len(len(vh)+len(payload))+vh+payload)
        h,b=recv_packet(self.s)
        if h>>4!=2 or len(b)<2 or b[1]!=0: raise RuntimeError('MQTT Login fehlgeschlagen')
    def subscribe(self,topic):
        self.pid=(self.pid%65535)+1; body=struct.pack('!H',self.pid)+mstr(topic)+bytes([0]); self.s.sendall(bytes([0x82])+enc_len(len(body))+body)
        h,b=recv_packet(self.s)
        if h>>4!=9: raise RuntimeError('MQTT SUBACK fehlt')
    def publish(self,topic,payload,retain=False):
        body=mstr(topic)+str(payload).encode('utf-8'); self.s.sendall(bytes([0x31 if retain else 0x30])+enc_len(len(body))+body)
    def ping(self): self.s.sendall(b'\xc0\x00')
    def close(self):
        try:
            if self.s:self.s.sendall(b'\xe0\x00'); self.s.close()
        except Exception:pass

def load_json(p):
    with open(p,encoding='utf-8') as f:return json.load(f)

def load_core(path):
    spec=importlib.util.spec_from_file_location('unifipoe_core',path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def payload_command(raw):
    txt=raw.decode('utf-8','replace').strip(); token=''
    try:
        obj=json.loads(txt)
        if isinstance(obj,dict):
            token=str(obj.get('token','') or '')
            txt=str(obj.get('action',obj.get('cmd','')))
    except Exception:
        if '|' in txt:
            token,txt=txt.split('|',1)
    a=txt.strip().lower()
    action={'1':'on','true':'on','ein':'on','on':'on','0':'off','false':'off','aus':'off','off':'off','restart':'cycle','reboot':'cycle','cycle':'cycle','status':'status','get':'status'}.get(a,a)
    return action,token.strip()

def handle(core,cfg,topic,payload):
    base=core.base_topic(cfg); prefix=base+'/set/'
    if not topic.startswith(prefix): return
    rel=topic[len(prefix):].split('/'); action,token=payload_command(payload); mc=cfg.get('mqtt',{}); expected=str(mc.get('command_token','') or '')
    if mc.get('command_token_required',True) and (not expected or not hmac.compare_digest(token,expected)): raise PermissionError('MQTT Command-Token fehlt oder ist ungültig')
    api=core.UniFi(cfg)
    if len(rel)>=3 and rel[0]=='port':
        sw=rel[1]; port=int(rel[2])
        if action=='on': r=api.set_poe(sw,port,'auto')
        elif action=='off': r=api.set_poe(sw,port,'off')
        elif action=='cycle':
            api.set_poe(sw,port,'off'); time.sleep(max(1,min(60,int(cfg.get('cycle_seconds',5))))); r=api.set_poe(sw,port,'auto')
        elif action=='status': r=api.status(sw,port)
        else: raise ValueError('Ungültige MQTT-Aktion: '+action)
    elif len(rel)>=2 and rel[0]=='group':
        group='/'.join(rel[1:])
        # Accept either exact group name or a slug produced by the UI.
        for g in cfg.get('groups',[]):
            if core.slug(g.get('name',''))==group: group=g.get('name',''); break
        if action not in ('on','off','cycle'): raise ValueError('Für Gruppen sind ON/OFF/CYCLE erlaubt')
        r=api.group(group,action)
    else: raise ValueError('Ungültiges MQTT Topic')
    core.mqtt_event(cfg,'command',{'topic':topic,'action':action,'ok':bool(r.get('ok',True)),'result':r},False)
    return r

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',required=True); ap.add_argument('--core',required=True); a=ap.parse_args()
    lockpath=os.path.join(os.path.dirname(a.config),'mqtt_listener.lock'); lock=open(lockpath,'w')
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: return 0
    core=load_core(a.core); backoff=2
    while RUN:
        try:
            cfg=load_json(a.config); cfg['_config_path']=a.config; mc_cfg=cfg.get('mqtt',{})
            if not mc_cfg.get('enabled') or not mc_cfg.get('listen_enabled',True): time.sleep(10); continue
            mc=core.mqtt_connection_config(cfg); base=core.base_topic(cfg); client=Client(mc); client.connect(); client.subscribe(base+'/set/#'); client.publish(base+'/availability','online',True)
            core.debug_log(cfg,'info',f'MQTT Listener über LoxBerry verbunden: {mc.get("host")}:{mc.get("port")} · {base}/set/#'); backoff=2; lastping=time.time(); mtime=os.path.getmtime(a.config); mqtt_mtime=core.mqtt_source_mtime(cfg)
            while RUN:
                if os.path.getmtime(a.config)!=mtime: raise RuntimeError('Plugin-Konfiguration geändert – MQTT Listener startet neu')
                if core.mqtt_source_mtime(cfg)!=mqtt_mtime: raise RuntimeError('LoxBerry MQTT-Konfiguration geändert – MQTT Listener startet neu')
                try: h,b=recv_packet(client.s)
                except socket.timeout:
                    if time.time()-lastping>20: client.ping(); lastping=time.time()
                    continue
                typ=h>>4
                if typ==3:
                    if len(b)<2: continue
                    n=struct.unpack('!H',b[:2])[0]; topic=b[2:2+n].decode('utf-8','replace'); pos=2+n
                    qos=(h>>1)&3
                    if qos: pos+=2
                    payload=b[pos:]
                    try: handle(core,cfg,topic,payload)
                    except Exception as e:
                        core.debug_log({**cfg,'_config_path':a.config},'error',f'MQTT command {topic}: {e}')
                        try: core.mqtt_event(cfg,'error',{'source':'mqtt','topic':topic,'error':str(e)},False)
                        except Exception: pass
                elif typ==13: pass
            client.close()
        except Exception as e:
            try:
                cfg=load_json(a.config); core.debug_log({**cfg,'_config_path':a.config},'warning',f'MQTT Listener reconnect: {e}')
            except Exception: pass
            time.sleep(backoff); backoff=min(60,backoff*2)
    try:
        cfg=load_json(a.config); cfg['_config_path']=a.config; mc_cfg=cfg.get('mqtt',{})
        if mc_cfg.get('enabled'):
            c=Client(core.mqtt_connection_config(cfg)); c.connect(); c.publish(core.base_topic(cfg)+'/availability','offline',True); c.close()
    except Exception: pass
    return 0
if __name__=='__main__': sys.exit(main())
