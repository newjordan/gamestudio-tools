import requests,os,json,random,time
UA={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
OUT='assets/ambientcg'; os.makedirs(OUT,exist_ok=True)
random.seed(11); rec=[]
for typ,n in [('Material',28),('HDRI',6),('3DModel',6)]:
    d=requests.get(f'https://ambientcg.com/api/v2/full_json?type={typ}&limit=200&include=downloadData,tagData,displayData',headers=UA,timeout=60).json()
    A=d['foundAssets']; bycat={}
    for a in A: bycat.setdefault(a.get('displayCategory') or a.get('category') or 'x',[]).append(a)
    sel=[];cats=sorted(bycat)
    while len(sel)<n and any(bycat.values()):
        for c in cats:
            if bycat[c] and len(sel)<n: sel.append(bycat[c].pop(random.randrange(len(bycat[c]))))
    for a in sel:
        best=None
        for fol in a['downloadFolders'].values():
            for cat in fol['downloadFiletypeCategories'].values():
                for dl in cat['downloads']:
                    at=dl.get('attribute','')
                    if typ=='Material' and at=='1K-JPG': best=dl
                    if typ=='HDRI' and at=='1K-HDR': best=dl
                    if typ=='3DModel' and at in ('1K-JPG','1K-PNG') and best is None: best=dl
        if not best or best['size']>40e6: rec.append(dict(id=a['assetId'],ok=False,why='no small variant')); continue
        p=f"{OUT}/{typ}/{best['fileName']}"; os.makedirs(os.path.dirname(p),exist_ok=True)
        try:
            with requests.get(best['downloadLink'],headers=UA,stream=True,timeout=180) as r:
                r.raise_for_status()
                with open(p,'wb') as f:
                    for c in r.iter_content(1<<20): f.write(c)
            rec.append(dict(id=a['assetId'],type=typ,file=p,size=os.path.getsize(p),ok=True,category=a.get('displayCategory'),page=f"https://ambientcg.com/view?id={a['assetId']}"))
        except Exception as e: rec.append(dict(id=a['assetId'],ok=False,why=repr(e)[:80]))
        time.sleep(1)
    json.dump(rec,open('r2/ambientcg_records.json','w'),indent=1); print(typ,len(sel),flush=True)
