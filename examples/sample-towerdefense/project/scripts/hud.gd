extends CanvasLayer
## Gold, core, wave and the selected tower. The nine-slice and the bitmap font are gst output.

var _gold: Label
var _info: Label


func _ready() -> void:
	layer = 10
	var panel := Panel.new()
	panel.position = Vector2(0, 0)
	panel.size = Vector2(320, 16)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", load("res://ui/panel_style.tres"))
	add_child(panel)
	_gold = _label(4)
	_info = _label(168)
	add_child(_gold)
	add_child(_info)


func _label(x: float) -> Label:
	var label := Label.new()
	label.theme = load("res://ui/reed11_theme.tres")
	label.position = Vector2(x, 1)
	label.size = Vector2(150, 14)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_color_override("font_color", Color(0.93, 0.95, 0.9))
	return label


func refresh(gold: int, core: int, wave: int, kind: String, paused: bool) -> void:
	_gold.text = tr("hud_gold") % gold + "  " + tr("hud_core") % core
	var extra := tr("hud_pause") if paused else tr("tower_" + kind)
	_info.text = tr("hud_wave") % wave + "  " + extra
