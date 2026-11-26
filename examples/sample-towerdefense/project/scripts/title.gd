extends Control
## Title menu. Autoplay cycles en -> de -> fr -> en with the L key, checks the
## input map, then starts the run with the gamepad A button.

var _title: Label
var _lines: Label
var _selected := 0
var _t := 0.0
var _step := 0


func _ready() -> void:
	theme = load("res://ui/reed11_theme.tres")
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := TextureRect.new()
	bg.texture = load("res://art/title_bg.png")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	bg.stretch_mode = TextureRect.STRETCH_SCALE
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var panel := Panel.new()
	panel.position = Vector2(40, 28)
	panel.size = Vector2(240, 120)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", load("res://ui/panel_style.tres"))
	add_child(panel)
	_title = Label.new()
	_title.theme = load("res://ui/reed16_theme.tres")
	_title.position = Vector2(0, 36)
	_title.size = Vector2(320, 24)
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_title.add_theme_color_override("font_color", Color(0.93, 0.95, 0.9))
	add_child(_title)
	_lines = Label.new()
	_lines.position = Vector2(16, 64)
	_lines.size = Vector2(288, 80)
	_lines.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_lines.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_lines.add_theme_color_override("font_color", Color(0.93, 0.95, 0.9))
	add_child(_lines)
	_refresh()


func _options() -> Array:
	return ["menu_continue", "menu_new"] if Game.has_save() else ["menu_new"]


func _refresh() -> void:
	_title.text = tr("title_name")
	var opts := _options()
	_selected = clampi(_selected, 0, opts.size() - 1)
	var s := tr("title_tagline") + "\n"
	for i in opts.size():
		s += ("> %s <" if i == _selected else "%s") % tr(opts[i]) + "\n"
	s += tr("menu_language") + "\n" + tr("menu_hint")
	_lines.text = s


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_language"):
		print("TITLE_LOCALE %s %s" % [Game.cycle_locale(), tr("title_name")])
		Game.play("blip")
		_refresh()
	elif event.is_action_pressed("select_next"):
		_selected = (_selected + 1) % _options().size()
		Game.play("blip")
		_refresh()
	elif event.is_action_pressed("confirm"):
		Game.play("blip")
		if _options()[_selected] == "menu_continue":
			Game.continue_run()
		else:
			Game.new_run()


func _send(ev: InputEvent) -> void:
	Input.parse_input_event(ev)


func _process(delta: float) -> void:
	if not Game.autoplay:
		return
	_t += delta
	if _t < 0.4:
		return
	_t = 0.0
	_step += 1
	if _step <= 3:
		var k := InputEventKey.new()
		k.physical_keycode = KEY_L
		k.keycode = KEY_L
		k.pressed = true
		_send(k)
		var up := k.duplicate()
		up.pressed = false
		_send(up)
	elif _step == 4:
		var space := InputEventKey.new()
		space.physical_keycode = KEY_SPACE
		space.pressed = true
		var joy := InputEventJoypadButton.new()
		joy.button_index = JOY_BUTTON_A
		joy.pressed = true
		var ok := InputMap.event_is_action(space, "place") and InputMap.event_is_action(joy, "confirm")
		var actions := InputMap.get_actions().filter(func(a): return not String(a).begins_with("ui_"))
		var pads := 0
		for a in actions:
			for ev in InputMap.action_get_events(a):
				if ev is InputEventJoypadButton or ev is InputEventJoypadMotion:
					pads += 1
					break
		print("INPUT_OK %s actions=%d with_gamepad=%d" % [ok, actions.size(), pads])
	elif _step == 5:
		var joy := InputEventJoypadButton.new()
		joy.button_index = JOY_BUTTON_A
		joy.pressed = true
		_send(joy)
