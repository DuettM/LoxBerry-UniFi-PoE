#!/usr/bin/perl
use strict; use warnings; use CGI; use JSON::PP; use LoxBerry::System;
my $q=CGI->new; my $log="$lbpconfigdir/unifipoe.log"; my $action=$q->param('action')//'read';
print "Content-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\n\r\n";
if($action eq 'watchdog'){
  my $wd="$lbpconfigdir/watchdog.json"; my $data={};
  if(open my $f,'<',$wd){ local $/; my $raw=<$f>; close $f; eval{$data=decode_json($raw);1}; }
  print encode_json({ok=>JSON::PP::true,watchdog=>$data}); exit;
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
