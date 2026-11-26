import requests,re,os,json,time,html
H={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
OUT='assets/opengameart'; os.makedirs(OUT,exist_ok=True)
def g(u,**k):
    time.sleep(10); return requests.get(u,headers=H,timeout=60,**k)
rec=[]
import shutil
TOT=0
def room(): return shutil.disk_usage('.').free/1e6>1650 and TOT<120e6
def txt(t): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',re.sub(r'<script[^>]*>.*?</script>|<style.*?</style>','',t,flags=re.S))))
for tid,name in [(9,'2d'),(10,'3d'),(12,'texture'),(13,'music'),(14,'sfx')]:
    r=g(f'https://opengameart.org/art-search-advanced?keys=&field_art_type_tid%5B%5D={tid}&field_art_licenses_tid%5B%5D=4&sort_by=count&sort_order=DESC')
    slugs=[]
    for s in re.findall(r'href="(/content/[^"#?]+)"',r.text):
        if s!='/content/faq' and s not in slugs: slugs.append(s)
    for s in slugs[6:11]:
        if not room(): break
        if os.path.isdir(f'{OUT}/{name}/{s.split("/")[-1]}'): continue
        try:
            p=g('https://opengameart.org'+s).text; t=txt(p)
            lic=re.findall(r'License\(s\):\s*((?:CC0|CC-BY-SA \d\.\d|CC-BY \d\.\d|GPL \d|OGA-BY \d\.\d|LGPL \d\.\d|CC-BY-SA|CC-BY)(?:\s*[0-9.]*)?(?: [^ ]+){0,6})',t)
            lic_txt=re.search(r'License\(s\):(.{0,80})',t)
            author=re.search(r'href="/users/([^"]+)"',p)
            files=re.findall(r'href="(https://opengameart\.org/sites/default/files/[^"]+)"',p)
            files=[f for f in dict.fromkeys(files) if not re.search(r'\.(png|jpg|jpeg|gif)$',f,re.I) or tid in(9,12)]
            files=[f for f in files if '/styles/' not in f and 'thumb' not in f.lower()][:4]
            L=lic_txt.group(1).strip() if lic_txt else ''
            ok=bool(re.search(r'CC0|CC-BY',L)) and not re.search(r'NC|ND',L)
            r0=dict(slug=s,type=name,author=author.group(1) if author else None,license=L,files=files,ok=ok,page='https://opengameart.org'+s)
            if ok:
                d=f'{OUT}/{name}/{s.split("/")[-1]}'; os.makedirs(d,exist_ok=True); got=[]
                for f in files:
                    fn=os.path.join(d,os.path.basename(f).split('?')[0])
                    with g(f,stream=True) as rr:
                        if rr.status_code!=200: continue
                        n=0
                        with open(fn,'wb') as fh:
                            for c in rr.iter_content(1<<20):
                                n+=len(c); fh.write(c)
                                if n>60e6: break
                    got.append(fn); TOT+=os.path.getsize(fn)
                r0['got']=got
            rec.append(r0)
        except Exception as e: rec.append(dict(slug=s,error=repr(e)[:100]))
        json.dump(rec,open('r3/oga_records.json','w'),indent=1)
    print(name,len(slugs),TOT,flush=True)
