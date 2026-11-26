extends Control

var _t := 0.0


func _ready() -> void:
	theme = load("res://ui/reed11_theme.tres")
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.055, 0.086, 0.07)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var title := Label.new()
	title.theme = load("res://ui/reed16_theme.tres")
	title.position = Vector2(0, 48)
	title.size = Vector2(320, 28)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.text = tr("win_title")
	title.add_theme_color_override("font_color", Color(0.93, 0.95, 0.9))
	add_child(title)
	var body := Label.new()
	body.position = Vector2(16, 88)
	body.size = Vector2(288, 64)
	body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body.add_theme_color_override("font_color", Color(0.93, 0.95, 0.9))
	var stats: Dictionary = Game.result
	body.text = tr("win_body") + "\n" + tr("hud_gold") % int(stats.get("gold", 0)) + "  " + tr("hud_core") % int(stats.get("core", 0))
	add_child(body)
	Game.play("win")


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("confirm") and not Game.autoplay:
		get_tree().change_scene_to_file("res://scenes/title.tscn")


func _process(delta: float) -> void:
	if not Game.autoplay:
		return
	_t += delta
	if _t < 1.0:
		return
	set_process(false)
	print("TD_DONE leaks=%s core=%s kills=%s towers=%s save=%s" % [
		Game.result.get("leaks", "?"), Game.result.get("core", "?"), Game.result.get("kills", "?"),
		Game.result.get("towers", "?"), ProjectSettings.globalize_path(Game.save_path)])
	Game.shutdown(0)
