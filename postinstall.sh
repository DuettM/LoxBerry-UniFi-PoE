#!/bin/bash
set -u
PDIR="${3:-}"
[ -n "$PDIR" ] || { echo "<FAIL> Plugin folder argument missing."; exit 1; }
PCONFIG="${LBPCONFIG:?LBPCONFIG missing}/$PDIR"
PBIN="${LBPBIN:?LBPBIN missing}/$PDIR"
PHTMLAUTH="${LBPHTMLAUTH:?LBPHTMLAUTH missing}/$PDIR"
PHTML="${LBPHTML:?LBPHTML missing}/$PDIR"
PDATA="${LBPDATA:?LBPDATA missing}/$PDIR"
PLOG="${LBPLOG:?LBPLOG missing}/$PDIR"
mkdir -p "$PCONFIG" "$PDATA" "$PLOG"

# IMPORTANT: config.json is NEVER shipped in the archive anymore. On a fresh
# install create it once from config.default.json. This prevents future updates
# from replacing credentials/settings with factory defaults.
if [ ! -f "$PCONFIG/config.json" ]; then
  cp "$PCONFIG/config.default.json" "$PCONFIG/config.json" || exit 1
  echo "<INFO> Fresh UniFi PoE configuration created."
fi

python3 - "$PCONFIG/config.json" "$PCONFIG/config.default.json" <<'PYCFG' || exit 1
import json,secrets,sys,os,tempfile,copy
p,dp=sys.argv[1:3]
with open(p,encoding='utf-8') as f:c=json.load(f)
with open(dp,encoding='utf-8') as f:d=json.load(f)
def merge(dst,defs):
    for k,v in defs.items():
        if k not in dst: dst[k]=copy.deepcopy(v)
        elif isinstance(v,dict) and isinstance(dst.get(k),dict): merge(dst[k],v)
merge(c,d)
if not c.get('api_token') or c.get('api_token')=='CHANGE_ME': c['api_token']=secrets.token_urlsafe(32)
# Migrate MQTT to LoxBerry Gateway while preserving genuinely custom topic roots.
mc=c.setdefault('mqtt',{})
if not mc.get('command_token') or mc.get('command_token')=='CHANGE_ME': mc['command_token']=secrets.token_urlsafe(32)
mc['command_token_required']=True
oldtopic=str(mc.get('base_topic','') or '').strip().strip('/')
host=os.uname().nodename.split('.')[0]
if c.get('config_version',0) < 5 and (not oldtopic or oldtopic.upper()=='AUTO/UNIFIPOE' or oldtopic.lower()==(host+'/unifipoe').lower()):
    mc['base_topic']='unifipoe'
mc['use_loxberry']=True
for key in ('host','port','username','password'):
    mc.pop(key,None)
c['config_version']=7
d=os.path.dirname(p); fd,tmp=tempfile.mkstemp(prefix='.config-',dir=d,text=True)
with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(c,f,ensure_ascii=False,indent=2); f.write('\n')
os.chmod(tmp,0o600); os.replace(tmp,p)
PYCFG

chmod 700 "$PBIN/unifipoe.py" "$PBIN/watchdog.py" "$PBIN/mqtt_listener.py" 2>/dev/null || true
chmod 755 "$PHTMLAUTH/index.cgi" "$PHTMLAUTH/config.cgi" "$PHTMLAUTH/debug.cgi" "$PHTMLAUTH/api.cgi" "$PHTML/poe.cgi" 2>/dev/null || true
chmod 600 "$PCONFIG/config.json" 2>/dev/null || true
touch "$PLOG/unifipoe.log"; chmod 600 "$PLOG/unifipoe.log" 2>/dev/null || true
printf "%s [INFO] Plugin 0.7.9 installiert\n" "$(date "+%Y-%m-%d %H:%M:%S")" >> "$PLOG/unifipoe.log" 2>/dev/null || true

# Start command receiver and (if enabled) one initial watchdog check.
nohup "$PBIN/mqtt_listener.py" --config "$PCONFIG/config.json" --core "$PBIN/unifipoe.py" >>"$PLOG/mqtt-daemon.log" 2>&1 &
python3 - "$PCONFIG/config.json" "$PBIN/watchdog.py" <<'PYWD' >/dev/null 2>&1
import json,sys,subprocess
cfg,wd=sys.argv[1:3]
try:
    c=json.load(open(cfg,encoding='utf-8'))
    if c.get('watchdog',{}).get('enabled'):
        subprocess.Popen([wd,cfg],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
except Exception: pass
PYWD
exit 0
