# Changelog

## 0.7.6

- MQTT wird beim Upgrade aus älteren Konfigurationen automatisch aktiviert.
- MQTT-Befehlslistener wird beim Upgrade automatisch aktiviert.
- Benutzerdefinierte MQTT-Basistopics bleiben erhalten.
- Systemstatus für MQTT und Watchdog zeigt eindeutige Zustände.
- Watchdog ist bei Neuinstallationen standardmäßig aktiviert; bestehende Einstellungen werden nicht überschrieben.

## 0.7.5

- MQTT auf das zentrale LoxBerry MQTT Gateway umgestellt.
- Broker-Adresse, Port und Zugangsdaten werden aus `$LBHOME/config/system/general.json` gelesen.
- Standard-Basistopic auf `unifipoe` gesetzt und weiterhin frei konfigurierbar.
- Bestehende benutzerdefinierte MQTT-Topic-Präfixe bleiben bei Updates erhalten.
- Bidirektionalen MQTT-Befehlslistener integriert.
- MQTT-Befehle für PoE-Ports und Gruppen ergänzt.
- MQTT-Listener reagiert auf Änderungen der Plugin- bzw. LoxBerry-MQTT-Konfiguration mit Reconnect.
- Installations- und Upgrade-Migration auf `config_version` 5 ergänzt.
- Watchdog und Selbsttest an die zentrale MQTT-Konfiguration angepasst.

## 0.7.4

- LoxBerry Auto-Update über `release.cfg` und `prerelease.cfg` aktiviert.

## Vorherige Versionen

- UniFi PoE-Portsteuerung über HTTP und MQTT.
- Port-Gruppen und Aliase.
- Watchdog, Selbsttest und Debug-Log.
- Session-Cache und Schutz vor UniFi HTTP-429-Loginlimits.
