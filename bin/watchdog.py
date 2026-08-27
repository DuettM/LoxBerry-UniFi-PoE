#!/usr/bin/env python3
from pathlib import Path
import json, os, sys, subprocess, time, importlib.util, fcntl, tempfile

cfgfile=sys.argv[1]
with open(cfgfile,encoding='utf-8') as f:c=json.load(f)
c['_config_path']=cfgfile
if not c.get('watchdog',{}).get('enabled'):sys.exit(0)

bindir=os.path.dirname(__file__)
binfile=os.path.join(bindir,'unifipoe.py')
folder=os.path.basename(os.path.dirname(cfgfile)); lbhome=os.environ.get('LBHOME') or str(Path(cfgfile).resolve().parents[3]); datadir=os.path.join(lbhome,'data','plugins',folder); os.makedirs(datadir,exist_ok=True)
statefile=os.path.join(datadir,'watchdog.json')
lockfile=os.path.join(datadir,'watchdog.lock')

# Prevent overlapping cron runs.
lock=open(lockfile,'w')
try:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(0)

def load_old():
    try:
        with open(statefile,encoding='utf-8') as f:return json.load(f)
    except Exception:return {}

def atomic_write(data):
    d=os.path.dirname(statefile)
    fd,tmp=tempfile.mkstemp(prefix='.watchdog-',dir=d)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
        os.replace(tmp,statefile)
    finally:
        try:
            if os.path.exists(tmp):os.unlink(tmp)
        except Exception:pass

def load_backend():
    spec=importlib.util.spec_from_file_location('unifipoe',binfile)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

mod=load_backend()
base=mod.base_topic(c)

def publish_health(mod,state):
    try:
        mod.mqtt_publish(c,f'{base}/health/ok','1' if state['ok'] else '0')
        mod.mqtt_publish(c,f'{base}/health/timestamp',state['timestamp'])
        mod.mqtt_publish(c,f'{base}/health/consecutive_failures',state['consecutive_failures'])
        mod.mqtt_publish(c,f'{base}/health/response_ms',state.get('response_ms',0))
        if state.get('error'):mod.mqtt_publish(c,f'{base}/health/error',state['error'][:500])
    except Exception:pass

old=load_old(); start=time.time(); last_error=''; data=None
config_mtime=int(os.path.getmtime(cfgfile))
# After an authentication failure, do not hammer UniFi every minute.
# Automatic checks resume only after the settings file was saved/changed.
if old.get('auth_failure') and int(old.get('config_mtime',0)) == config_mtime:
    state=dict(old)
    state.update({'ok':False,'timestamp':int(time.time()),'error':'Automatische UniFi-Anmeldung pausiert: Zugangsdaten speichern/prüfen, um den Watchdog wieder freizugeben.'})
    atomic_write(state); publish_health(mod,state)
    mod.debug_log(c,'warning','Watchdog auth pause active; no controller login attempted')
    sys.exit(3)

def is_rate_limit(text):
    t=str(text).lower()
    return ('http 429 ' in t or 'limit_reached' in t or 'login attempt limit' in t or 'local_login_backoff' in t or 'login vorübergehend pausiert' in t)

def is_auth_error(text):
    t=str(text).lower()
    if is_rate_limit(t): return False
    return ('account_locked' in t or 'sso account locked' in t or 'http 401 ' in t or 'http 403 ' in t or 'unauthorized' in t or 'forbidden' in t or 'authentication_failed' in t)

for attempt in range(1,4):
    try:
        p=subprocess.run([binfile,'--config',cfgfile,'devices'],capture_output=True,text=True,timeout=35)
        if p.returncode!=0:raise RuntimeError((p.stdout+p.stderr)[-800:] or 'Backend return code '+str(p.returncode))
        data=json.loads(p.stdout)
        if not data.get('ok'):raise RuntimeError(data.get('error','UniFi API Fehler'))
        break
    except Exception as e:
        last_error=str(e)
        if is_rate_limit(last_error) or is_auth_error(last_error):
            break
        if attempt<3:time.sleep(attempt)

mod.debug_log(c,'debug','Watchdog run started')
if data:
    # Publish states from the one API snapshot; no extra controller requests per port.
    for d in data.get('devices',[]):
        for p in d.get('ports',[]):
            r={'switch':d.get('name') or d.get('mac'),'port':p.get('port_idx'),'alias':p.get('alias') or p.get('name') or f"Port {p.get('port_idx')}",'poe_mode':p.get('poe_mode','auto'),'poe_power':p.get('poe_power'),'poe_current':p.get('poe_current'),'poe_voltage':p.get('poe_voltage'),'link_up':bool(p.get('link_up')),'up':p.get('poe_mode','auto')!='off'}
            try:
                base_topic=mod.base_topic(c)
                key=mod.slug(r['alias']); root=f"{base_topic}/{mod.slug(r['switch'])}/{key}"
                for k in ('up','poe_mode','poe_power','poe_current','poe_voltage','link_up'):
                    if r.get(k) is not None:mod.mqtt_publish(c,f'{root}/{k}',('1' if r[k] is True else '0' if r[k] is False else r[k]))
            except Exception:pass
    state={'ok':True,'timestamp':int(time.time()),'last_success':int(time.time()),'consecutive_failures':0,'response_ms':int((time.time()-start)*1000),'switches':len(data.get('devices',[])),'ports':sum(len(d.get('ports',[])) for d in data.get('devices',[])),'error':'','auth_failure':False,'rate_limited':False,'config_mtime':config_mtime}
    atomic_write(state);publish_health(mod,state);mod.debug_log(c,'debug',f"Watchdog OK: {state['switches']} Switch(es), {state['ports']} Ports, {state['response_ms']} ms");sys.exit(0)
else:
    state={'ok':False,'timestamp':int(time.time()),'last_success':old.get('last_success',0),'consecutive_failures':int(old.get('consecutive_failures',0))+1,'response_ms':int((time.time()-start)*1000),'switches':old.get('switches',0),'ports':old.get('ports',0),'error':last_error[:800],'auth_failure':is_auth_error(last_error),'rate_limited':is_rate_limit(last_error),'config_mtime':config_mtime}
    atomic_write(state);publish_health(mod,state);mod.debug_log(c,'error',f"Watchdog failed: {last_error}");sys.exit(2)
