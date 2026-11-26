. "$(dirname "$0")/_common.sh"
python3 - <<'PY'
from PIL import Image; import json
im=Image.new("RGBA",(8,8),(0,0,0,0)); [im.putpixel((x,y),(255,0,0,255)) for x in range(6) for y in range(4)]; im.save("a.png")
json.dump({"frames":{"run_0.png":{"frame":{"x":0,"y":0,"w":6,"h":4},"rotated":False,"trimmed":True,
 "spriteSourceSize":{"x":5,"y":9,"w":6,"h":4},"sourceSize":{"w":16,"h":16}}},"meta":{"image":"a.png","size":{"w":8,"h":8}}},open("a.json","w"))
PY
gst atlas-to-godot a.json -o f.tres --res res://a.png
grep -A3 'sub_resource type="AtlasTexture"' f.tres
