from pathlib import Path

# Backend enrichment: wired clients + LLDP fallback
p=Path('bin/unifipoe.py')
s=p.read_text()
s=s.replace("VERSION='0.7.23'","VERSION='0.7.24'",1)
s=s.replace("self._devices_cache=None","self._devices_cache=None; self._clients_cache=None",1)
old="""    def switches(self):return [d for d in self.devices() if d.get('type')=='usw']
    def find_device(self,ident):"""
new="""    def switches(self):return [d for d in self.devices() if d.get('type')=='usw']
    @staticmethod
    def _norm_mac(v):
        return ''.join(ch for ch in str(v or '').lower() if ch in '0123456789abcdef')
    def clients(self,refresh=False):
        if self._clients_cache is not None and not refresh:return self._clients_cache
        self.login()
        path=f'{self.prefix()}/api/s/{self.site}/stat/sta'
        try:
            self._clients_cache=self.req('GET',path).get('data',[])
        except UniFiError as e:
            if self.session_enabled and e.status==401:
                self._clear_session();self.logged_in=False;self.login(force=True);self._clients_cache=self.req('GET',path).get('data',[])
            else:
                debug_log(self.cfg,'warning',f'Client-Liste konnte nicht gelesen werden: {e}')
                self._clients_cache=[]
        return self._clients_cache
    def _client_for_port(self,d,port_idx):
        dmac=self._norm_mac(d.get('mac'))
        matches=[]
        for c in self.clients():
            cmac=self._norm_mac(c.get('sw_mac') or c.get('switch_mac') or c.get('uplink_mac'))
            cp=c.get('sw_port') if c.get('sw_port') is not None else c.get('switch_port')
            try: cp=int(cp)
            except Exception: continue
            if cmac==dmac and cp==int(port_idx):matches.append(c)
        if not matches:return None
        matches.sort(key=lambda c:(int(c.get('last_seen',0) or 0),int(c.get('uptime',0) or 0)),reverse=True)
        c=matches[0]
        name=c.get('name') or c.get('hostname') or c.get('dev_name') or c.get('oui') or c.get('mac') or 'Gerät'
        model=c.get('model') or c.get('dev_cat_name') or c.get('dev_family') or ''
        return {'name':name,'hostname':c.get('hostname') or '','mac':c.get('mac') or '','ip':c.get('ip') or c.get('fixed_ip') or '','vendor':c.get('oui') or c.get('manufacturer') or '','model':model,'source':'client'}
    def _lldp_for_port(self,d,port_idx):
        rows=(d.get('lldp_table') or d.get('lldp') or [])
        for x in rows:
            raw=x.get('local_port_idx')
            if raw is None:raw=x.get('port_idx')
            if raw is None:raw=x.get('local_port_num')
            if raw is None:raw=x.get('local_port')
            try: pi=int(raw)
            except Exception: continue
            if pi!=int(port_idx):continue
            name=x.get('system_name') or x.get('sys_name') or x.get('device_name') or x.get('chassis_id') or 'LLDP-Gerät'
            ip=x.get('management_address') or x.get('management_ip') or x.get('ip') or ''
            model=x.get('model') or x.get('system_description') or x.get('sys_desc') or ''
            return {'name':name,'hostname':x.get('system_name') or x.get('sys_name') or '','mac':x.get('chassis_id') or '','ip':ip,'vendor':'','model':model,'source':'lldp'}
        return None
    def attached_for_port(self,d,port_idx):
        return self._client_for_port(d,port_idx) or self._lldp_for_port(d,port_idx) or {}
    def find_device(self,ident):"""
if old not in s: raise SystemExit('switches marker not found')
s=s.replace(old,new,1)
old="""                    ports.append({'port_idx':idx,'name':p.get('name'),'alias':aliases.get(f'{d.get(\"_id\")}:{idx}',''),'poe_mode':mode,'poe_power':power,'poe_current':current,'poe_voltage':voltage,'link_up':p.get('up')})"""
new="""                    attached=self.attached_for_port(d,idx)
                    ports.append({'port_idx':idx,'name':p.get('name'),'alias':aliases.get(f'{d.get(\"_id\")}:{idx}',''),'poe_mode':mode,'poe_power':power,'poe_current':current,'poe_voltage':voltage,'link_up':p.get('up'),'attached':attached})"""
