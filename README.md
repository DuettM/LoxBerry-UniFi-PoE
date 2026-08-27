# LoxBerry UniFi PoE Control

Aktuelle Version: **0.7.6**

LoxBerry-Plugin zur direkten Steuerung und Überwachung von PoE-Ports auf UniFi-Switches. Das Plugin verbindet LoxBerry/Loxone direkt mit einem UniFi OS Controller bzw. einer UDM und stellt HTTP- sowie MQTT-Schnittstellen für Automatisierungen bereit.

**Autor:** Düthorn Marco  
**Kontakt:** duett86@web.de

## Funktionen

- PoE **EIN / AUS / Power-Cycle** pro Port
- UniFi OS / UDM-Anbindung mit Session-Cache
- Schutz vor unnötigen UniFi-Logins und HTTP-429-Limits
- automatische Erkennung von Switches und PoE-Ports
- Anzeige von PoE-Leistung, Spannung, Strom und Linkstatus
- Port-Aliase und Port-Gruppen
- HTTP-API für Loxone und andere Systeme
- bidirektionale MQTT-Kommunikation
- MQTT- und HTTP-Befehlsgenerator im Webinterface
- MQTT-Befehle für einzelne Ports und Gruppen
- Watchdog mit Status-Publishing
- nicht-destruktiver Selbsttest
- Debug-Log und Diagnosefunktionen
- update-sichere Benutzerkonfiguration
- LoxBerry Auto-Update über GitHub

## Neu in 0.7.6: Status und automatische Aktivierung

- MQTT wird beim Upgrade von älteren Plugin-Versionen automatisch aktiviert.
- Der MQTT-Befehlslistener wird beim Upgrade ebenfalls aktiviert.
- Eigene MQTT-Basistopics bleiben erhalten.
- Systemstatus unterscheidet jetzt klar zwischen **Deaktiviert**, **Aktiv · Verbunden** und **Aktiv · Verbindung fehlgeschlagen**.
- Der Watchdog ist bei Neuinstallationen standardmäßig aktiviert; bestehende Benutzereinstellungen bleiben erhalten.

## Neu in 0.7.5: LoxBerry MQTT Gateway

Ab Version **0.7.5** verwendet das Plugin standardmäßig das zentrale **LoxBerry MQTT Gateway**. Broker-Adresse, Port, Benutzer und Passwort werden automatisch aus

`$LBHOME/config/system/general.json`

Bereich `Mqtt` übernommen. MQTT-Zugangsdaten müssen dadurch nicht mehr zusätzlich im UniFi-PoE-Plugin gepflegt werden.

Der MQTT-Basistopic ist standardmäßig:

`unifipoe`

Der Basistopic kann im Webinterface frei geändert werden. Bestehende benutzerdefinierte Topic-Präfixe bleiben beim Update erhalten.

### MQTT Beispiele

Status eines Ports:

`unifipoe/<switch>/<port>/poe_mode`

Befehl für einen Port:

`unifipoe/set/port/<switch-id>/<port>`

Mögliche Payloads sind unter anderem `ON`, `OFF`, `CYCLE` und `STATUS`.

Gruppen können ebenfalls über MQTT angesprochen werden.

## Loxone / HTTP API

Beispiel zum Ausschalten eines Ports:

`/plugins/unifipoe/poe.cgi?token=DEIN_TOKEN&cmd=off&switch=SWITCH_ID&port=3`

Unterstützte Befehle umfassen unter anderem:

- `on`
- `off`
- `cycle`
- `status`
- `devices`
- `selftest`
- `group-on`
- `group-off`
- `group-cycle`

## Installation

Die aktuelle Installationsdatei liegt unter:

`releases/LoxBerry-UniFi-PoE-0.7.6.zip`

Diese ZIP-Datei kann direkt über die LoxBerry-Pluginverwaltung installiert werden.

## Auto-Update

Ab Version **0.7.4** ist die LoxBerry-Auto-Update-Funktion aktiviert. Die stabile Version wird über `release.cfg` bereitgestellt. Version **0.7.6** ist aktuell als Stable eingetragen.

## Sicherheit

Die echte Benutzerdatei `config.json` mit UniFi-Zugangsdaten und API-Token wird **nicht** im Repository gespeichert. Im Repository befindet sich ausschließlich `config/config.default.json`.

Beim Update wird die vorhandene Benutzerkonfiguration erhalten und nur um fehlende Standardwerte ergänzt.

## Lizenz

MIT License.
