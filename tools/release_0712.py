#!/usr/bin/env python3
from pathlib import Path

# Version bumps
p=Path('plugin.cfg'); s=p.read_text(); s=s.replace('VERSION=0.7.11','VERSION=0.7.12'); p.write_text(s)
p=Path('bin/unifipoe.py'); s=p.read_text(); s=s.replace("VERSION='0.7.11'","VERSION='0.7.12'"); p.write_text(s)
for fn in ('postinstall.sh','postupgrade.sh'):
    p=Path(fn); s=p.read_text().replace('0.7.11','0.7.12'); p.write_text(s)

# index.cgi: session-bound stateless HMAC CSRF token.
p=Path('webfrontend/htmlauth/index.cgi'); s=p.read_text()
if 'use Digest::SHA qw(hmac_sha256_hex);' not in s:
    s=s.replace('use File::Basename qw(basename);','use File::Basename qw(basename);\nuse Digest::SHA qw(hmac_sha256_hex);')
marker="my $public_api_js = encode_json('/plugins/'.$plugin_folder.'/poe.cgi');"
if 'my $csrf_js' not in s:
    s=s.replace(marker, marker+"\nmy $csrf_seed = ($ENV{HTTP_COOKIE}//'').'|'.($ENV{HTTP_USER_AGENT}//'');\nmy $csrf_js = encode_json(hmac_sha256_hex($csrf_seed, ($c->{api_token}//'')));" )
if "const CSRF=$csrf_js;" not in s:
    s=s.replace("const API='api.cgi';", "const API='api.cgi'; const CSRF=$csrf_js;",1)
old="async function jsonFetch(url,opts={}){let r=await fetch(url,{cache:'no-store',...opts})"
new="async function jsonFetch(url,opts={}){let hdr=new Headers(opts.headers||{});if((opts.method||'GET').toUpperCase()==='POST')hdr.set('X-UniFi-CSRF',CSRF);let r=await fetch(url,{cache:'no-store',...opts,headers:hdr})"
if old in s: s=s.replace(old,new,1)
elif 'X-UniFi-CSRF' not in s: raise SystemExit('index jsonFetch pattern not found')
p.write_text(s)

csrf_helpers="""sub ct_eq {
  my ($a,$b)=@_; return 0 if !defined($a)||!defined($b)||length($a)!=length($b);
  my $v=0; for(my $i=0;$i<length($a);$i++){ $v |= ord(substr($a,$i,1)) ^ ord(substr($b,$i,1)); } return $v==0;
}
sub require_csrf {
  open my $cf,'<',$cfgfile or out({ok=>JSON::PP::false,error=>'CSRF-Konfiguration nicht lesbar.'});
  local $/; my $raw=<$cf>//''; close $cf; my $cc; eval{$cc=decode_json($raw);1} or out({ok=>JSON::PP::false,error=>'CSRF-Konfiguration ungültig.'});
  my $seed=($ENV{HTTP_COOKIE}//'').'|'.($ENV{HTTP_USER_AGENT}//'');
  my $expected=hmac_sha256_hex($seed,($cc->{api_token}//''));
  my $sent=$ENV{HTTP_X_UNIFI_CSRF}//'';
  out({ok=>JSON::PP::false,error=>'CSRF-Prüfung fehlgeschlagen.'}) unless ct_eq($sent,$expected);
}
"""

# api.cgi
p=Path('webfrontend/htmlauth/api.cgi'); s=p.read_text()
if 'use Digest::SHA qw(hmac_sha256_hex);' not in s:
    s=s.replace('use LoxBerry::System;','use LoxBerry::System;\nuse Digest::SHA qw(hmac_sha256_hex);')
