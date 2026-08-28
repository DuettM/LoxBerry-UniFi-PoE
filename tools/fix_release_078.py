from pathlib import Path
p=Path('tools/release_078.py')
s=p.read_text()
start=s.index('old="print \'<div class=\\"field\\"><label>Broker</label>')
end=s.index('old="<label><input type=\\"checkbox\\" name=\\"mqtt_retain', start)
block=r'''broker_needle="print '<div class=\"field\"><label>Broker</label><input value=\"LoxBerry MQTT Gateway (automatisch)\" disabled><div class=\"hint\">Wird aus $LBHOME/config/system/general.json → Mqtt gelesen.</div></div></div><div class=\"checks\"><label><input type=\"checkbox\" name=\"mqtt_enabled\""
broker_repl="print '<div class=\"field\"><label>Broker</label><input value=\"LoxBerry MQTT Gateway (automatisch)\" disabled><div class=\"hint\">Wird aus $LBHOME/config/system/general.json → Mqtt gelesen.</div></div>';\nprint '<div class=\"field\"><label>MQTT Command-Token</label><div style=\"display:flex;gap:6px\"><input id=\"mqtt_command_token\" name=\"mqtt_command_token\" value=\"'.esc($c->{mqtt}{command_token}//'').'\"><button class=\"btn\" type=\"button\" onclick=\"newMqttToken()\">Neu</button><button class=\"btn\" type=\"button\" onclick=\"copyMqttToken()\">Kopieren</button></div><div class=\"hint\">Muss bei MQTT-Schaltbefehlen im Payload mitgesendet werden.</div></div></div><div class=\"checks\"><label><input type=\"checkbox\" name=\"mqtt_enabled\""
if 'MQTT Command-Token</label>' not in s:
    pass
if broker_needle not in s:
    raise RuntimeError('index broker pattern missing')
s=s.replace(broker_needle,broker_repl)
'''
s=s[:start]+block+s[end:]
p.write_text(s)
