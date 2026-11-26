extends CanvasLayer
## HUD: nine-slice panel (nine-slice-to-godot), heart/coin/key icons (atlas-unpack of the
## pickups atlas), BMFont labels (bmfont-gen + font-to-godot), and a toast line.

var _hearts: Array[TextureRect] = []
var _coins: Label
var _key: TextureRect
var _floor: Label
var _toast: Label
var _toast_t := 0.0


func _ready() -> void:
	layer = 10
	var root := Control.new()
	root.theme = load("res://ui/ember11_theme.tres")
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	var panel := Panel.new()
	panel.add_theme_stylebox_override("panel", load("res://ui/panel_style.tres"))
	panel.position = Vector2(2, 2)
	panel.size = Vector2(316, 20)
	root.add_child(panel)
	var heart_tex: Texture2D = load("res://ui/icons/heart-idle_0.png")
	for i in Game.max_hp / 2:
		var h := TextureRect.new()
		h.texture = heart_tex
		h.position = Vector2(6 + i * 13, 6)
		root.add_child(h)
		_hearts.append(h)
	var coin := TextureRect.new()
	coin.texture = load("res://ui/icons/coin-spin_0.png")
	coin.position = Vector2(54, 6)
	root.add_child(coin)
	_coins = Label.new()
	_coins.position = Vector2(68, 4)
	root.add_child(_coins)
	_key = TextureRect.new()
	_key.texture = load("res://ui/icons/key-idle_0.png")
	_key.position = Vector2(100, 6)
	root.add_child(_key)
	_floor = Label.new()
	_floor.position = Vector2(150, 4)
	_floor.size = Vector2(162, 14)
	_floor.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	root.add_child(_floor)
	_toast = Label.new()
	_toast.position = Vector2(0, 150)
	_toast.size = Vector2(320, 14)
	_toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	root.add_child(_toast)
	refresh()


func refresh() -> void:
	if _coins == null:
		return
	for i in _hearts.size():
		var full := Game.hp - i * 2
		_hearts[i].modulate = Color.WHITE if full >= 2 else (Color(1, 1, 1, 0.6) if full == 1 else Color(0.2, 0.2, 0.3, 0.8))
	_coins.text = "x%d" % Game.coins
	_key.visible = Game.has_key
	_floor.text = tr("hud_boss") if Game.level_name() == "boss" else tr("hud_floor").format({"n": Game.floor})


func toast(text: String) -> void:
	_toast.text = text
	_toast_t = 2.0


func _process(delta: float) -> void:
	_toast_t -= delta
	_toast.visible = _toast_t > 0.0
