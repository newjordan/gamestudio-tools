#!/usr/bin/env python3
"""asset-viewer: bake a single self-contained HTML file for eyeballing atlases and tile maps offline.

  atlas : atlas.png + atlas.json (from atlas-pack / TexturePacker hash) -> pan/zoom, frame outlines, hover names
  map   : Tiled-style JSON (dungeon-gen / wfc-tiles output) [+ tileset PNG and tile size] -> pan/zoom render,
          coloured tiles when no tileset is given; hover shows tile id and cell
  frames: a folder of PNG frames -> contact grid with names and play button (animation preview)
No server, no network, no dependencies: images are embedded as base64 and the viewer is plain JS.
"""
import argparse, os, base64, io, json, sys
from PIL import Image

HTML = r"""<!doctype html><meta charset=utf-8><title>__TITLE__</title>
<style>html,body{margin:0;height:100%;background:#1e1e22;color:#ddd;font:13px system-ui}#bar{position:fixed;top:0;left:0;right:0;padding:6px 10px;background:#0009;z-index:2}
canvas{display:block;image-rendering:pixelated}button{margin-left:6px}</style>
<div id=bar><b>__TITLE__</b> <span id=info></span> <button id=fit>fit</button><button id=one>1:1</button><button id=play style=display:none>play</button></div>
<canvas id=c></canvas>
<script>
const DATA=__DATA__;
const cv=document.getElementById('c'),ctx=cv.getContext('2d'),info=document.getElementById('info');
let scale=1,ox=0,oy=0,img=null,tileimg=null,anim=0,animT=null;
function resize(){cv.width=innerWidth;cv.height=innerHeight;draw()}
function loadImg(b64){return new Promise(r=>{if(!b64)return r(null);const i=new Image();i.onload=()=>r(i);i.src='data:image/png;base64,'+b64})}
function hue(id){return 'hsl('+(id*47%360)+',55%,'+(35+id*13%35)+'%)'}
function size(){if(DATA.mode==='atlas')return[img.width,img.height];if(DATA.mode==='map')return[DATA.w*DATA.tw,DATA.h*DATA.th];
 const c=DATA.cols,r=Math.ceil(DATA.frames.length/c);return[c*DATA.cell,r*(DATA.cell+14)]}
function fit(){const[w,h]=size();scale=Math.max(0.05,Math.min((cv.width-20)/w,(cv.height-60)/h));ox=(cv.width-w*scale)/2;oy=50;draw()}
function draw(){ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,cv.width,cv.height);ctx.imageSmoothingEnabled=false;ctx.setTransform(scale,0,0,scale,ox,oy);
 if(DATA.mode==='atlas'){ctx.fillStyle='#2a2a30';ctx.fillRect(0,0,img.width,img.height);ctx.drawImage(img,0,0);ctx.lineWidth=1/scale;ctx.strokeStyle='#0f0';
  for(const f of DATA.frames)ctx.strokeRect(f.x+.5/scale,f.y+.5/scale,f.w,f.h)}
 else if(DATA.mode==='map'){const{w,h,tw,th,data,tcols}=DATA;for(let y=0;y<h;y++)for(let x=0;x<w;x++){const id=data[y*w+x];if(!id)continue;
  if(tileimg){const t=id-1;ctx.drawImage(tileimg,(t%tcols)*tw,Math.floor(t/tcols)*th,tw,th,x*tw,y*th,tw,th)}else{ctx.fillStyle=hue(id);ctx.fillRect(x*tw,y*th,tw,th)}}}
 else{const c=DATA.cols,cell=DATA.cell;ctx.font='9px sans-serif';DATA.frames.forEach((f,i)=>{const x=(i%c)*cell,y=Math.floor(i/c)*(cell+14);
  ctx.fillStyle=i===anim&&animT?'#345':'#2a2a30';ctx.fillRect(x+1,y+1,cell-2,cell+12);const k=Math.min(1,(cell-6)/Math.max(f.img.width,f.img.height));
  ctx.drawImage(f.img,x+3,y+3,f.img.width*k,f.img.height*k);ctx.fillStyle='#ccc';ctx.fillText(f.name,x+3,y+cell+8)})}}
cv.onwheel=e=>{e.preventDefault();const k=e.deltaY<0?1.15:1/1.15,mx=e.offsetX,my=e.offsetY;ox=mx-(mx-ox)*k;oy=my-(my-oy)*k;scale*=k;draw()};
let drag=null;cv.onmousedown=e=>drag=[e.clientX-ox,e.clientY-oy];onmouseup=()=>drag=null;
cv.onmousemove=e=>{if(drag){ox=e.clientX-drag[0];oy=e.clientY-drag[1];draw();return}const x=(e.offsetX-ox)/scale,y=(e.offsetY-oy)/scale;
 if(DATA.mode==='atlas'){const f=DATA.frames.find(f=>x>=f.x&&x<f.x+f.w&&y>=f.y&&y<f.y+f.h);info.textContent=f?f.name+' '+f.w+'x'+f.h+' @'+f.x+','+f.y:''}
 else if(DATA.mode==='map'){const cx=Math.floor(x/DATA.tw),cy=Math.floor(y/DATA.th);info.textContent=(cx>=0&&cy>=0&&cx<DATA.w&&cy<DATA.h)?'cell '+cx+','+cy+' tile '+DATA.data[cy*DATA.w+cx]:''}};
document.getElementById('fit').onclick=fit;document.getElementById('one').onclick=()=>{scale=1;ox=10;oy=50;draw()};
(async()=>{img=await loadImg(DATA.image);tileimg=await loadImg(DATA.tileset);
 if(DATA.mode==='frames'){for(const f of DATA.frames)f.img=await loadImg(f.b64);const b=document.getElementById('play');b.style.display='';
  b.onclick=()=>{if(animT){clearInterval(animT);animT=null;b.textContent='play';draw();return}b.textContent='stop';animT=setInterval(()=>{anim=(anim+1)%DATA.frames.length;draw()},1000/DATA.fps)}}
 info.textContent=DATA.mode+' - scroll to zoom, drag to pan';addEventListener('resize',resize);resize();fit()})();
</script>"""


