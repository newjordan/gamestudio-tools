import requests,sys,os,re,time,json
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
def dl(slug,out):
    s=requests.Session(); s.headers['User-Agent']=UA
    page=f'https://kenney.nl/assets/{slug}'
    r=s.get(page,timeout=30)
    if r.status_code!=200: return None,'page %d'%r.status_code
    h=('assets/'+slug).encode().hex()
    j=s.get('https://kenney.nl/download-link/'+h,headers={'Referer':page,'Accept':'application/json'},timeout=30)
    if j.status_code!=200: return None,'link %d'%j.status_code
    url=j.json()['url']
    os.makedirs(out,exist_ok=True); p=os.path.join(out,slug+'.zip')
    with s.get(url,stream=True,timeout=300) as rr:
        rr.raise_for_status()
        if int(rr.headers.get('content-length',0))>60e6: return None,'too large %s'%rr.headers.get('content-length')
        with open(p,'wb') as f:
            for c in rr.iter_content(1<<20): f.write(c)
    return p,r.text
if __name__=='__main__':
    for slug in sys.argv[2:]:
        p,info=dl(slug,sys.argv[1]); print(slug,p and os.path.getsize(p),'' if p else info); time.sleep(2)
