from pathlib import Path
import re


def replace(path, old, new, required=True):
    p=Path(path); s=p.read_text()
    if old not in s:
        if required: raise RuntimeError(f'pattern missing in {path}: {old[:100]!r}')
        return
    p.write_text(s.replace(old,new))

# Core version
replace('bin/unifipoe.py', "VERSION='0.7.7'", "VERSION='0.7.8'")

# Public Loxone API: query-string tokens are no longer accepted.
Path('webfrontend/html/poe.cgi').write_text(r'''#!/usr/bin/perl
use strict; use warnings; use CGI; use JSON::PP; use LoxBerry::System;
my $q=CGI->new; my $cfgfile="$lbpconfigdir/config.json";
open my $f,'<',$cfgfile or die "Content-Type: application/json\r\n\r\n{\"ok\":false,\"error\":\"config missing\"}";
local $/; my $c=decode_json(<$f>); close $f;
print "Content-Type: application/json\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n\r\n";
sub eq_ct { my($a,$b)=@_; return 0 if !defined($a)||!defined($b)||length($a)!=length($b); my $d=0; for(my $i=0;$i<length($a);$i++){ $d |= ord(substr($a,$i,1)) ^ ord(substr($b,$i,1)); } return $d==0; }
my %body;
if(uc($ENV{REQUEST_METHOD}//'GET') eq 'POST'){
  my $raw=$q->param('POSTDATA');
  if(defined($raw) && $raw ne ''){ eval { my $x=decode_json($raw); %body=%$x if ref($x) eq 'HASH'; 1; }; }
  for my $k (qw(token cmd switch port group)){ my $v=$q->param($k); $body{$k}=$v if defined $v; }
}
my $token=$ENV{HTTP_X_API_TOKEN}//'';
if($token eq '' && ($ENV{HTTP_AUTHORIZATION}//'') =~ /^Bearer\s+(.+)$/i){ $token=$1; }
$token=$body{token}//'' if $token eq '';
if(!eq_ct($token,$c->{api_token}//'')){ print encode_json({ok=>JSON::PP::false,error=>'unauthorized'}); exit; }
my $cmd=$body{cmd}//$q->param('cmd')//'status';
my %allowed=map { $_=>1 } qw(devices selftest on off status cycle group-on group-off group-cycle);
if(!$allowed{$cmd}){ print encode_json({ok=>JSON::PP::false,error=>'invalid command'}); exit; }
my @args=("$lbpbindir/unifipoe.py",'--config',$cfgfile,$cmd);
if($cmd =~ /^group-/){ my $g=$body{group}//$q->param('group')//''; if($g eq ''){print encode_json({ok=>JSON::PP::false,error=>'group missing'});exit;} push @args,'--group',$g; }
elsif($cmd ne 'devices' && $cmd ne 'selftest'){ my $sw=$body{switch}//$q->param('switch')//''; my $port=$body{port}//$q->param('port')//''; if($sw eq ''||$port!~/^\d+$/){print encode_json({ok=>JSON::PP::false,error=>'switch/port missing'});exit;} push @args,'--switch',$sw,'--port',$port; }
open my $p,'-|',@args or do{print encode_json({ok=>JSON::PP::false,error=>'backend start failed'});exit;}; local $/; my $out=<$p>; close $p; print $out||encode_json({ok=>JSON::PP::false,error=>'empty backend response'});
''')

# Config UI/backend persistence for MQTT command token.
p=Path('webfrontend/htmlauth/config.cgi'); s=p.read_text()
needle="$cfg->{mqtt}{listen_enabled} = (($q->param('mqtt_listen_enabled')//'0') eq '1') ? JSON::PP::true : JSON::PP::false;"
extra=needle+"\n    my $mct = $q->param('mqtt_command_token');\n    $cfg->{mqtt}{command_token} = $mct if defined($mct) && $mct ne '';\n    $cfg->{mqtt}{command_token_required} = (($q->param('mqtt_command_token_required')//'0') eq '1') ? JSON::PP::true : JSON::PP::false;"
if 'mqtt_command_token_required' not in s:
    if needle not in s: raise RuntimeError('config mqtt pattern missing')
    s=s.replace(needle,extra)
