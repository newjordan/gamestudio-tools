extends Control
## Title screen: nine-slice panel + bitmap-font labels, all text via tr().

@onready var title: Label = $Panel/VBox/Title
@onready var start_lbl: Label = $Panel/VBox/Start
@onready var hint: Label = $Panel/VBox/Hint
var _t := 0.0
var _flips := 0

func _ready() -> void:
	_refresh()

func _refresh() -> void:
	title.text = tr("TITLE")
	start_lbl.text = tr("PRESS_START")
	hint.text = tr("LANG_HINT")

func _process(delta: float) -> void:
	_t += delta
	start_lbl.modulate.a = 0.55 + 0.45 * sin(_t * 5.0)
	if Game.autoplay:
		# show both locales, then start
		if _flips == 0 and _t > 1.0 or _flips == 1 and _t > 2.2:
			_flips += 1
			Game.toggle_locale()
			_refresh()
		elif _t > 3.0:
			set_process(false)
			Game.start()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_L:
			Game.toggle_locale()
			_refresh()
		elif event.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
			Game.start()
