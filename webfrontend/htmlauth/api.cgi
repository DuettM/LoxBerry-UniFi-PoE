#!/usr/bin/perl
use strict;
use warnings;
use CGI;
use JSON::PP;
use LoxBerry::System;

my $q=CGI->new;
my $cfgfile="$lbpconfigdir/config.json";
print "Content-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n";
sub out { my ($x)=@_; print encode_json($x); exit; }
sub atomic_json_write {
  my ($path,$obj)=@_;
  my $tmp=$path.'.tmp';
  if(open my $f,'>',$tmp){ print $f JSON::PP->new->utf8->canonical->pretty->encode($obj); close $f; chmod 0600,$tmp; rename $tmp,$path; }
}
my $cmd=$q->param('cmd')//'devices';
my %allowed=map { $_=>1 } qw(devices selftest on off status cycle group-on group-off group-cycle);
out({ok=>JSON::PP::false,error=>'Ungültiger Befehl.'}) unless $allowed{$cmd};
my @args=("$lbpbindir/unifipoe.py",'--config',$cfgfile,$cmd);
if($cmd =~ /^group-/){ my $g=$q->param('group')//''; out({ok=>JSON::PP::false,error=>'Gruppe fehlt.'}) if $g eq ''; push @args,'--group',$g; }
elsif($cmd ne 'devices' && $cmd ne 'selftest'){
  my $sw=$q->param('switch')//''; my $port=$q->param('port')//'';
  out({ok=>JSON::PP::false,error=>'Switch/Port fehlt.'}) if $sw eq '' || $port !~ /^\d+$/;
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
