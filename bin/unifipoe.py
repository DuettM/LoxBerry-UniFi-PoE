#!/usr/bin/env python3
import argparse, json, ssl, sys, time, urllib.request, urllib.error, http.cookiejar, socket, struct, random, os, tempfile, urllib.parse

VERSION='0.5.0'
class UniFiError(RuntimeError): pass

LOG_LEVELS = {'debug':10,'info':20,'warning':30,'error':40}

def debug_log(cfg, level, message):
    """Write a bounded plugin debug log. Logging must never break PoE control."""
    try:
        level=str(level).lower()
        cfg_level=str(cfg.get('debug',{}).get('level','info')).lower()
        if LOG_LEVELS.get(level,20) < LOG_LEVELS.get(cfg_level,20):
            return
        cfg_path=cfg.get('_config_path','')
        log_path=cfg.get('debug',{}).get('log_file') or (os.path.join(os.path.dirname(cfg_path),'unifipoe.log') if cfg_path else '/tmp/unifipoe.log')
        max_bytes=int(cfg.get('debug',{}).get('max_bytes',524288))
        backups=max(1,min(5,int(cfg.get('debug',{}).get('backups',2))))
        if os.path.exists(log_path) and os.path.getsize(log_path) >= max_bytes:
            for i in range(backups,0,-1):
                src=log_path if i==1 else f'{log_path}.{i-1}'
                dst=f'{log_path}.{i}'
                if os.path.exists(src):
                    try:
                        if os.path.exists(dst): os.remove(dst)
                        os.replace(src,dst)
                    except Exception: pass
        ts=time.strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path,'a',encoding='utf-8') as f:
            f.write(f'{ts} [{level.upper()}] {message}\n')
    except Exception:
        pass

def slug(s):
    out=''.join(c.lower() if c.isalnum() else '_' for c in str(s))
    while '__' in out: out=out.replace('__','_')
    return out.strip('_') or 'port'

def loxberry_mqtt_settings(cfg):
    """Return broker credentials from LoxBerry general.json plus plugin MQTT options."""
    mc=dict(cfg.get('mqtt',{}) or {})
    lbhome=os.environ.get('LBHOME','/opt/loxberry')
    general=os.path.join(lbhome,'config','system','general.json')
    try:
        with open(general,encoding='utf-8') as f:
            g=json.load(f)
        m=g.get('Mqtt')
        if not isinstance(m,dict):
            raise RuntimeError('MQTT Gateway ist in LoxBerry nicht konfiguriert (Mqtt fehlt in general.json)')
        mc['host']=m.get('Brokerhost')
        mc['port']=int(m.get('Brokerport'))
        mc['username']=m.get('Brokeruser','')
        mc['password']=m.get('Brokerpass','')
        if not mc.get('host') or not mc.get('port'):
            raise RuntimeError('Ungültige LoxBerry MQTT Brokerdaten')
        return mc
    except Exception as e:
        raise RuntimeError(f'LoxBerry MQTT Konfiguration nicht lesbar: {e}')

class MQTT:
    def __init__(self,cfg): self.c=cfg or {}; self.s=None
    @staticmethod
    def _enc_len(n):
        out=b''
        while True:
            d=n%128; n//=128
            if n: d|=128
            out+=bytes([d])
            if not n:return out
    @staticmethod
    def _str(s):
        b=str(s).encode(); return struct.pack('!H',len(b))+b
    def connect(self):
        host=self.c.get('host','127.0.0.1'); port=int(self.c.get('port',1883)); cid='lb-unifipoe-%04x'%random.randint(0,65535)
        flags=2; payload=self._str(cid)
        if self.c.get('username'):
            flags|=0x80; payload+=self._str(self.c['username'])
            if self.c.get('password') is not None: flags|=0x40; payload+=self._str(self.c.get('password',''))
        vh=self._str('MQTT')+bytes([4,flags])+struct.pack('!H',20)
        pkt=bytes([0x10])+self._enc_len(len(vh)+len(payload))+vh+payload
        self.s=socket.create_connection((host,port),timeout=5); self.s.sendall(pkt); r=self.s.recv(4)
        if len(r)<4 or r[0]!=0x20 or r[3]!=0: raise RuntimeError('MQTT connect failed')
    def publish(self,topic,payload,retain=True):
        if not self.s:self.connect()
        body=self._str(topic)+str(payload).encode(); hdr=0x31 if retain else 0x30
        self.s.sendall(bytes([hdr])+self._enc_len(len(body))+body)
    def close(self):
        try:
            if self.s:self.s.sendall(b'\xe0\x00'); self.s.close()
        except Exception: pass