s=s.replace('$cfg->{config_version} = 5;', '$cfg->{config_version} = 7;').replace('$cfg->{config_version} = 6;', '$cfg->{config_version} = 7;')
p.write_text(s)

# MQTT command-token enforcement.
p=Path('bin/mqtt_listener.py'); s=p.read_text()
s=s.replace('import argparse, json, os, socket, struct, time, random, signal, sys, fcntl, importlib.util', 'import argparse, json, os, socket, struct, time, random, signal, sys, fcntl, importlib.util, hmac')
old="""def payload_action(raw):
    txt=raw.decode('utf-8','replace').strip()
    try:
        obj=json.loads(txt)
        if isinstance(obj,dict): txt=str(obj.get('action',obj.get('cmd','')))
    except Exception: pass
    a=txt.strip().lower()
    return {'1':'on','true':'on','ein':'on','on':'on','0':'off','false':'off','aus':'off','off':'off','restart':'cycle','reboot':'cycle','cycle':'cycle','status':'status','get':'status'}.get(a,a)
"""
new="""def payload_command(raw):
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
"""
if 'def payload_command' not in s:
    if old not in s: raise RuntimeError('mqtt payload parser missing')
    s=s.replace(old,new)
old2="rel=topic[len(prefix):].split('/'); action=payload_action(payload); api=core.UniFi(cfg)"
new2="rel=topic[len(prefix):].split('/'); action,token=payload_command(payload); mc=cfg.get('mqtt',{}); expected=str(mc.get('command_token','') or '')\n    if mc.get('command_token_required',True) and (not expected or not hmac.compare_digest(token,expected)): raise PermissionError('MQTT Command-Token fehlt oder ist ungültig')\n    api=core.UniFi(cfg)"
if old2 in s: s=s.replace(old2,new2)
p.write_text(s)

# Migration creates secure random MQTT command token.
for fn in ('postinstall.sh','postupgrade.sh'):
    p=Path(fn); s=p.read_text()
    marker="mc=c.setdefault('mqtt',{})"
    add=marker+"\nif not mc.get('command_token') or mc.get('command_token')=='CHANGE_ME': mc['command_token']=secrets.token_urlsafe(32)\nmc['command_token_required']=True"
    if "mc['command_token_required']=True" not in s:
        if marker not in s: raise RuntimeError(f'mqtt migration marker missing in {fn}')
        s=s.replace(marker,add,1)
    s=s.replace("c['config_version']=5", "c['config_version']=7").replace("c['config_version']=6", "c['config_version']=7")
    s=s.replace('Plugin 0.7.5 installiert','Plugin 0.7.8 installiert').replace('Plugin 0.7.6 installiert','Plugin 0.7.8 installiert').replace('Plugin auf 0.7.6 aktualisiert','Plugin auf 0.7.8 aktualisiert')
    p.write_text(s)