if 'sub require_csrf' not in s: s=s.replace('sub reject_cross_site {',csrf_helpers+'sub reject_cross_site {')
needle="  reject_cross_site();\n  out({ok=>JSON::PP::false,error=>'Schaltbefehle sind nur per POST erlaubt.'})"
if needle in s: s=s.replace(needle,"  reject_cross_site();\n  require_csrf();\n  out({ok=>JSON::PP::false,error=>'Schaltbefehle sind nur per POST erlaubt.'})")
s=s.replace("if($cmd =~ /^group-/){ my $g=$q->param('group')//''; out({ok=>JSON::PP::false,error=>'Gruppe fehlt.'}) if $g eq '';", "if($cmd =~ /^group-/){ my $g=$q->param('group')//''; out({ok=>JSON::PP::false,error=>'Gruppe ungültig.'}) if $g eq '' || length($g)>80 || $g =~ /[\\r\\n\\0]/;")
s=s.replace("out({ok=>JSON::PP::false,error=>'Switch/Port fehlt.'}) if $sw eq '' || $port !~ /^\\d+$/;", "out({ok=>JSON::PP::false,error=>'Switch/Port ungültig.'}) if $sw eq '' || length($sw)>128 || $sw =~ /[\\r\\n\\0]/ || $port !~ /^\\d+$/ || $port < 1 || $port > 512;")
p.write_text(s)

# config.cgi
p=Path('webfrontend/htmlauth/config.cgi'); s=p.read_text()
if 'use Digest::SHA qw(hmac_sha256_hex);' not in s: s=s.replace('use File::Temp qw(tempfile);','use File::Temp qw(tempfile);\nuse Digest::SHA qw(hmac_sha256_hex);')
if 'sub require_csrf' not in s: s=s.replace('sub reject_cross_site {',csrf_helpers+'sub reject_cross_site {')
for text in ("Speichern ist nur per POST erlaubt.","Verbindungstest ist nur per POST erlaubt."):
    needle="    reject_cross_site();\n    out({ok=>JSON::PP::false,error=>'"+text+"'})"
    if needle in s: s=s.replace(needle,"    reject_cross_site();\n    require_csrf();\n    out({ok=>JSON::PP::false,error=>'"+text+"'})")
validate="""sub validate_cfg {
    my ($cfg)=@_;
    my $controller=$cfg->{controller}//'';
    out({ok=>JSON::PP::false,error=>'Controller-URL ungültig.'}) unless $controller =~ m{^https?://[^\\s/]+(?::\\d{1,5})?(?:/.*)?$}i && length($controller)<=512;
    out({ok=>JSON::PP::false,error=>'Benutzername ungültig.'}) if !defined($cfg->{username}) || $cfg->{username} eq '' || length($cfg->{username})>128 || $cfg->{username}=~/[\\r\\n\\0]/;
    my $site=$cfg->{site}//'default'; out({ok=>JSON::PP::false,error=>'Site ungültig.'}) if length($site)>80 || $site=~/[\\r\\n\\0]/;
    my $cy=int($cfg->{cycle_seconds}//5); out({ok=>JSON::PP::false,error=>'Cycle-Zeit muss zwischen 1 und 120 Sekunden liegen.'}) if $cy<1 || $cy>120;
    my $api=$cfg->{api_token}//''; out({ok=>JSON::PP::false,error=>'API-Token ungültig.'}) if length($api)<16 || length($api)>256 || $api=~/[\\r\\n\\0]/;
    my $topic=$cfg->{mqtt}{base_topic}//'unifipoe'; out({ok=>JSON::PP::false,error=>'MQTT Topic ungültig.'}) if length($topic)>128 || $topic=~/[+#\\s\\0]/;
}
"""
if 'sub validate_cfg' not in s: s=s.replace('sub overlay_from_request {',validate+'sub overlay_from_request {')
s=s.replace("    $cfg = overlay_from_request($cfg, 0);", "    $cfg = overlay_from_request($cfg, 0);\n    validate_cfg($cfg);")
s=s.replace("    $cfg = overlay_from_request($cfg, 1);", "    $cfg = overlay_from_request($cfg, 1);\n    validate_cfg($cfg);")
p.write_text(s)

