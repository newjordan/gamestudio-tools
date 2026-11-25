extends Node2D
## Minimal top-down showcase: kit-generated tiles, SpriteFrames, step SFX and BMFont.
## User args: --verify (assert wall collision, print GST_SHOWCASE_OK, quit)
##            --preview (auto-walk a few frames; optional PNG shots under preview/)

const TILE := 16

@onready var map: TileMapLayer = $TileMapLayer
@onready var player: CharacterBody2D = $Player
@onready var sprite: AnimatedSprite2D = $Player/Sprite
@onready var step: AudioStreamPlayer = $Player/Step
@onready var label: Label = $HUD/Label

var cells: Dictionary
var verify := false
var preview := false
var frames := 0
var start_pos := Vector2.ZERO
var wall_dir := Vector2.ZERO
var walk_dir := Vector2.ZERO
var last_step_cell := Vector2i.ZERO


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
	for c in cells["tiles"]:
		map.set_cell(Vector2i(int(c["x"]), int(c["y"])), 0, Vector2i(int(c["atlas_x"]), int(c["atlas_y"])))
	var sx := int(cells["spawn"]["x"])
	var sy := int(cells["spawn"]["y"])
	player.global_position = Vector2(sx * TILE + TILE / 2.0, sy * TILE + TILE / 2.0)
	start_pos = player.global_position
	wall_dir = Vector2(float(cells["wall_dir"]["x"]), float(cells["wall_dir"]["y"]))
	walk_dir = Vector2(float(cells["walk_dir"]["x"]), float(cells["walk_dir"]["y"]))
	last_step_cell = Vector2i(sx, sy)
	if sprite.sprite_frames and sprite.sprite_frames.has_animation("walk"):
		sprite.play("walk")
	if verify:
		player.velocity = wall_dir * 80.0
	elif preview:
		player.velocity = walk_dir * 40.0


func _physics_process(_delta: float) -> void:
	frames += 1
	if not verify and not preview:
		var v := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
		player.velocity = v * 60.0 if v.length() > 0.0 else Vector2.ZERO
	player.move_and_slide()
	var cell := Vector2i(int(floor(player.global_position.x / TILE)), int(floor(player.global_position.y / TILE)))
	if cell != last_step_cell:
		last_step_cell = cell
		if not step.playing:
			step.play()
	if preview and frames in [8, 16, 24]:
		_save_preview_shot(frames)
	if verify and frames >= 30:
		_check_wall_collision()


func _save_preview_shot(n: int) -> void:
	var img := get_viewport().get_texture().get_image()
	if img == null:
		return
	var path := ProjectSettings.globalize_path("res://preview/shot_%02d.png" % n)
	img.save_png(path)
	print("GST_SHOWCASE_SHOT ", path)


func _check_wall_collision() -> void:
	var spawn := Vector2i(int(cells["spawn"]["x"]), int(cells["spawn"]["y"]))
	var wall_cell := spawn + Vector2i(int(wall_dir.x), int(wall_dir.y))
	var pc := Vector2i(int(floor(player.global_position.x / TILE)), int(floor(player.global_position.y / TILE)))
	var into := (player.global_position - start_pos).dot(wall_dir)
	if pc == wall_cell or into > 10.0:
		push_error("GST_SHOWCASE_FAIL cell=%s wall=%s into=%.2f pos=%s" % [pc, wall_cell, into, player.global_position])
		get_tree().quit(1)
		return
	print("GST_SHOWCASE_OK cell=%s into=%.2f pos=%s" % [pc, into, player.global_position])
	label.text = "OK"
	get_tree().quit(0)
