extends Node
## Ember Crypt run state, data tables, save/load, audio and the autoplay switches.
## Data comes from gst: res://data/enemies.tres (data-to-godot), res://data/loot.json
## (drop-sim checked), res://i18n/*.translation (loc-to-godot), res://audio (sfx-gen family).

const SAVE_VERSION := 1
const LEVELS := ["floor1", "floor2", "boss"]
## literal paths so gst asset-unused / godot-res-lint can see every sound
const SFX := {
	"swing": "res://audio/sfx/swing.wav",
	"hit_0": "res://audio/sfx/hit_0.wav",
	"hit_1": "res://audio/sfx/hit_1.wav",
	"hit_2": "res://audio/sfx/hit_2.wav",
	"hurt": "res://audio/sfx/hurt.wav",
	"coin": "res://audio/sfx/coin.wav",
	"pickup": "res://audio/sfx/pickup.wav",
	"shoot": "res://audio/sfx/shoot.wav",
	"death": "res://audio/sfx/death.wav",
	"roar": "res://audio/sfx/roar.wav",
	"stairs": "res://audio/sfx/stairs.wav",
	"blip": "res://audio/sfx/blip.wav",
}

var autoplay := false
var timeout := 150.0
var run_seed := 7
var save_path := "user://ember_save.json"
var floor := 1
var hp := 6
var max_hp := 6
var coins := 0
var has_key := false
var run_time := 0.0
var stats := {}
var loot := {}
var rng := RandomNumberGenerator.new()
var music: AudioStreamPlayer
var _sfx := {}
var _players: Array[AudioStreamPlayer] = []
var _elapsed := 0.0
var _locales := ["en", "de", "fr"]


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var locale := "en"
	for a in OS.get_cmdline_user_args():
		if a == "--autoplay":
			autoplay = true
		elif a.begins_with("--locale="):
			locale = a.get_slice("=", 1)
		elif a.begins_with("--timeout="):
			timeout = float(a.get_slice("=", 1))
		elif a.begins_with("--save="):
			save_path = a.get_slice("=", 1)
	TranslationServer.set_locale(locale)
	var table: Resource = load("res://data/enemies.tres")
	for row in table.rows:
		stats[row["id"]] = row
	var f := FileAccess.open("res://data/loot.json", FileAccess.READ)
	loot = JSON.parse_string(f.get_as_text())["tables"]
	for s in SFX:
		_sfx[s] = load(SFX[s])
	for i in 8:
		var p := AudioStreamPlayer.new()
		add_child(p)
		_players.append(p)
	music = AudioStreamPlayer.new()
	music.stream = load("res://audio/music.wav")
	music.volume_db = -6.0
	add_child(music)
	music.play()
	if autoplay and FileAccess.file_exists(save_path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(save_path))
	var parts := []
	for l in _locales:
		TranslationServer.set_locale(l)
		parts.append("%s=%s|%s" % [l, tr("title_name"), tr("hud_key")])
	TranslationServer.set_locale(locale)
	print("TOPDOWN_BOOT seed=%d locale=%s enemies=%d loot=%d music_loop=%d %s" % [
		run_seed, locale, stats.size(), loot.size(), (music.stream as AudioStreamWAV).loop_mode, " ".join(parts)])


func _process(delta: float) -> void:
	_elapsed += delta
	if get_tree().current_scene and get_tree().current_scene.name == "Level":
		run_time += delta
	if autoplay and _elapsed > timeout:
		print("TOPDOWN_FAIL timeout at %.1fs floor=%d" % [_elapsed, floor])
		shutdown(1)


func elapsed() -> float:
	return _elapsed


func shutdown(code := 0) -> void:
	## Stop and drop every stream first so nothing is still playing (in use) at exit.
	set_process(false)
	music.stop()
	music.stream = null
	for p in _players:
		p.stop()
		p.stream = null
	_sfx.clear()
	OS.delay_msec(250)
	get_tree().quit(code)