# debug.cgi
p=Path('webfrontend/htmlauth/debug.cgi'); s=p.read_text()
if 'use Digest::SHA qw(hmac_sha256_hex);' not in s: s=s.replace('use LoxBerry::System;','use LoxBerry::System; use Digest::SHA qw(hmac_sha256_hex);')
dbg_helpers=csrf_helpers.replace("out({ok=>JSON::PP::false,error=>'CSRF-Konfiguration nicht lesbar.'});","print encode_json({ok=>JSON::PP::false,error=>'CSRF-Konfiguration nicht lesbar.'}); exit;").replace("out({ok=>JSON::PP::false,error=>'CSRF-Konfiguration ungültig.'});","print encode_json({ok=>JSON::PP::false,error=>'CSRF-Konfiguration ungültig.'}); exit;").replace("out({ok=>JSON::PP::false,error=>'CSRF-Prüfung fehlgeschlagen.'}) unless ct_eq($sent,$expected);","if(!ct_eq($sent,$expected)){ print encode_json({ok=>JSON::PP::false,error=>'CSRF-Prüfung fehlgeschlagen.'}); exit; }")
if 'sub require_csrf' not in s: s=s.replace('sub cross_site {',dbg_helpers+'sub cross_site {')
for action in ('watchdog_run','clear'):
    needle="if($action eq '"+action+"'){\n  if(cross_site())"
    repl="if($action eq '"+action+"'){\n  if(uc($ENV{REQUEST_METHOD}//'GET') ne 'POST'){ print encode_json({ok=>JSON::PP::false,error=>'Nur POST erlaubt.'}); exit; }\n  require_csrf();\n  if(cross_site())"
    if needle in s: s=s.replace(needle,repl)
redact="""sub redact_line {
  my ($line,$cfg)=@_;
  my @secrets=grep { defined($_) && length($_)>=4 } ($cfg->{password},$cfg->{api_token},$cfg->{mqtt}{command_token});
  for my $secret (@secrets){ $line =~ s/\\Q$secret\\E/[REDACTED]/g; }
  $line =~ s{(Authorization\\s*:\\s*(?:Bearer|Basic)\\s+)[^\\s,;]+}{$1[REDACTED]}ig;
  $line =~ s{((?:password|passwd|token|api[_-]?token|secret)\\s*[=:]\\s*)[^\\s,;]+}{$1[REDACTED]}ig;
  $line =~ s{(\"(?:password|passwd|token|api_token|secret)\"\\s*:\\s*\")[^\"]*(\")}{$1[REDACTED]$2}ig;
  return $line;
}
"""
if 'sub redact_line' not in s: s=s.replace('sub read_json_file {',redact+'sub read_json_file {')
old="chomp @all;\nprint encode_json({ok=>JSON::PP::true,lines=>\\@all,count=>scalar(@all)});"
new="chomp @all;\nmy $rcfg=read_json_file(\"$lbpconfigdir/config.json\"); @all=map { redact_line($_,$rcfg) } @all;\nprint encode_json({ok=>JSON::PP::true,lines=>\\@all,count=>scalar(@all)});"
if old in s: s=s.replace(old,new)
p.write_text(s)

p=Path('CHANGELOG.md'); s=p.read_text(); note='''## 0.7.12\n\n- Sitzungsgebundener HMAC-CSRF-Schutz für Admin-POSTs.\n- Zusätzliche Eingabevalidierung für Controller, MQTT, Ports, Gruppen und Tokens.\n- Secret-Redaction im Debug-Log für Passwörter, Tokens und Authorization-Header.\n- Debug-Mutationen nur noch per POST.\n\n'''
if '## 0.7.12' not in s: s=s.replace('# Changelog\n\n','# Changelog\n\n'+note)
p.write_text(s)