if old not in s: raise SystemExit('list_devices port append marker not found')
s=s.replace(old,new,1)
old="""        debug_log(self.cfg,'debug',f'Device scan: {len(ds)} Switch(es), {sum(len(d[\"ports\"]) for d in ds)} PoE-Port(s)');return {'ok':True,'devices':ds}"""
new="""        attached_count=sum(1 for d in ds for p in d['ports'] if p.get('attached'))
        debug_log(self.cfg,'debug',f'Device scan: {len(ds)} Switch(es), {sum(len(d[\"ports\"]) for d in ds)} PoE-Port(s), {attached_count} Gerät(e) zugeordnet');return {'ok':True,'devices':ds}"""
if old not in s: raise SystemExit('device scan log marker not found')
s=s.replace(old,new,1)
p.write_text(s)

# UI: show connected device in quick table, full port table, and group picker
p=Path('webfrontend/htmlauth/index.cgi')
s=p.read_text()
s=s.replace('<th>Port</th><th>Name</th><th>PoE</th><th>Leistung</th><th>Link</th><th>Aktionen</th>','<th>Port</th><th>Name</th><th>Angeschlossenes Gerät</th><th>PoE</th><th>Leistung</th><th>Link</th><th>Aktionen</th>',1)
s=s.replace('id="quick-ports"><tr><td colspan="6">Lade Daten …</td>','id="quick-ports"><tr><td colspan="7">Lade Daten …</td>',1)
s=s.replace('<th>Port</th><th>Name</th><th>UniFi-Name</th><th>PoE</th><th>Spannung</th><th>Leistung</th><th>Link</th><th>Aktionen</th>','<th>Port</th><th>Name</th><th>UniFi-Name</th><th>Angeschlossenes Gerät</th><th>PoE</th><th>Spannung</th><th>Leistung</th><th>Link</th><th>Aktionen</th>',1)
s=s.replace('id="ports-body"><tr><td colspan="8">Lade Daten …</td>','id="ports-body"><tr><td colspan="9">Lade Daten …</td>',1)
s=s.replace("document.getElementById('ports-body').innerHTML='<tr><td colspan=\"8\" class=\"bad\">'","document.getElementById('ports-body').innerHTML='<tr><td colspan=\"9\" class=\"bad\">'",1)
s=s.replace("document.getElementById('quick-ports').innerHTML='<tr><td colspan=\"6\" class=\"bad\">'","document.getElementById('quick-ports').innerHTML='<tr><td colspan=\"7\" class=\"bad\">'",1)
marker="function rowHtml(d,p,quick){"
helper="""function attachedHtml(p,quick){let a=p.attached||{};if(!(a.name||a.hostname||a.mac||a.ip||a.model))return '<span class=\"muted\">–</span>';let name=a.name||a.hostname||a.model||a.mac||'Gerät',meta=[];if(a.model&&a.model!==name)meta.push(a.model);if(a.ip)meta.push(a.ip);if(a.mac)meta.push(a.mac);if(a.vendor&&!meta.includes(a.vendor))meta.push(a.vendor);let title=[name,...meta].filter(Boolean).join(' · ');if(quick)return '<span title=\"'+h(title)+'\">'+h(name)+'</span>';return '<div><b>'+h(name)+'</b>'+(meta.length?'<div class=\"muted\" style=\"font-size:11px\">'+h(meta.join(' · '))+'</div>':'')+'</div>'}
"""
if marker not in s: raise SystemExit('rowHtml marker not found')
s=s.replace(marker,helper+marker,1)
old="""if(quick)return '<tr><td>'+p.port_idx+'</td><td>'+h(alias)+'</td><td><span class=\"pill '+(on?'':'off')+'\">'+(on?'Ein':'Aus')+'</span></td><td>'+w.toFixed(1)+' W</td><td class=\"'+(p.link_up?'ok':'muted')+'\">'+(p.link_up?'Online':'–')+'</td><td>'+acts+'</td></tr>';return '<tr><td>'+p.port_idx+'</td><td>'+h(alias)+'</td><td>'+h(p.name||'–')+'</td><td><span class=\"pill '+(on?'':'off')+'\">'+(on?'Ein':'Aus')+'</span></td><td>'+h(v)+' V</td><td>'+w.toFixed(1)+' W</td><td class=\"'+(p.link_up?'ok':'muted')+'\">'+(p.link_up?'Online':'–')+'</td><td>'+acts+'</td></tr>'"""
new="""if(quick)return '<tr><td>'+p.port_idx+'</td><td>'+h(alias)+'</td><td>'+attachedHtml(p,true)+'</td><td><span class=\"pill '+(on?'':'off')+'\">'+(on?'Ein':'Aus')+'</span></td><td>'+w.toFixed(1)+' W</td><td class=\"'+(p.link_up?'ok':'muted')+'\">'+(p.link_up?'Online':'–')+'</td><td>'+acts+'</td></tr>';return '<tr><td>'+p.port_idx+'</td><td>'+h(alias)+'</td><td>'+h(p.name||'–')+'</td><td>'+attachedHtml(p,false)+'</td><td><span class=\"pill '+(on?'':'off')+'\">'+(on?'Ein':'Aus')+'</span></td><td>'+h(v)+' V</td><td>'+w.toFixed(1)+' W</td><td class=\"'+(p.link_up?'ok':'muted')+'\">'+(p.link_up?'Online':'–')+'</td><td>'+acts+'</td></tr>'"""
if old not in s: raise SystemExit('rowHtml body marker not found')
s=s.replace(old,new,1)
s=s.replace("<tr><td colspan=\"6\">Keine Daten.</td></tr>","<tr><td colspan=\"7\">Keine Daten.</td></tr>",1)
s=s.replace("<tr><td colspan=\"6\">Keine PoE-Ports erkannt.</td></tr>","<tr><td colspan=\"7\">Keine PoE-Ports erkannt.</td></tr>",1)
s=s.replace("<tr><td colspan=\"8\">Keine Daten.</td></tr>","<tr><td colspan=\"9\">Keine Daten.</td></tr>",1)
s=s.replace("<tr><td colspan=\"8\">Keine passenden Ports.</td></tr>","<tr><td colspan=\"9\">Keine passenden Ports.</td></tr>",1)
old="""let k=portKey(d.id,p.port_idx),alias=ALIASES[k]||p.alias||p.name||('Port '+p.port_idx);return '<div style=\"display:grid;grid-template-columns:34px 70px minmax(180px,1fr);gap:8px;align-items:center;padding:8px 12px;border-bottom:1px solid #edf0f2\"><input class=\"group-port-check\" type=\"checkbox\" data-switch=\"'+h(d.id)+'\" data-port=\"'+p.port_idx+'\" '+(selected.has(k)?'checked':'')+'><b>Port '+p.port_idx+'</b><input class=\"group-alias-input\" data-key=\"'+h(k)+'\" value=\"'+h(alias)+'\" placeholder=\"Portname\"></div>'"""
new="""let k=portKey(d.id,p.port_idx),alias=ALIASES[k]||p.alias||p.name||('Port '+p.port_idx),a=p.attached||{},dev=a.name||a.hostname||a.model||a.ip||a.mac||'–',devmeta=[a.ip,a.mac].filter(Boolean).join(' · ');return '<div style=\"display:grid;grid-template-columns:34px 70px minmax(180px,1fr) minmax(180px,1fr);gap:8px;align-items:center;padding:8px 12px;border-bottom:1px solid #edf0f2\"><input class=\"group-port-check\" type=\"checkbox\" data-switch=\"'+h(d.id)+'\" data-port=\"'+p.port_idx+'\" '+(selected.has(k)?'checked':'')+'><b>Port '+p.port_idx+'</b><input class=\"group-alias-input\" data-key=\"'+h(k)+'\" value=\"'+h(alias)+'\" placeholder=\"Portname\"><div><b>'+h(dev)+'</b>'+(devmeta?'<div class=\"muted\" style=\"font-size:11px\">'+h(devmeta)+'</div>':'')+'</div></div>'"""
if old not in s: raise SystemExit('group picker marker not found')
s=s.replace(old,new,1)
s=s.replace('<div class="ok">0.7.5</div>','<div class="ok">0.7.24</div>',1)
p.write_text(s)

# Version metadata: keep release.cfg on current official release; only prerelease points to test version after release exists.
p=Path('plugin.cfg'); t=p.read_text().replace('VERSION=0.7.23','VERSION=0.7.24',1); p.write_text(t)
cp=Path('CHANGELOG.md'); cs=cp.read_text()
if '## 0.7.24' not in cs:
    cp.write_text('## 0.7.24\n- Ports: angeschlossene Geräte aus UniFi Wired-Client-Daten zuordnen.\n- Ports: LLDP-Fallback für UniFi/AP/Switch-Nachbarn und andere LLDP-Geräte.\n- UI: Gerätename, IP, MAC, Hersteller/Modell in PoE-Portansicht.\n- UI: angeschlossenes Gerät auch in der Gruppenauswahl sichtbar.\n\n'+cs)
