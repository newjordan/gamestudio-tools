. "$(dirname "$0")/_common.sh"
mkdir -p p/art p/ui p/i18n; cd p
printf 'config_version=5\n[application]\nrun/main_scene="res://main.tscn"\nconfig/icon="res://art/icon.png"\n[autoload]\nGame="*res://game.gd"\n[internationalization]\nlocale/translations=PackedStringArray("res://i18n/s.en.translation")\n' > project.godot
printf '[gd_scene format=3]\n[ext_resource type="Theme" path="res://ui/theme.tres" id="1"]\n[node name="M" type="Node"]\n' > main.tscn
printf '[gd_resource type="Theme" format=3]\n[ext_resource type="FontFile" path="res://ui/f.fnt" id="1"]\n[resource]\n' > ui/theme.tres
printf 'info face="x" size=11\ncommon lineHeight=13 base=10 scaleW=64 scaleH=64 pages=1\npage id=0 file="f.png"\nchars count=0\n' > ui/f.fnt
python3 -c 'from PIL import Image;[Image.new("RGBA",(2,2)).save(p) for p in ("art/icon.png","ui/f.png","art/orphan.png")]'
printf 'extends Node\n' > game.gd; printf 'RSRC' > i18n/s.en.translation
cd ..; gst asset-unused p --json unused.json
python3 -c 'import json;print("unused:",json.load(open("unused.json"))["unused"])'
