#!/usr/bin/perl
use strict;
use warnings;
use CGI;
use JSON::PP;
use LoxBerry::System;
use File::Basename qw(basename);

my $q = CGI->new;
my $cfgfile = "$lbpconfigdir/config.json";
my %out = (
  ok => JSON::PP::false,
  plugin_folder => ($lbpplugindir // ''),
  config_dir => ($lbpconfigdir // ''),
  config_file => $cfgfile,
  config_exists => (-e $cfgfile ? JSON::PP::true : JSON::PP::false),
  config_readable => (-r $cfgfile ? JSON::PP::true : JSON::PP::false),
  config_writable => (-w $cfgfile ? JSON::PP::true : JSON::PP::false),
  dir_writable => (-w $lbpconfigdir ? JSON::PP::true : JSON::PP::false),
);
if (-e $cfgfile) {
  my @st = stat($cfgfile);
  $out{size} = $st[7] // 0;
  $out{mtime} = $st[9] // 0;
  if (open my $fh, '<', $cfgfile) {
    local $/; my $raw = <$fh> // ''; close $fh;
    my $cfg;
    if (eval { $cfg = decode_json($raw); 1 }) {
      $out{ok} = JSON::PP::true;
      $out{controller} = $cfg->{controller} // '';
      $out{username} = $cfg->{username} // '';
      $out{password_saved} = (defined($cfg->{password}) && $cfg->{password} ne '') ? JSON::PP::true : JSON::PP::false;
      $out{config_version} = $cfg->{config_version} // 0;
      $out{site} = $cfg->{site} // '';
      $out{controller_type} = $cfg->{controller_type} // '';
    } else {
      $out{error} = 'config.json ist kein gültiges JSON';
    }
  } else {
    $out{error} = "config.json nicht lesbar: $!";
  }
}
print "Content-Type: application/json; charset=utf-8\r\nCache-Control: no-store, no-cache, must-revalidate\r\nPragma: no-cache\r\nX-Content-Type-Options: nosniff\r\n\r\n";
print JSON::PP->new->utf8->canonical->pretty->encode(\%out);
