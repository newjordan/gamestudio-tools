# glTF strip, rename, pivot, material audit

Convert a small OBJ (optional), strip unused extras, rename nodes, move the pivot to the bounding-box
centre (or feet), and audit materials / texture slots.

## Tools

obj-split → obj-merge → obj-triangulate → obj-subdivide → obj-decimate → obj-drop-unused → obj-flip → obj-validate → obj-clean-uv → obj-normals → obj-bounds → obj-to-glb → gltf-strip → glb-extras-strip → glb-weld → glb-quantize → glb-attr-drop → glb-attr-rename → glb-rename-nodes → mesh-pivot-fix / glb-center → glb-uv-transform → material-audit → glb-split

## Commands

```bash
mkdir -p /tmp/pipe-gltf
# optional: gst obj-split samples/pipelines/mesh/prop.obj -o /tmp/pipe-gltf/parts --by o
gst obj-triangulate samples/pipelines/mesh/prop.obj -o /tmp/pipe-gltf/prop_tri.obj
# optional: gst obj-subdivide /tmp/pipe-gltf/prop_tri.obj -o /tmp/pipe-gltf/prop_sub.obj --times 1
# optional: gst obj-decimate /tmp/pipe-gltf/prop_tri.obj -o /tmp/pipe-gltf/prop_lod.obj --ratio 0.5
gst obj-normals /tmp/pipe-gltf/prop_tri.obj -o /tmp/pipe-gltf/prop_n.obj --mode smooth
gst obj-bounds /tmp/pipe-gltf/prop_n.obj -o /tmp/pipe-gltf/bounds.json
gst obj-to-glb /tmp/pipe-gltf/prop_n.obj -o /tmp/pipe-gltf
gst gltf-strip /tmp/pipe-gltf/prop_n.glb -o /tmp/pipe-gltf/strip.glb --drop-extras
gst glb-rename-nodes /tmp/pipe-gltf/strip.glb -o /tmp/pipe-gltf/named.glb --prefix Prop_
gst glb-weld /tmp/pipe-gltf/named.glb -o /tmp/pipe-gltf/weld.glb
# optional: gst obj-flip /tmp/pipe-gltf/prop_tri.obj -o /tmp/pipe-gltf/prop_flip.obj --axis x
# optional: gst obj-validate /tmp/pipe-gltf/prop_tri.obj --json /tmp/pipe-gltf/val.json
# optional: gst glb-quantize /tmp/pipe-gltf/weld.glb -o /tmp/pipe-gltf/q.glb --digits 4
# optional: gst obj-clean-uv mesh.obj -o /tmp/pipe-gltf/mesh_uv.obj --clamp --weld 0.0001
# optional: gst glb-attr-drop /tmp/pipe-gltf/q.glb -o /tmp/pipe-gltf/slim.glb --drop NORMAL
# optional: gst glb-attr-rename /tmp/pipe-gltf/slim.glb -o /tmp/pipe-gltf/renamed.glb --map TEXCOORD_0=TEXCOORD_1
# optional: gst obj-drop-unused mesh.obj -o /tmp/pipe-gltf/mesh_tight.obj
# optional: gst glb-extras-strip /tmp/pipe-gltf/renamed.glb -o /tmp/pipe-gltf/noextras.glb
gst glb-center /tmp/pipe-gltf/weld.glb -o /tmp/pipe-gltf/pivot.glb --mode center
# (mesh-pivot-fix --mode bottom remains the feet-pivot option)
gst material-audit /tmp/pipe-gltf/pivot.glb --json /tmp/pipe-gltf/audit.json
gst glb-split /tmp/pipe-gltf/pivot.glb -o /tmp/pipe-gltf/parts --by mesh
```

OBJ-only recentering (keeping `usemtl` / groups) is `obj-recenter`. Node remames leave skin and
animation channel *indices* intact.

## Known gaps

A file with skins may need the same shift applied to joints (mesh-pivot-fix warns). material-audit
`--fail-on-missing` exits 1 when an external texture URI is absent; embedded images count as present.
