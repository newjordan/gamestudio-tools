import requests,re,sys,json,os,hashlib
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
def list_uploads(page_url):
    s=requests.Session(); s.headers['User-Agent']=UA
    r=s.get(page_url,timeout=30); r.raise_for_status()
    csrf=re.search(r'name="csrf_token" value="([^"]+)"',r.text).group(1)
    r2=s.post(page_url.rstrip('/')+'/download_url',data={'csrf_token':csrf},timeout=30)
    j=r2.json(); dl=j['url']
    r3=s.get(dl,timeout=30)
    ups=[]
    for m in re.finditer(r'<div class="upload">(.*?)</div>\s*</div>\s*(?=<div class="upload">|</div>|$)',r3.text,re.S):
        blk=m.group(1)
        uid=re.search(r'data-upload_id="(\d+)"',blk); name=re.search(r'class="upload_name"[^>]*>.*?title="([^"]*)"',blk,re.S)
        size=re.search(r'class="file_size"[^>]*><span>([^<]*)',blk)
        ups.append((uid.group(1) if uid else None,name.group(1) if name else None,size.group(1) if size else None))
    return s,dl,csrf_from(r3.text),r3.text,ups
def csrf_from(t):
    m=re.search(r'name="csrf_token" value="([^"]+)"',t) or re.search(r'csrf_token["\']?\s*[:=]\s*["\']([^"\']+)',t)
    return m.group(1) if m else None
if __name__=='__main__':
    s,dl,csrf,html,ups=list_uploads(sys.argv[1])
    print(dl); print(ups)

def fetch_all(page_url,outdir,maxmb=300,only=None):
    s,dl,csrf,html,ups=list_uploads(page_url)
    base=page_url.rstrip('/')
    os.makedirs(outdir,exist_ok=True)
    res=[]
    for uid,name,size in ups:
        if only and not only(name): res.append((name,size,'skipped-filter')); continue
        mb=None
        if size:
            m=re.match(r'([\d.]+)\s*(KB|MB|GB|bytes)',size)
            if m:
                v=float(m.group(1)); mb=v*{'KB':1/1024,'MB':1,'GB':1024,'bytes':1/1048576}[m.group(2)]
        if mb and mb>maxmb: res.append((name,size,'skipped-too-big')); continue
        r=s.post(f"{base}/file/{uid}?source=game_download&as_props=1&after_download_lightbox=true",data={'csrf_token':csrf},timeout=30)
        url=r.json()['url']
        p=os.path.join(outdir,re.sub(r'[^\w.\- ()]','_',name))
        with s.get(url,stream=True,timeout=120) as rr:
            rr.raise_for_status()
            with open(p,'wb') as f:
                for ch in rr.iter_content(1<<20): f.write(ch)
        res.append((name,size,p))
    return res