# Verified update downloader. It does NOT execute the archive.
Path('bin/secure_update.py').write_text(r'''#!/usr/bin/env python3
import argparse, hashlib, hmac, json, os, tempfile, urllib.parse, urllib.request
ALLOWED_HOSTS={'raw.githubusercontent.com','github.com','objects.githubusercontent.com'}
def fetch(url, limit=20*1024*1024):
    u=urllib.parse.urlparse(url)
    if u.scheme!='https' or u.hostname not in ALLOWED_HOSTS: raise RuntimeError('Unsichere oder nicht erlaubte Update-URL')
    req=urllib.request.Request(url,headers={'User-Agent':'LoxBerry-UniFi-PoE-secure-updater/0.7.8'})
    with urllib.request.urlopen(req,timeout=20) as r: data=r.read(limit+1)
    if len(data)>limit: raise RuntimeError('Update-Datei ist unerwartet groß')
    return data
def parse_cfg(data):
    out={}
    for line in data.decode('utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith(('#','[')) or '=' not in line: continue
        k,v=line.split('=',1); out[k.strip().upper()]=v.strip()
    return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--manifest',default='https://raw.githubusercontent.com/DuettM/LoxBerry-UniFi-PoE/main/release.cfg'); ap.add_argument('--output-dir',default=''); a=ap.parse_args()
    meta=parse_cfg(fetch(a.manifest,256*1024)); url=meta.get('ARCHIVEURL',''); checksum_url=meta.get('SHA256URL','')
    if not url or not checksum_url: raise RuntimeError('Release-Manifest enthält keine verifizierbare Prüfsumme')
    expected=fetch(checksum_url,4096).decode('utf-8').strip().split()[0].lower()
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected): raise RuntimeError('Ungültige SHA256-Prüfsumme')
    blob=fetch(url); actual=hashlib.sha256(blob).hexdigest()
    if not hmac.compare_digest(actual,expected): raise RuntimeError('SHA256-Prüfung FEHLGESCHLAGEN – Update wird verworfen')
    outdir=a.output_dir or tempfile.gettempdir(); os.makedirs(outdir,exist_ok=True)
    name=os.path.basename(urllib.parse.urlparse(url).path) or 'unifipoe-update.zip'; path=os.path.join(outdir,name)
    fd,tmp=tempfile.mkstemp(prefix='.verified-',dir=outdir)
    with os.fdopen(fd,'wb') as f: f.write(blob)
    os.chmod(tmp,0o600); os.replace(tmp,path)
    print(json.dumps({'ok':True,'version':meta.get('VERSION',''),'sha256':actual,'path':path},ensure_ascii=False))
if __name__=='__main__': main()
''')

# UI controls and generator.
p=Path('webfrontend/htmlauth/index.cgi'); s=p.read_text()
old="print '<div class=\"field\"><label>Broker</label><input value=\"LoxBerry MQTT Gateway (automatisch)\" disabled><div class=\"hint\">Wird aus $LBHOME/config/system/general.json → Mqtt gelesen.</div></div></div><div class=\"checks\">';"
new="print '<div class=\"field\"><label>Broker</label><input value=\"LoxBerry MQTT Gateway (automatisch)\" disabled><div class=\"hint\">Wird aus $LBHOME/config/system/general.json → Mqtt gelesen.</div></div>';\nprint '<div class=\"field\"><label>MQTT Command-Token</label><div style=\"display:flex;gap:6px\"><input id=\"mqtt_command_token\" name=\"mqtt_command_token\" value=\"'.esc($c->{mqtt}{command_token}//'').'\"><button class=\"btn\" type=\"button\" onclick=\"newMqttToken()\">Neu</button><button class=\"btn\" type=\"button\" onclick=\"copyMqttToken()\">Kopieren</button></div><div class=\"hint\">Muss bei MQTT-Schaltbefehlen im Payload mitgesendet werden.</div></div></div><div class=\"checks\">';"
if 'MQTT Command-Token</label>' not in s:
    if old not in s: raise RuntimeError('index broker pattern missing')
    s=s.replace(old,new)
old="<label><input type=\"checkbox\" name=\"mqtt_retain\" value=\"1\"'.($c->{mqtt}{retain}?' checked':'').'> Status retained</label>"
new=old+"<label><input type=\"checkbox\" name=\"mqtt_command_token_required\" value=\"1\"'.(($c->{mqtt}{command_token_required}//1)?' checked':'').'> MQTT Command-Token erforderlich</label>"
if 'name="mqtt_command_token_required"' not in s: s=s.replace(old,new)
s=s.replace("for(const n of ['verify_ssl','watchdog_enabled','mqtt_enabled','mqtt_listen_enabled','mqtt_retain'])", "for(const n of ['verify_ssl','watchdog_enabled','mqtt_enabled','mqtt_listen_enabled','mqtt_retain','mqtt_command_token_required'])")
copyfun="async function copyToken(){let t=document.getElementById('api_token').value;if(await copyText(t)){let s=document.getElementById('settings-state');s.textContent='Token kopiert';setTimeout(()=>s.textContent='',1800)}}"
if 'function newMqttToken()' not in s:
    s=s.replace(copyfun,copyfun+"\nfunction newMqttToken(){let a=new Uint8Array(32);crypto.getRandomValues(a);document.getElementById('mqtt_command_token').value=Array.from(a,b=>b.toString(16).padStart(2,'0')).join('');buildLoxoneUrl()}\nasync function copyMqttToken(){let t=document.getElementById('mqtt_command_token').value;if(await copyText(t)){let s=document.getElementById('settings-state');s.textContent='MQTT-Token kopiert';setTimeout(()=>s.textContent='',1800)}}")