def mqtt_publish(cfg, topic, payload):
    mc=cfg.get('mqtt',{})
    if not mc.get('enabled'): return
    broker=loxberry_mqtt_settings(cfg)
    m=MQTT(broker)
    try:m.publish(topic,payload,bool(mc.get('retain',True)))
    finally:m.close()

class UniFi:
    def __init__(self,cfg):
        self.cfg=cfg; self.base=cfg['controller'].rstrip('/'); self.site=cfg.get('site','default'); self.kind=cfg.get('controller_type','unifios')
        ctx=ssl.create_default_context() if cfg.get('verify_ssl',False) else ssl._create_unverified_context()
        self.cookies=http.cookiejar.CookieJar(); self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies),urllib.request.HTTPSHandler(context=ctx)); self.csrf=None
    def req(self,method,path,payload=None):
        data=None if payload is None else json.dumps(payload).encode(); headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'LoxBerry-UniFi-PoE/'+VERSION}
        if self.csrf:headers['X-CSRF-Token']=self.csrf
        r=urllib.request.Request(self.base+path,data=data,headers=headers,method=method)
        try:
            with self.opener.open(r,timeout=12) as resp:
                self.csrf=resp.headers.get('X-CSRF-Token') or self.csrf; raw=resp.read().decode('utf-8','replace'); return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e: raise UniFiError(f'HTTP {e.code}: {e.read().decode("utf-8","replace")[:500]}')
        except Exception as e: raise UniFiError(str(e))
    def login(self):self.req('POST','/api/auth/login' if self.kind=='unifios' else '/api/login',{'username':self.cfg.get('username',''),'password':self.cfg.get('password',''),'remember':True})
    def prefix(self):return '/proxy/network' if self.kind=='unifios' else ''
    def devices(self):self.login(); return self.req('GET',f'{self.prefix()}/api/s/{self.site}/stat/device').get('data',[])
    def switches(self):return [d for d in self.devices() if d.get('type')=='usw']
    def find_device(self,ident):
        norm=ident.lower().replace('-','').replace(':','')
        for d in self.switches():
            vals=[str(d.get('_id','')),str(d.get('name','')),str(d.get('mac',''))]
            if any(v.lower()==ident.lower() for v in vals) or str(d.get('mac','')).lower().replace(':','')==norm:return d
        raise UniFiError(f'Switch nicht gefunden: {ident}')
    def port_info(self,d,port):
        for p in d.get('port_table',[]):
            if int(p.get('port_idx',-1))==int(port):return p
        raise UniFiError(f'Port {port} nicht gefunden')
    def alias(self,d,port):return self.cfg.get('aliases',{}).get(f'{d.get("_id")}:{port}') or self.port_info(d,port).get('name') or f'Port {port}'
    def set_poe(self,ident,port,mode):
        if mode not in ('auto','off'):raise UniFiError('poe_mode muss auto oder off sein')
        d=self.find_device(ident); p=self.port_info(d,port); overrides=[dict(x) for x in d.get('port_overrides',[])]; found=False
        for ov in overrides:
            if int(ov.get('port_idx',-1))==int(port):ov['poe_mode']=mode;found=True;break
        if not found:
            ov={'port_idx':int(port),'poe_mode':mode,'port_security_mac_address':[]}
            if p.get('portconf_id'):ov['portconf_id']=p['portconf_id']
            overrides.append(ov)
        self.login(); self.req('PUT',f'{self.prefix()}/api/s/{self.site}/rest/device/{d["_id"]}',{'port_overrides':overrides})
        time.sleep(.35)
        result={'ok':True,'switch':d.get('name') or d.get('mac'),'device_id':d['_id'],'port':int(port),'alias':self.alias(d,port),'poe_mode':mode,'up':mode!='off'}
        self.publish_state(result); debug_log(self.cfg,'info',f"PoE {mode}: {result['switch']} Port {port} ({result['alias']})"); return result
    def status(self,ident,port):
        d=self.find_device(ident); p=self.port_info(d,port); mode=p.get('poe_mode','auto')
        r={'ok':True,'switch':d.get('name') or d.get('mac'),'device_id':d['_id'],'port':int(port),'alias':self.alias(d,port),'poe_mode':mode,'poe_power':p.get('poe_power'),'poe_current':p.get('poe_current'),'poe_voltage':p.get('poe_voltage'),'link_up':bool(p.get('up')),'up':mode!='off'}
        self.publish_state(r); return r
    def publish_state(self,r):
        mc=self.cfg.get('mqtt',{}); base=mc.get('base_topic','unifipoe').strip('/'); key=slug(r.get('alias') or f'p{r["port"]}')
        root=f'{base}/{slug(r.get("switch","switch"))}/{key}'
        for k in ('up','poe_mode','poe_power','poe_current','poe_voltage','link_up'):
            if k in r and r[k] is not None:mqtt_publish(self.cfg,f'{root}/{k}',('1' if r[k] is True else '0' if r[k] is False else r[k]))
    def list_devices(self):
        ds=[]
        aliases=self.cfg.get('aliases',{})
        for d in self.switches():
            ports=[]
            for p in d.get('port_table',[]):
                if p.get('port_poe') or p.get('poe_mode') is not None:
                    idx=p.get('port_idx'); ports.append({'port_idx':idx,'name':p.get('name'),'alias':aliases.get(f'{d.get("_id")}:{idx}',''),'poe_mode':p.get('poe_mode'),'poe_power':p.get('poe_power'),'poe_current':p.get('poe_current'),'poe_voltage':p.get('poe_voltage'),'link_up':p.get('up')})
            ds.append({'id':d.get('_id'),'name':d.get('name'),'mac':d.get('mac'),'model':d.get('model'),'ip':d.get('ip'),'ports':ports})
        debug_log(self.cfg,'debug',f'Device scan: {len(ds)} Switch(es), {sum(len(d["ports"]) for d in ds)} PoE-Port(s)'); return {'ok':True,'devices':ds}
    def group(self,name,cmd):
        g=next((x for x in self.cfg.get('groups',[]) if x.get('name','').lower()==name.lower()),None)
        if not g:raise UniFiError('Gruppe nicht gefunden: '+name)
        res=[]
        for x in g.get('ports',[]):
            try:
                if cmd=='cycle':self.set_poe(x['switch'],int(x['port']),'off'); res.append({'switch':x['switch'],'port':x['port'],'phase':'off'})
                else:res.append(self.set_poe(x['switch'],int(x['port']),'auto' if cmd=='on' else 'off'))
            except Exception as e:res.append({'ok':False,'switch':x.get('switch'),'port':x.get('port'),'error':str(e)})
        if cmd=='cycle':
            time.sleep(max(1,min(60,int(self.cfg.get('cycle_seconds',5)))))
            for x in g.get('ports',[]):
                try:res.append(self.set_poe(x['switch'],int(x['port']),'auto'))
                except Exception as e:res.append({'ok':False,'switch':x.get('switch'),'port':x.get('port'),'error':str(e)})
        return {'ok':all(x.get('ok',True) for x in res),'group':name,'action':cmd,'results':res}

