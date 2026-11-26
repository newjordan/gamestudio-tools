import json,os,csv
H='/workspace/gamedata-work/x_harvest'
R=json.load(open(f'{H}/r3/repos.json'))
game_code={'sprite-stack-engine','sprite-stack-animation','sprite-stacking','hexbreach','lanternfall','pine-hollow','sled-free','sled-free-exact','fog-demo','codevember','zombie-sim','genetic-walker','voxeldemo9000','3DParticlePlasmaTerrain','pointplanets','game-off-2012','chip8','jest','ribbitsmash','box','Javascript-Canvas-Terrain-Generator','JQuery-Snowfall','burstfx','slimey-web-component','demos-and-deviations','atari7800dev','AtariRomDisplay','Android-Forest-LWP','llm-lan-party','Local-AI-Game-Assistant','canvas-image-filters','canvasfilters','oilpaint-filter','ambient-sound-visualizer','pixi.js','abuse','tiny-lm','visual-llm','gamecode','VitaTester','soul-sacrifice-preservation','LSPK-Extracter','static-img','web-screensavers','html5-animation','3DParticlePlasmaTerrain'}
tools={'soul-sacrifice-preservation','LSPK-Extracter','Recordio','govee-light-control','comfyui-workflows','atari7800dev','7800bas-syntax-highlighting','AtariRomDisplay','chip8'}
llm={'llm-test-pages','llm-website-demos','qwen-data-set','model-compare','qwen3-8-27b-vs-deepseek-v4-flash','prompt-blocks','grok-heavy-test','qwen38-flash-next-vllm-3090-recipe','glm53-flash-llamacpp-3090-recipe','yue2-fp16-turing','multigpu-p2p-tweaks','project-maya','delta-moe','agent-skills','my-claude-plugins','agent-work','Browser-AI','Bookmark-Curator','GPT-OSS-20b-TAKE-THE-WHEEL','Qwen3Guard','smol-course','chatterbox','TRELLIS-for-windows','Auto-Claude','hermes-agent','page-agent','github-mcp-server','openwebui-vector-prune','Audio-transcribe-server','taskllama','linkedIn_auto_jobs_applier_with_AI','ToMoE'}
def cat(n):
    if n in llm: return 'AI/LLM tooling or LLM-test output (not game dev)'
    if n in {'sprite-stacking','sprite-stack-animation','sprite-stack-engine'}: return 'game code + tutorial/prompt recipe + sample art (sprite stacking)'
    if n in {'hexbreach','lanternfall','pine-hollow','sled-free','sled-free-exact','fog-demo','codevember','zombie-sim','genetic-walker','voxeldemo9000','game-off-2012','ribbitsmash','jest','box','3DParticlePlasmaTerrain','pointplanets','Javascript-Canvas-Terrain-Generator','llm-lan-party','Local-AI-Game-Assistant','Android-Forest-LWP','pixi.js','abuse','VitaTester','JQuery-Snowfall','burstfx','slimey-web-component','tiny-lm','visual-llm','static-img','canvas-image-filters','canvasfilters','oilpaint-filter','ambient-sound-visualizer','demos-and-deviations','web-screensavers','html5-animation','chip8'}: return 'game/graphics code or demo'
    if n in {'atari7800dev','AtariRomDisplay','7800bas-syntax-highlighting','LSPK-Extracter','soul-sacrifice-preservation'}: return 'tools (retro/modding)'
    return 'other (web/React/blog/AoC/misc)'
inc={}
for d,lab in [('assets/github_loktar','assets'),('reference/loktar00','reference')]:
    p=f'{H}/{d}'
    if os.path.isdir(p):
        for n in os.listdir(p):
            if os.path.isdir(f'{p}/{n}'): inc[n]=(lab,d)
rows=[]
for r in R:
    n=r['name']; lab=inc.get(n)
    if lab: dec=f"included ({lab[0]}) at {lab[1]}/{n}"
    elif r['fork']: dec='skipped: fork of someone else\'s repo'
    elif n in llm: dec='skipped: LLM/AI tooling or very large LLM-test output, not game dev reference'
    elif r['kb']>200000: dec='skipped: very large (>200 MB)'
    elif n=='soul-sacrifice-preservation': dec='skipped: modding toolkit for a commercial game'
    elif n=='abuse': dec='skipped: fork'
    elif r['kb']==0: dec='skipped: empty'
    else: dec='skipped: not game dev (web/React/blog/AoC/misc)'
    rows.append(dict(name=n,url=r['url'],description=r['desc'] or '',licence=r['lic'] or 'none',stars=r['stars'],last_push=r['pushed'],size_mb=round(r['kb']/1024,1),fork=r['fork'],language=r['lang'] or '',category=cat(n),decision=dec))
rows.sort(key=lambda x:-x['stars'])
with open(f'{H}/loktar00_repo_inventory.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
import collections
print(len(rows),collections.Counter(r['decision'].split(' (')[0].split(':')[0]+':'+r['decision'].split(':')[-1][:30] if r['decision'].startswith('skipped') else 'included' for r in rows))
