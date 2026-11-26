import json,sys
t=open(sys.argv[1]).read()
i=t.index('{"');j=t.rindex('}')
d=json.loads(t[i:j+1])
users={u['id']:u['username'] for u in d.get('includes',{}).get('users',[])}
print(d.get('meta'))
for p in d.get('data',[]):
    urls=[u.get('expanded_url') for u in p.get('entities',{}).get('urls',[]) if not any(h in (u.get('expanded_url') or '') for h in ('x.com/','twitter.com/'))]
    print(p['id'],users.get(p['author_id']),p['public_metrics']['like_count'],'|',p['text'][:160].replace('\n',' '),'|',urls)