def b64png(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def b64file(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def build(mode, **kw):
    if mode == "atlas":
        meta = json.load(open(kw["json"]))
        frames = [{"name": n, **v["frame"]} for n, v in meta["frames"].items()]
        data = {"mode": "atlas", "image": b64file(kw["image"]), "frames": frames}
        title = os.path.basename(kw["image"])
    elif mode == "map":
        m = json.load(open(kw["json"]))
        layer = next(l for l in m["layers"] if l["type"] == "tilelayer")
        tw, th = kw.get("tile") or (m["tilewidth"], m["tileheight"])
        data = {"mode": "map", "w": layer["width"], "h": layer["height"], "tw": tw, "th": th, "data": layer["data"],
                "tileset": b64file(kw["tileset"]) if kw.get("tileset") else None,
                "tcols": (Image.open(kw["tileset"]).width // tw) if kw.get("tileset") else 0}
        title = os.path.basename(kw["json"])
    else:
        files = sorted(f for f in os.listdir(kw["folder"]) if f.lower().endswith(".png"))
        frames, cell = [], 0
        for f in files:
            im = Image.open(os.path.join(kw["folder"], f)).convert("RGBA")
            cell = max(cell, im.width, im.height)
            frames.append({"name": os.path.splitext(f)[0], "b64": b64png(im)})
        data = {"mode": "frames", "frames": frames, "cell": min(max(cell, 32), 96) + 6, "cols": 8, "fps": kw.get("fps", 10), "image": None}
        title = os.path.basename(os.path.abspath(kw["folder"]))
    return HTML.replace("__TITLE__", title).replace("__DATA__", json.dumps(data))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bake a self-contained HTML viewer.")
    sub = ap.add_subparsers(dest="mode", required=True)
    a1 = sub.add_parser("atlas"); a1.add_argument("image"); a1.add_argument("json")
    a2 = sub.add_parser("map"); a2.add_argument("json"); a2.add_argument("--tileset"); a2.add_argument("--tile", help="WxH")
    a3 = sub.add_parser("frames"); a3.add_argument("folder"); a3.add_argument("--fps", type=int, default=10)
    for s in (a1, a2, a3):
        s.add_argument("-o", "--out", required=True)
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    # refuse dest == input unless --in-place
    def _paths(v):
        if not v:
            return []
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                out.extend(_paths(x))
            return out
        return [v]
    _srcs, _dsts = [], []
    _src_keys = ('image', 'folder', 'json')
    for _k in _src_keys:
        if hasattr(a, _k):
            _srcs.extend(_paths(getattr(a, _k)))
    for _k in ('out', 'outdir', 'output', 'dest', 'json_report', 'report', 'preview', 'out_csv', 'map_out', 'json', 'cues', 'cues_json'):
        if _k in _src_keys:
            continue
        if hasattr(a, _k) and getattr(a, _k):
            _d = getattr(a, _k)
            _dsts.extend(_paths(_d))
    for _s in _srcs:
        for _d in _dsts:
            if _s and _d and os.path.abspath(str(_s)) == os.path.abspath(str(_d)) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different output path or pass --in-place")

    kw = {k: v for k, v in vars(a).items() if k not in ("mode", "out")}
    if a.mode == "map" and a.tile:
        kw["tile"] = tuple(int(v) for v in a.tile.lower().split("x"))
    html = build(a.mode, **kw)
    open(a.out, "w", encoding="utf-8").write(html)
    print(f"wrote {a.out} ({len(html) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
