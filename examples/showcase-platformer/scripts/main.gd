extends Node2D
## Side-view platformer showcase: kit-generated tiles, SpriteFrames, coin SFX,
## parallax layers and a BMFont HUD. Gaps were validated by jump-arc using the
## same gravity / jump velocity / speed this script applies.
## User args: --verify (scripted jump across the first gap, print GST_PLATFORMER_OK, quit)
##            --preview (auto-run and jump; optional PNG shots under preview/)

const TILE := 16

@onready var ground: TileMapLayer = $Ground
@onready var platforms: TileMapLayer = $Platforms
@onready var player: CharacterBody2D = $Player
@onready var sprite: AnimatedSprite2D = $Player/Sprite
@onready var coin: Area2D = $Coin
@onready var coin_sfx: AudioStreamPlayer = $CoinSfx
@onready var label: Label = $HUD/Label

var cells: Dictionary
var verify := false
var preview := false
var frames := 0
var coins := 0
var gravity := 800.0
var jump_v := 220.0
var speed := 120.0
var takeoffs: Array = []
var jumped: Dictionary = {}


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	verify = "--verify" in args
	preview = "--preview" in args
	var fa := FileAccess.open("res://art/cells.json", FileAccess.READ)
	if fa == null:
		push_error("missing res://art/cells.json — run ./build_showcase.sh")
		get_tree().quit(2)
		return
	var parsed = JSON.parse_string(fa.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("cells.json is not an object")
		get_tree().quit(2)
		return
	cells = parsed
	gravity = float(cells.get("gravity", 800))
	jump_v = float(cells.get("jump_v", 220))
	speed = float(cells.get("speed", 120))
	var mf := FileAccess.open("res://art/level.json", FileAccess.READ)
	if mf == null:
		push_error("missing res://art/level.json — run ./build_showcase.sh")
		get_tree().quit(2)
		return
	var level = JSON.parse_string(mf.get_as_text())
	if typeof(level) != TYPE_DICTIONARY:
		push_error("level.json is not an object")
		get_tree().quit(2)
		return
	_fill_layer(ground, _layer_data(level, "ground"))
	_fill_layer(platforms, _layer_data(level, "platforms"))
	player.global_position = Vector2(float(cells["spawn"]["x"]), float(cells["spawn"]["y"]))
	for g in cells.get("gaps", []):
		takeoffs.append(float(g["takeoff"][0]))
	var cx := float(cells["coin"]["x"])
	var cy := float(cells["coin"]["y"])
	coin.global_position = Vector2(cx, cy)
	coin.body_entered.connect(_on_coin_body_entered)
	if sprite.sprite_frames and sprite.sprite_frames.has_animation("walk"):
		sprite.play("walk")
	label.text = "COINS 0"


func _layer_data(level: Dictionary, name: String) -> Array:
	for layer in level.get("layers", []):
		if str(layer.get("name", "")) == name:
			return layer.get("data", [])
	return []


func _fill_layer(node: TileMapLayer, data: Array) -> void:
	var w := int(cells.get("map", {}).get("w", 32))
	for i in range(data.size()):
		var gid := int(data[i]) & 0x1FFFFFFF
		if gid <= 0:
			continue
		var local := gid - 1
		var atlas := Vector2i(local % 3, local / 3)
		node.set_cell(Vector2i(i % w, int(i / w)), 0, atlas)


func _physics_process(delta: float) -> void:
	frames += 1
	if not player.is_on_floor():
		player.velocity.y += gravity * delta
	elif player.velocity.y > 0.0:
		player.velocity.y = 0.0
	if verify or preview:
		player.velocity.x = speed
		if player.is_on_floor():
			for t in takeoffs:
				if player.global_position.x >= float(t) and not jumped.has(t):
					player.velocity.y = -jump_v
					jumped[t] = true
					break
	else:
		var axis := Input.get_axis("ui_left", "ui_right")
		player.velocity.x = axis * speed
		if player.is_on_floor() and (Input.is_action_just_pressed("ui_accept") or Input.is_action_just_pressed("ui_up")):
			player.velocity.y = -jump_v
	player.move_and_slide()
	if player.velocity.x != 0.0:
		sprite.flip_h = player.velocity.x < 0.0
	# Movie Maker records at 10 FPS; physics still ticks at 60 Hz.
	# Frame 216 is the last tick and can be skipped when --quit-after 36 fires,
	# so the last still is taken at 210 (3.5s, movie frame 35).
	if preview:
		if frames == 72:
			_save_preview_shot(12)
		elif frames == 144:
			_save_preview_shot(24)
		elif frames == 210:
			_save_preview_shot(36)
	if verify and frames >= int(cells.get("verify_frames", 90)):
		_check_landing()


func _on_coin_body_entered(body: Node2D) -> void:
	if body != player or not coin.visible:
		return
	coin.visible = false
	coin.set_deferred("monitoring", false)
	coins += 1
	if not coin_sfx.playing:
		coin_sfx.play()
	label.text = "COINS %d" % coins


func _save_preview_shot(n: int) -> void:
	var img := get_viewport().get_texture().get_image()
	if img == null:
		return
	var path := ProjectSettings.globalize_path("res://preview/shot_%02d.png" % n)
	img.save_png(path)
	print("GST_PLATFORMER_SHOT ", path)


func _check_landing() -> void:
	var gaps: Array = cells.get("gaps", [])
	if gaps.is_empty():
		push_error("GST_PLATFORMER_FAIL no gaps in cells.json")
		get_tree().quit(1)
		return
	var land_min := float(gaps[0]["land_min"])
	var land_max := float(gaps[0]["land_max"])
	var pos := player.global_position
	if not player.is_on_floor():
		push_error("GST_PLATFORMER_FAIL not on floor pos=%s" % pos)
		get_tree().quit(1)
		return
	if pos.x < land_min or pos.x >= land_max:
		push_error("GST_PLATFORMER_FAIL x=%.1f not in [%.1f, %.1f)" % [pos.x, land_min, land_max])
		get_tree().quit(1)
		return
	print("GST_PLATFORMER_OK pos=%s coins=%s" % [pos, coins])
	label.text = "OK"
	get_tree().quit(0)
