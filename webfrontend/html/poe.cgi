#!/usr/bin/perl
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
