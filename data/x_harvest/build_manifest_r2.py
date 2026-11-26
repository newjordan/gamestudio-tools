import json,re,os,csv,glob,hashlib,sys
sys.path.insert(0,'.')
from build_manifest import tree_sha
H='/workspace/gamedata-work/x_harvest'
posts=json.load(open(f'{H}/all_posts.json'))
def purl(pid):
    p=posts[pid]; return p.get('url') or f"https://x.com/{p['username']}/status/{pid}"
def sha(n): return open(f'{H}/assets/github/{n}.sha').read().strip()
rows=[]
def add(pid,src,page,lic,proof,attr,typ,path,notes='',ai=False):
    p=f'{H}/{path}'
    if not os.path.exists(p): return
    s,n,sz=tree_sha(p)
    rows.append(dict(x_post_url=purl(pid),author_handle='@'+posts[pid]['username'],asset_page_url=page,licence=lic,licence_proof_url=proof,attribution=attr,asset_type=typ,file_count=n,size_bytes=sz,sha256_tree=s,local_path=p,source=src,ai_generated=ai,notes=notes,round=2))
# Kenney
K16={'retro-textures-liminal':'2124844949837418601','scribble-planes':'2122307886986494215','mini-characters':'2119334844672958723','interface-sounds':'2118044691858121004','input-prompts':'2122600627939287474','ui-pack':'2121456684233286037','fantasy-ui-borders':'2121456684233286037','pattern-pack-2':'2121473916053147854','generic-items':'2123473312118399110','pattern-pack':'2121251882920280133','pattern-pack-extra':'2121251882920280133','pattern-pack-lines':'2121251882920280133','pattern-pack-pixel':'2121251882920280133','animated-characters-protagonists':'2125216303669510250','animated-characters-retro':'2125216303669510250','animated-characters-survivors':'2125216303669510250'}
KNOTE='Held in round 1 for the kenney.nl robots noai,noimageai + tdm-reservation meta; fetched in round 2 per Jordan (restriction dropped). Licence itself is CC0.'
for d,base in [('assets/kenney','https://kenney.nl/assets/'),('assets/kenney_itch','https://kenney-assets.itch.io/')]:
    for z in sorted(glob.glob(f'{H}/{d}/*.zip')):
        slug=os.path.basename(z)[:-4]
        pid=K16.get(slug,'2120937913110163708')
        src='search' if slug in K16 else 'search (aggregator post naming Kenney)'
        add(pid,src,base+slug,'CC0-1.0','https://kenney.nl/support (all assets CC0)','Kenney (www.kenney.nl) - credit not required','Kenney pack (2D/3D/UI/audio/fonts) zip',f'{d}/{os.path.basename(z)}',KNOTE if slug in K16 else 'Kenney pack; kenney.nl meta noai/tdm-reservation recorded, restriction dropped per Jordan.')
add('2116828187141550346','search','https://github.com/Hidencod/tge-assets','CC0-1.0',f"https://github.com/Hidencod/tge-assets/blob/{sha('Hidencod_tge-assets')}/LICENSE",'Models by Kenney (CC0), converted to GLB with thumbnails by Hidencod; credit not required','3D models (1883 GLB in 19 packs, all Kenney)','assets/github/Hidencod_tge-assets','Redistribution of Kenney CC0 models; same kenney.nl noai meta caveat as the Kenney packs.')
# Quaternius
qa={'quaternius.com sample':0}
for d in sorted(glob.glob(f'{H}/assets/quaternius_itch/quaternius_*')):
    slug=os.path.basename(d).replace('quaternius_','')
    add('2124855250901180832','search (aggregator post naming Quaternius)',f'https://quaternius.itch.io/{slug}','CC0-1.0 (kit licence listed CC0 on quaternius.com pack page)','https://quaternius.com/faq.html (each kit CC0 or QAL; this kit is CC0) + license txt inside zip','Quaternius - credit not required','3D models (low-poly) zip',f'assets/quaternius_itch/quaternius_{slug}','Author states no AI used (quaternius.com/faq.html). QAL-licensed kits were not downloaded.')
# KayKit
for d in sorted(glob.glob(f'{H}/assets/kaykit/kaylousberg_*')):
    slug=os.path.basename(d).replace('kaylousberg_','')
    add('2122722984284569778','search (aggregator post naming KayKit)',f'https://kaylousberg.itch.io/{slug}','CC0-1.0','https://kaylousberg.itch.io/'+slug+' ("CC0 Licensed") + License.txt in zip','Kay Lousberg (KayKit) - credit not required','3D models zip (free tier of the pack)',f'assets/kaykit/kaylousberg_{slug}','Free tier only; paid tiers not fetched.')
# Poly Haven
for t,nm in [('textures','PBR textures (1k jpg: diffuse, normal gl, rough, arm), 90 assets'),('models','3D models (glTF 1k with textures), 45 assets'),('hdris','HDRIs (1k hdr), 20 assets')]:
    add('2123544420142166080','search (aggregator post naming Poly Haven)','https://polyhaven.com/'+t,'CC0-1.0','https://polyhaven.com/license','Poly Haven artists - credit not required (credit appreciated)',nm,f'assets/polyhaven/{t}','Fetched via the public API (api.polyhaven.com) with a descriptive User-Agent as their ToS requires; site states all assets are CC0 and made without generative AI (polyhaven.com/llms.txt). Per-asset list in r2/polyhaven_records.json.')
