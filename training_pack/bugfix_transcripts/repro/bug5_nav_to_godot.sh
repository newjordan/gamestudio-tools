# needs GODOT_BIN (Godot 4.7+) for the path query
. "$(dirname "$0")/_common.sh"
mkdir p; printf 'config_version=5\n[navigation]\nworld/map_use_async_iterations=false\n' > p/project.godot
# 4x4 map, gid 1 floor / 2 wall: a 4-tile strip on row 0 and a corridor down column 0 (a T-junction at x=16,y=16)
python3 -c '
import json
d=[1,1,1,1, 1,2,2,2, 1,2,2,2, 1,2,2,2]
json.dump({"width":4,"height":4,"tilewidth":16,"tileheight":16,"orientation":"orthogonal","type":"map","infinite":False,
 "tilesets":[{"firstgid":1,"name":"t","tilecount":2,"columns":2,"tilewidth":16,"tileheight":16,"image":"t.png","imagewidth":32,"imageheight":16}],
 "layers":[{"id":1,"name":"g","type":"tilelayer","width":4,"height":4,"x":0,"y":0,"opacity":1,"visible":True,"data":d}]},open("m.json","w"))'
gst nav-to-godot m.json -o p/nav.tscn --solid-ids 2
grep -E '^(vertices|polygons)' p/nav.tscn | cut -c1-160
printf 'extends SceneTree\nfunc _initialize():\n\troot.add_child(load("res://nav.tscn").instantiate())\n\tfor i in 4:\n\t\tawait physics_frame\n\tvar m = root.get_world_2d().navigation_map\n\tvar p = NavigationServer2D.map_get_path(m, Vector2(56, 8), Vector2(8, 56), true)\n\tprint("path from (56,8) to (8,56) ends at %%s" %% [p[p.size() - 1] if p.size() else Vector2(-1, -1)])\n\tquit()\n' > p/t.gd
export HOME="$T/h" XDG_CONFIG_HOME="$T/h/c" XDG_DATA_HOME="$T/h/d" XDG_CACHE_HOME="$T/h/k"; mkdir -p "$HOME"
"$GODOT_BIN" --headless --path p --import --quit >/dev/null 2>&1
"$GODOT_BIN" --headless --path p -s t.gd 2>&1 | grep "path from"