func play(name: String, pitch := 1.0) -> void:
	if not _sfx.has(name):
		return
	for p in _players:
		if not p.playing:
			p.stream = _sfx[name]
			p.pitch_scale = pitch
			p.play()
			return


func cycle_locale() -> String:
	var i := (_locales.find(TranslationServer.get_locale().substr(0, 2)) + 1) % _locales.size()
	TranslationServer.set_locale(_locales[i])
	return _locales[i]


func new_run() -> void:
	floor = 1
	hp = max_hp
	coins = 0
	has_key = false
	run_time = 0.0
	rng.seed = run_seed * 1000
	get_tree().change_scene_to_file("res://scenes/level.tscn")


func level_name() -> String:
	return LEVELS[clampi(floor - 1, 0, LEVELS.size() - 1)]


func roll_drop(table_name: String) -> Dictionary:
	## Same table semantics as gst drop-sim: weighted entries, guaranteed items.
	var out := {}
	var t: Dictionary = loot[table_name]
	for g in t.get("guaranteed", []):
		out[g["item"]] = out.get(g["item"], 0) + int(g.get("count", 1))
	var total := 0.0
	for e in t["entries"]:
		total += float(e.get("weight", 1))
	var r := rng.randf() * total
	for e in t["entries"]:
		r -= float(e.get("weight", 1))
		if r <= 0.0:
			if e.has("item") and not e.get("nothing", false):
				var lo := int(e.get("min", 1))
				var hi := int(e.get("max", lo))
				out[e["item"]] = out.get(e["item"], 0) + rng.randi_range(lo, hi)
			break
	return out


func save_dict() -> Dictionary:
	return {"version": SAVE_VERSION, "seed": run_seed, "floor": floor, "hp": hp, "max_hp": max_hp,
		"coins": coins, "locale": TranslationServer.get_locale().substr(0, 2), "time": snappedf(run_time, 0.01)}


func save_game() -> bool:
	## A JSON list with one object, so gst game-data-lint can check the file the game wrote.
	var f := FileAccess.open(save_path, FileAccess.WRITE)
	if f == null:
		return false
	f.store_string(JSON.stringify([save_dict()], " "))
	f.close()
	print("SAVE_OK floor=%d hp=%d coins=%d path=%s" % [floor, hp, coins, ProjectSettings.globalize_path(save_path)])
	return true


func has_save() -> bool:
	return FileAccess.file_exists(save_path)


func load_game() -> bool:
	if not has_save():
		return false
	var data = JSON.parse_string(FileAccess.get_file_as_string(save_path))
	if typeof(data) != TYPE_ARRAY or data.is_empty() or int(data[0].get("version", 0)) != SAVE_VERSION:
		print("LOAD_FAIL bad save")
		return false
	var d: Dictionary = data[0]
	run_seed = int(d["seed"])
	floor = int(d["floor"])
	hp = int(d["hp"])
	max_hp = int(d["max_hp"])
	coins = int(d["coins"])
	run_time = float(d["time"])
	TranslationServer.set_locale(String(d["locale"]))
	has_key = false
	rng.seed = run_seed * 1000 + floor
	print("LOAD_OK floor=%d hp=%d coins=%d locale=%s" % [floor, hp, coins, d["locale"]])
	return true


func continue_run() -> void:
	if load_game():
		get_tree().change_scene_to_file("res://scenes/level.tscn")


func floor_cleared() -> void:
	floor += 1
	has_key = false
	if floor > LEVELS.size():
		print("TOPDOWN_WIN time=%.1f coins=%d hp=%d" % [run_time, coins, hp])
		get_tree().change_scene_to_file("res://scenes/win.tscn")
		return
	save_game()
	continue_run()


func player_died() -> void:
	print("TOPDOWN_RETRY floor=%d" % floor)
	hp = max_hp
	if has_save():
		continue_run()
	else:
		new_run()


func _unhandled_input(event: InputEvent) -> void:
	var lv := get_tree().current_scene
	if event.is_action_pressed("pause") and lv and lv.name == "Level":
		get_tree().paused = not get_tree().paused
		lv.hud.toast(tr("hud_paused") if get_tree().paused else "")