# ambientCG
for t,nm in [('Material','PBR materials (1K-JPG zips)'),('HDRI','HDRIs (1K-HDR zips)'),('3DModel','3D models (1K zips)')]:
    add('2115191478779785268','search','https://ambientcg.com/list?type='+t.lower(),'CC0-1.0','https://ambientcg.com/view?id=Fabric087 (FAQ: all assets CC0) + https://docs.ambientcg.com/license','ambientCG - credit not required',nm,f'assets/ambientcg/{t}','Fetched via public API v2. Per-asset list in r2/ambientcg_records.json.')
# Vuena
add('2124986142319939912','search','https://github.com/Vuena/vuena-assets-mcp','CC0-1.0 (assets), MIT (code)','https://vuena-assets.test-games.workers.dev/manifest.json','Vuena - credit not required','3D models (76 GLB, 14 rigged)','assets/vuena','Models are procedural, generated by AI-assisted code (author statement); no AI mesh generators. Repo licence flag was NOASSERTION; licence taken from the live catalog/manifest.')
# itch r2
add('2124111152468644338','search','https://ansimuz.itch.io/sunny-land-pixel-game-art','CC0-1.0','https://ansimuz.itch.io/sunny-land-pixel-game-art (Asset license: Creative Commons Zero v1.0 Universal; no generative AI)','Artwork by Luis Zuno (@ansimuz)','tileset + sprites + music + Godot/Phaser projects','assets/itch/ansimuz_sunny-land-pixel-game-art','Music by Pascal Belisle zip says credit required (music-pascal-public-license.txt): credit www.soundcloud.com/thetoadz. Page lists price as $5+ but a free download exists.')
add('2125682274033168781','search','https://purrplecat.itch.io/bloom','CC-BY-4.0','https://purrplecat.itch.io/bloom (Asset license: Creative Commons Attribution v4.0 International; No generative AI)','Attribution required: "Bloom" soundtrack by purrplecat (https://purrplecat.itch.io/bloom), CC BY 4.0','music (10 mp3 tracks)','assets/itch/purrplecat_bloom','Post by @Ophthordle references the pack.')
# GitHub r2
for pid,repo,lic,attr,typ,notes in [
 ('2121805441680458043','Orama-Interactive/Pixelorama','MIT','Orama Interactive, MIT; bundled addons keep their own LICENSE files (one CC-BY, one GPL-ish installer util)','tool (Godot pixel-art editor, source + assets)','Subfolder licences vary; see per-folder LICENSE files.'),
 ('2120858694137090141','markocrafts/pixelartstudio','MIT','MarkoCrafts, MIT','tool (browser pixel art studio)',''),
 ('2113520183952408855','neilsonnn/image-blaster','MIT','neilsonnn, MIT','tool (image to 3D scene)',''),
 ('2116282150056292505','WZ2009git/WZ2009-Map-Editor','Apache-2.0','WZ2009, Apache-2.0; see NOTICE','tool (Blender map-editor addon)',''),
 ('2114099613808353561','gamedev-skills/awesome-gamedev-agent-skills','Apache-2.0','gamedev-skills contributors, Apache-2.0; see NOTICE','agent skills / docs (game dev)','Previously skipped in round 1 as Apache-2.0; accepted after Jordan update.'),
 ('2118337347896930563','ramenvr/autopilot','Apache-2.0','ramenvr, Apache-2.0','tool (game dev agent autopilot)','Previously skipped in round 1 as Apache-2.0; accepted after Jordan update.'),
 ('2125326939476852885','ikonnow/Assets2Godot','GPL-3.0','Ingmar Konnow and contributors, GPL-3.0','tool (Godot asset import addon)','GPL: derivatives must stay GPL. Previously skipped in round 1; accepted after Jordan update.')]:
    n=repo.replace('/','_')
    add(pid,'search',f'https://github.com/{repo}',lic,f"https://github.com/{repo}/blob/{sha(n)}/LICENSE",attr,typ,f'assets/github/{n}',notes)
# OGA
if os.path.exists(f'{H}/r2/oga_records.json'):
    for r in json.load(open(f'{H}/r2/oga_records.json')):
        if not r.get('ok') or not r.get('got'): continue
        d=os.path.dirname(r['got'][0]).replace(H+'/','')
        lic=re.match(r'(CC0|CC-BY-SA|CC-BY)',r['license']); lic=lic.group(1) if lic else r['license'][:20]
        add('2120937913110163708','search (OGA via ptb_games aggregator post)',r['page'],lic,r['page']+' (License(s) field)',f"By {r['author']} on OpenGameArt - credit not required for CC0",f"OpenGameArt {r['type']} submission",d,'opengameart.org robots.txt disallows AI crawlers; items fetched individually at 10 s intervals; restriction dropped per Jordan.')
# merge
old=[json.loads(l) for l in open(f'{H}/manifest.jsonl')]
old=[o for o in old if o.get('round')!=2]
for o in old: o.setdefault('round',1)
allr=old+rows
with open(f'{H}/manifest.jsonl','w') as f:
    for r in allr: f.write(json.dumps(r)+'\n')
with open(f'{H}/manifest.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(allr[0])); w.writeheader(); w.writerows(allr)
print(len(old),len(rows),sum(r['size_bytes'] for r in rows)/1e6,'MB r2')
