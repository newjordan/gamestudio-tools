import json,re,csv,collections
H='/workspace/gamedata-work/x_harvest'
posts=json.load(open(f'{H}/all_posts.json')); tco=json.load(open(f'{H}/tco_cache.json'))
r2=set(json.load(open(f'{H}/r2/r2_posts.json')))|set(json.load(open(f'{H}/r2/r2b_posts.json')))
got={json.loads(l)['x_post_url'].rsplit('/',1)[1] for l in open(f'{H}/manifest.jsonl')}
itch=json.load(open(f'{H}/r2/itch_check.json'))
R={}
def s(reason,*ids):
    for i in ids: R[i]=reason
def hasurl(sub): return [pid for pid in r2 if any(sub in (tco.get(u) or '') for u in re.findall(r'https://t\.co/\w+',posts[pid]['text']))]
s('custom_licence_no_redistribution: commercial use OK but resale/redistribution barred (not an open licence)',*sum([hasurl(x) for x in ['vill8tion.itch.io','rjc-dude.itch.io','v3su.itch.io','andy0327','akalionly','ibingames','thecolourfulsuit','gmingassets','dead-channel','buchedegato','xtypeapps','bitwisegaming','twelfstudio','guilherme587','taskirancemal','vdsounds']],[]))
s('paid_or_pay_to_unlock: price shown, only paid tier has the assets',*sum([hasurl(x) for x in ['ansimuz.itch.io/magic-pack','ansimuz.itch.io/ghost-town','ansimuz.itch.io/bb-pack','ansimuz.itch.io/sci-fi-icon','ansimuz.itch.io/gothicvania','pixel-poem','maevedevs','cupnooble','zerie.itch.io','kenmi-art','craftpix.net']],[]))
s('licence_not_stated_on_page: free download but no licence text found',*sum([hasurl(x) for x in ['forsaken-pixels','anokolisa','timethetea','kevins-moms-house','sergilazaro','ojeda-g','gvesster','profactor','negentropy','grokcodereliant.itch.io/turkey','youkaicountry/yknytt','Vuena/vuena-assets-mcp']],[]))
s('license_blocked_or_unverifiable: 3dtextures.me returns 403 to the box; terms not readable',*hasurl('3dtextures.me'))
s('source_available_not_open: Aseprite EULA / angel-named repo / too large (godot, three.js 1.7 GB)',*sum([hasurl(x) for x in ['aseprite/aseprite','Angels-95','mrdoob/three.js','godotengine/godot','anthropics/skills','WhiteTowerAI/ohmygame']],[]))
s('login_or_gated: cgtrader / gumroad / ko-fi store',*sum([hasurl(x) for x in ['cgtrader','gumroad','ko-fi']],[]))
s('aggregator_or_news_post: no downloadable asset itself (docs, directories, sale posts)',*sum([hasurl(x) for x in ['docs.ambientcg','slopstar','assetsifter','incompetech','itch.io/b/','itch.io/launch-sale']],[]))
rows=[]
for pid in r2:
    if pid in got: continue
    p=posts[pid]
    links=[tco.get(u) for u in re.findall(r'https://t\.co/\w+',p['text'])]; links=[l for l in links if l and not re.search(r'//(x|twitter)\.com/',l)]
    if not links: continue
    reason=R.get(pid,'off_topic_or_no_usable_open_asset: promo, news, personal project, or no downloadable file')
    rows.append(dict(x_post_url=p.get('url') or f"https://x.com/{p['username']}/status/{pid}",author='@'+str(p['username']),source='search_r2',links=' '.join(links)[:300],reason=reason,text=p['text'][:140].replace('\n',' ')))
old=list(csv.DictReader(open(f'{H}/candidates_skipped.csv')))
# round-1 Kenney rows now fetched -> drop from skipped
old=[o for o in old if not o['reason'].startswith('kenney_noai') and o['x_post_url'].rsplit('/',1)[-1] not in got]
for o in old: o['round']='1'
for r in rows: r['round']='2'
allr=old+rows
with open(f'{H}/candidates_skipped.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['x_post_url','author','source','links','reason','text','round']); w.writeheader(); w.writerows(allr)
json.dump(allr,open(f'{H}/candidates_skipped.json','w'),indent=1)
print(len(old),len(rows),collections.Counter(r['reason'].split(':')[0] for r in rows))
