## 0.7.23
- Logging: erfolgreicher Selbsttest wird auf INFO protokolliert.
- Logging: Watchdog schreibt beim Start/Wechsel auf OK einen INFO-Eintrag, zyklische OK-Läufe bleiben DEBUG.
- Logging: PoE-Schaltungen, Warnungen und Fehler bleiben sichtbar, ohne das Log mit 30-Sekunden-Abfragen zu füllen.
- Intern: Backend-Version auf 0.7.23 aktualisiert.

## 0.7.22
- Fix: Dashboard Systemtest/Watchdog use api.cgi health endpoint instead of debug.cgi.
- Fix: Watchdog kick uses authenticated POST.

## 0.7.21
- Fix: debug.cgi 500 error for dashboard self-test/watchdog status.
- UI: Port names and groups moved to Groups page.
- UI: Visual port selection, port-name editing, group create/edit/delete.
- TLS: strict certificate verification clarified for self-signed UniFi certificates.

# Changelog

## 0.7.14

- Interne LoxBerry-Plugin-Identität auf den ursprünglichen Autorenwert zurückgesetzt, damit Updates keine Doppelinstallation erzeugen.
- UniFi-Daemon und Watchdog-Cron erkennen Installationen nur noch über die Plugin-ID `unifipoe`.
- Speichern der UniFi-Zugangsdaten verbessert: Benutzername wird bereinigt, gespeichert und anschließend direkt verifiziert.
- Konfigurationsschema beim Speichern auf Version 8 korrigiert.
- Native LoxBerry-AutoUpdate-Auswahl bleibt aktiviert.

## 0.7.13

- Hotfix: Daemon-Ordnererkennung ist nicht mehr von Autorenname oder Autoren-E-Mail abhängig.
- Behebt den Ausfall der MQTT-/Statusdaten nach der Datenschutzbereinigung.
- Fallback auf den Standardordner `unifipoe`, falls die LoxBerry-Plugindatenbank nicht gelesen werden kann.
- Autorenanzeige auf `Marco Düthorn` geändert.
- Native LoxBerry-Auswahl für automatische Updates wieder aktiviert.

## 0.7.12

- Sitzungsgebundener HMAC-CSRF-Schutz für Admin-POSTs.
- Zusätzliche Eingabevalidierung für Controller, MQTT, Ports, Gruppen und Tokens.
- Secret-Redaction im Debug-Log für Passwörter, Tokens und Authorization-Header.
- Debug-Mutationen nur noch per POST.

## 0.7.11

- LoxBerry-V4-Compliance-Audit gegen das aktuelle SamplePlugin-V4.
- Tatsächlicher Pluginordner wird für öffentliche API-URLs dynamisch ermittelt (`unifipoe`, `unifipoe01`, ...).
- Veraltete Token-in-URL-Anzeige aus der Diagnose entfernt; HTTP-Generator zeigt POST-Body.
- Interne PoE-Schaltbefehle nur noch per POST; reine Statusabfragen bleiben GET.
- MQTT-Listener läuft nach Boot nicht mehr als root, sondern mit Privilege Drop als Benutzer `loxberry`.
- Uninstaller beendet nur noch den MQTT-Listener der konkreten Plugininstallation.
- `.gitattributes` erzwingt LF-Zeilenenden für LoxBerry-Skripte.
- SHA-256- und Ed25519-signierte Updatekette bleibt unverändert aktiv.

## 0.7.10

- MQTT Command-Token ist wieder optional und standardmäßig deaktiviert.
- LoxBerry MQTT Benutzername/Passwort bleibt die normale Zugriffssicherung.
- Bestehende 0.7.9-Installationen werden einmalig auf normalen MQTT-Payload (`ON`, `OFF`, `CYCLE`, `STATUS`) zurückgestellt.
- Optionaler Command-Token bleibt als zusätzliche zweite Schutzschicht verfügbar.
- Signierter Updatepfad mit SHA-256 + Ed25519 bleibt unverändert aktiv.

## 0.7.9

- Ed25519-Publisher-Signaturen für Update-Archive.
- Secure Updater verlangt SHA-256 **und** gültige Ed25519-Signatur.
- Öffentlicher Vertrauensschlüssel ist fest im Plugin eingebettet.
- Manipulierte oder nur neu gehashte Fremdarchive werden verworfen.

## 0.7.8

- Loxone API-Token aus der URL entfernt; Authentifizierung über `X-API-Token`, `Authorization: Bearer` oder POST-Body.
- MQTT-Command-Token eingeführt und bei Updates automatisch zufällig erzeugt.
- Reine MQTT-ON/OFF/CYCLE-Payloads werden bei aktiviertem Token-Schutz abgewiesen.
- Native ungeprüfte LoxBerry-Auto-Installation deaktiviert.
- Neuer `secure_update.py` akzeptiert ein Update-ZIP nur nach erfolgreicher SHA-256-Prüfung gegen das Release-Checksum-Asset.
- Eine Publisher-Signatur bleibt optional für einen später hinterlegten privaten Signierschlüssel; kein privater Schlüssel wird im Repository gespeichert.

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
