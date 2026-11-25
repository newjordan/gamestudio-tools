extends Node2D
## Assembles one level from the gst-generated scenes:
##   levels/levelN_tiles.tscn    map-to-godot          (TileMapLayers, flipped tiles)
##   levels/levelN_solid.tscn    tile-colliders-to-godot (StaticBody2D)
##   levels/levelN_oneway.tscn   tile-colliders-to-godot (made one-way here)
##   levels/levelN_nav.tscn      nav-to-godot          (NavigationRegion2D)
##   levels/levelN_objects.tscn  map-objects-to-godot  (spawn, enemies, patrols, gem, door, exit)

const PlayerScene := preload("res://scenes/player.tscn")
const EnemyScene := preload("res://scenes/enemy.tscn")
const MAP_W := 800.0
const MAP_H := 192.0

var player: CharacterBody2D
var exit_open := false
var gem_total := 0
@onready var hud_label: Label = $HUD/Panel/Label
@onready var msg: Label = $HUD/Msg
@onready var sky: ColorRect = $Sky/Color

func _ready() -> void:
	var base := "res://levels/level%d" % Game.level
	sky.color = Game.SKY[Game.level]
	add_child(load(base + "_tiles.tscn").instantiate())
	add_child(load(base + "_solid.tscn").instantiate())
	var oneway: Node = load(base + "_oneway.tscn").instantiate()
	for c in oneway.get_children():
		if c is CollisionShape2D:
			c.one_way_collision = true
	add_child(oneway)
	add_child(load(base + "_nav.tscn").instantiate())
	var objs: Node = load(base + "_objects.tscn").instantiate()
	add_child(objs)
	var patrols := {}
	var enemies := []
	for o in objs.get_node("objects").get_children():
		match String(o.get_meta("tiled_type", "")):
			"spawn":
				player = PlayerScene.instantiate()
				player.position = o.position
				add_child(player)
			"patrol":
				var line: Line2D = o.get_node("Line")
				patrols[o.name] = [o.position + line.points[0], o.position + line.points[line.points.size() - 1]]
				o.visible = false
				o.monitoring = false
				o.monitorable = false
			"enemy":
				enemies.append(o)
			"gem":
				_make_gem(o)
			"exit":
				o.collision_layer = 0
				o.collision_mask = 2
				o.body_entered.connect(_on_exit)
	for o in enemies:
		var e := EnemyScene.instantiate()
		e.position = o.position
		var pts: Array = patrols.get(String(o.get_meta("patrol", "")), [o.position, o.position])
		e.setup(String(o.get_meta("kind", "slime")), pts[0], pts[1])
		add_child(e)
	var cam: Camera2D = player.get_node("Camera")
	cam.limit_left = 0
	cam.limit_top = 0
	cam.limit_right = int(MAP_W)
	cam.limit_bottom = int(MAP_H)
	player.hurt.connect(_refresh_hud)
	_refresh_hud()

func _make_gem(sprite: Node2D) -> void:
	gem_total += 1
	var area := Area2D.new()
	area.collision_layer = 0
	area.collision_mask = 2
	var shape := CollisionShape2D.new()
	var circle := CircleShape2D.new()
	circle.radius = 7.0
	shape.shape = circle
	shape.position = Vector2(8, 8)
	area.add_child(shape)
	sprite.add_child(area)
	area.body_entered.connect(func(_b): _collect(sprite))

func _collect(sprite: Node2D) -> void:
	if not is_instance_valid(sprite) or sprite.is_queued_for_deletion():
		return
	sprite.queue_free()
	Game.gems += 1
	exit_open = true
	player.play_sfx("Coin")
	print("SAMPLE_GAME_GEM level=%d" % Game.level)
	_flash(tr("GEMS") + " +1")
	_refresh_hud()

func _on_exit(body: Node) -> void:
	if body != player:
		return
	if exit_open:
		set_deferred("process_mode", Node.PROCESS_MODE_DISABLED)
		Game.level_done()
	else:
		_flash(tr("LOCKED"))

func _flash(text: String) -> void:
	msg.text = text
	msg.visible = true
	await get_tree().create_timer(1.2).timeout
	if is_instance_valid(msg):
		msg.visible = false

func _refresh_hud() -> void:
	hud_label.text = "%s %d  %s %d  %s %d/%d" % [tr("LEVEL"), Game.level, tr("HEARTS"), Game.hearts,
		tr("GEMS"), Game.gems, Game.LEVELS]

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode == KEY_L:
		Game.toggle_locale()
		_refresh_hud()
