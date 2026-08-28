#!/usr/bin/env python3
import argparse, hashlib, hmac, json, os, tempfile, urllib.parse, urllib.request
ALLOWED_HOSTS={'raw.githubusercontent.com','github.com','objects.githubusercontent.com'}
def fetch(url, limit=20*1024*1024):
    u=urllib.parse.urlparse(url)
    if u.scheme!='https' or u.hostname not in ALLOWED_HOSTS: raise RuntimeError('Unsichere oder nicht erlaubte Update-URL')
    req=urllib.request.Request(url,headers={'User-Agent':'LoxBerry-UniFi-PoE-secure-updater/0.7.8'})
    with urllib.request.urlopen(req,timeout=20) as r: data=r.read(limit+1)
    if len(data)>limit: raise RuntimeError('Update-Datei ist unerwartet groß')
    return data
def parse_cfg(data):
    out={}
    for line in data.decode('utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith(('#','[')) or '=' not in line: continue
        k,v=line.split('=',1); out[k.strip().upper()]=v.strip()
    return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--manifest',default='https://raw.githubusercontent.com/DuettM/LoxBerry-UniFi-PoE/main/release.cfg'); ap.add_argument('--output-dir',default=''); a=ap.parse_args()
    meta=parse_cfg(fetch(a.manifest,256*1024)); url=meta.get('ARCHIVEURL',''); checksum_url=meta.get('SHA256URL','')
    if not url or not checksum_url: raise RuntimeError('Release-Manifest enthält keine verifizierbare Prüfsumme')
    expected=fetch(checksum_url,4096).decode('utf-8').strip().split()[0].lower()
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected): raise RuntimeError('Ungültige SHA256-Prüfsumme')
    blob=fetch(url); actual=hashlib.sha256(blob).hexdigest()
    if not hmac.compare_digest(actual,expected): raise RuntimeError('SHA256-Prüfung FEHLGESCHLAGEN – Update wird verworfen')
    outdir=a.output_dir or tempfile.gettempdir(); os.makedirs(outdir,exist_ok=True)
    name=os.path.basename(urllib.parse.urlparse(url).path) or 'unifipoe-update.zip'; path=os.path.join(outdir,name)
    fd,tmp=tempfile.mkstemp(prefix='.verified-',dir=outdir)
    with os.fdopen(fd,'wb') as f: f.write(blob)
    os.chmod(tmp,0o600); os.replace(tmp,path)
    print(json.dumps({'ok':True,'version':meta.get('VERSION',''),'sha256':actual,'path':path},ensure_ascii=False))
if __name__=='__main__': main()
