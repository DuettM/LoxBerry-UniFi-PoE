#!/usr/bin/env python3
import json, os, sys, tempfile

path=sys.argv[1]
with open(path,encoding='utf-8') as f:
    cfg=json.load(f)
mqtt=cfg.setdefault('mqtt',{})
for key in ('host','port','username','password'):
    mqtt.pop(key,None)
if not mqtt.get('base_topic') or mqtt.get('base_topic') == 'loxberry/unifipoe':
    mqtt['base_topic']='unifipoe'
mqtt.setdefault('enabled',True)
mqtt.setdefault('retain',True)
fd,tmp=tempfile.mkstemp(prefix='.unifipoe-config-',dir=os.path.dirname(path))
try:
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        json.dump(cfg,f,ensure_ascii=False,indent=2)
        f.write('\n')
    os.replace(tmp,path)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
