. "$(dirname "$0")/_common.sh"
gst dungeon-gen --mode bsp --size 34x22 --seed 701 -o f1
python3 -c 'import json;m=json.load(open("f1.json"));print("tilesets:",json.dumps(m.get("tilesets"))[:100]);print("layers:",[l["name"] for l in m["layers"]])'
gst map-to-godot f1.json -o f1.tscn --write-tileset f1_ts.tres
gst map-reach f1.json --start 4,2 --solid-ids 2 --json reach.json
gst map-reach f1.json --start 4,2 --json reach_nosolid.json
