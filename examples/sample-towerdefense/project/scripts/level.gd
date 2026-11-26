extends Node2D
## Fixed-step combat. The order matches src/sim.py: place, spawn, shoot, move.
## Creeps follow curve-gen samples. NavigationServer2D is probed, not used to walk,
## so the run stays identical to the Python sim. A failed probe still fails autoplay.

const STEP := 1.0 / 60.0
const KINDS: Array[String] = ["arrow", "frost", "mortar"]

var combat: Dictionary
var samples: Array
var length: float
var tile: int
var towers_def: Dictionary
var creeps_def: Dictionary
var build: Array
var events: Array
var map: Dictionary
var gold: int
var core: int
var leaks := 0
var kills := 0
var wave := 0
var frame := 0
var event_i := 0
var next_id := 1
var towers: Array = []
var creeps: Array = []
var puffs: Array = []
var occupied := {}
var selected := 0
var paused := false
var done := false
var nav_ok := false
var nav_checked := false
var nav_map: RID
var creep_frames: SpriteFrames
var tower_frames: SpriteFrames
var puff_frames: SpriteFrames
var hud: CanvasLayer


func _ready() -> void:
	name = "Level"
	combat = _json("res://data/combat.json")
	var route: Dictionary = _json("res://data/route.json")
	var rules: Dictionary = _json("res://data/rules.json")
	map = _json("res://levels/causeway.json")
	# data-to-godot tables stay loaded so the resources are referenced
	var table: Resource = load("res://data/towers.tres")
	load("res://data/creeps.tres")
	load("res://data/waves.tres")
	load("res://data/build.tres")
	samples = route["samples"]
	length = float(route["length"])
	tile = int(combat["tile"])
	towers_def = combat["towers"]
	creeps_def = combat["creeps"]
	build = combat["build"]
	events = combat["events"]
	gold = int(combat["gold"])
	core = int(combat["core"])
	Game.run_seed = int(rules["seed"])
	creep_frames = load("res://art/creeps_frames.tres")
	tower_frames = load("res://art/towers_frames.tres")
	puff_frames = load("res://art/puff_frames.tres")
	add_child(load("res://levels/causeway_tiles.tscn").instantiate())
	add_child(load("res://levels/causeway_solid.tscn").instantiate())
	add_child(load("res://levels/causeway_nav.tscn").instantiate())
	var objects: Node = load("res://levels/causeway_objects.tscn").instantiate()
	objects.visible = false
	add_child(objects)
	nav_map = get_world_2d().navigation_map
	hud = preload("res://scripts/hud.gd").new()
	add_child(hud)
	_refresh_hud()
	print("TD_LEVEL towers=%d events=%d length=%.1f rows=%d" % [
		build.size(), events.size(), length, table.rows.size()])


func _json(path: String):
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("missing " + path)
		return {}
	var data = JSON.parse_string(f.get_as_text())
	f.close()
	return data


func _physics_process(_delta: float) -> void:
	if done:
		return
	if paused and not Game.autoplay:
		return
	if not nav_checked:
		_try_nav()
	_step()


func _try_nav() -> void:
	if frame < 8:
		return
	var start := _sample_pos(0)
	var goal := _sample_pos(samples.size() - 1)
	var pts := NavigationServer2D.map_get_path(nav_map, start, goal, true)
	var reached := pts.size() >= 2 and pts[pts.size() - 1].distance_to(goal) < 8.0
	if reached:
		nav_ok = true
		nav_checked = true
		print("NAV_OK points=%d" % pts.size())
	elif frame >= 30:
		nav_checked = true
		print("NAV_FAIL points=%d" % pts.size())


func _sample_pos(i: int) -> Vector2:
	var p: Array = samples[i]["p"]
	return Vector2(float(p[0]), float(p[1]))


func point_at(dist: float) -> Vector2:
	var origin: Array = samples[0]["p"]
	if dist <= float(samples[0]["s"]):
		return Vector2(float(origin[0]), float(origin[1]))
	for i in range(1, samples.size()):
		var s1 := float(samples[i]["s"])
		if dist <= s1:
			var s0 := float(samples[i - 1]["s"])
			var p0: Array = samples[i - 1]["p"]
			var p1: Array = samples[i]["p"]
			var u := 0.0 if s1 == s0 else (dist - s0) / (s1 - s0)
			return Vector2(
				float(p0[0]) + (float(p1[0]) - float(p0[0])) * u,
				float(p0[1]) + (float(p1[1]) - float(p0[1])) * u)
	var last: Array = samples[samples.size() - 1]["p"]
	return Vector2(float(last[0]), float(last[1]))


