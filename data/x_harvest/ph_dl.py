import requests,os,json,random,time,hashlib,sys
UA={'User-Agent':'x-harvest-research (OmniSpace Technologies; personal dataset building)'}
OUT='assets/polyhaven'; os.makedirs(OUT,exist_ok=True)
def get(u): 
    for i in range(3):
        try:
            r=requests.get(u,headers=UA,timeout=40)
            if r.status_code==200: return r
        except Exception: pass
        time.sleep(2)
def fetch(url,p):
    os.makedirs(os.path.dirname(p),exist_ok=True)
    with requests.get(url,headers=UA,stream=True,timeout=120) as r:
        r.raise_for_status()
        with open(p,'wb') as f:
            for c in r.iter_content(1<<20): f.write(c)
random.seed(7)
rec=[]
def pick(t,n):
    d=get(f'https://api.polyhaven.com/assets?t={t}').json()
    bycat={}
    for k,v in d.items(): bycat.setdefault(v['categories'][0] if v['categories'] else 'x',[]).append(k)
    sel=[]; cats=sorted(bycat)
    while len(sel)<n and any(bycat.values()):
        for c in cats:
            if bycat[c] and len(sel)<n: sel.append(bycat[c].pop(random.randrange(len(bycat[c]))))
    return sel,d
for t,n,fn in [('textures',90,'tex'),('models',45,'mod'),('hdris',20,'hdri')]:
    sel,meta=pick(t,n)
    for s in sel:
        f=get(f'https://api.polyhaven.com/files/{s}').json(); base=f'{OUT}/{t}/{s}'; ok=True
        try:
            if t=='textures':
                for m in ['Diffuse','nor_gl','Rough','arm']:
                    if m in f and '1k' in f[m] and 'jpg' in f[m]['1k']:
                        u=f[m]['1k']['jpg']['url']; fetch(u,f'{base}/{os.path.basename(u)}')
            elif t=='models':
                g=f['gltf']['1k']['gltf']; fetch(g['url'],f"{base}/{os.path.basename(g['url'])}")
                for rel,inc in g.get('include',{}).items(): fetch(inc['url'],f'{base}/{rel}')
            else:
                h=f['hdri']['1k']['hdr']; fetch(h['url'],f"{base}/{os.path.basename(h['url'])}")
        except Exception as e: ok=False; print('ERR',s,repr(e)[:100])
        rec.append(dict(slug=s,type=t,ok=ok,name=meta[s]['name'],authors=meta[s].get('authors'),page=f'https://polyhaven.com/a/{s}'))
        time.sleep(0.3)
    json.dump(rec,open('r2/polyhaven_records.json','w'),indent=1); print(t,len(sel),flush=True)
