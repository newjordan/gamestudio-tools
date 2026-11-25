extends Node
## Autoload: run state, the data-table enemy stats, locale and autoplay flags.

const LEVELS := 3
const TITLES := ["", "Meadow", "Ruins", "Cave"]
const SKY := [Color.BLACK, Color("5fa8e8"), Color("c99a6b"), Color("2b2b45")]

var level := 1
var hearts := 3
var gems := 0
var autoplay := false
var stats := {}            # enemy id -> row Dictionary from res://data/enemies.tres
var _t := 0.0
var _timeout := 120.0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var args := OS.get_cmdline_user_args()
	autoplay = "--autoplay" in args
	for a in args:
		if a.begins_with("--locale="):
			TranslationServer.set_locale(a.substr(9))
		elif a.begins_with("--timeout="):
			_timeout = float(a.substr(10))
	if not TranslationServer.get_locale().begins_with("de"):
		TranslationServer.set_locale("en")
	var table: Resource = load("res://data/enemies.tres")
	for row in table.rows:
		stats[row["id"]] = row
	var keep := TranslationServer.get_locale()
	TranslationServer.set_locale("en")
	var en := tr("TITLE")
	TranslationServer.set_locale("de")
	var de := tr("TITLE")
	TranslationServer.set_locale(keep)
	print("SAMPLE_GAME_BOOT locale=%s enemies=%s tr_en=%s tr_de=%s" % [keep, ",".join(PackedStringArray(stats.keys())), en, de])

func _process(delta: float) -> void:
	_t += delta
	if autoplay and _t > _timeout:
		print("SAMPLE_GAME_FAIL timeout level=%d" % level)
		get_tree().quit(1)
		set_process(false)

func toggle_locale() -> void:
	TranslationServer.set_locale("de" if TranslationServer.get_locale().begins_with("en") else "en")
	print("SAMPLE_GAME_LOCALE %s" % TranslationServer.get_locale())

func start() -> void:
	level = 1
	hearts = 3
	gems = 0
	_enter()

func _enter() -> void:
	print("SAMPLE_GAME_LEVEL %d %s t=%.1f" % [level, TITLES[level], _t])
	get_tree().change_scene_to_file.call_deferred("res://scenes/level.tscn")

func level_done() -> void:
	print("SAMPLE_GAME_L%d_OK t=%.1f" % [level, _t])
	if level >= LEVELS:
		print("SAMPLE_GAME_WIN gems=%d hearts=%d t=%.1f" % [gems, hearts, _t])
		get_tree().change_scene_to_file.call_deferred("res://scenes/win.tscn")
		return
	level += 1
	_enter()

func player_died() -> void:
	hearts = 3
	print("SAMPLE_GAME_RETRY level=%d" % level)
	_enter()