def safe_selftest(cfg, config_path):
    tests=[]
    def add(name, ok, detail='', level='ok'):
        tests.append({'name':name,'ok':bool(ok),'detail':str(detail),'level':level if ok else 'error'})
    try:add('Konfiguration lesbar', True, config_path)
    except Exception as e:add('Konfiguration lesbar', False, e)
    controller=str(cfg.get('controller','')).strip()
    try:
        u=urllib.parse.urlparse(controller); valid=u.scheme in ('http','https') and bool(u.hostname)
        add('Controller-URL gültig', valid, controller if valid else 'HTTP/HTTPS URL mit Host erforderlich')
    except Exception as e:add('Controller-URL gültig', False, e)
    add('API-Token gesetzt', bool(cfg.get('api_token')) and cfg.get('api_token')!='CHANGE_ME', 'Token ist gesetzt' if cfg.get('api_token') and cfg.get('api_token')!='CHANGE_ME' else 'Bitte Standardtoken ersetzen')
    groups=cfg.get('groups',[])
    try:
        names=[]; valid=True; detail=[]
        for g in groups:
            n=str(g.get('name','')).strip(); names.append(n.lower())
            if not n or not isinstance(g.get('ports',[]),list): valid=False
            for x in g.get('ports',[]):
                if not x.get('switch') or not str(x.get('port','')).isdigit(): valid=False
        if len(names)!=len(set(names)): valid=False; detail.append('Doppelte Gruppennamen')
        add('Port-Gruppen gültig', valid, ', '.join(detail) if detail else f'{len(groups)} Gruppe(n)')
    except Exception as e:add('Port-Gruppen gültig', False, e)
    try:
        d=os.path.dirname(config_path) or '.'; fd,tmp=tempfile.mkstemp(prefix='.unifipoe-test-',dir=d); os.write(fd,b'ok'); os.close(fd); os.unlink(tmp)
        add('Konfigurationsordner beschreibbar', True, d)
    except Exception as e:add('Konfigurationsordner beschreibbar', False, e)
    if controller:
        try:
            u=urllib.parse.urlparse(controller); port=u.port or (443 if u.scheme=='https' else 80); t=time.time(); sock=socket.create_connection((u.hostname,port),timeout=4); sock.close()
            add('Controller TCP erreichbar', True, f'{u.hostname}:{port} · {int((time.time()-t)*1000)} ms')
        except Exception as e:add('Controller TCP erreichbar', False, e)
        try:
            t=time.time(); api=UniFi(cfg); data=api.list_devices(); elapsed=int((time.time()-t)*1000); count=len(data.get('devices',[])); ports=sum(len(d.get('ports',[])) for d in data.get('devices',[]))
            add('UniFi Login/API', True, f'{count} Switch(es), {ports} PoE-Port(s), {elapsed} ms'); add('PoE-Daten lesbar', ports>0, f'{ports} PoE-Port(s) erkannt' if ports else 'Keine PoE-Ports erkannt')
        except Exception as e:add('UniFi Login/API', False, e); add('PoE-Daten lesbar', False, 'API-Test fehlgeschlagen')
    mc=cfg.get('mqtt',{})
    if mc.get('enabled'):
        m=None
        try:
            broker=loxberry_mqtt_settings(cfg); m=MQTT(broker); t=time.time(); m.connect(); add('MQTT Verbindung', True, f"{broker.get('host')}:{broker.get('port')} · LoxBerry MQTT · {int((time.time()-t)*1000)} ms")
        except Exception as e:add('MQTT Verbindung', False, e)
        finally:
            if m: m.close()
    else:tests.append({'name':'MQTT Verbindung','ok':True,'detail':'MQTT deaktiviert','level':'info'})
    wdpath=os.path.join(os.path.dirname(config_path),'watchdog.json')
    if cfg.get('watchdog',{}).get('enabled'):
        try:
            with open(wdpath,encoding='utf-8') as f: wd=json.load(f)
            age=int(time.time()-int(wd.get('timestamp',0))); ok=bool(wd.get('ok')) and age<180
            add('Watchdog aktuell', ok, f'letzte Prüfung vor {age}s · Fehlerfolge {wd.get("consecutive_failures",0)}')
        except Exception as e:add('Watchdog aktuell', False, f'Noch kein gültiger Watchdog-Status: {e}')
    else:tests.append({'name':'Watchdog aktuell','ok':True,'detail':'Watchdog deaktiviert','level':'info'})
    failed=sum(1 for x in tests if not x['ok'])
    return {'ok':failed==0,'version':VERSION,'timestamp':int(time.time()),'summary':{'total':len(tests),'passed':len(tests)-failed,'failed':failed},'tests':tests}