oldgen="if(mode==='mqtt'){let map={on:'ON',off:'OFF',cycle:'CYCLE',status:'STATUS'};out.textContent=resolvedMqttBase()+'/set/port/'+d.id+'/'+p;pl.textContent=map[a]||a.toUpperCase();pw.style.display='block';lab.textContent='MQTT Topic'}else{out.textContent=location.origin+'/plugins/unifipoe/poe.cgi?token='+encodeURIComponent(t)+'&cmd='+encodeURIComponent(a)+'&switch='+encodeURIComponent(d.id)+'&port='+encodeURIComponent(p);pw.style.display='none';lab.textContent='Fertige URL'}"
newgen="if(mode==='mqtt'){let mt=document.getElementById('mqtt_command_token')?.value||'';out.textContent=resolvedMqttBase()+'/set/port/'+d.id+'/'+p;pl.textContent=JSON.stringify({token:mt,action:a.toUpperCase()});pw.style.display='block';lab.textContent='MQTT Topic'}else{out.textContent=location.origin+'/plugins/unifipoe/poe.cgi';pl.textContent='token='+encodeURIComponent(t)+'&cmd='+encodeURIComponent(a)+'&switch='+encodeURIComponent(d.id)+'&port='+encodeURIComponent(p);pw.style.display='block';lab.textContent='HTTP POST URL'}"
if oldgen not in s: raise RuntimeError('generator pattern missing')
s=s.replace(oldgen,newgen)
s=s.replace("let mode=document.getElementById('gen-mode')?.value||'http',v=document.getElementById('gen-url').textContent+(mode==='mqtt'?'\\nPayload: '+document.getElementById('gen-payload').textContent:'')", "let mode=document.getElementById('gen-mode')?.value||'http',v=document.getElementById('gen-url').textContent+'\\nPayload: '+document.getElementById('gen-payload').textContent")
s=s.replace('HTTP nutzt den API-Token. MQTT nutzt automatisch', 'HTTP nutzt POST-Body oder Header statt Token in der URL. MQTT nutzt ein separates Command-Token und automatisch')
p.write_text(s)

# Release metadata uses external checksum asset to avoid self-referential archive hashing.
release='''[AUTOUPDATE]\nVERSION=0.7.8\nARCHIVEURL=https://github.com/DuettM/LoxBerry-UniFi-PoE/releases/download/v0.7.8/LoxBerry-UniFi-PoE-0.7.8.zip\nINFOURL=https://github.com/DuettM/LoxBerry-UniFi-PoE/blob/main/CHANGELOG.md\nSHA256URL=https://github.com/DuettM/LoxBerry-UniFi-PoE/releases/download/v0.7.8/LoxBerry-UniFi-PoE-0.7.8.zip.sha256\n'''
Path('release.cfg').write_text(release); Path('prerelease.cfg').write_text(release)

p=Path('CHANGELOG.md'); s=p.read_text(); note='''## 0.7.8\n\n- Loxone API-Token aus der URL entfernt; Authentifizierung über `X-API-Token`, `Authorization: Bearer` oder POST-Body.\n- MQTT-Command-Token eingeführt und bei Updates automatisch zufällig erzeugt.\n- Reine MQTT-ON/OFF/CYCLE-Payloads werden bei aktiviertem Token-Schutz abgewiesen.\n- Native ungeprüfte LoxBerry-Auto-Installation deaktiviert.\n- Neuer `secure_update.py` akzeptiert ein Update-ZIP nur nach erfolgreicher SHA-256-Prüfung gegen das Release-Checksum-Asset.\n- Eine Publisher-Signatur bleibt optional für einen später hinterlegten privaten Signierschlüssel; kein privater Schlüssel wird im Repository gespeichert.\n\n'''
if '## 0.7.8' not in s: s=s.replace('# Changelog\n\n','# Changelog\n\n'+note)
p.write_text(s)
