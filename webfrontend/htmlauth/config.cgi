#!/usr/bin/perl
use strict;
use warnings;
use CGI;
use JSON::PP;
use LoxBerry::System;
use File::Temp qw(tempfile);
use Digest::SHA qw(hmac_sha256_hex);

my $q = CGI->new;
my $cfgfile = "$lbpconfigdir/config.json";
my $json = JSON::PP->new->utf8->pretty->canonical;

print "Content-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n\r\n";

sub out {
    my ($obj) = @_;
    print encode_json($obj);
    exit;
}

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
    my $site = lc($ENV{HTTP_SEC_FETCH_SITE}//'');
    out({ok=>JSON::PP::false,error=>'Cross-Site-Anfrage blockiert.'}) if $site eq 'cross-site';
    my $host = lc($ENV{HTTP_HOST}//'');
    for my $h (qw(HTTP_ORIGIN HTTP_REFERER)) {
        my $v = lc($ENV{$h}//'');
        next if $v eq '' || $host eq '';
        if ($v =~ m{^https?://([^/]+)} && $1 ne $host) {
            out({ok=>JSON::PP::false,error=>'Cross-Site-Anfrage blockiert.'});
        }
    }
}

sub read_cfg {
    open my $fh, '<', $cfgfile or out({ok=>JSON::PP::false,error=>'Konfiguration konnte nicht gelesen werden: '.$!});
    local $/;
    my $raw = <$fh>;
    close $fh;
    my $cfg;
    eval { $cfg = decode_json($raw); 1 } or out({ok=>JSON::PP::false,error=>'Konfiguration ist ungültig.'});
    return $cfg;
}

sub normalize_controller {
    my ($v) = @_;
    $v //= '';
    $v =~ s/^\s+|\s+$//g;
    return '' if $v eq '';
    $v = 'https://'.$v if $v !~ m{^https?://}i;
    $v =~ s{/+$}{};
    return $v;
}

sub validate_cfg {
    my ($cfg)=@_;
    my $controller=$cfg->{controller}//'';
    out({ok=>JSON::PP::false,error=>'Controller-URL ungültig.'}) unless $controller =~ m{^https?://[^\s/]+(?::\d{1,5})?(?:/.*)?$}i && length($controller)<=512;
    out({ok=>JSON::PP::false,error=>'Benutzername ungültig.'}) if !defined($cfg->{username}) || $cfg->{username} eq '' || length($cfg->{username})>128 || $cfg->{username}=~/[\r\n\0]/;
    my $site=$cfg->{site}//'default'; out({ok=>JSON::PP::false,error=>'Site ungültig.'}) if length($site)>80 || $site=~/[\r\n\0]/;
    my $cy=int($cfg->{cycle_seconds}//5); out({ok=>JSON::PP::false,error=>'Cycle-Zeit muss zwischen 1 und 120 Sekunden liegen.'}) if $cy<1 || $cy>120;
    my $api=$cfg->{api_token}//''; out({ok=>JSON::PP::false,error=>'API-Token ungültig.'}) if length($api)<16 || length($api)>256 || $api=~/[\r\n\0]/;
    my $topic=$cfg->{mqtt}{base_topic}//'unifipoe'; out({ok=>JSON::PP::false,error=>'MQTT Topic ungültig.'}) if length($topic)>128 || $topic=~/[+#\s\0]/;
}
sub overlay_from_request {
    my ($cfg, $for_test) = @_;
    my $controller = normalize_controller($q->param('controller'));
    $cfg->{controller} = $controller if $controller ne '' || !$for_test;

    for my $k (qw(username site controller_type api_token)) {
        my $v = $q->param($k);
        $cfg->{$k} = $v if defined $v;
    }
    my $pw = $q->param('password');
    $cfg->{password} = $pw if defined($pw) && $pw ne '';

    my $cycle = $q->param('cycle_seconds');
    $cfg->{cycle_seconds} = int($cycle) if defined($cycle) && $cycle =~ /^\d+$/;
    $cfg->{verify_ssl} = (($q->param('verify_ssl')//'0') eq '1') ? JSON::PP::true : JSON::PP::false;

    $cfg->{mqtt} ||= {};
    my $mtopic = $q->param('mqtt_base_topic');
    if (defined $mtopic) {
        $mtopic =~ s/^\s+|\s+$//g;
        $mtopic =~ s{^/+|/+$}{}g;
        $mtopic = 'unifipoe' if $mtopic eq '';
        $cfg->{mqtt}{base_topic} = $mtopic;
    }
    $cfg->{mqtt}{use_loxberry} = JSON::PP::true;
    delete @{$cfg->{mqtt}}{qw(host port username password)};
    $cfg->{mqtt}{enabled} = (($q->param('mqtt_enabled')//'0') eq '1') ? JSON::PP::true : JSON::PP::false;
    $cfg->{mqtt}{retain} = (($q->param('mqtt_retain')//'0') eq '1') ? JSON::PP::true : JSON::PP::false;
    $cfg->{mqtt}{listen_enabled} = (($q->param('mqtt_listen_enabled')//'0') eq '1') ? JSON::PP::true : JSON::PP::false;
    my $mct = $q->param('mqtt_command_token');
    $cfg->{mqtt}{command_token} = $mct if defined($mct) && $mct ne '';
    $cfg->{mqtt}{command_token_required} = (($q->param('mqtt_command_token_required')//'0') eq '1') ? JSON::PP::true : JSON::PP::false;

    $cfg->{watchdog} ||= {};
    $cfg->{watchdog}{enabled} = (($q->param('watchdog_enabled')//'0') eq '1') ? JSON::PP::true : JSON::PP::false;

    $cfg->{debug} ||= {};
    my $lvl = lc($q->param('debug_level')//'info');
    $lvl = 'info' unless $lvl =~ /^(?:debug|info|warning|error)$/;
    $cfg->{debug}{level} = $lvl;

    my $aliases = $q->param('aliases_json');
    if (defined $aliases) {
        my $v;
        eval { $v = decode_json($aliases); 1 } or out({ok=>JSON::PP::false,error=>'Port-Aliase enthalten ungültiges JSON.'});
        out({ok=>JSON::PP::false,error=>'Port-Aliase müssen ein JSON-Objekt sein.'}) unless ref($v) eq 'HASH';
        $cfg->{aliases} = $v;
    }
    my $groups = $q->param('groups_json');
    if (defined $groups) {
        my $v;
        eval { $v = decode_json($groups); 1 } or out({ok=>JSON::PP::false,error=>'Gruppen enthalten ungültiges JSON.'});
        out({ok=>JSON::PP::false,error=>'Gruppen müssen ein JSON-Array sein.'}) unless ref($v) eq 'ARRAY';
        $cfg->{groups} = $v;
    }
    return $cfg;
}

my $action = $q->param('action') // '';
my $cfg = read_cfg();

if ($action eq 'save') {
    reject_cross_site();
    require_csrf();
    out({ok=>JSON::PP::false,error=>'Speichern ist nur per POST erlaubt.'}) if uc($ENV{REQUEST_METHOD}//'GET') ne 'POST';
    $cfg = overlay_from_request($cfg, 0);
    validate_cfg($cfg);
    out({ok=>JSON::PP::false,error=>'UDM/Controller-Adresse fehlt.'}) unless $cfg->{controller};
    out({ok=>JSON::PP::false,error=>'Benutzername fehlt.'}) unless defined($cfg->{username}) && $cfg->{username} ne '';
    out({ok=>JSON::PP::false,error=>'Controller-Typ ungültig.'}) unless ($cfg->{controller_type}//'') =~ /^(?:unifios|classic)$/;
    $cfg->{site} = 'default' if !defined($cfg->{site}) || $cfg->{site} eq '';
    $cfg->{config_version} = 7;
    $cfg->{update} ||= { channel => 'stable' };

    my $tmp = $cfgfile.'.tmp';
    open my $fh, '>', $tmp or out({ok=>JSON::PP::false,error=>'Konfiguration konnte nicht geschrieben werden: '.$!});
    chmod 0600, $tmp;
    print $fh $json->encode($cfg);
    close $fh;
    rename $tmp, $cfgfile or out({ok=>JSON::PP::false,error=>'Konfiguration konnte nicht aktiviert werden: '.$!});
    chmod 0600, $cfgfile;
    for my $sf (qw(unifi_session.cookies unifi_session.json)) { unlink "$lbpdatadir/$sf" if -e "$lbpdatadir/$sf"; }
    out({ok=>JSON::PP::true,message=>'Einstellungen gespeichert. Passwortfelder bleiben aus Sicherheitsgründen leer.'});
}

if ($action eq 'test') {
    reject_cross_site();
    require_csrf();
    out({ok=>JSON::PP::false,error=>'Verbindungstest ist nur per POST erlaubt.'}) if uc($ENV{REQUEST_METHOD}//'GET') ne 'POST';
    $cfg = overlay_from_request($cfg, 1);
    validate_cfg($cfg);
    out({ok=>JSON::PP::false,error=>'UDM/Controller-Adresse fehlt.'}) unless $cfg->{controller};
    out({ok=>JSON::PP::false,error=>'Benutzername fehlt.'}) unless defined($cfg->{username}) && $cfg->{username} ne '';
    out({ok=>JSON::PP::false,error=>'Passwort fehlt. Bitte einmal eingeben oder zuvor speichern.'}) unless defined($cfg->{password}) && $cfg->{password} ne '';

    my ($fh, $tmp) = tempfile('unifipoe-test-XXXX', DIR=>'/tmp', UNLINK=>0);
    chmod 0600, $tmp;
    print $fh $json->encode($cfg);
    close $fh;
    my @args = ("$lbpbindir/unifipoe.py", '--config', $tmp, '--no-session', 'devices');
    open my $p, '-|', @args or do { unlink $tmp; out({ok=>JSON::PP::false,error=>'Backend konnte nicht gestartet werden.'}); };
    local $/;
    my $raw = <$p> // '';
    close $p;
    my $rc = $? >> 8;
    unlink $tmp;
    my $res;
    eval { $res = decode_json($raw); 1 } or out({ok=>JSON::PP::false,error=>'Ungültige Antwort vom UniFi-Backend: '.substr($raw,0,250)});
    if ($rc != 0 || !$res->{ok}) {
        out({ok=>JSON::PP::false,error=>$res->{error}//'UniFi-Verbindung fehlgeschlagen.'});
    }
    my $switches = scalar(@{$res->{devices}||[]});
    my $ports = 0;
    $ports += scalar(@{$_->{ports}||[]}) for @{$res->{devices}||[]};
    out({ok=>JSON::PP::true,message=>"Verbindung erfolgreich: $switches Switch(es), $ports PoE-Port(s) erkannt.",switches=>$switches,ports=>$ports});
}

out({ok=>JSON::PP::false,error=>'Ungültige Aktion.'});
