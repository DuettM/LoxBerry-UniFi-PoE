from pathlib import Path

p=Path('bin/unifipoe.py')
s=p.read_text()
s=s.replace("VERSION='0.7.12'","VERSION='0.7.23'")
old="""        elif a.cmd=='selftest':print(json.dumps(safe_selftest(cfg,a.config),ensure_ascii=False))"""
new="""        elif a.cmd=='selftest':
            r=safe_selftest(cfg,a.config)
            debug_log(cfg,'info',f\"Selbsttest {'OK' if r.get('ok') else 'FEHLER'}: {len(r.get('tests',[]))} Prüfungen\")
            print(json.dumps(r,ensure_ascii=False))"""
if old not in s: raise SystemExit('selftest branch not found')
s=s.replace(old,new,1)
p.write_text(s)

p=Path('bin/watchdog.py')
s=p.read_text()
old="""    atomic_write(state);publish_health(mod,state);mod.debug_log(c,'debug',f\"Watchdog OK: {state['switches']} Switch(es), {state['ports']} Ports, {state['response_ms']} ms\");sys.exit(0)"""
new="""    atomic_write(state);publish_health(mod,state)
    if old.get('ok') is not True:
        mod.debug_log(c,'info',f\"Watchdog OK: {state['switches']} Switch(es), {state['ports']} Ports, {state['response_ms']} ms\")
    else:
        mod.debug_log(c,'debug',f\"Watchdog OK: {state['switches']} Switch(es), {state['ports']} Ports, {state['response_ms']} ms\")
    sys.exit(0)"""
if old not in s: raise SystemExit('watchdog success branch not found')
s=s.replace(old,new,1)
p.write_text(s)

for fn in ['plugin.cfg','release.cfg','prerelease.cfg']:
    q=Path(fn); t=q.read_text().replace('0.7.22','0.7.23'); q.write_text(t)

cp=Path('CHANGELOG.md'); cs=cp.read_text()
if '## 0.7.23' not in cs:
    cp.write_text('## 0.7.23\n- Logging: erfolgreicher Selbsttest wird auf INFO protokolliert.\n- Logging: Watchdog schreibt beim Start/Wechsel auf OK einen INFO-Eintrag, zyklische OK-Läufe bleiben DEBUG.\n- Logging: PoE-Schaltungen, Warnungen und Fehler bleiben sichtbar, ohne das Log mit 30-Sekunden-Abfragen zu füllen.\n- Intern: Backend-Version auf 0.7.23 aktualisiert.\n\n'+cs)
