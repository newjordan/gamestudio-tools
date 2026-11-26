import json,re,csv
H='/workspace/gamedata-work/x_harvest'
posts=json.load(open(f'{H}/all_posts.json')); tco=json.load(open(f'{H}/tco_cache.json'))
got={json.loads(l)['x_post_url'].rsplit('/',1)[1] for l in open(f'{H}/manifest.jsonl')}
R={}
def s(reason,*ids):
    for i in ids: R[i]=reason
KEN='kenney_noai_signal: CC0 licence, but kenney.nl pages carry robots noai,noimageai + tdm-reservation meta; held for Jordan decision'
s(KEN,'2124844949837418601','2121251882920280133','2122307886986494215','2119334844672958723','2118044691858121004','2122600627939287474','2119738358452908053','2121456684233286037','2121473916053147854','2123473312118399110','2125216303669510250','2125433186729746784','2124941638070051000','2116828187141550346','2119642827873550714','2122827130837057765')
s('license_not_in_allowed_set: Apache-2.0','2114099613808353561','2125406446187843953','2118337347896930563')
s('license_not_in_allowed_set: GPL-2.0','2125326939476852885','2125701698135937174')
s('license_unclear: Apache-2.0 code + CC-BY docs/assets mixed (NVIDIA); research code with model weights; not fetched','2123138842375107057')
s('too_large_or_off_topic: godot-sqlite 586 MB / godot engine / TRELLIS 1.1 GB ML code','2104511765790835150','2108147260953415775','2123038555253481515')
s('paid_product: only the CC0 icon zip is separate, behind purchase ($14.99 kit)','2120991206838595860')
s('huggingface_source_and_ai_generated: Hugging Face pulls barred; dataset is AI-generated','2120433302666666400')
s('login_or_patreon_gated_or_licence_unverified','2114967456670224680','2106843721082028132','2082518235816042660','2081816892764016808')
s('licence_unclear_or_not_published: video link / not yet released / page blocked','2093807430534574272','2120172279220908242','2073527288679764438','2051528712831500797','2074882871483850952','2098530421139206578','2114874716888650044')
s('off_topic_or_not_an_asset: runtime/library/mod tooling','2116657806426435800','2082225563930952081','2110658868439122109','2108281563528286594','2125487809398231097','2125478065883291825','2122261146681983402','2125475649632829552')
s('no_repo_or_asset_link_recoverable_from_post (media-only link)','2125567678152872165','2110901978662621545')
s('model_weights_or_paper: Hugging Face source, not fetched','2117091981973434415','2123331996927897922')
s('aggregator_or_list_post: names sources (Quaternius, KayKit, Poly Haven, ambientCG...) but not evaluated this run','2120185836008308866','2122722984284569778','2120937913110163708','2124849972051063101','2124855250901180832','2123544420142166080','2124592502355206296','2122752880935621089','2113347153653583910')
kw=re.compile(r'game|sprite|tile|pixel|texture|sfx|shader|blender|godot|unity|unreal|3d|asset|animation|spine|itch|mesh|voxel|music|audio|motion|CC0|free',re.I)
rows=[]
for pid,p in posts.items():
    if pid in got: continue
    links=[tco.get(u) for u in re.findall(r'https://t\.co/\w+',p['text'])]
    links=[l for l in links if l and not re.search(r'//(x|twitter)\.com/',l)]
    if pid in R: reason=R[pid]
    elif p['src']=='bookmark':
        if not kw.search(p['text']): continue
        reason='bookmark_off_topic: AI/ML news, not a game-dev asset'
    else:
        reason='off_topic_or_no_downloadable_open_asset: news, promo, NFT/crypto, personal project, or no usable link'
    rows.append(dict(x_post_url=p.get('url') or f"https://x.com/{p['username']}/status/{pid}",author='@'+str(p['username']),source=p['src'],links=' '.join(links),reason=reason,text=p['text'][:140].replace('\n',' ')))
json.dump(rows,open(f'{H}/candidates_skipped.json','w'),indent=1)
with open(f'{H}/candidates_skipped.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
import collections
c=collections.Counter(r['reason'].split(':')[0] for r in rows)
print(len(rows),c)
srcs=collections.Counter(p['src'] for p in posts.values()); print(srcs,len(posts))