def load(path):
    with open(path,encoding='utf-8') as f:c=json.load(f)
    c['_config_path']=path
    return c

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);sp=ap.add_subparsers(dest='cmd',required=True);sp.add_parser('devices');sp.add_parser('selftest')
    for n in ('on','off','status','cycle'):
        p=sp.add_parser(n);p.add_argument('--switch',required=True);p.add_argument('--port',required=True,type=int)
    for n in ('group-on','group-off','group-cycle'):
        p=sp.add_parser(n);p.add_argument('--group',required=True)
    a=ap.parse_args();cfg=load(a.config);u=UniFi(cfg);debug_log(cfg,'debug',f'Backend command={a.cmd}')
    try:
        if a.cmd=='devices':print(json.dumps(u.list_devices(),ensure_ascii=False))
        elif a.cmd=='selftest':print(json.dumps(safe_selftest(cfg,a.config),ensure_ascii=False))
        elif a.cmd=='on':print(json.dumps(u.set_poe(a.switch,a.port,'auto'),ensure_ascii=False))
        elif a.cmd=='off':print(json.dumps(u.set_poe(a.switch,a.port,'off'),ensure_ascii=False))
        elif a.cmd=='status':print(json.dumps(u.status(a.switch,a.port),ensure_ascii=False))
        elif a.cmd=='cycle':u.set_poe(a.switch,a.port,'off');time.sleep(max(1,min(60,int(cfg.get('cycle_seconds',5)))));print(json.dumps(u.set_poe(a.switch,a.port,'auto'),ensure_ascii=False))
        else:print(json.dumps(u.group(a.group,{'group-on':'on','group-off':'off','group-cycle':'cycle'}[a.cmd]),ensure_ascii=False))
    except Exception as e:
        debug_log(cfg,'error',f'{a.cmd}: {e}'); print(json.dumps({'ok':False,'error':str(e)},ensure_ascii=False));sys.exit(2)
if __name__=='__main__':main()