func _step() -> void:
	_place_queue()
	_spawn()
	_shoot()
	_move()
	_fade_puffs()
	frame += 1
	_refresh_hud()
	var built := 0
	for row in build:
		if row.get("placed", false):
			built += 1
	var cleared := event_i >= events.size() and creeps.is_empty()
	if core <= 0 or cleared or frame > 60 * 90:
		var win := core > 0 and leaks == 0 and kills == events.size() and built == build.size() and creeps.is_empty() and nav_ok
		_finish(win, built)


func _place_queue() -> void:
	if not Game.autoplay:
		return
	for row in build:
		if row.get("placed", false):
			continue
		var kind: String = str(row["kind"])
		var spec: Dictionary = towers_def[kind]
		var cost := int(spec["cost"])
		if gold < cost:
			continue
		gold -= cost
		row["placed"] = true
		_add_tower(kind, int(row["x"]), int(row["y"]), spec)


func _add_tower(kind: String, tx: int, ty: int, spec: Dictionary) -> void:
	var pos := Vector2((tx + 0.5) * tile, (ty + 0.5) * tile)
	var spr := AnimatedSprite2D.new()
	spr.sprite_frames = tower_frames
	spr.play(kind)
	spr.position = pos
	spr.z_index = 1
	add_child(spr)
	towers.append({
		"kind": kind, "pos": pos, "range": float(spec["range"]), "dmg": int(spec["dmg"]),
		"cd": float(spec["cd"]), "cool": 0.0, "slow": float(spec["slow"]),
		"slow_time": float(spec["slow_time"]), "splash": float(spec["splash"]), "spr": spr,
	})
	occupied["%d,%d" % [tx, ty]] = true
	print("TD_PLACE %s %d,%d gold=%d" % [kind, tx, ty, gold])
	Game.play("place")


func _spawn() -> void:
	while event_i < events.size() and int(events[event_i]["step"]) <= frame:
		var event: Dictionary = events[event_i]
		event_i += 1
		var kind: String = str(event["kind"])
		var spec: Dictionary = creeps_def[kind]
		var pos := point_at(0.0)
		var spr := AnimatedSprite2D.new()
		spr.sprite_frames = creep_frames
		spr.play(kind)
		spr.position = pos
		spr.z_index = 2
		add_child(spr)
		creeps.append({
			"id": next_id, "kind": kind, "hp": int(spec["hp"]), "speed": float(spec["speed"]),
			"gold": int(spec["gold"]), "leak": int(spec["leak"]), "dist": 0.0,
			"slow": 1.0, "slow_left": 0.0, "pos": pos, "spr": spr,
		})
		next_id += 1
		var w := int(event["wave"])
		if w != wave:
			wave = w
			print("TD_WAVE %d" % wave)
			Game.play("wave")


func _shoot() -> void:
	for tw in towers:
		tw["cool"] = float(tw["cool"]) - STEP
		if float(tw["cool"]) > 0.0:
			continue
		var target := _pick(tw)
		if target.is_empty():
			continue
		var victims: Array = [target]
		if float(tw["splash"]) > 0.0:
			victims = []
			var splash2 := float(tw["splash"]) * float(tw["splash"])
			var tp: Vector2 = target["pos"]
			for creep in creeps:
				if int(creep["hp"]) <= 0:
					continue
				if _dist2(creep["pos"], tp) <= splash2:
					victims.append(creep)
		for victim in victims:
			victim["hp"] = int(victim["hp"]) - int(tw["dmg"])
			if float(tw["slow"]) < 1.0:
				victim["slow"] = float(tw["slow"])
				victim["slow_left"] = float(tw["slow_time"])
		tw["cool"] = float(tw["cd"])
		Game.play("shoot")


func _pick(tw: Dictionary) -> Dictionary:
	var best: Dictionary = {}
	var reach2 := float(tw["range"]) * float(tw["range"])
	var origin: Vector2 = tw["pos"]
	for creep in creeps:
		if int(creep["hp"]) <= 0:
			continue
		if _dist2(creep["pos"], origin) > reach2:
			continue
		if best.is_empty() or float(creep["dist"]) > float(best["dist"]) or (
				float(creep["dist"]) == float(best["dist"]) and int(creep["id"]) < int(best["id"])):
			best = creep
	return best


func _dist2(a: Vector2, b: Vector2) -> float:
	var d := a - b
	return d.x * d.x + d.y * d.y


