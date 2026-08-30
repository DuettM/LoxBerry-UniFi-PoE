from pathlib import Path

# API: add health + watchdog-run commands.
p = Path('webfrontend/htmlauth/api.cgi')
s = p.read_text()
old = "my %allowed=map { $_=>1 } qw(devices selftest on off status cycle group-on group-off group-cycle);"
new = "my %allowed=map { $_=>1 } qw(devices selftest health watchdog-run on off status cycle group-on group-off group-cycle);"
if old not in s:
    raise SystemExit('allowed command list not found')
s = s.replace(old, new, 1)
marker = "my @args=(\"$lbpbindir/unifipoe.py\",'--config',$cfgfile,$cmd);"
block = r'''if($cmd eq 'health'){
  sub read_json_file { my ($path)=@_; my $data={}; if(open my $f,'<',$path){ local $/; my $raw=<$f>//''; close $f; eval{$data=decode_json($raw);1} or $data={}; } return $data; }
  my $self=read_json_file("$lbpdatadir/selftest.json");
  my $watch=read_json_file("$lbpdatadir/watchdog.json");
  my $cfg=read_json_file($cfgfile);
  out({ok=>JSON::PP::true,selftest=>$self,selftest_exists=>(-f "$lbpdatadir/selftest.json"?JSON::PP::true:JSON::PP::false),watchdog=>$watch,watchdog_exists=>(-f "$lbpdatadir/watchdog.json"?JSON::PP::true:JSON::PP::false),watchdog_enabled=>(($cfg->{watchdog}&&$cfg->{watchdog}{enabled})?JSON::PP::true:JSON::PP::false)});
}
if($cmd eq 'watchdog-run'){
  reject_cross_site(); require_csrf();
  out({ok=>JSON::PP::false,error=>'Watchdog-Start ist nur per POST erlaubt.'}) if uc($ENV{REQUEST_METHOD}//'GET') ne 'POST';
  my $pid=fork(); out({ok=>JSON::PP::false,error=>'Watchdog konnte nicht gestartet werden.'}) unless defined $pid;
  if($pid==0){ open STDIN,'<','/dev/null'; open STDOUT,'>','/dev/null'; open STDERR,'>','/dev/null'; exec "$lbpbindir/watchdog.py",$cfgfile; exit 127; }
  out({ok=>JSON::PP::true,started=>JSON::PP::true});
}
my @args=("$lbpbindir/unifipoe.py",'--config',$cfgfile,$cmd);'''
if marker not in s:
    raise SystemExit('backend args marker not found')
s = s.replace(marker, block, 1)
s = s.replace("elsif($cmd ne 'devices' && $cmd ne 'selftest'){", "elsif($cmd ne 'devices' && $cmd ne 'selftest' && $cmd ne 'health' && $cmd ne 'watchdog-run'){")
p.write_text(s)

# Dashboard: health status only through api.cgi.
p = Path('webfrontend/htmlauth/index.cgi')
s = p.read_text()
old = "async function loadSelftestStatus(){if(SELFTEST_CHECKED)return;SELFTEST_CHECKED=true;try{let j=await jsonFetch('debug.cgi?action=selftest'),st=j.selftest||{},age=st.timestamp?Math.floor(Date.now()/1000)-Number(st.timestamp):999999;if(j.exists&&st.timestamp){renderSelftestResult(st)}if(!j.exists||!st.timestamp||age>21600){await runSelftest(false)}}catch(e){document.getElementById('m-system').textContent='FEHLER';document.getElementById('m-system-sub').textContent='Selbstteststatus nicht lesbar'}}"
new = "async function loadSelftestStatus(){if(SELFTEST_CHECKED)return;SELFTEST_CHECKED=true;try{let j=await call('cmd=health'),st=j.selftest||{},age=st.timestamp?Math.floor(Date.now()/1000)-Number(st.timestamp):999999;if(j.selftest_exists&&st.timestamp){renderSelftestResult(st)}if(!j.selftest_exists||!st.timestamp||age>21600){await runSelftest(false)}}catch(e){document.getElementById('m-system').textContent='FEHLER';document.getElementById('m-system-sub').textContent='Selbstteststatus nicht lesbar: '+e.message}}"
if old not in s:
    raise SystemExit('selftest dashboard block not found')
