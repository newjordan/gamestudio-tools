import json,re,os,hashlib,csv,glob
H='/workspace/gamedata-work/x_harvest'
posts=json.load(open(f'{H}/all_posts.json')); tco=json.load(open(f'{H}/tco_cache.json'))
def purl(pid):
    p=posts[pid]; return p.get('url') or f"https://x.com/{p['username']}/status/{pid}"
def tree_sha(path):
    if os.path.isfile(path):
        h=hashlib.sha256()
        with open(path,'rb') as f:
            for c in iter(lambda:f.read(1<<20),b''): h.update(c)
        return h.hexdigest(),1,os.path.getsize(path)
    lines=[];n=0;sz=0
    for r,d,fs in os.walk(path):
        d.sort()
        for fn in sorted(fs):
            fp=os.path.join(r,fn); rel=os.path.relpath(fp,path)
            h=hashlib.sha256()
            with open(fp,'rb') as f:
                for c in iter(lambda:f.read(1<<20),b''): h.update(c)
            lines.append(f"{h.hexdigest()}  {rel}"); n+=1; sz+=os.path.getsize(fp)
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest(),n,sz
GH=lambda r,sha:f"https://github.com/{r}/blob/{sha}/LICENSE"
def sha(n): return open(f'{H}/assets/github/{n}.sha').read().strip()
items=[
 dict(pid='2122826168005013999',src='search',page='https://nerijs.itch.io/pvfx-foundry',lic='CC0-1.0',proof='https://nerijs.itch.io/pvfx-foundry (License section: sprite sheets and metadata CC0 1.0; LICENSE.txt in zip states CC0 scope)',attr='VFX from PVFX Foundry by Pixel VFX Studio (nerijs) - credit appreciated, not required',typ='sprite sheets / VFX',path='assets/itch/nerijs_pvfx-foundry',notes='itch AI disclosure: AI Assisted (Code, Text). CC0 scope covers effects sprite sheets+manifests only.'),
 dict(pid='2116863413439623537',src='search',page='https://ansimuz.itch.io/super-grotto-escape-pack',lic='CC0-1.0',proof='https://ansimuz.itch.io/super-grotto-escape-pack (Asset license: Creative Commons Zero v1.0 Universal; No generative AI was used)',attr='Artwork by Luis Zuno (@ansimuz) - credit not required',typ='tileset + sprites + music (16x16 pixel art)',path='assets/itch/ansimuz_super-grotto-escape-pack',notes='Windows/Mac demo executables deleted (not assets). Godot project zip included.'),
 dict(pid='2061851663770464395',src='search',page='https://sigilsvault.itch.io/modular-dungeon-kit-v10',lic='CC0-1.0',proof='https://sigilsvault.itch.io/modular-dungeon-kit-v10 (CC0 tag, No generative AI) + LICENSE.txt in zip',attr='Modular Dungeon Kit by SigilsVault (Kevin Barany) - credit appreciated, not required',typ='3D models (GLB/FBX) + textures',path='assets/itch/sigilsvault_modular-dungeon-kit-v10',notes=''),
 dict(pid='2125031654674530559',src='search',page='https://lazyneonstudio.itch.io/neon-pixel-tileset-vol1',lic='CC0-1.0',proof='https://lazyneonstudio.itch.io/neon-pixel-tileset-vol1 + license.txt in zip (CC0 1.0 dedication)',attr='lazy neon studio - credit not required',typ='tileset (16x16 pixel art)',path='assets/ai_generated/itch_lazyneonstudio_neon-pixel-tileset-vol1',notes='AI-GENERATED per author ("100% ai-generated"). Quarantined in assets/ai_generated/; do not use as benchmark ground truth.',ai=True),
 dict(pid='2107976325881323997',src='search',page='https://mustafa-sec.itch.io/godotdialogue-lite',lic='MIT',proof='https://mustafa-sec.itch.io/godotdialogue-lite (Free MIT JSON dialogue for Godot 4) + LICENSE in zip',attr='Copyright (c) 2026 Fortress MSSP LLC, MIT License - keep LICENSE',typ='Godot addon (code)',path='assets/itch/mustafa-sec_godotdialogue-lite',notes=''),
 dict(pid='2110976747886072164',src='search',page='https://github.com/GrokCodeReliant/OpenKit3D',repo='GrokCodeReliant/OpenKit3D',lic='CC0-1.0',proof_gh=True,attr='Open Kit 3D (GrokCodeReliant) - credit not required. Anim clips derived from KayKit (Kay Lousberg) and Quaternius UAL2, both CC0',typ='3D models (FBX), Unity project, 218 prop packs',path='assets/github/GrokCodeReliant_OpenKit3D',notes='LICENSES.md: all CC0, no other third-party material. Repo says built by an AI crew; assets are procedural Blender scripts (PLAN.md says AI mesh tools not used).'),
 dict(pid='2121938456020689010',src='search',page='https://github.com/DylanMartinLSC/amber-pixel64',repo='DylanMartinLSC/amber-pixel64',lic='CC0-1.0 (per-sprite: CC0-1.0, PDM-1.0, Public-Domain, US-Gov-PD)',proof_gh=True,attr='Per-sprite author and source_url columns in parquet; see repo README',typ='pixel-art sprite dataset (102,489 captioned 64x64 PNG in parquet)',path='assets/github/DylanMartinLSC_amber-pixel64',notes='Measured: 102,489 rows; 19,332 rows have Kenney in author/pack (Kenney site sets noai meta) - filter on author column before any training. Captions partly model-written. Pulled from GitHub, not Hugging Face.'),
 dict(pid='2112515947953107455',src='bookmark',page='https://github.com/Hugo-Dz/spritefusion-sprite-normals',repo='Hugo-Dz/spritefusion-sprite-normals',lic='MIT',proof_gh=True,attr='Hugo Duprez / Sprite Fusion, MIT',typ='tool (CLI: normal maps for pixel-art sprites)',path='assets/github/Hugo-Dz_spritefusion-sprite-normals',notes='Bookmarked post is by @hakimieiqbal; repo link was in his reply (t.co/Eht3BL4XSG). Replies in that thread dispute originality of the idea; the repo itself is MIT.'),
 dict(pid='2120020645853753722',src='search',page='https://github.com/kanaworksai-hue/sozai-search-mcp',repo='kanaworksai-hue/sozai-search-mcp',lic='MIT',proof_gh=True,attr='MIT, keep LICENSE',typ='tool (MCP index over CC0 asset sites)',path='assets/github/kanaworksai-hue_sozai-search-mcp',notes='Useful as a source map of CC0 3D libraries (Poly Haven, ambientCG, ...).'),
 dict(pid='2116510551937523878',src='search',page='https://github.com/patch-gg/pixelfx',repo='patch-gg/pixelfx',lic='MIT (code); gallery/fonts excluded (not MIT)',proof_gh=True,attr='Copyright (c) 2026 Patch and Hugo Duprez, MIT; NOTICE.md lists adapted MIT code',typ='code: 244 procedural pixel-art effects + skill',path='assets/github/patch-gg_pixelfx',notes='Removed gallery/fonts per NOTICE.md.'),
 dict(pid='2115871312811794906',src='search',page='https://github.com/reidhannaford/godot-workbench',repo='reidhannaford/godot-workbench',lic='MIT',proof_gh=True,attr='MIT, keep LICENSE',typ='Godot addon (code)',path='assets/github/reidhannaford_godot-workbench',notes=''),
 dict(pid='2103097017073361137',src='bookmark',page='https://github.com/scenario-labs/skills',repo='scenario-labs/skills',lic='MIT',proof_gh=True,attr='scenario-labs, MIT',typ='agent skills for game art/3D pipelines (text)',path='assets/github/scenario-labs_skills',notes='Repo link found in replies to bookmarked post (the "GameDev OS" skill library). Skills need Scenario MCP/account to run; content is just text.'),
 dict(pid='2116953443143500149',src='search',page='https://github.com/arjun988/blender-skills',repo='arjun988/blender-skills',lic='MIT',proof_gh=True,attr='MIT, keep LICENSE',typ='agent skills for Blender (text)',path='assets/github/arjun988_blender-skills',notes=''),
 dict(pid='2108527285179473984',src='search',page='https://github.com/CloudAI-X/threejs-skills',repo='CloudAI-X/threejs-skills',lic='MIT',proof_gh=True,attr='MIT, keep LICENSE',typ='agent skills for three.js (text)',path='assets/github/CloudAI-X_threejs-skills',notes=''),
 dict(pid='2111069465609932877',src='search',page='https://github.com/christoskaramou/RenderLens',repo='christoskaramou/RenderLens',lic='MIT',proof_gh=True,attr='MIT, keep LICENSE; Godot asset library entry 5527 also says MIT',typ='Godot plugin (code)',path='assets/github/christoskaramou_RenderLens',notes=''),
]
if __name__=='__main__':
    rows=[]
    for it in items:
        p=f"{H}/{it['path']}"
        s,n,sz=tree_sha(p)
        proof=it['proof'] if 'proof' in it else GH(it['repo'],sha(it['path'].split('/')[-1]))
        rows.append(dict(x_post_url=purl(it['pid']),author_handle='@'+posts[it['pid']]['username'],asset_page_url=it['page'],licence=it['lic'],licence_proof_url=proof,attribution=it['attr'],asset_type=it['typ'],file_count=n,size_bytes=sz,sha256_tree=s,local_path=p,source=it['src'],ai_generated=bool(it.get('ai')),notes=it['notes']))
    with open(f'{H}/manifest.jsonl','w') as f:
        for r in rows: f.write(json.dumps(r)+'\n')
    with open(f'{H}/manifest.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    tot=sum(r['size_bytes'] for r in rows)
    print(len(rows),tot/1e6,'MB'); 
    for r in rows: print(r['author_handle'],r['asset_type'][:40],r['file_count'],r['size_bytes'],r['sha256_tree'][:10])