func _move() -> void:
	var alive: Array = []
	for creep in creeps:
		if int(creep["hp"]) <= 0:
			gold += int(creep["gold"])
			kills += 1
			_burst(creep["pos"])
			_free_creep(creep)
			Game.play("death")
			print("TD_KILL %d" % int(creep["id"]))
			continue
		if float(creep["slow_left"]) > 0.0:
			creep["slow_left"] = float(creep["slow_left"]) - STEP
			if float(creep["slow_left"]) <= 0.0:
				creep["slow"] = 1.0
				creep["slow_left"] = 0.0
		var prev: float = creep["pos"].x
		creep["dist"] = float(creep["dist"]) + float(creep["speed"]) * float(creep["slow"]) * STEP
		if float(creep["dist"]) >= length:
			leaks += 1
			core -= int(creep["leak"])
			_free_creep(creep)
			Game.play("leak")
			print("TD_LEAK id=%d core=%d" % [int(creep["id"]), core])
			continue
		creep["pos"] = point_at(float(creep["dist"]))
		var spr: AnimatedSprite2D = creep["spr"]
		spr.position = creep["pos"]
		if creep["pos"].x < prev - 0.01:
			spr.flip_h = true
		elif creep["pos"].x > prev + 0.01:
			spr.flip_h = false
		alive.append(creep)
	creeps = alive


func _burst(pos: Vector2) -> void:
	var spr := AnimatedSprite2D.new()
	spr.sprite_frames = puff_frames
	spr.play("puff")
	spr.position = pos
	spr.z_index = 3
	add_child(spr)
	puffs.append({"spr": spr, "life": 0.45})


func _fade_puffs() -> void:
	var kept: Array = []
	for puff in puffs:
		puff["life"] = float(puff["life"]) - STEP
		if float(puff["life"]) <= 0.0:
			(puff["spr"] as AnimatedSprite2D).queue_free()
		else:
			kept.append(puff)
	puffs = kept


func _free_creep(creep: Dictionary) -> void:
	(creep["spr"] as AnimatedSprite2D).queue_free()


func _refresh_hud() -> void:
	if hud:
		hud.refresh(gold, core, wave, KINDS[selected], paused)


func _finish(win: bool, built: int) -> void:
	if done:
		return
	done = true
	print("TD_END nav=%s core=%d leaks=%d kills=%d gold=%d towers=%d frames=%d" % [
		nav_ok, core, leaks, kills, gold, built, frame])
	if win:
		Game.save_win({
			"seed": Game.run_seed, "waves": 4, "core": core, "gold": gold,
			"leaks": leaks, "towers": built, "kills": kills, "time": frame * STEP,
		})
		print("TD_WIN core=%d leaks=%d kills=%d gold=%d towers=%d frames=%d" % [core, leaks, kills, gold, built, frame])
		call_deferred("_go", "res://scenes/win.tscn")
	else:
		print("TD_FAIL core=%d leaks=%d kills=%d towers=%d nav=%s" % [core, leaks, kills, built, nav_ok])
		call_deferred("_go", "res://scenes/lose.tscn")


func _go(path: String) -> void:
	get_tree().change_scene_to_file(path)


func _unhandled_input(event: InputEvent) -> void:
	if done:
		return
	if event.is_action_pressed("pause"):
		paused = not paused
		_refresh_hud()
	elif event.is_action_pressed("toggle_language"):
		Game.cycle_locale()
		Game.play("blip")
		_refresh_hud()
	elif event.is_action_pressed("select_next") and not Game.autoplay:
		selected = (selected + 1) % KINDS.size()
		Game.play("blip")
		_refresh_hud()
	elif event.is_action_pressed("place") and not Game.autoplay:
		var cell := _mouse_cell()
		_try_human(cell.x, cell.y)
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT and not Game.autoplay:
		var cell := _mouse_cell()
		_try_human(cell.x, cell.y)


func _mouse_cell() -> Vector2i:
	var p := get_global_mouse_position()
	return Vector2i(int(p.x / tile), int(p.y / tile))


func _try_human(tx: int, ty: int) -> void:
	if tx < 0 or ty < 0 or tx >= int(map["width"]) or ty >= int(map["height"]):
		return
	if occupied.has("%d,%d" % [tx, ty]):
		return
	if _cell_gid("ground", tx, ty) != 1 or _cell_gid("path", tx, ty) != 0:
		return
	var kind: String = KINDS[selected]
	var spec: Dictionary = towers_def[kind]
	var cost := int(spec["cost"])
	if gold < cost:
		return
	gold -= cost
	_add_tower(kind, tx, ty, spec)


func _cell_gid(layer_name: String, tx: int, ty: int) -> int:
	for layer in map["layers"]:
		if layer["name"] == layer_name and str(layer.get("type", "")) == "tilelayer":
			var data: Array = layer["data"]
			return int(data[ty * int(map["width"]) + tx]) & 0x1FFFFFFF
	return -1
