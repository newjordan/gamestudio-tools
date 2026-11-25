extends CharacterBody2D
## Slime: stats from the data-table Resource (data-to-godot), patrols between
## the two ends of its Tiled patrol polyline by following NavigationServer2D
## paths over the nav-to-godot region.

const GRAVITY := 900.0
var kind := "slime"
var speed := 30.0
var bounce := 260.0
var a := Vector2.ZERO
var b := Vector2.ZERO
var target := Vector2.ZERO
var path := PackedVector2Array()
var repath := 0.0
var dead := false
var spawn_x := 0.0
static var nav_reported := {}
@onready var spr: AnimatedSprite2D = $Sprite

func setup(k: String, pa: Vector2, pb: Vector2) -> void:
	kind = k
	a = pa
	b = pb
	target = pb

func _ready() -> void:
	add_to_group("enemies")
	spawn_x = position.x
	var row: Dictionary = Game.stats.get(kind, {})
	speed = float(row.get("speed", 30))
	bounce = float(row.get("stomp_bounce", 260))
	spr.modulate = Color(String(row.get("tint", "#ffffff")))
	for h in $Hitboxes.get_children():
		if h is Area2D:
			h.collision_layer = 16
			h.collision_mask = 0
			h.monitoring = false
	spr.play("walk")

func _physics_process(delta: float) -> void:
	if dead:
		return
	velocity.y = minf(velocity.y + GRAVITY * delta, 500.0)
	repath -= delta
	var map := get_world_2d().navigation_map
	if repath <= 0.0 and NavigationServer2D.map_get_iteration_id(map) > 0:
		repath = 0.4
		path = NavigationServer2D.map_get_path(map, global_position + Vector2(0, -8), target, true)
		var key := "%d" % Game.level
		if path.size() > 1 and not nav_reported.has(key):
			nav_reported[key] = true
			print("SAMPLE_GAME_NAV_OK level=%d kind=%s points=%d" % [Game.level, kind, path.size()])
	var dx := target.x - global_position.x
	if path.size() > 1:
		dx = path[1].x - global_position.x
		if absf(dx) < 2.0 and path.size() > 2:
			dx = path[2].x - global_position.x
	if absf(target.x - global_position.x) < 4.0:
		target = a if target == b else b
		repath = 0.0
	velocity.x = signf(dx) * speed
	spr.flip_h = velocity.x < 0.0
	move_and_slide()

func stomp() -> void:
	dead = true
	print("SAMPLE_GAME_STOMP level=%d kind=%s patrolled_from_spawn=%.0fpx" % [Game.level, kind, absf(global_position.x - spawn_x)])
	spr.play("hurt")
	for h in $Hitboxes.get_children():
		if h is Area2D:
			h.set_deferred("monitorable", false)
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector2(1.4, 0.2), 0.25)
	tw.tween_callback(queue_free)
