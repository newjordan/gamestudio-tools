import requests,re,json,sys,time
UA={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
def check(url):
    r=requests.get(url,headers=UA,timeout=30)
    if r.status_code!=200: return dict(url=url,status=r.status_code)
    t=r.text
    price=re.search(r'itemprop="price" content="([\d.]+)"',t) or re.search(r'class="price_value">([^<]*)<',t)
    t2=re.sub(r'<script[^>]*>.*?</script>|<style.*?</style>','',t,flags=re.S); t2=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',t2))
    lic=re.search(r'Asset license ([^ ].{0,60}?) (?:Content|Download|Purchase|Tags|Author|Made|Links|Average|Release|Rating|Status)',t2)
    tags=re.search(r'Tags ((?:[^ ]+ ?,? ?){1,25})',t2)
    ai=re.search(r'(No generative AI[^.]{0,30}|AI Disclosure [A-Za-z\- ]{0,40}|AI[- ]generated|100% ai)',t2,re.I)
    dl=bool(re.search(r'Download Now|Name your own price|No payment|Download',t2)) 
    buy=re.search(r'(\$\d+(?:\.\d\d)?(?: \w{3})? or more|Buy Now)',t2)
    lines=[m.group(0) for m in re.finditer(r'.{50}(CC0|CC-BY|CC BY|public domain|licen[sc]e).{100}',t2,re.I)][:2]
    return dict(url=url,status=200,title=re.search(r'<title>(.*?)</title>',t).group(1)[:70],lic=lic.group(1) if lic else None,price=price.group(1) if price else None,buy=buy.group(0) if buy else None,ai=ai.group(0) if ai else None,lines=lines)
if __name__=='__main__':
    urls=json.load(open('r2/cand_pages.json'))['itch']
    out=[]
    for u in urls:
        try: out.append(check(u))
        except Exception as e: out.append(dict(url=u,error=repr(e)[:80]))
        time.sleep(0.7)
    json.dump(out,open('r2/itch_check.json','w'),indent=1)
    for o in out: print(o['url'].split('//')[1],'|',o.get('lic'),'|',o.get('buy'),'|',o.get('ai'),'|',(o.get('lines') or [''])[0][:150])
