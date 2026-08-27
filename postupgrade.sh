#!/bin/bash
# Restore user configuration after update. The archive contains only
# config.default.json, never config.json, so credentials cannot be replaced by
# package defaults even if backup/restore is skipped by an installer variant.
set -u
PDIR="${3:-}"
[ -n "$PDIR" ] || { echo "<FAIL> Plugin folder argument missing."; exit 1; }
PCONFIG="${LBPCONFIG:?LBPCONFIG missing}/$PDIR"
PBIN="${LBPBIN:?LBPBIN missing}/$PDIR"
PDATA="${LBPDATA:?LBPDATA missing}/$PDIR"
PLOG="${LBPLOG:?LBPLOG missing}/$PDIR"
BACKUP="/tmp/loxberry-unifipoe-${PDIR}-config-backup.json"
mkdir -p "$PCONFIG" "$PDATA" "$PLOG"

if [ -f "$BACKUP" ]; then
  if python3 -m json.tool "$BACKUP" >/dev/null 2>&1; then
    cp -p "$BACKUP" "$PCONFIG/config.json" || exit 1
    chmod 600 "$PCONFIG/config.json" 2>/dev/null || true
    echo "<INFO> Existing UniFi PoE configuration restored."
  else
    echo "<WARNING> Upgrade backup is invalid JSON and was not restored."
  fi
  rm -f "$BACKUP"
fi

# Safety fallback: only create a new config on installations where no user
# config exists at all.
if [ ! -f "$PCONFIG/config.json" ]; then
  cp "$PCONFIG/config.default.json" "$PCONFIG/config.json" || exit 1
  echo "<WARNING> No previous config found; created defaults. Credentials must be entered once."
fi

python3 - "$PCONFIG/config.json" "$PCONFIG/config.default.json" <<'PYMIG' || exit 1
import json,sys,os,tempfile,secrets,copy
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
oldtopic=str(mc.get('base_topic','') or '').strip().strip('/')
host=os.uname().nodename.split('.')[0]
if c.get('config_version',0) < 5 and (not oldtopic or oldtopic.upper()=='AUTO/UNIFIPOE' or oldtopic.lower()==(host+'/unifipoe').lower()):
    mc['base_topic']='unifipoe'
mc['use_loxberry']=True
for key in ('host','port','username','password'):
    mc.pop(key,None)
c['config_version']=5
fd,tmp=tempfile.mkstemp(prefix='.config-',dir=os.path.dirname(p),text=True)
with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(c,f,ensure_ascii=False,indent=2); f.write('\n')
os.chmod(tmp,0o600); os.replace(tmp,p)
PYMIG

printf "%s [INFO] Plugin auf 0.7.5 aktualisiert; Benutzerkonfiguration erhalten\n" "$(date "+%Y-%m-%d %H:%M:%S")" >> "$PLOG/unifipoe.log" 2>/dev/null || true
rm -f "$PDATA/unifi_session.cookies" "$PDATA/unifi_session.json" 2>/dev/null || true
nohup "$PBIN/mqtt_listener.py" --config "$PCONFIG/config.json" --core "$PBIN/unifipoe.py" >>"$PLOG/mqtt-daemon.log" 2>&1 &
# Run watchdog once after upgrade if enabled so the dashboard gets a state immediately.
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
