extends Control

var _t := 0.0


func _ready() -> void:
	theme = load("res://ui/reed11_theme.tres")
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.08, 0.05, 0.05)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var title := Label.new()
	title.theme = load("res://ui/reed16_theme.tres")
	title.position = Vector2(0, 64)
	title.size = Vector2(320, 28)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.text = tr("lose_title")
	title.add_theme_color_override("font_color", Color(0.93, 0.85, 0.8))
	add_child(title)
	var body := Label.new()
	body.position = Vector2(16, 100)
	body.size = Vector2(288, 40)
	body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body.text = tr("lose_body")
	body.add_theme_color_override("font_color", Color(0.93, 0.85, 0.8))
	add_child(body)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("confirm") and not Game.autoplay:
		get_tree().change_scene_to_file("res://scenes/title.tscn")


func _process(delta: float) -> void:
	if not Game.autoplay:
		return
	_t += delta
	if _t < 0.3:
		return
	set_process(false)
	Game.shutdown(1)
