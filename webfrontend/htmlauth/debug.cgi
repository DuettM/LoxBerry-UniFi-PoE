#!/usr/bin/perl
use strict; use warnings; use CGI; use JSON::PP; use LoxBerry::System; use Digest::SHA qw(hmac_sha256_hex);
my $q=CGI->new; my $log="$lbplogdir/unifipoe.log"; my $action=$q->param('action')//'read';
print "Content-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n\r\n";
sub ct_eq {
  my ($a,$b)=@_; return 0 if !defined($a)||!defined($b)||length($a)!=length($b);
  my $v=0; for(my $i=0;$i<length($a);$i++){ $v |= ord(substr($a,$i,1)) ^ ord(substr($b,$i,1)); } return $v==0;
}
sub require_csrf {
  open my $cf,'<',$cfgfile or print encode_json({ok=>JSON::PP::false,error=>'CSRF-Konfiguration nicht lesbar.'}); exit;
  local $/; my $raw=<$cf>//''; close $cf; my $cc; eval{$cc=decode_json($raw);1} or print encode_json({ok=>JSON::PP::false,error=>'CSRF-Konfiguration ungültig.'}); exit;
  my $seed=($ENV{HTTP_COOKIE}//'').'|'.($ENV{HTTP_USER_AGENT}//'');
  my $expected=hmac_sha256_hex($seed,($cc->{api_token}//''));
  my $sent=$ENV{HTTP_X_UNIFI_CSRF}//'';
  if(!ct_eq($sent,$expected)){ print encode_json({ok=>JSON::PP::false,error=>'CSRF-Prüfung fehlgeschlagen.'}); exit; }
}
sub cross_site {
  return 1 if lc($ENV{HTTP_SEC_FETCH_SITE}//'') eq 'cross-site';
  my $host=lc($ENV{HTTP_HOST}//'');
  for my $h (qw(HTTP_ORIGIN HTTP_REFERER)) { my $v=lc($ENV{$h}//''); next if $v eq '' || $host eq ''; return 1 if $v =~ m{^https?://([^/]+)} && $1 ne $host; }
  return 0;
}
sub redact_line {
  my ($line,$cfg)=@_;
  my @secrets=grep { defined($_) && length($_)>=4 } ($cfg->{password},$cfg->{api_token},$cfg->{mqtt}{command_token});
  for my $secret (@secrets){ $line =~ s/\Q$secret\E/[REDACTED]/g; }
  $line =~ s{(Authorization\s*:\s*(?:Bearer|Basic)\s+)[^\s,;]+}{$1[REDACTED]}ig;
  $line =~ s{((?:password|passwd|token|api[_-]?token|secret)\s*[=:]\s*)[^\s,;]+}{$1[REDACTED]}ig;
  $line =~ s{("(?:password|passwd|token|api_token|secret)"\s*:\s*")[^"]*(")}{$1[REDACTED]$2}ig;
  return $line;
}
sub read_json_file {
  my ($path)=@_; my $data={};
  if(open my $f,'<',$path){ local $/; my $raw=<$f>//''; close $f; eval{$data=decode_json($raw);1} or $data={}; }
  return $data;
}
if($action eq 'watchdog'){
  my $cfg=read_json_file("$lbpconfigdir/config.json");
  my $enabled=($cfg->{watchdog} && $cfg->{watchdog}{enabled}) ? JSON::PP::true : JSON::PP::false;
  my $wd="$lbpdatadir/watchdog.json"; my $data=read_json_file($wd);
  print encode_json({ok=>JSON::PP::true,enabled=>$enabled,exists=>(-f $wd?JSON::PP::true:JSON::PP::false),watchdog=>$data}); exit;
}
if($action eq 'selftest'){
  my $st="$lbpdatadir/selftest.json"; my $data=read_json_file($st);
  print encode_json({ok=>JSON::PP::true,exists=>(-f $st?JSON::PP::true:JSON::PP::false),selftest=>$data}); exit;
}
if($action eq 'watchdog_run'){
  if(uc($ENV{REQUEST_METHOD}//'GET') ne 'POST'){ print encode_json({ok=>JSON::PP::false,error=>'Nur POST erlaubt.'}); exit; }
  require_csrf();
  if(cross_site()){ print encode_json({ok=>JSON::PP::false,error=>'Cross-Site-Anfrage blockiert.'}); exit; }
  my $cfg=read_json_file("$lbpconfigdir/config.json");
  my $enabled=($cfg->{watchdog} && $cfg->{watchdog}{enabled}) ? 1 : 0;
  if(!$enabled){ print encode_json({ok=>JSON::PP::true,started=>JSON::PP::false,reason=>'disabled'}); exit; }
  my $pid=fork();
  if(!defined $pid){ print encode_json({ok=>JSON::PP::false,error=>'Watchdog konnte nicht gestartet werden.'}); exit; }
  if($pid==0){
    open STDIN,'<','/dev/null'; open STDOUT,'>','/dev/null'; open STDERR,'>','/dev/null';
    exec "$lbpbindir/watchdog.py", "$lbpconfigdir/config.json"; exit 127;
  }
  print encode_json({ok=>JSON::PP::true,started=>JSON::PP::true}); exit;
}
if($action eq 'clear'){
  if(uc($ENV{REQUEST_METHOD}//'GET') ne 'POST'){ print encode_json({ok=>JSON::PP::false,error=>'Nur POST erlaubt.'}); exit; }
  require_csrf();
  if(cross_site()){ print encode_json({ok=>JSON::PP::false,error=>'Cross-Site-Anfrage blockiert.'}); exit; }
  if(open my $f,'>',$log){ close $f; print encode_json({ok=>JSON::PP::true}); }
  else{ print encode_json({ok=>JSON::PP::false,error=>"$!"}); }
  exit;
}
my $lines=int($q->param('lines')||100); $lines=20 if $lines<20; $lines=500 if $lines>500;
my @all;
if(open my $f,'<',$log){ @all=<$f>; close $f; }
@all=@all[-$lines..-1] if @all>$lines;
chomp @all;
my $rcfg=read_json_file("$lbpconfigdir/config.json"); @all=map { redact_line($_,$rcfg) } @all;
print encode_json({ok=>JSON::PP::true,lines=>\@all,count=>scalar(@all)});
