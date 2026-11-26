extends Control
## Title: new run / continue (if a save exists), language switch en/de/fr.
## Autoplay walks the three locales, checks that keyboard AND gamepad events reach the
## input map, then starts a seeded run.

var _title: Label
var _lines: Label
var _selected := 0
var _t := 0.0
var _step := 0


func _ready() -> void:
	theme = load("res://ui/ember11_theme.tres")
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := TextureRect.new()
	bg.texture = load("res://art/title_bg.png")
	add_child(bg)
	_title = Label.new()
	_title.theme = load("res://ui/ember22_theme.tres")
	_title.position = Vector2(0, 34)
	_title.size = Vector2(320, 30)
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_title)
	_lines = Label.new()
	_lines.position = Vector2(0, 74)
	_lines.size = Vector2(320, 100)
	_lines.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_lines)
	_refresh()


func _options() -> Array:
	return ["menu_continue", "menu_new"] if Game.has_save() else ["menu_new"]


func _refresh() -> void:
	_title.text = tr("title_name")
	var opts := _options()
	_selected = clampi(_selected, 0, opts.size() - 1)
	var s := tr("title_tagline") + "\n\n"
	for i in opts.size():
		s += ("> %s <" if i == _selected else "%s") % tr(opts[i]) + "\n"
	s += tr("menu_language") + "\n\n" + tr("menu_hint")
	_lines.text = s


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("move_down") or event.is_action_pressed("move_up"):
		_selected = (_selected + 1) % _options().size()
		Game.play("blip")
		_refresh()
	elif event.is_action_pressed("toggle_language"):
		print("TITLE_LOCALE %s %s" % [Game.cycle_locale(), tr("title_name")])
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
	if _t < 0.5:
		return
	_t = 0.0
	_step += 1
	if _step <= 3:
		# L key x3 cycles en -> de -> fr -> en through the real input map
		var k := InputEventKey.new()
		k.physical_keycode = KEY_L
		k.keycode = KEY_L
		k.pressed = true
		_send(k)
		var up := k.duplicate()
		up.pressed = false
		_send(up)
	elif _step == 4:
		var k := InputEventKey.new()
		k.physical_keycode = KEY_SPACE
		k.pressed = true
		var j := InputEventJoypadButton.new()
		j.button_index = JOY_BUTTON_A
		j.pressed = true
		var m := InputEventJoypadMotion.new()
		m.axis = JOY_AXIS_LEFT_X
		m.axis_value = -1.0
		var ok := InputMap.event_is_action(k, "attack") and InputMap.event_is_action(j, "confirm") \
			and InputMap.event_is_action(m, "move_left")
		var actions := InputMap.get_actions().filter(func(a): return not String(a).begins_with("ui_"))
		var pads := 0
		for a in actions:
			for ev in InputMap.action_get_events(a):
				if ev is InputEventJoypadButton or ev is InputEventJoypadMotion:
					pads += 1
					break
		print("INPUT_OK %s actions=%d with_gamepad=%d" % [ok, actions.size(), pads])
	elif _step == 5:
		var j := InputEventJoypadButton.new()
		j.button_index = JOY_BUTTON_A
		j.pressed = true
		_send(j)
