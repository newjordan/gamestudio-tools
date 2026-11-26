. "$(dirname "$0")/_common.sh"
mkdir fr; python3 -c '
from PIL import Image
for c in ("walk-down","walk-up","idle"):
  for i in range(2): Image.new("RGBA",(4,4),(9,9,9,255)).save("fr/%s_%d.png"%(c,i))'
gst anim-from-folder fr -o clips.json --pattern '{clip}_{frame}.png' --default-fps 8 --fps 'walk-*=10' --fps idle=4 --once 'idl*'
python3 -c 'import json;c=json.load(open("clips.json"))["clips"];[print(k,"fps=%s loop=%s"%(v["fps"],v["loop"])) for k,v in sorted(c.items())]'
