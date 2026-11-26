extends Node
## Run state, audio and the autoplay switches for Reed Causeway.
## Tables and the route come from gst (data-to-godot, curve-gen, src/sim.py).
## Sound paths are literals so asset-unused and godot-res-lint can see them.

const SAVE_VERSION := 1
const SFX := {
	"blip": "res://audio/sfx/blip.wav",
	"place": "res://audio/sfx/place.wav",
	"shoot": "res://audio/sfx/shoot.wav",
	"hit": "res://audio/sfx/hit.wav",
	"death": "res://audio/sfx/death.wav",
	"win": "res://audio/sfx/win.wav",
	"leak": "res://audio/sfx/leak.wav",
	"wave": "res://audio/sfx/wave.wav",
}

var autoplay := false
var timeout := 90.0
var run_seed := 11
var save_path := "user://reed_save.json"
var result := {}
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
	for s in SFX:
		_sfx[s] = load(SFX[s])
	for i in 12:
		var p := AudioStreamPlayer.new()
		add_child(p)
		_players.append(p)
	music = AudioStreamPlayer.new()
	music.stream = load("res://audio/music.wav")
	music.volume_db = -8.0
	add_child(music)
	music.play()
	if autoplay and FileAccess.file_exists(save_path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(save_path))
	var parts := []
	for l in _locales:
		TranslationServer.set_locale(l)
		parts.append("%s=%s" % [l, tr("title_name")])
	TranslationServer.set_locale(locale)
	var loop_mode := -1
	if music.stream is AudioStreamWAV:
		loop_mode = (music.stream as AudioStreamWAV).loop_mode
	print("TD_BOOT seed=%d locale=%s music_loop=%d %s" % [run_seed, locale, loop_mode, " ".join(parts)])


func _process(delta: float) -> void:
	_elapsed += delta
	if autoplay and _elapsed > timeout:
		print("TD_FAIL timeout at %.1fs" % _elapsed)
		shutdown(1)


func shutdown(code := 0) -> void:
	set_process(false)
	if music:
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


func has_save() -> bool:
	return FileAccess.file_exists(save_path)


func new_run() -> void:
	get_tree().change_scene_to_file("res://scenes/level.tscn")


func continue_run() -> void:
	var f := FileAccess.open(save_path, FileAccess.READ)
	if f == null:
		new_run()
		return
	var data = JSON.parse_string(f.get_as_text())
	f.close()
	if data is Array and data.size() > 0:
		result = data[0]
	get_tree().change_scene_to_file("res://scenes/win.tscn")


func save_win(stats: Dictionary) -> void:
	result = {
		"version": SAVE_VERSION,
		"seed": int(stats["seed"]),
		"waves": int(stats["waves"]),
		"core": int(stats["core"]),
		"gold": int(stats["gold"]),
		"leaks": int(stats["leaks"]),
		"towers": int(stats["towers"]),
		"kills": int(stats["kills"]),
		"locale": TranslationServer.get_locale().substr(0, 2),
		"time": float(stats["time"]),
	}
	var f := FileAccess.open(save_path, FileAccess.WRITE)
	f.store_string(JSON.stringify([result], "  "))
	f.close()
