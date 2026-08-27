#!/usr/bin/perl
use strict; use warnings; use CGI; use JSON::PP; use LoxBerry::System;
my $q=CGI->new; my $log="$lbplogdir/unifipoe.log"; my $action=$q->param('action')//'read';
print "Content-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\n\r\n";
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
  if(open my $f,'>',$log){ close $f; print encode_json({ok=>JSON::PP::true}); }
  else{ print encode_json({ok=>JSON::PP::false,error=>"$!"}); }
  exit;
}
my $lines=int($q->param('lines')||100); $lines=20 if $lines<20; $lines=500 if $lines>500;
my @all;
if(open my $f,'<',$log){ @all=<$f>; close $f; }
@all=@all[-$lines..-1] if @all>$lines;
chomp @all;
print encode_json({ok=>JSON::PP::true,lines=>\@all,count=>scalar(@all)});
