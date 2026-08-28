#!/usr/bin/env python3
import argparse, base64, hashlib, hmac, json, os, tempfile, urllib.parse, urllib.request

ALLOWED_HOSTS={'raw.githubusercontent.com','github.com','objects.githubusercontent.com'}
TRUSTED_PUBLIC_KEY_HEX='e9a33e9c989020db24130fe7d5f3079517074ce54313dbc27fd730e6a21ebfc2'

# Minimal Ed25519 verification based on the public-domain reference equations.
b=256
q=2**255-19
l=2**252+27742317777372353535851937790883648493
d=(-121665*pow(121666,q-2,q))%q
I=pow(2,(q-1)//4,q)

def H(m): return hashlib.sha512(m).digest()
def Hint(m): return int.from_bytes(H(m),'little')
def inv(x): return pow(x,q-2,q)
def xrecover(y):
    xx=(y*y-1)*inv(d*y*y+1)%q
    x=pow(xx,(q+3)//8,q)
    if (x*x-xx)%q!=0: x=x*I%q
    if x%2!=0: x=q-x
    return x
By=4*inv(5)%q
Bx=xrecover(By)
B=(Bx,By)
def edwards(P,Q):
    x1,y1=P; x2,y2=Q
    den=inv(1+d*x1*x2*y1*y2)
    x3=(x1*y2+x2*y1)*den%q
    den=inv(1-d*x1*x2*y1*y2)
    y3=(y1*y2+x1*x2)*den%q
    return (x3,y3)
def scalarmult(P,e):
    Q=(0,1)
    while e:
        if e&1: Q=edwards(Q,P)
        P=edwards(P,P); e>>=1
    return Q
def decodepoint(s):
    if len(s)!=32: raise ValueError('bad point length')
    y=int.from_bytes(s,'little') & ((1<<255)-1)
    x=xrecover(y)
    if (x&1) != (s[31]>>7): x=q-x
    P=(x,y)
    if (y*y-x*x-1-d*x*x*y*y)%q!=0: raise ValueError('point not on curve')
    return P
def verify_ed25519(sig,msg,pub):
    if len(sig)!=64 or len(pub)!=32: return False
    try:
        R=decodepoint(sig[:32]); A=decodepoint(pub)
        S=int.from_bytes(sig[32:],'little')
        if S>=l: return False
        h=Hint(sig[:32]+pub+msg)%l
        return scalarmult(B,S)==edwards(R,scalarmult(A,h))
    except Exception:
        return False

def fetch(url, limit=20*1024*1024):
    u=urllib.parse.urlparse(url)
    if u.scheme!='https' or u.hostname not in ALLOWED_HOSTS:
        raise RuntimeError('Unsichere oder nicht erlaubte Update-URL')
    req=urllib.request.Request(url,headers={'User-Agent':'LoxBerry-UniFi-PoE-secure-updater/0.7.9'})
    with urllib.request.urlopen(req,timeout=20) as r:
        data=r.read(limit+1)
    if len(data)>limit:
        raise RuntimeError('Update-Datei ist unerwartet groß')
    return data

def parse_cfg(data):
    out={}
    for line in data.decode('utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith(('#','[')) or '=' not in line: continue
        k,v=line.split('=',1); out[k.strip().upper()]=v.strip()
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',default='https://raw.githubusercontent.com/DuettM/LoxBerry-UniFi-PoE/main/release.cfg')
    ap.add_argument('--output-dir',default='')
    a=ap.parse_args()

    meta=parse_cfg(fetch(a.manifest,256*1024))
    url=meta.get('ARCHIVEURL','')
    checksum_url=meta.get('SHA256URL','')
    signature_url=meta.get('SIGURL','')
    if not url or not checksum_url or not signature_url:
        raise RuntimeError('Release-Manifest enthält SHA256 oder Signatur nicht vollständig')

    expected=fetch(checksum_url,4096).decode('utf-8').strip().split()[0].lower()
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):
        raise RuntimeError('Ungültige SHA256-Prüfsumme')

    blob=fetch(url)
    actual=hashlib.sha256(blob).hexdigest()
    if not hmac.compare_digest(actual,expected):
        raise RuntimeError('SHA256-Prüfung FEHLGESCHLAGEN – Update wird verworfen')

    rawsig=fetch(signature_url,4096).strip()
    try:
        sig=base64.b64decode(rawsig,validate=True)
    except Exception:
        raise RuntimeError('Ungültiges Signaturformat')
    pub=bytes.fromhex(TRUSTED_PUBLIC_KEY_HEX)
    if not verify_ed25519(sig,blob,pub):
        raise RuntimeError('Ed25519-Signaturprüfung FEHLGESCHLAGEN – Update wird verworfen')

    outdir=a.output_dir or tempfile.gettempdir()
    os.makedirs(outdir,exist_ok=True)
    name=os.path.basename(urllib.parse.urlparse(url).path) or 'unifipoe-update.zip'
    path=os.path.join(outdir,name)
    fd,tmp=tempfile.mkstemp(prefix='.verified-',dir=outdir)
    with os.fdopen(fd,'wb') as f: f.write(blob)
    os.chmod(tmp,0o600)
    os.replace(tmp,path)
    print(json.dumps({'ok':True,'version':meta.get('VERSION',''),'sha256':actual,'signature':'valid','path':path},ensure_ascii=False))

if __name__=='__main__': main()
