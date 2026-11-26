import json,re,subprocess,concurrent.futures as cf,os
posts=json.load(open('search_posts.json'))
bm=json.load(open('bookmarks_raw.json'))
bu={u['id']:u['username'] for u in bm['includes']['users']}
for p in bm['data']:
    p['username']=bu.get(p['author_id']); p['src']='bookmark'; posts.setdefault(p['id'],p)
for p in posts.values(): p.setdefault('src','search')
cache=json.load(open('tco_cache.json')) if os.path.exists('tco_cache.json') else {}
links=set()
for p in posts.values():
    links|=set(re.findall(r'https://t\.co/\w+',p['text']))
links-=set(cache)
def r(u):
    try:
        o=subprocess.run(['curl','-sI','-m','15',u],capture_output=True,text=True).stdout
        m=re.search(r'(?im)^location:\s*(\S+)',o)
        return u,(m.group(1) if m else None)
    except Exception as e: return u,None
with cf.ThreadPoolExecutor(8) as ex:
    for u,l in ex.map(r,sorted(links)): cache[u]=l
json.dump(cache,open('tco_cache.json','w'),indent=0)
json.dump(posts,open('all_posts.json','w'))
print(len(posts),len(cache),sum(1 for v in cache.values() if v is None))
