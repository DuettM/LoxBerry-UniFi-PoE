#!/usr/bin/perl
use strict;
use warnings;
use CGI;
use JSON::PP;
use LoxBerry::System;
use Digest::SHA qw(hmac_sha256_hex);

my $q=CGI->new;
my $cfgfile="$lbpconfigdir/config.json";
print "Content-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n\r\n";
sub out { my ($x)=@_; print encode_json($x); exit; }
sub ct_eq {
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
sub reject_cross_site {
  my $site=lc($ENV{HTTP_SEC_FETCH_SITE}//'');
  out({ok=>JSON::PP::false,error=>'Cross-Site-Anfrage blockiert.'}) if $site eq 'cross-site';
  my $host=lc($ENV{HTTP_HOST}//'');
  for my $h (qw(HTTP_ORIGIN HTTP_REFERER)) {
    my $v=lc($ENV{$h}//''); next if $v eq '' || $host eq '';
    out({ok=>JSON::PP::false,error=>'Cross-Site-Anfrage blockiert.'}) if $v =~ m{^https?://([^/]+)} && $1 ne $host;
  }
}
sub atomic_json_write {
  my ($path,$obj)=@_;
  my $tmp=$path.'.tmp';
  if(open my $f,'>',$tmp){ print $f JSON::PP->new->utf8->canonical->pretty->encode($obj); close $f; chmod 0600,$tmp; rename $tmp,$path; }
}
my $cmd=$q->param('cmd')//'devices';
my %allowed=map { $_=>1 } qw(devices selftest health watchdog-run on off status cycle group-on group-off group-cycle);
out({ok=>JSON::PP::false,error=>'Ungültiger Befehl.'}) unless $allowed{$cmd};
if ($cmd =~ /^(?:on|off|cycle|group-on|group-off|group-cycle)$/) {
  reject_cross_site();
  require_csrf();
  out({ok=>JSON::PP::false,error=>'Schaltbefehle sind nur per POST erlaubt.'}) if uc($ENV{REQUEST_METHOD}//'GET') ne 'POST';
}
if($cmd eq 'health'){
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
my @args=("$lbpbindir/unifipoe.py",'--config',$cfgfile,$cmd);
if($cmd =~ /^group-/){ my $g=$q->param('group')//''; out({ok=>JSON::PP::false,error=>'Gruppe ungültig.'}) if $g eq '' || length($g)>80 || $g =~ /[\r\n\0]/; push @args,'--group',$g; }
elsif($cmd ne 'devices' && $cmd ne 'selftest' && $cmd ne 'health' && $cmd ne 'watchdog-run'){
  my $sw=$q->param('switch')//''; my $port=$q->param('port')//'';
  out({ok=>JSON::PP::false,error=>'Switch/Port ungültig.'}) if $sw eq '' || length($sw)>128 || $sw =~ /[\r\n\0]/ || $port !~ /^\d+$/ || $port < 1 || $port > 512;
  push @args,'--switch',$sw,'--port',$port;
}
open my $p,'-|',@args or out({ok=>JSON::PP::false,error=>'Backend konnte nicht gestartet werden.'});
local $/; my $raw=<$p>//''; close $p;
my $res; eval{$res=decode_json($raw);1} or out({ok=>JSON::PP::false,error=>'Backend lieferte keine gültige JSON-Antwort.'});
if($cmd eq 'selftest'){
  $res->{cached_at}=time();
  atomic_json_write("$lbpdatadir/selftest.json",$res);
}
out($res);
