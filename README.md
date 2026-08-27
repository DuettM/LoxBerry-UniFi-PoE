# UniFi PoE Control 0.5.0 für LoxBerry

Direkte lokale Steuerung von UniFi-PoE-Switches aus LoxBerry/Loxone

## Funktionen
- UniFi OS / UDM / CloudKey und Classic Network Controller
- automatische Switch- und PoE-Port-Erkennung
- PoE Ein, Aus und Power-Cycle
- Port-Aliase und Gruppen
- HTTP-API für Loxone
- MQTT-Zustände und Health-Topics über die zentrale LoxBerry-MQTT-Konfiguration
- MQTT-Basistopic frei änderbar, Standard: `unifipoe`
- Watchdog mit Retry und Lock gegen Parallelstarts
- nicht-destruktiver Selbsttest
- echtes Debug-Log mit Logrotation, Filter-Level, Auto-Refresh und Löschen
- responsives LoxBerry-Design

## Hinweise
Das Plugin verändert bei einem Schaltvorgang nur `poe_mode` im bestehenden UniFi-Port-Override. Vorhandene Port-/VLAN-Einstellungen bleiben erhalten.

Der Selbsttest schaltet keine Ports. Er prüft Konfiguration, Schreibrechte, Controller-Erreichbarkeit, UniFi-Login/API, erkannte PoE-Ports, MQTT und Watchdog.

## Loxone HTTP API
Beispiel:

`/plugins/unifipoe/poe.cgi?token=TOKEN&cmd=off&switch=SWITCH_ID&port=3`

Befehle: `on`, `off`, `cycle`, `status`, `devices`, `selftest`, `group-on`, `group-off`, `group-cycle`.

## MQTT
Das Plugin verwendet keine separat gepflegten Broker-Zugangsdaten mehr. Host, Port, Benutzer und Passwort werden automatisch aus der zentralen LoxBerry-Konfiguration (`$LBHOME/config/system/general.json`, Bereich `Mqtt`) gelesen.

Standard-Basistopic: `unifipoe` (im Webinterface änderbar).

Beispiel-Topics:

- `unifipoe/<switch>/<port>/up`
- `unifipoe/<switch>/<port>/poe_mode`
- `unifipoe/<switch>/<port>/poe_power`
- `unifipoe/<switch>/<port>/link_up`
- `unifipoe/health/ok`
- `unifipoe/health/timestamp`
