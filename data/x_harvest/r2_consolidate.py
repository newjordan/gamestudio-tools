import json,re,subprocess,concurrent.futures as cf,os
A='/cursor/stores/user/grok-bot/agents/f5794917-34c0-4044-8883-ca075957425b/assets/'
files='01M8ACBR8TGH9CHA3W4G0M5W3M 01M8ACBSR3H7RZDJDQMMMY7H0P 01M8ACBVTC4PS26GFHBTF3JC90 01M8ACBXAN3BBVV68A0Z40B70D 01M8ACBYPX7TC721Y4NEN9468P 01M8ABXQMV71SHVV4TMYD2KSZJ 01M8ABXSK1CA161JF91MKYKK9R 01M8ABXT9R1MYNBZTHJ0FEN7AJ 01M8ABXW2KW2FHWTJX813DFNB8 01M8ABXXJXQVD1J849PDTBG4C6 01M8ABXZAVA6X2DF9JPZ4F9MBF 01M8ABY4MA1AGCAHQQKHA9NT20 01M8ABY6N4P503CZA89WSJ2TAE 01M8ABY7VV78AJ7JW9FNDEG4JX 01M8ABY9NANGN9SET8J00QMCMX 01M8ABYAHK2DDT477DMRJWV1ME 01M8ABYDC6A275XX5N9FPA5PJA'.split()
old=json.load(open('all_posts.json'))
new={};per=[]
for f in files:
    t=open(A+f+'.txt').read(); d=json.loads(t[t.index('{"'):t.rindex('}')+1])
    users={u['id']:u['username'] for u in d.get('includes',{}).get('users',[])}
    per.append(len(d.get('data',[])))
    for p in d.get('data',[]):
        p['username']=users.get(p['author_id']); p['src']='search_r2'
        if p['id'] not in old: new[p['id']]=p
cache=json.load(open('tco_cache.json'))
links=set()
for p in new.values(): links|=set(re.findall(r'https://t\.co/\w+',p['text']))
links-=set(cache)
def r(u):
    o=subprocess.run(['curl','-sI','-m','15',u],capture_output=True,text=True).stdout
    m=re.search(r'(?im)^location:\s*(\S+)',o); return u,(m.group(1) if m else None)
with cf.ThreadPoolExecutor(8) as ex:
    for u,l in ex.map(r,sorted(links)): cache[u]=l
json.dump(cache,open('tco_cache.json','w'),indent=0)
json.dump(new,open('r2/r2_posts.json','w'))
allp=dict(old); allp.update(new); json.dump(allp,open('all_posts.json','w'))
print(per,len(new),len(allp))
out=open('r2/cand_links.txt','w')
for pid,p in sorted(new.items(),key=lambda x:-x[1]['public_metrics']['like_count']):
    ls=[cache.get(u) for u in re.findall(r'https://t\.co/\w+',p['text'])]
    ls=[l for l in ls if l and not re.search(r'//(x|twitter)\.com/',l)]
    if ls: print(pid,p['username'],p['public_metrics']['like_count'],'|',p['text'][:100].replace('\n',' '),'|',ls,file=out)
