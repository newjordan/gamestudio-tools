import json,glob,os
A='/cursor/stores/user/grok-bot/agents/f5794917-34c0-4044-8883-ca075957425b/assets/'
files=['01M8AB4CQ2Z5T36XKD5CQEX2ET','01M8AB4S9DW0F78F94SR19C9VM','01M8AB4WG0YWVHNDEY6HS018K8','01M8AB4XTRBN42ZZMSGTQMJZV5','01M8AB4YC2N4YHVJZQGX17JA9C','01M8AB5287DQMPV21E5SJRVSB3','01M8AB54N6NG2A2F8R6PP8MAPA','01M8AB54XXHHNHQ0YF3NE4QZPR','01M8AB55REVYY1CCDYG2NPWD1G','01M8AB68B9CVS44ARE5GSK1QMR','01M8AB69CR9BEPNVPPRXAGE480','01M8AB6AV5WER06JEKDQZFSJJE','01M8AB6CKF729PVV2XNKWPBR1G']
posts={}
per=[]
for f in files:
    t=open(A+f+'.txt').read()
    d=json.loads(t[t.index('{"'):t.rindex('}')+1])
    users={u['id']:u['username'] for u in d.get('includes',{}).get('users',[])}
    per.append((f,len(d.get('data',[])),d['meta'].get('next_token') is not None))
    for p in d.get('data',[]):
        p['username']=users.get(p['author_id'])
        posts[p['id']]=p
json.dump(posts,open('search_posts.json','w'),indent=0)
print(per,len(posts))
