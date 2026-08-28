#!/usr/bin/perl
use strict; use warnings; use CGI; use JSON::PP; use LoxBerry::System;
my $q=CGI->new;my $cfgfile="$lbpconfigdir/config.json";open my $f,'<',$cfgfile or die "Content-Type: application/json\r\n\r\n{\"ok\":false,\"error\":\"config missing\"}";local $/;my $c=decode_json(<$f>);close $f;
print "Content-Type: application/json\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n\r\n";
if (($q->param('token')//'') ne ($c->{api_token}//'')){print encode_json({ok=>JSON::PP::false,error=>'unauthorized'});exit;}
my $cmd=$q->param('cmd')//'status';my %allowed=map { $_=>1 } qw(devices selftest on off status cycle group-on group-off group-cycle);if(!$allowed{$cmd}){print encode_json({ok=>JSON::PP::false,error=>'invalid command'});exit;}my @args=("$lbpbindir/unifipoe.py",'--config',$cfgfile,$cmd);
if ($cmd =~ /^group-/){my $g=$q->param('group')//'';if($g eq ''){print encode_json({ok=>JSON::PP::false,error=>'group missing'});exit;}push @args,'--group',$g;}
elsif ($cmd ne 'devices' && $cmd ne 'selftest'){my $sw=$q->param('switch')//'';my $port=$q->param('port')//'';if($sw eq ''||$port!~/^\d+$/){print encode_json({ok=>JSON::PP::false,error=>'switch/port missing'});exit;}push @args,'--switch',$sw,'--port',$port;}
open my $p,'-|',@args or do{print encode_json({ok=>JSON::PP::false,error=>'backend start failed'});exit;};local $/;my $out=<$p>;close $p;print $out||encode_json({ok=>JSON::PP::false,error=>'empty backend response'});
