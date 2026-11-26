extends Control
## Win screen: localized stats; autoplay checks the save file and quits.

var _t := 0.0


func _ready() -> void:
	theme = load("res://ui/ember11_theme.tres")
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := TextureRect.new()
	bg.texture = load("res://art/title_bg.png")
	add_child(bg)
	var t := Label.new()
	t.theme = load("res://ui/ember22_theme.tres")
	t.text = tr("win_title")
	t.position = Vector2(0, 50)
	t.size = Vector2(320, 30)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(t)
	var s := Label.new()
	s.text = tr("win_stats").format({"coins": Game.coins, "time": "%.1f" % Game.run_time}) + "\n\n" + tr("menu_hint")
	s.position = Vector2(0, 92)
	s.size = Vector2(320, 60)
	s.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(s)
	Game.play("roar", 1.5)


func _process(delta: float) -> void:
	_t += delta
	if Game.autoplay and _t > 2.5:
		set_process(false)
		print("TOPDOWN_DONE coins=%d time=%.1f save=%s" % [Game.coins, Game.run_time, ProjectSettings.globalize_path(Game.save_path)])
		Game.shutdown(0)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("confirm"):
		get_tree().change_scene_to_file("res://scenes/title.tscn")