s = s.replace(old, new, 1)
start = s.find('async function loadWatchdog(){')
end = s.find('async function loadLog(){', start)
if start < 0 or end < 0:
    raise SystemExit('watchdog dashboard block not found')
new_watch = '''async function loadWatchdog(){try{let j=await call('cmd=health'),w=j.watchdog||{},enabled=!!j.watchdog_enabled,exists=!!j.watchdog_exists;if(!enabled){document.getElementById('wd-ok').innerHTML='<span class="muted">Deaktiviert</span>';for(const id of ['wd-last','wd-ms','wd-fails','wd-switches','wd-ports'])document.getElementById(id).textContent='–';document.getElementById('m-watchdog').textContent='AUS';document.getElementById('m-watchdog-sub').textContent='Deaktiviert';document.getElementById('sys-watchdog').innerHTML='<span class="muted">Deaktiviert</span>';return}if(!exists||!w.timestamp){document.getElementById('wd-ok').innerHTML='<span class="warn">Ausstehend</span>';document.getElementById('m-watchdog').textContent='START';document.getElementById('m-watchdog-sub').textContent='Warte auf erste Prüfung';document.getElementById('sys-watchdog').innerHTML='<span class="warn">Wartet</span>';if(!WATCHDOG_KICKED){WATCHDOG_KICKED=true;try{await call('cmd=watchdog-run',true);setTimeout(loadWatchdog,2500)}catch(e){}}return}let age=Math.floor(Date.now()/1000)-Number(w.timestamp||0),stale=age>180;document.getElementById('wd-ok').innerHTML=w.ok&&!stale?'<span class="ok">OK</span>':(stale?'<span class="warn">Veraltet</span>':'<span class="bad">Fehler</span>');document.getElementById('wd-last').textContent=w.last_success?new Date(w.last_success*1000).toLocaleString():'–';document.getElementById('wd-ms').textContent=(w.response_ms??'–')+' ms';document.getElementById('wd-fails').textContent=w.consecutive_failures??'–';document.getElementById('wd-switches').textContent=w.switches??'–';document.getElementById('wd-ports').textContent=w.ports??'–';document.getElementById('m-watchdog').textContent=w.ok&&!stale?'OK':(stale?'ALT':'FEHLER');document.getElementById('m-watchdog-sub').textContent=(stale?'Status veraltet · ':'Letzte Prüfung: ')+new Date(w.timestamp*1000).toLocaleTimeString();document.getElementById('sys-watchdog').innerHTML=w.ok&&!stale?'<span class="ok">Aktiv · OK</span>':(stale?'<span class="warn">Aktiv · Status veraltet</span>':'<span class="bad">Aktiv · Fehler</span>')}catch(e){document.getElementById('m-watchdog').textContent='FEHLER';document.getElementById('m-watchdog-sub').textContent='Status nicht lesbar: '+e.message;document.getElementById('sys-watchdog').innerHTML='<span class="bad">Fehler</span>'}}
'''
s = s[:start] + new_watch + s[end:]
p.write_text(s)

# Version metadata.
for fn in ['plugin.cfg', 'release.cfg', 'prerelease.cfg']:
    q = Path(fn)
    q.write_text(q.read_text().replace('0.7.21', '0.7.22'))

cp = Path('CHANGELOG.md')
cs = cp.read_text()
if '## 0.7.22' not in cs:
    cp.write_text('## 0.7.22\n- Fix: Dashboard Systemtest/Watchdog use api.cgi health endpoint instead of debug.cgi.\n- Fix: Watchdog kick uses authenticated POST.\n\n' + cs)
